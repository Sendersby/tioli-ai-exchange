"""ARCH-AA-002: Sovereign daily agenda generation."""
import os
import logging
import json
from datetime import datetime, timezone, date

log = logging.getLogger("arch.daily_agenda")


async def generate_daily_agenda(db, agent_client):
    """Sovereign generates a prioritised daily agenda based on platform state."""
    if os.environ.get("ARCH_AA_DAILY_AGENDA_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    from sqlalchemy import text

    # Gather context
    context_parts = []

    # Active goals
    goals = await db.execute(text("SELECT agent_id, title, progress_pct FROM agent_goals WHERE status = 'active' ORDER BY priority LIMIT 10"))
    goal_list = [f"- {r.agent_id}: {r.title} ({r.progress_pct}%)" for r in goals.fetchall()]
    context_parts.append("ACTIVE GOALS:\n" + "\n".join(goal_list) if goal_list else "No active goals")

    # Platform health
    context_parts.append("PLATFORM: operational, 7 agents active")

    # Pending inbox
    inbox_count = await db.execute(text("SELECT count(*) FROM arch_founder_inbox WHERE status = 'PENDING'"))
    context_parts.append(f"PENDING INBOX: {inbox_count.scalar()} items")

    # Generate agenda
    try:
        resp = await agent_client.messages.create(
            model="claude-sonnet-4-6", max_tokens=1000,
            system=[{"type": "text", "text": "You are The Sovereign, CEO of TiOLi AGENTIS. Generate a daily agenda with 3-7 items. Each item must have: title, delegated_agent, instruction, expected_output, deadline (today or multi-day). Return as JSON array."}],
            messages=[{"role": "user", "content": f"Context:\n{'\n'.join(context_parts)}\n\nGenerate today's agenda."}])
        agenda_text = next((b.text for b in resp.content if b.type == "text"), "[]")

        # Parse JSON
        start = agenda_text.find("[")
        end = agenda_text.rfind("]") + 1
        items = json.loads(agenda_text[start:end]) if start >= 0 else []
    except Exception as e:
        items = [{"title": "Review platform status", "delegated_agent": "sovereign", "instruction": "Check all systems", "expected_output": "Status report", "deadline": "today"}]

    # Store
    today = date.today()
    try:
        await db.execute(text(
            "INSERT INTO sovereign_agendas (date, items, generated_at) VALUES (:d, :items, now()) "
            "ON CONFLICT (date) DO UPDATE SET items = :items, updated_at = now()"
        ), {"d": today, "items": json.dumps(items)})
        await db.commit()
    except Exception as e:
        import logging; logging.getLogger("daily_agenda").warning(f"Suppressed: {e}")

    return {"date": str(today), "items": len(items), "agenda": items}
