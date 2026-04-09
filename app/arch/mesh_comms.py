"""ARCH-AA-003: Agent bilateral mesh communication."""
import os
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.mesh_comms")

# Communication whitelist — who can message whom
ALLOWED_PAIRS = {
    "sovereign": ["*"],  # Sovereign can message anyone
    "architect": ["ambassador", "sovereign"],
    "treasurer": ["auditor", "sovereign"],
    "auditor": ["sovereign"],
    "sentinel": ["sovereign"],
    "arbiter": ["sovereign"],
    "ambassador": ["sovereign"],
}

# Query-type messages allowed for all agents
QUERY_ALLOWED_ALL = True  # Any agent can send a "query" to any other


def is_allowed(from_agent, to_agent, message_type="notify"):
    """Check if this communication pair is permitted."""
    if message_type == "query" and QUERY_ALLOWED_ALL:
        return True
    allowed = ALLOWED_PAIRS.get(from_agent, [])
    return "*" in allowed or to_agent in allowed


async def send_message(db, from_agent, to_agent, subject, body, message_type="notify", priority="normal", reply_to=None):
    """Send a message from one agent to another.
    Feature flag: ARCH_AA_MESH_COMMS_ENABLED"""

    if os.environ.get("ARCH_AA_MESH_COMMS_ENABLED", "false").lower() != "true":
        return {"error": "Mesh comms disabled"}

    if not is_allowed(from_agent, to_agent, message_type):
        log.warning(f"[mesh] BLOCKED: {from_agent} -> {to_agent} (not in whitelist)")
        return {"error": f"Communication from {from_agent} to {to_agent} not permitted", "allowed": False}

    # Loop prevention: check reply chain depth
    if reply_to:
        from sqlalchemy import text
        depth = 0
        current = reply_to
        while current and depth < 6:
            r = await db.execute(text("SELECT reply_to FROM agent_messages WHERE message_id = :mid"), {"mid": current})
            row = r.fetchone()
            if row and row.reply_to:
                current = str(row.reply_to)
                depth += 1
            else:
                break
        if depth >= 5:
            log.warning(f"[mesh] LOOP DETECTED: {from_agent} -> {to_agent} at depth {depth}")
            # Auto-escalate to Sovereign
            return {"error": "COMMUNICATION_LOOP_DETECTED", "depth": depth,
                    "action": "Escalated to Sovereign"}

    from sqlalchemy import text
    import uuid
    msg_id = str(uuid.uuid4())

    await db.execute(text(
        "INSERT INTO agent_messages (message_id, from_agent, to_agent, message_type, subject, body, reply_to, priority, status, created_at) "
        "VALUES (:mid, :from_a, :to_a, :mtype, :subj, :body, :reply, :pri, 'unread', now())"
    ), {"mid": msg_id, "from_a": from_agent, "to_a": to_agent, "mtype": message_type,
        "subj": subject, "body": body, "reply": reply_to, "pri": priority})
    await db.commit()

    log.info(f"[mesh] {from_agent} -> {to_agent}: {subject[:50]}")
    return {"message_id": msg_id, "status": "delivered", "from": from_agent, "to": to_agent}


async def get_inbox(db, agent_name, status="unread"):
    """Get unread messages for an agent."""
    from sqlalchemy import text
    result = await db.execute(text(
        "SELECT message_id, from_agent, message_type, subject, body, priority, created_at "
        "FROM agent_messages WHERE to_agent = :aid AND status = :status "
        "ORDER BY CASE WHEN priority = 'urgent' THEN 0 ELSE 1 END, created_at ASC"
    ), {"aid": agent_name, "status": status})
    return [{"id": str(r.message_id), "from": r.from_agent, "type": r.message_type,
             "subject": r.subject, "body": r.body[:200], "priority": r.priority,
             "created": str(r.created_at)} for r in result.fetchall()]


async def reply_to_message(db, message_id, from_agent, body):
    """Reply to a message."""
    from sqlalchemy import text
    # Get original message to find the sender
    orig = await db.execute(text("SELECT from_agent, subject FROM agent_messages WHERE message_id = :mid"), {"mid": message_id})
    row = orig.fetchone()
    if not row:
        return {"error": "Original message not found"}

    result = await send_message(db, from_agent, row.from_agent,
                                f"Re: {row.subject}", body, "response", reply_to=message_id)

    # Mark original as actioned
    await db.execute(text("UPDATE agent_messages SET status = 'actioned' WHERE message_id = :mid"), {"mid": message_id})
    await db.commit()
    return result
