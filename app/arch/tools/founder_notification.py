"""Founder notification tool — lets any Arch Agent escalate to the founder.

Inserts into arch_founder_inbox (primary) or notifications (fallback).
Maps priority levels to the database enum: info/warning -> ROUTINE,
urgent -> URGENT, critical -> EMERGENCY.
"""

import logging
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

logger = logging.getLogger("arch.founder_notification")

# Map caller-friendly priority names to database enum values
_PRIORITY_MAP = {
    "info": "ROUTINE",
    "warning": "ROUTINE",
    "urgent": "URGENT",
    "critical": "EMERGENCY",
}

FOUNDER_NOTIFICATION_TOOLS = [
    {
        "name": "send_founder_notification",
        "description": (
            "Send a notification to the platform founder (Stephen Endersby). "
            "Use this to escalate issues, report findings, request decisions, "
            "or alert about problems that need human attention. Priority levels: "
            "info (FYI), warning (should review), urgent (needs action today), "
            "critical (immediate attention required)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "priority": {
                    "type": "string",
                    "enum": ["info", "warning", "urgent", "critical"],
                    "description": "Notification priority level",
                },
                "subject": {
                    "type": "string",
                    "description": "Brief subject line (max 200 chars)",
                },
                "body": {
                    "type": "string",
                    "description": (
                        "Detailed notification body with context, findings, "
                        "and recommended actions"
                    ),
                },
                "action_required": {
                    "type": "boolean",
                    "description": (
                        "Whether the founder needs to take action (true) "
                        "or this is informational (false)"
                    ),
                },
            },
            "required": ["priority", "subject", "body"],
        },
    }
]


async def send_founder_notification(
    db,
    agent_name: str,
    priority: str,
    subject: str,
    body: str,
    action_required: bool = False,
) -> dict:
    """Send a structured notification to the founder's inbox.

    Priority levels: info, warning, urgent, critical.
    Maps to arch_msg_priority enum: ROUTINE, URGENT, EMERGENCY.
    """
    valid_priorities = {"info", "warning", "urgent", "critical"}
    if priority not in valid_priorities:
        priority = "info"

    db_priority = _PRIORITY_MAP.get(priority, "ROUTINE")

    # Build description JSON with structured fields
    description = json.dumps({
        "subject": subject[:200],
        "body": body[:5000],
        "action_required": action_required,
        "priority_requested": priority,
        "from_agent": agent_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    try:
        # Look up agent UUID for prepared_by FK
        agent_row = await db.execute(
            text("SELECT id FROM arch_agents WHERE agent_name = :n"),
            {"n": agent_name},
        )
        agent_uuid = agent_row.scalar()

        await db.execute(
            text(
                "INSERT INTO arch_founder_inbox "
                "(item_type, priority, description, prepared_by, status, due_at) "
                "VALUES (:item_type, :priority, :desc, :agent, 'PENDING', "
                "now() + interval '24 hours')"
            ),
            {
                "item_type": f"AGENT_NOTIFICATION",
                "priority": db_priority,
                "desc": description,
                "agent": agent_uuid,
            },
        )
        await db.commit()

        logger.info(
            f"Founder notification sent: [{priority}] {subject[:50]} from {agent_name}"
        )

        return {
            "sent": True,
            "priority": priority,
            "db_priority": db_priority,
            "subject": subject[:200],
            "from": agent_name,
            "action_required": action_required,
            "note": "Notification delivered to founder inbox.",
        }
    except Exception as e:
        logger.error(f"Founder notification primary insert failed: {e}")
        # Fallback: use notifications table
        try:
            await db.rollback()
            notification_id = str(uuid.uuid4())
            await db.execute(
                text(
                    "INSERT INTO notifications "
                    "(id, recipient_id, recipient_type, category, severity, "
                    "title, message, is_read, is_dismissed, created_at) "
                    "VALUES (:id, :recipient, 'founder', :cat, :sev, "
                    ":title, :msg, false, false, now())"
                ),
                {
                    "id": notification_id,
                    "recipient": "founder",
                    "cat": f"arch_{priority}",
                    "sev": priority,
                    "title": subject[:200],
                    "msg": body[:5000],
                },
            )
            await db.commit()
            logger.info(
                f"Founder notification sent via fallback: [{priority}] {subject[:50]}"
            )
            return {
                "sent": True,
                "notification_id": notification_id,
                "priority": priority,
                "fallback": True,
                "note": "Delivered via notifications table (fallback).",
            }
        except Exception as e2:
            logger.error(f"Founder notification fallback also failed: {e2}")
            return {"sent": False, "error": str(e2)}
