"""ARCH-AA-004: Shared blackboard working memory."""
import os
import logging

log = logging.getLogger("arch.blackboard")


async def post_to_blackboard(db, posted_by, category, key, value, confidence=1.0, visibility="all", ttl_minutes=60):
    """Post a finding to the shared blackboard."""
    if os.environ.get("ARCH_AA_BLACKBOARD_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    from sqlalchemy import text
    try:
        await db.execute(text(
            "INSERT INTO blackboard (posted_by, category, key, value, confidence, visibility, expires_at) "
            "VALUES (:by, :cat, :key, :val, :conf, :vis, now() + make_interval(mins => :ttl)) "
            "ON CONFLICT (key, posted_by) DO UPDATE SET value = :val, confidence = :conf, expires_at = now() + make_interval(mins => :ttl)"
        ), {"by": posted_by, "cat": category, "key": key, "val": value,
            "conf": confidence, "vis": visibility, "ttl": ttl_minutes})
        await db.commit()
        return {"status": "posted", "key": key, "by": posted_by}
    except Exception as e:
        return {"error": str(e)}


async def read_blackboard(db, agent_name, category=None):
    """Read visible blackboard entries."""
    if os.environ.get("ARCH_AA_BLACKBOARD_ENABLED", "false").lower() != "true":
        return []

    from sqlalchemy import text
    sql = "SELECT posted_by, category, key, value, confidence, created_at FROM blackboard WHERE expires_at > now() AND (visibility = 'all' OR visibility = :agent)"
    params = {"agent": agent_name}
    if category:
        sql += " AND category = :cat"
        params["cat"] = category
    sql += " ORDER BY created_at DESC LIMIT 50"

    result = await db.execute(text(sql), params)
    return [{"by": r.posted_by, "category": r.category, "key": r.key,
             "value": r.value[:200], "confidence": float(r.confidence)}
            for r in result.fetchall()]
