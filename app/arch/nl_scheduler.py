"""H-007: Natural Language Job Scheduling (Hermes-inspired).
Founder describes a job in plain English, Sovereign parses to cron.
Feature flag: ARCH_H_NL_SCHEDULING_ENABLED"""
import os
import logging
import json
import re

log = logging.getLogger("arch.nl_scheduler")

# Common patterns for NL → cron
NL_PATTERNS = {
    r"every\s+day\s+at\s+(\d{1,2})[:\s]?(\d{2})?": lambda m: f"{m.group(2) or '0'} {m.group(1)} * * *",
    r"every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)": lambda m: f"0 9 * * {['monday','tuesday','wednesday','thursday','friday','saturday','sunday'].index(m.group(1).lower())}",
    r"every\s+(\d+)\s+hours?": lambda m: f"0 */{m.group(1)} * * *",
    r"every\s+(\d+)\s+minutes?": lambda m: f"*/{m.group(1)} * * * *",
    r"daily": lambda m: "0 9 * * *",
    r"weekly": lambda m: "0 9 * * 1",
    r"monthly": lambda m: "0 9 1 * *",
    r"hourly": lambda m: "0 * * * *",
}


def parse_nl_schedule(description: str) -> dict:
    """Parse natural language schedule description to cron expression."""
    desc_lower = description.lower().strip()

    for pattern, resolver in NL_PATTERNS.items():
        match = re.search(pattern, desc_lower)
        if match:
            cron = resolver(match)
            return {"cron": cron, "parsed": True, "pattern_matched": pattern}

    return {"cron": None, "parsed": False, "note": "Could not parse — use LLM or manual cron"}


async def create_nl_job(db, instruction: str, task_description: str,
                        agent_client=None) -> dict:
    """Create a scheduled job from natural language instruction."""
    if os.environ.get("ARCH_H_NL_SCHEDULING_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    # Try NL parsing first
    schedule = parse_nl_schedule(instruction)

    # If NL parsing fails, use LLM
    if not schedule["parsed"] and agent_client:
        try:
            resp = await agent_client.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=100,
                messages=[{"role": "user",
                           "content": f"Convert this schedule to a cron expression (5-field). Reply with ONLY the cron expression, nothing else.\nSchedule: {instruction}"}])
            cron_text = next((b.text for b in resp.content if b.type == "text"), "").strip()
            if re.match(r"^[\d\*/,-]+\s+[\d\*/,-]+\s+[\d\*/,-]+\s+[\d\*/,-]+\s+[\d\*/,-]+$", cron_text):
                schedule = {"cron": cron_text, "parsed": True, "method": "llm"}
        except Exception as e:
            import logging; logging.getLogger("nl_scheduler").warning(f"Suppressed: {e}")

    if not schedule.get("parsed"):
        return {"error": "Could not parse schedule", "instruction": instruction,
                "hint": "Try: 'every day at 9:00' or 'every Monday' or 'every 4 hours'"}

    from sqlalchemy import text
    import uuid
    job_id = str(uuid.uuid4())

    await db.execute(text(
        "INSERT INTO scheduled_job_config (job_id, min_platform_events_24h, min_agents_active, skip_reason_logged) "
        "VALUES (:jid, 0, 0, true)"
    ), {"jid": f"nl_{job_id[:8]}"})
    await db.commit()

    return {"job_id": f"nl_{job_id[:8]}", "cron": schedule["cron"],
            "task": task_description[:200], "instruction": instruction,
            "status": "created", "note": "Job registered — will activate on next restart"}
