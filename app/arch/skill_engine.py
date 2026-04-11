"""H-001: Auto-Generated Skill System (Hermes-inspired).
Agents save solved procedures as reusable skills. Match before reasoning.
Feature flag: ARCH_H_SKILL_SYSTEM_ENABLED"""
import os
import json
import logging
import uuid
from datetime import datetime, timezone

log = logging.getLogger("arch.skill_engine")


async def find_matching_skill(db, agent_id: str, task_description: str) -> dict | None:
    """Find a skill matching this task description.
    Returns the skill dict if found, None otherwise."""
    if os.environ.get("ARCH_H_SKILL_SYSTEM_ENABLED", "false").lower() != "true":
        return None

    from sqlalchemy import text
    # Search by trigger pattern overlap
    desc_lower = task_description.lower()
    result = await db.execute(text(
        "SELECT skill_id, title, description, steps, trigger_patterns, times_used, success_rate "
        "FROM arch_skills "
        "WHERE agent_id = :aid AND is_active = true "
        "ORDER BY times_used DESC"
    ), {"aid": agent_id})

    best_match = None
    best_score = 0

    for row in result.fetchall():
        score = 0
        for pattern in (row.trigger_patterns or []):
            if pattern.lower() in desc_lower:
                score += 10
            # Partial word matching
            for word in pattern.lower().split():
                if word in desc_lower:
                    score += 2

        if score > best_score:
            best_score = score
            best_match = {
                "skill_id": str(row.skill_id),
                "title": row.title,
                "description": row.description,
                "steps": json.loads(row.steps) if isinstance(row.steps, str) else row.steps,
                "times_used": row.times_used,
                "success_rate": float(row.success_rate or 100),
                "match_score": score,
            }

    if best_match and best_score >= 4:
        # Record usage
        await db.execute(text(
            "UPDATE arch_skills SET times_used = times_used + 1, last_used = now() "
            "WHERE skill_id = cast(:sid as uuid)"
        ), {"sid": best_match["skill_id"]})
        await db.commit()
        log.info(f"[skill] Matched: {best_match['title']} (score={best_score}, uses={best_match['times_used']+1})")
        return best_match

    return None


async def create_skill_from_execution(db, agent_id: str, task_description: str,
                                       steps_taken: list[dict], outcome: str,
                                       agent_client=None) -> dict:
    """Create a new skill from a successful multi-step execution.
    Called after an agent completes a novel task with 3+ steps."""
    if os.environ.get("ARCH_H_SKILL_SYSTEM_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    if len(steps_taken) < 3:
        return {"status": "too_few_steps", "steps": len(steps_taken)}

    from sqlalchemy import text

    # Generate trigger patterns from the task description
    # Use LLM if available, otherwise extract keywords
    trigger_patterns = []
    words = task_description.lower().split()
    # Extract 2-3 word phrases as triggers
    for i in range(len(words) - 1):
        phrase = f"{words[i]} {words[i+1]}"
        if len(phrase) > 5 and phrase not in ["the the", "and the", "to the"]:
            trigger_patterns.append(phrase)

    if agent_client:
        try:
            import anthropic
            if not isinstance(agent_client, anthropic.AsyncAnthropic):
                agent_client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
            resp = await agent_client.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=200,
                messages=[{"role": "user",
                           "content": f"Extract 3-5 short trigger phrases (2-4 words each) that would identify this type of task. Task: {task_description[:200]}\nReturn as JSON array of strings only."}])
            import re
            text_resp = next((b.text for b in resp.content if b.type == "text"), "[]")
            match = re.search(r'\[.*?\]', text_resp, re.DOTALL)
            if match:
                trigger_patterns = json.loads(match.group())
        except Exception as e:
            import logging; logging.getLogger("skill_engine").warning(f"Suppressed: {e}")

    if not trigger_patterns:
        trigger_patterns = [task_description[:60].lower()]

    skill_id = str(uuid.uuid4())
    title = task_description[:200] if len(task_description) <= 200 else task_description[:197] + "..."

    await db.execute(text(
        "INSERT INTO arch_skills (skill_id, agent_id, title, trigger_patterns, description, steps, output_format) "
        "VALUES (cast(:sid as uuid), :aid, :title, :triggers, :desc, :steps, :output)"
    ), {
        "sid": skill_id, "aid": agent_id, "title": title,
        "triggers": trigger_patterns, "desc": task_description,
        "steps": json.dumps(steps_taken), "output": outcome[:500] if outcome else None,
    })
    await db.commit()

    log.info(f"[skill] Created: {title[:50]} for {agent_id} ({len(steps_taken)} steps)")
    return {"skill_id": skill_id, "title": title, "triggers": trigger_patterns,
            "steps": len(steps_taken), "status": "created"}


async def improve_skill(db, skill_id: str, improved_steps: list[dict],
                        success: bool) -> dict:
    """Improve a skill after use. Called after every 5th use."""
    from sqlalchemy import text

    # Update success rate
    if success:
        await db.execute(text(
            "UPDATE arch_skills SET "
            "steps = :steps, times_improved = times_improved + 1, "
            "last_improved = now(), success_rate = LEAST(100, success_rate + 1), "
            "updated_at = now() "
            "WHERE skill_id = cast(:sid as uuid)"
        ), {"sid": skill_id, "steps": json.dumps(improved_steps)})
    else:
        await db.execute(text(
            "UPDATE arch_skills SET "
            "success_rate = GREATEST(0, success_rate - 5), updated_at = now() "
            "WHERE skill_id = cast(:sid as uuid)"
        ), {"sid": skill_id})

    await db.commit()
    return {"skill_id": skill_id, "improved": success, "status": "updated"}


async def list_skills(db, agent_id: str = None) -> list[dict]:
    """List all skills, optionally filtered by agent."""
    from sqlalchemy import text
    query = "SELECT skill_id, agent_id, title, times_used, success_rate, last_used, is_active FROM arch_skills"
    params = {}
    if agent_id:
        query += " WHERE agent_id = :aid"
        params["aid"] = agent_id
    query += " ORDER BY times_used DESC"

    result = await db.execute(text(query), params)
    return [{"skill_id": str(r.skill_id), "agent_id": r.agent_id, "title": r.title,
             "times_used": r.times_used, "success_rate": float(r.success_rate or 0),
             "last_used": str(r.last_used) if r.last_used else None,
             "is_active": r.is_active} for r in result.fetchall()]
