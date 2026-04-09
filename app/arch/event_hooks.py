"""H-011: Event Hook System (Hermes-inspired).
Pre/post hooks on tool execution, messages, goals.
Feature flag: ARCH_H_EVENT_HOOKS_ENABLED"""
import os
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.event_hooks")

# In-memory hook registry (loaded from DB)
_hooks = {}


async def load_hooks(db):
    """Load active hooks from database."""
    global _hooks
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT hook_id, event_type, action, config FROM arch_event_hooks WHERE is_active = true"
    ))
    for row in r.fetchall():
        event = row.event_type
        if event not in _hooks:
            _hooks[event] = []
        _hooks[event].append({
            "hook_id": str(row.hook_id),
            "action": row.action,
            "config": json.loads(row.config) if isinstance(row.config, str) else (row.config or {}),
        })
    log.info(f"[hooks] Loaded {sum(len(v) for v in _hooks.values())} hooks for {len(_hooks)} event types")


async def trigger_event(db, event_type: str, event_data: dict) -> list[dict]:
    """Trigger all hooks for an event type."""
    if os.environ.get("ARCH_H_EVENT_HOOKS_ENABLED", "false").lower() != "true":
        return []

    # Auto-load hooks if not yet loaded
    if not _hooks:
        await load_hooks(db)
    hooks = _hooks.get(event_type, [])
    results = []

    from sqlalchemy import text
    for hook in hooks:
        try:
            action = hook["action"]
            config = hook["config"]

            if action == "log":
                level = config.get("log_level", "info")
                getattr(log, level, log.info)(f"[hook] {event_type}: {json.dumps(event_data)[:200]}")
                results.append({"hook_id": hook["hook_id"], "action": "log", "status": "executed"})

            elif action == "alert":
                priority = config.get("priority", "routine")
                target = config.get("target", "founder_inbox")
                if target == "founder_inbox":
                    await db.execute(text(
                        "INSERT INTO arch_founder_inbox (item_type, priority, description, status, due_at) "
                        "VALUES ('INFORMATION', :pri, :desc, 'PENDING', now() + interval '24 hours')"
                    ), {"pri": priority.upper(),
                        "desc": json.dumps({"subject": f"Event: {event_type}", "situation": json.dumps(event_data)[:1500]})})
                    await db.commit()
                results.append({"hook_id": hook["hook_id"], "action": "alert", "status": "executed"})

            elif action == "webhook":
                # Future: HTTP POST to configured URL
                results.append({"hook_id": hook["hook_id"], "action": "webhook", "status": "skipped"})

            elif action == "block":
                results.append({"hook_id": hook["hook_id"], "action": "block", "status": "blocked"})
                return results  # Stop processing

            # Update execution count
            await db.execute(text(
                "UPDATE arch_event_hooks SET executions = executions + 1, last_triggered = now() "
                "WHERE hook_id = cast(:hid as uuid)"
            ), {"hid": hook["hook_id"]})
            await db.commit()

        except Exception as e:
            log.warning(f"[hooks] Hook {hook['hook_id']} failed: {e}")
            results.append({"hook_id": hook["hook_id"], "action": hook["action"], "status": "error", "error": str(e)})

    return results


async def list_hooks(db) -> list[dict]:
    """List all configured hooks."""
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT hook_id, event_type, action, config, is_active, executions, last_triggered "
        "FROM arch_event_hooks ORDER BY event_type"
    ))
    return [{"hook_id": str(row.hook_id), "event_type": row.event_type,
             "action": row.action, "config": row.config,
             "active": row.is_active, "executions": row.executions,
             "last_triggered": str(row.last_triggered) if row.last_triggered else None}
            for row in r.fetchall()]
