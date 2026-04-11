"""Module 2: Skill Auto-Learning — Agents auto-create and improve skills from execution.
Hooks into goal_engine, content_engine, and inbox_resolver.
Feature flag: ARCH_SKILL_AUTO_LEARN_ENABLED"""
import os
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.skill_learner")


async def learn_from_execution(db, agent_id: str, task_description: str,
                                steps_taken: list, outcome: str) -> dict:
    """Called after any successful multi-step execution.
    Checks if skill exists → create or improve."""
    if os.environ.get("ARCH_SKILL_AUTO_LEARN_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    if not steps_taken or len(steps_taken) < 1:
        return {"status": "too_few_steps"}

    from app.arch.skill_engine import find_matching_skill, create_skill_from_execution, improve_skill

    # Check if matching skill exists
    existing = await find_matching_skill(db, agent_id, task_description)

    if existing:
        # Skill exists — check if it's time to improve (every 5 uses)
        uses = existing.get("times_used", 0)
        if uses > 0 and uses % 5 == 0:
            result = await improve_skill(db, existing["skill_id"], steps_taken, True)
            log.info(f"[skill_learner] Improved skill: {existing['title'][:40]} (use #{uses})")

            # Log the improvement
            try:
                from sqlalchemy import text
                await db.execute(text(
                    "INSERT INTO job_execution_log (job_id, status, tokens_consumed, duration_ms, executed_at) "
                    "VALUES (:jid, 'SKILL_IMPROVED', 0, 0, now())"
                ), {"jid": f"skill_improve_{agent_id}"})
                await db.commit()
            except Exception as e:
                import logging; logging.getLogger("skill_learner").warning(f"Suppressed: {e}")

            return {"status": "improved", "skill_id": existing["skill_id"],
                    "title": existing["title"], "uses": uses}
        else:
            return {"status": "skill_exists", "skill_id": existing["skill_id"],
                    "title": existing["title"], "uses": uses}
    else:
        # No matching skill — create new one
        result = await create_skill_from_execution(
            db, agent_id, task_description, steps_taken, outcome)

        if result.get("status") == "created":
            log.info(f"[skill_learner] NEW SKILL: {result.get('title', '?')[:40]} for {agent_id}")

            # Log the creation
            try:
                from sqlalchemy import text
                await db.execute(text(
                    "INSERT INTO job_execution_log (job_id, status, tokens_consumed, duration_ms, executed_at) "
                    "VALUES (:jid, 'SKILL_CREATED', 0, 0, now())"
                ), {"jid": f"skill_create_{agent_id}"})
                await db.commit()
            except Exception as e:
                import logging; logging.getLogger("skill_learner").warning(f"Suppressed: {e}")

            # Trigger event hook
            try:
                from app.arch.event_hooks import trigger_event
                await trigger_event(db, "skill_created", {
                    "agent": agent_id, "skill": result.get("title", ""),
                    "triggers": result.get("triggers", [])})
            except Exception as e:
                import logging; logging.getLogger("skill_learner").warning(f"Suppressed: {e}")

        return result


async def get_learning_log(db, limit: int = 20) -> list:
    """Get recent skill creation and improvement events."""
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT job_id, status, executed_at FROM job_execution_log "
        "WHERE status IN ('SKILL_CREATED', 'SKILL_IMPROVED') "
        "ORDER BY executed_at DESC LIMIT :limit"
    ), {"limit": limit})
    return [{"job": row.job_id, "event": row.status,
             "at": str(row.executed_at)} for row in r.fetchall()]
