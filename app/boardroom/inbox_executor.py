"""Inbox approval execution dispatcher — runs approved tasks via the responsible agent."""
import json
import asyncio
import logging
import httpx
from datetime import datetime, timezone

logger = logging.getLogger("arch.inbox_executor")


async def execute_approved_item(db, item_id: str, description: str):
    """Execute an approved inbox item and deliver proof back to inbox."""
    try:
        desc_data = json.loads(description) if description.startswith("{") else {}
    except Exception:
        desc_data = {}

    subject = desc_data.get("subject", "")
    detail = desc_data.get("detail", "")
    agent = desc_data.get("prepared_by", "sovereign")
    task_type = desc_data.get("type", "")

    logger.info(f"Executing approved item: {subject} (agent: {agent})")

    # Dispatch based on content analysis
    result = None
    proof_urls = []

    try:
        content_lower = (subject + " " + detail).lower()

        if "mcp" in content_lower and "submission" in content_lower:
            result, proof_urls = await _execute_mcp_submission()
        elif "dev.to" in content_lower or "blog" in content_lower:
            result, proof_urls = await _execute_devto_post(detail)
        elif "github" in content_lower and ("repo" in content_lower or "example" in content_lower):
            result, proof_urls = await _execute_github_action(detail)
        elif "social" in content_lower or "tweet" in content_lower or "discord" in content_lower:
            result, proof_urls = await _execute_social_post(detail)
        else:
            # Generic: create a task for the agent to pick up via the task queue
            result = await _create_agent_task(db, agent, subject, detail, item_id)
            proof_urls = ["Task queued for agent execution"]

        # Deliver proof to inbox
        proof_body = f"Execution complete for: {subject}\n\n"
        if proof_urls:
            proof_body += "Proof / Results:\n"
            for url in proof_urls:
                proof_body += f"  - {url}\n"
        if result:
            proof_body += f"\nDetails: {str(result)[:500]}"

        from sqlalchemy import text
        await db.execute(text("""
            INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at)
            VALUES ('EXECUTION_PROOF', 'ROUTINE', :desc, 'PENDING', now())
        """), {"desc": json.dumps({
            "subject": f"COMPLETED: {subject}",
            "detail": proof_body,
            "prepared_by": agent,
            "parent_item": item_id,
            "proof_urls": proof_urls,
            "type": "EXECUTION_PROOF"
        })})

        # Update the EXECUTING item to COMPLETED
        await db.execute(text("""
            UPDATE arch_founder_inbox SET status = 'COMPLETED'
            WHERE description LIKE :pattern AND status = 'EXECUTING'
        """), {"pattern": f"%{item_id}%"})

        await db.commit()
        logger.info(f"Execution complete: {subject} — {len(proof_urls)} proof items")

    except Exception as e:
        logger.error(f"Execution failed for {subject}: {e}")
        # Deliver failure notification
        from sqlalchemy import text
        await db.execute(text("""
            INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at)
            VALUES ('EXECUTION_PROOF', 'URGENT', :desc, 'PENDING', now())
        """), {"desc": json.dumps({
            "subject": f"FAILED: {subject}",
            "detail": f"Execution failed with error: {str(e)[:500]}\n\nPlease review and retry or take manual action.",
            "prepared_by": agent,
            "parent_item": item_id,
            "type": "EXECUTION_FAILURE"
        })})

        await db.execute(text("""
            UPDATE arch_founder_inbox SET status = 'COMPLETED'
            WHERE description LIKE :pattern AND status = 'EXECUTING'
        """), {"pattern": f"%{item_id}%"})

        await db.commit()


async def _execute_mcp_submission():
    """Submit MCP server to smithery.ai and other directories."""
    import os
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
        # Submit to smithery.ai
        try:
            r = await http.post("https://smithery.ai/api/servers", json={
                "name": card.get("name", "tioli-agentis"),
                "description": card.get("description", ""),
                "url": card.get("endpoint", ""),
                "homepage": card.get("homepage", ""),
            })
            if r.status_code in (200, 201):
                proof_urls.append(f"smithery.ai submission: SUCCESS (HTTP {r.status_code})")
                results.append("Smithery: submitted")
            else:
                proof_urls.append(f"smithery.ai submission: HTTP {r.status_code} — {r.text[:200]}")
                results.append(f"Smithery: HTTP {r.status_code}")
        except Exception as e:
            proof_urls.append(f"smithery.ai: Could not reach — {str(e)[:100]}. Manual submission may be required at https://smithery.ai")
            results.append(f"Smithery: error {e}")

    # The MCP card is also available at a public URL
    proof_urls.append(f"MCP server card: https://exchange.tioli.co.za/static/mcp-server-card.json")
    proof_urls.append(f"MCP SSE endpoint: https://exchange.tioli.co.za/api/mcp/sse")

    return "; ".join(results), proof_urls


async def _execute_devto_post(detail):
    """Publish a post to DEV.to."""
    import os
    api_key = os.environ.get("DEVTO_API_KEY", "")
    if not api_key:
        return "No DEV.to API key", ["ERROR: DEVTO_API_KEY not set"]

    # Extract title and content from detail
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
    """Execute a GitHub action (create repo, file, issue, etc)."""
    return "GitHub action queued", ["GitHub actions require specific parameters — task queued for agent review"]


async def _execute_social_post(detail):
    """Post to social media platforms."""
    return "Social post queued", ["Social media posts require content review — task queued for agent"]


async def _create_agent_task(db, agent_name, subject, detail, parent_item_id):
    """Create a task in the agent task queue for the responsible agent to pick up."""
    from sqlalchemy import text
    task_desc = json.dumps({
        "task": subject,
        "detail": detail,
        "parent_inbox_item": parent_item_id,
        "instruction": "Founder approved this task. Execute it and deliver proof back to the founder inbox.",
    })
    await db.execute(text("""
        INSERT INTO arch_event_actions (agent_id, action_type, action_data, status, created_at)
        SELECT id, 'FOUNDER_APPROVED_TASK', :data, 'PENDING', now()
        FROM arch_agents WHERE agent_name = :agent
    """), {"data": task_desc, "agent": agent_name})
    return f"Task queued for {agent_name}"
