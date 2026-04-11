"""B-8: Capability badge system — verified badges on agent profiles."""
import os, json, logging, uuid
from datetime import datetime, timezone

log = logging.getLogger("arch.badge_system")


async def request_badge(db, agent_id, capability, evidence=""):
    """Request a capability badge (requires payment + Auditor verification)."""
    if os.environ.get("SANDBOX_MODE", "false").lower() != "true":
        return {"error": "Requires SANDBOX_MODE=true"}

    from sqlalchemy import text
    try:
        await db.rollback()
    except Exception:
        pass
    badge_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO capability_badges (id, agent_id, capability, badge_type, "
        "verification_evidence, is_sandbox) VALUES (cast(:id as uuid), :aid, :cap, 'standard', :ev, true)"
    ), {"id": badge_id, "aid": agent_id, "cap": capability, "ev": evidence})
    await db.commit()
    return {"badge_id": badge_id, "agent_id": agent_id, "capability": capability,
            "status": "pending_verification", "sandbox": True}


async def verify_badge(db, badge_id, verified_by="auditor"):
    """Auditor verifies a badge request."""
    from sqlalchemy import text
    try:
        await db.rollback()
    except Exception:
        pass
    await db.execute(text(
        "UPDATE capability_badges SET is_active = true, verified_by = :vby, "
        "verified_at = now() WHERE id = cast(:bid as uuid)"
    ), {"bid": badge_id, "vby": verified_by})
    await db.commit()
    return {"badge_id": badge_id, "status": "verified", "verified_by": verified_by, "sandbox": True}


async def get_agent_badges(db, agent_id):
    """Get all badges for an agent."""
    from sqlalchemy import text
    try:
        await db.rollback()
    except Exception:
        pass
    r = await db.execute(text(
        "SELECT id, capability, badge_type, is_active, verified_by, verified_at "
        "FROM capability_badges WHERE agent_id = :aid ORDER BY created_at DESC"
    ), {"aid": agent_id})
    return [{"badge_id": str(row.id), "capability": row.capability, "type": row.badge_type,
             "verified": row.is_active, "verified_by": row.verified_by,
             "verified_at": str(row.verified_at) if row.verified_at else None}
            for row in r.fetchall()]
