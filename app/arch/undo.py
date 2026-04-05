"""Undo Engine — one-click reversal for agent actions.

Every reversible action stores enough state to undo it.
Irreversible actions are marked as such.

Reversal types:
- FILE_WRITE: delete the file or restore previous version
- SHELL_COMMAND: run inverse command if available
- CONTENT_GENERATED: mark as withdrawn/retracted
- SOCIAL_POST: delete from queue
- DB_CHANGE: restore previous state from snapshot
- CHAT_MESSAGE: mark as retracted
- BOARD_SESSION: no undo (constitutional record)
- CONSTITUTIONAL_RULING: no undo (immutable)
"""

import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import text

log = logging.getLogger("arch.undo")

# Which action types can be undone
REVERSIBLE_ACTIONS = {
    "content.generated": "RETRACT",
    "system.command_executed": "CONDITIONAL",
    "executor.content_generate": "RETRACT",
    "executor.file_write": "DELETE_FILE",
    "executor.shell_command": "CONDITIONAL",
    "executor.social_post": "DELETE_QUEUE",
    "executor.browse_url": "NO_UNDO",
    "executor.http_request": "NO_UNDO",
    "boardroom.founder_message": "RETRACT",
    "boardroom.agent_response": "RETRACT",
    "boardroom.session_convened": "NO_UNDO",
    "boardroom.session_closed": "NO_UNDO",
    "governance.constitutional_ruling": "NO_UNDO",
    "agent.governance": "CONDITIONAL",
}


async def get_undo_status(action_id: str, db) -> dict:
    """Check if an action can be undone and what the undo would do."""
    result = await db.execute(text("""
        SELECT id::text, agent_id, event_type, action_taken,
               tool_called, tool_input, tool_output, created_at
        FROM arch_event_actions WHERE id = cast(:aid as uuid)
    """), {"aid": action_id})
    row = result.fetchone()

    if not row:
        return {"error": "Action not found"}

    event_type = row.event_type
    reversible = REVERSIBLE_ACTIONS.get(event_type, "NO_UNDO")

    # Check if already undone
    existing_undo = await db.execute(text("""
        SELECT id FROM arch_event_actions
        WHERE event_type = 'system.undo'
          AND tool_input::text LIKE :pattern
    """), {"pattern": f"%{action_id}%"})

    already_undone = existing_undo.fetchone() is not None

    undo_info = {
        "action_id": action_id,
        "agent": row.agent_id,
        "event_type": event_type,
        "action": row.action_taken,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "reversible": reversible != "NO_UNDO",
        "undo_type": reversible,
        "already_undone": already_undone,
        "undo_description": _describe_undo(reversible, row),
    }

    return undo_info


def _describe_undo(undo_type: str, row) -> str:
    """Human-readable description of what the undo will do."""
    if undo_type == "NO_UNDO":
        return "This action cannot be undone (constitutional/immutable record)."
    elif undo_type == "RETRACT":
        return "This will mark the content as retracted. The record remains in the audit trail but is flagged as withdrawn."
    elif undo_type == "DELETE_FILE":
        tool_input = row.tool_input if isinstance(row.tool_input, dict) else json.loads(row.tool_input or "{}")
        path = tool_input.get("path", "unknown")
        return f"This will delete the file: {path}"
    elif undo_type == "DELETE_QUEUE":
        return "This will remove the content from the posting queue."
    elif undo_type == "CONDITIONAL":
        return "This action may be partially reversible. Review the details before proceeding."
    return "Unknown undo type."


