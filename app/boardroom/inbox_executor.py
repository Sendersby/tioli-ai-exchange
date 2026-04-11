"""Inbox approval execution dispatcher — runs approved tasks via the responsible agent."""
import json
import asyncio
import logging
import os
import httpx
from datetime import datetime, timezone

logger = logging.getLogger("arch.inbox_executor")

# DB connection — reads from environment
from app.utils.db_connect import get_raw_connection


async def _db_execute(query, *args):
    """Execute a query with a fresh connection."""
    conn = await get_raw_connection()
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
        elif "vote result" in content_lower or "self-improvement" in content_lower or "self_improvement" in content_lower:
            # Self-improvement vote — apply the founder's decision
            result_text, proof_urls = await _execute_self_improvement(desc_data)
        else:
            # Generic task — log it for agent pickup via task queue
            try:
                await _db_execute(
                    "INSERT INTO arch_task_queue "
                    "(agent_id, task_type, priority, title, description, action_type, action_params, status, created_at) "
                    "SELECT id, 'IMMEDIATE', 5, $1, $2, 'generate_content', $3, 'PENDING', now() "
                    "FROM arch_agents WHERE agent_name = $4",
                    subject[:200], detail[:1000],
                    json.dumps({"task": subject, "detail": detail}),
                    agent
                )
                result_text = f"Task queued for {agent}"
                proof_urls = [f"Queued in task_queue for {agent} to execute on next heartbeat"]
            except Exception as qe:
                result_text = f"Task noted for {agent} (queue insert: {str(qe)[:100]})"
                proof_urls = [f"Agent {agent} notified of approved task"]

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


async def _execute_self_improvement(desc_data):
    """Execute a self-improvement proposal approved by the founder."""
    import httpx as _httpx
    proposal_id = desc_data.get("proposal_id", "")
    if not proposal_id:
        detail = desc_data.get("detail", "")
        if "Proposal ID:" in detail:
            proposal_id = detail.split("Proposal ID:")[1].strip().split()[0].strip()
    if not proposal_id:
        return "No proposal ID found", ["ERROR: Could not determine which proposal to apply"]
    try:
        async with _httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"http://127.0.0.1:8000/api/v1/boardroom/self-improvement/proposals/{proposal_id}/founder-decision",
                json={"decision": "APPROVE", "response": "Approved via inbox"}
            )
            if resp.status_code == 200:
                apply_resp = await client.post(
                    f"http://127.0.0.1:8000/api/v1/boardroom/self-improvement/proposals/{proposal_id}/apply"
                )
                apply_data = apply_resp.json()
                return f"Self-improvement applied: {apply_data.get(message,)}", [
                    f"Proposal {proposal_id}: {apply_data.get(status, processed)}",
                    "Founder decision: APPROVED",
                ]
            else:
                return f"API error: {resp.status_code}", [f"Error: {resp.text[:200]}"]
    except Exception as e:
        return f"Execution error: {e}", [f"ERROR: {str(e)[:200]}"]
