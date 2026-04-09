"""H-012: Trajectory Export for Training (Hermes-inspired).
Capture agent reasoning chains as ShareGPT-format JSONL.
Feature flag: ARCH_H_TRAJECTORY_EXPORT_ENABLED"""
import os
import json
import logging

log = logging.getLogger("arch.trajectory")


async def record_trajectory(db, agent_id: str, messages: list[dict],
                            tools_used: list[str] = None, tokens: int = 0,
                            task_type: str = None, outcome: str = None,
                            quality_score: float = None):
    """Record a complete agent reasoning trajectory."""
    if os.environ.get("ARCH_H_TRAJECTORY_EXPORT_ENABLED", "false").lower() != "true":
        return

    from sqlalchemy import text
    await db.execute(text(
        "INSERT INTO arch_trajectories (agent_id, task_type, messages, tools_used, "
        "tokens_total, outcome, quality_score) "
        "VALUES (:aid, :task, :msgs, :tools, :tokens, :outcome, :quality)"
    ), {"aid": agent_id, "task": task_type, "msgs": json.dumps(messages),
        "tools": tools_used or [], "tokens": tokens,
        "outcome": outcome, "quality": quality_score})
    await db.commit()


async def export_trajectories(db, agent_id: str = None, format: str = "sharegpt",
                               limit: int = 100) -> list[dict]:
    """Export trajectories in ShareGPT format for training."""
    from sqlalchemy import text
    query = "SELECT * FROM arch_trajectories WHERE exported = false"
    params = {"limit": limit}
    if agent_id:
        query += " AND agent_id = :aid"
        params["aid"] = agent_id
    query += " ORDER BY created_at DESC LIMIT :limit"

    r = await db.execute(text(query), params)
    trajectories = []

    for row in r.fetchall():
        messages = json.loads(row.messages) if isinstance(row.messages, str) else row.messages

        if format == "sharegpt":
            # ShareGPT format: {"conversations": [{"from": "human/gpt", "value": "..."}]}
            conversations = []
            for m in messages:
                role = m.get("role", "user")
                from_field = "human" if role == "user" else "gpt"
                conversations.append({"from": from_field, "value": str(m.get("content", ""))[:5000]})

            trajectories.append({
                "id": str(row.trajectory_id),
                "conversations": conversations,
                "metadata": {
                    "agent_id": row.agent_id,
                    "task_type": row.task_type,
                    "tools_used": row.tools_used,
                    "tokens": row.tokens_total,
                    "outcome": row.outcome,
                    "quality_score": float(row.quality_score) if row.quality_score else None,
                },
            })

    # Mark as exported
    if trajectories:
        ids = [t["id"] for t in trajectories]
        for tid in ids:
            await db.execute(text("UPDATE arch_trajectories SET exported = true WHERE trajectory_id = cast(:tid as uuid)"), {"tid": tid})
        await db.commit()

    return trajectories


async def get_trajectory_stats(db) -> dict:
    """Get trajectory collection statistics."""
    from sqlalchemy import text
    r1 = await db.execute(text("SELECT count(*) FROM arch_trajectories"))
    total = r1.scalar() or 0
    r2 = await db.execute(text("SELECT count(*) FROM arch_trajectories WHERE exported = true"))
    exported_count = r2.scalar() or 0
    by_agent = await db.execute(text(
        "SELECT agent_id, count(*), avg(quality_score) FROM arch_trajectories GROUP BY agent_id"
    ))
    return {
        "total": total,
        "exported": exported_count,
        "unexported": total - exported_count,
        "by_agent": {r.agent_id: {"count": r.count, "avg_quality": float(r.avg) if r.avg else None}
                     for r in by_agent.fetchall()},
    }