async def execute_undo(action_id: str, db, reason: str = "Founder requested undo") -> dict:
    """Execute the undo for a specific action."""

    # Get action details
    result = await db.execute(text("""
        SELECT id::text, agent_id, event_type, action_taken,
               tool_called, tool_input, tool_output, created_at
        FROM arch_event_actions WHERE id = cast(:aid as uuid)
    """), {"aid": action_id})
    row = result.fetchone()

    if not row:
        return {"error": "Action not found", "undone": False}

    undo_type = REVERSIBLE_ACTIONS.get(row.event_type, "NO_UNDO")

    if undo_type == "NO_UNDO":
        return {"error": "This action cannot be undone", "undone": False,
                "reason": "Constitutional or immutable record"}

    # Check if already undone
    existing = await db.execute(text("""
        SELECT id FROM arch_event_actions
        WHERE event_type = 'system.undo'
          AND tool_input::text LIKE :pattern
    """), {"pattern": f"%{action_id}%"})
    if existing.fetchone():
        return {"error": "Already undone", "undone": False}

    undo_result = {}
    tool_input = row.tool_input if isinstance(row.tool_input, dict) else json.loads(row.tool_input or "{}")

    try:
        if undo_type == "DELETE_FILE":
            path = tool_input.get("path", "")
            if path and os.path.exists(path):
                # Backup before delete
                backup_path = path + f".undo_backup_{int(datetime.now(timezone.utc).timestamp())}"
                os.rename(path, backup_path)
                undo_result = {"deleted": path, "backup": backup_path}
            else:
                undo_result = {"note": f"File {path} not found — may already be deleted"}

        elif undo_type == "DELETE_QUEUE":
            # Find and remove from content queue
            platform = tool_input.get("platform", "")
            content_preview = tool_input.get("content_preview", "")
            queue_dir = f"/home/tioli/app/content_queue/{platform}"
            if os.path.exists(queue_dir):
                for f in os.listdir(queue_dir):
                    fpath = os.path.join(queue_dir, f)
                    with open(fpath) as fh:
                        if content_preview[:50] in fh.read():
                            os.rename(fpath, fpath + ".undone")
                            undo_result = {"removed": fpath}
                            break
            if not undo_result:
                undo_result = {"note": "Queue file not found"}

        elif undo_type == "RETRACT":
            # Mark the original action as retracted
            await db.execute(text("""
                UPDATE arch_event_actions
                SET action_taken = '[RETRACTED] ' || action_taken
                WHERE id = cast(:aid as uuid)
            """), {"aid": action_id})
            undo_result = {"retracted": True, "action_id": action_id}

        elif undo_type == "CONDITIONAL":
            # For shell commands — we can't truly undo, but we log the reversal request
            undo_result = {
                "note": "Conditional undo logged. The original command's effects may require manual review.",
                "original_command": tool_input.get("command", "unknown")[:200],
            }

    except Exception as e:
        undo_result = {"error": str(e)}

    # Record the undo action in the activity feed
    await db.execute(text("""
        INSERT INTO arch_event_actions
            (agent_id, event_type, action_taken, tool_called, tool_input, processing_time_ms)
        VALUES (:agent, 'system.undo', :action, 'UNDO', :input, 0)
    """), {
        "agent": row.agent_id,
        "action": f"UNDO of [{row.event_type}]: {row.action_taken[:150]} — Reason: {reason}",
        "input": json.dumps({
            "undone_action_id": action_id,
            "undo_type": undo_type,
            "reason": reason,
            "result": undo_result,
        }, default=str),
    })

    # Also record in the immutable founder actions
    await db.execute(text("""
        INSERT INTO boardroom_founder_actions
            (action_type, reference_type, context_snapshot)
        VALUES ('INBOX_ACTIONED', 'undo_action', :context)
    """), {
        "context": json.dumps({
            "undone_action_id": action_id,
            "agent": row.agent_id,
            "original_action": row.action_taken[:300],
            "undo_type": undo_type,
            "reason": reason,
            "result": undo_result,
        }, default=str),
    })

    await db.commit()

    log.info(f"[undo] Action {action_id} undone by founder. Type: {undo_type}")

    return {
        "undone": True,
        "action_id": action_id,
        "undo_type": undo_type,
        "result": undo_result,
        "logged": True,
    }
