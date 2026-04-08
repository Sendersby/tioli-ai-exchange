"""Automated agent evaluation — score agent performance periodically."""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.evaluation")


async def evaluate_agent(db, agent_name: str, agent_client=None):
    """Evaluate an Arch Agent's performance across key dimensions."""
    from sqlalchemy import text

    scores = {}

    # 1. Activity score (0-25): How active has the agent been?
    try:
        actions = await db.execute(text(
            "SELECT count(*) FROM arch_event_actions WHERE agent_name = :name "
            "AND created_at > now() - interval '7 days'"
        ), {"name": agent_name})
        action_count = actions.scalar() or 0
        scores["activity"] = min(25, action_count * 2)
    except Exception:
        scores["activity"] = 0

    # 2. Memory utilisation (0-20): Is the agent learning?
    try:
        mems = await db.execute(text(
            "SELECT count(*) FROM arch_memory_outbox WHERE agent_id IN "
            "(SELECT id::text FROM arch_agents WHERE agent_name = :name) "
            "AND created_at > now() - interval '7 days'"
        ), {"name": agent_name})
        mem_count = mems.scalar() or 0
        scores["memory"] = min(20, mem_count)
    except Exception:
        scores["memory"] = 0

    # 3. Task completion (0-25): Has the agent completed tasks?
    try:
        tasks = await db.execute(text(
            "SELECT count(*) FROM arch_task_queue WHERE agent_name = :name AND status = 'completed'"
        ), {"name": agent_name})
        task_count = tasks.scalar() or 0
        scores["tasks"] = min(25, task_count * 5)
    except Exception:
        scores["tasks"] = 0

    # 4. Communication (0-15): Is the agent producing outputs?
    try:
        inbox = await db.execute(text(
            "SELECT count(*) FROM arch_founder_inbox WHERE description LIKE :pattern"
        ), {"pattern": f"%{agent_name}%"})
        inbox_count = inbox.scalar() or 0
        scores["communication"] = min(15, inbox_count)
    except Exception:
        scores["communication"] = 0

    # 5. Reliability (0-15): Error rate
    scores["reliability"] = 15  # Default — reduce based on errors

    total = sum(scores.values())
    grade = "A" if total >= 80 else "B" if total >= 60 else "C" if total >= 40 else "D" if total >= 20 else "F"

    return {
        "agent": agent_name,
        "total_score": total,
        "max_score": 100,
        "grade": grade,
        "scores": scores,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }


async def evaluate_all_agents(db, agent_client=None):
    """Evaluate all 7 Arch Agents."""
    from sqlalchemy import text
    agents = await db.execute(text("SELECT agent_name FROM arch_agents"))
    results = []
    for row in agents.fetchall():
        result = await evaluate_agent(db, row.agent_name, agent_client)
        results.append(result)
    return sorted(results, key=lambda x: x["total_score"], reverse=True)
