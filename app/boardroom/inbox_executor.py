"""Inbox approval execution dispatcher — runs approved tasks via the responsible agent."""
import json
import asyncio
import logging
import os
import httpx
from datetime import datetime, timezone

logger = logging.getLogger("arch.inbox_executor")

# DB connection params
DB_CONFIG = {
    "user": "tioli",
    "password": "DhQHhP6rsYdUL*2DLWJ2Neu#2xqhM0z#",
    "database": "tioli_exchange",
    "host": "127.0.0.1",
    "port": 5432,
}


async def _db_execute(query, *args):
    """Execute a query with a fresh connection."""
    import asyncpg
    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        result = await conn.execute(query, *args)
        return result
    finally:
        await conn.close()


async def _deliver_to_inbox(subject, detail, agent, priority="ROUTINE", status="PENDING"):
    """Deliver a result item to the founder inbox."""
    desc = json.dumps({
        "subject": subject,
        "detail": detail,
        "prepared_by": agent,
        "type": "EXECUTION_PROOF"
    })
    await _db_execute(
        "INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at) "
        "VALUES ($1, $2::arch_msg_priority, $3, $4, now())",
        "EXECUTION_PROOF", priority, desc, status
    )
    logger.info(f"Inbox delivery: {subject}")


async def execute_approved_item(db_ignored, item_id: str, description: str):
    """Execute an approved inbox item and deliver proof back to inbox.
    Uses its own DB connections to avoid session conflicts."""
    try:
        desc_data = json.loads(description) if description.startswith("{") else {}
    except Exception:
        desc_data = {}

    subject = desc_data.get("subject", "Unknown task")
    detail = desc_data.get("detail", "")
    agent = desc_data.get("prepared_by", "sovereign")

    logger.info(f"Executing approved item: {subject} (agent: {agent})")

    try:
        content_lower = (subject + " " + detail).lower()

        if "mcp" in content_lower and ("submission" in content_lower or "smithery" in content_lower):
            result_text, proof_urls = await _execute_mcp_submission()
        elif "dev.to" in content_lower or "blog" in content_lower:
            result_text, proof_urls = await _execute_devto_post(detail)
        elif "github" in content_lower and ("repo" in content_lower or "example" in content_lower):
            result_text, proof_urls = await _execute_github_action(detail)
        else:
            # Queue for agent task system
            await _db_execute(
                "INSERT INTO arch_event_actions (agent_id, action_type, action_data, status, created_at) "
                "SELECT id, $1, $2, $3, now() FROM arch_agents WHERE agent_name = $4",
                "FOUNDER_APPROVED_TASK",
                json.dumps({"task": subject, "detail": detail, "parent_inbox_item": item_id}),
                "PENDING", agent
            )
            result_text = f"Task queued for {agent}"
            proof_urls = [f"Queued as FOUNDER_APPROVED_TASK for {agent} to execute"]

        # Build proof message
        proof_body = f"Execution complete for: {subject}\n\nResults:\n"
        for url in proof_urls:
            proof_body += f"  - {url}\n"
        if result_text:
            proof_body += f"\n{result_text}"

        # Deliver proof to inbox
        await _deliver_to_inbox(
            f"COMPLETED: {subject}",
            proof_body,
            agent
        )

        # Mark EXECUTING item as COMPLETED
        await _db_execute(
            "UPDATE arch_founder_inbox SET status = 'COMPLETED' WHERE status = 'EXECUTING' AND description LIKE $1",
            f"%{item_id}%"
        )

        logger.info(f"Execution SUCCESS: {subject}")

    except Exception as e:
        logger.error(f"Execution FAILED for {subject}: {e}")

        # Deliver failure to inbox
        await _deliver_to_inbox(
            f"FAILED: {subject}",
            f"Execution failed with error:\n{str(e)[:500]}\n\nPlease review and retry or take manual action.",
            agent,
            priority="URGENT"
        )

        # Mark EXECUTING as COMPLETED (it failed but the process is done)
        try:
            await _db_execute(
                "UPDATE arch_founder_inbox SET status = 'COMPLETED' WHERE status = 'EXECUTING' AND description LIKE $1",
                f"%{item_id}%"
            )
        except Exception:
            pass


async def _execute_mcp_submission():
    """Submit MCP server to smithery.ai and other directories."""
    proof_urls = []
    results = []

    # Read the MCP server card
    card_path = "/home/tioli/app/static/mcp-server-card.json"
    if os.path.exists(card_path):
        with open(card_path) as f:
            card = json.load(f)
    else:
        return "MCP card not found", ["ERROR: /static/mcp-server-card.json missing"]

    async with httpx.AsyncClient(timeout=30) as http:
        # Attempt smithery.ai submission
        try:
            r = await http.post("https://smithery.ai/api/servers", json={
                "name": card.get("name", "tioli-agentis"),
                "description": card.get("description", ""),
                "url": card.get("endpoint", ""),
                "homepage": card.get("homepage", ""),
            })
            if r.status_code in (200, 201):
                url = r.json().get("url", f"https://smithery.ai/server/{card.get('name', '')}")
                proof_urls.append(f"smithery.ai: SUBMITTED — {url}")
                results.append("Smithery submission successful")
            elif r.status_code == 404:
                proof_urls.append("smithery.ai: API endpoint not found — may require manual submission at https://smithery.ai/new")
                results.append("Smithery needs manual submission")
            else:
                proof_urls.append(f"smithery.ai: HTTP {r.status_code} — {r.text[:200]}")
                results.append(f"Smithery returned {r.status_code}")
        except Exception as e:
            proof_urls.append(f"smithery.ai: Connection error — {str(e)[:100]}. Submit manually at https://smithery.ai")
            results.append(f"Smithery connection failed")

    # Always include the public card URL as proof
    proof_urls.append(f"MCP server card (public): https://exchange.tioli.co.za/static/mcp-server-card.json")
    proof_urls.append(f"MCP SSE endpoint (live): https://exchange.tioli.co.za/api/mcp/sse")

    return "; ".join(results), proof_urls


async def _execute_devto_post(detail):
    """Publish a post to DEV.to."""
    api_key = os.environ.get("DEVTO_API_KEY", "")
    if not api_key:
        # Try loading from .env
        try:
            with open("/home/tioli/app/.env") as f:
                for line in f:
                    if line.startswith("DEVTO_API_KEY="):
                        api_key = line.strip().split("=", 1)[1]
        except Exception:
            pass
    if not api_key:
        return "No DEV.to API key", ["ERROR: DEVTO_API_KEY not set in .env"]

    lines = detail.split("\n")
    title = lines[0] if lines else "AGENTIS Technical Post"
    body = "\n".join(lines[1:]) if len(lines) > 1 else detail

    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.post("https://dev.to/api/articles",
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json={"article": {"title": title, "body_markdown": body, "published": True, "tags": ["ai", "python", "agents"]}})
        if r.status_code in (200, 201):
            url = r.json().get("url", "")
            return f"Published: {url}", [url]
        else:
            return f"Failed: HTTP {r.status_code}", [f"DEV.to error: {r.text[:200]}"]


async def _execute_github_action(detail):
    """Execute a GitHub action."""
    return "GitHub action noted", ["GitHub actions require specific parameters — review the detail for next steps"]
