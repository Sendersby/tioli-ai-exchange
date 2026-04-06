"""Autonomous Task Queue — agents schedule and execute work 24/7.

Runs on the server independent of the founder's PC or Claude Code sessions.
Agents create tasks, the queue processes them autonomously.

Task types:
- IMMEDIATE: execute now
- SCHEDULED: execute at a specific time
- RECURRING: execute on a cron schedule
- QUEUED_FOR_CLAUDE: requires Claude Code session (batched for next session)
- QUEUED_FOR_FOUNDER: requires founder approval before execution
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta

from sqlalchemy import text

log = logging.getLogger("arch.task_queue")


TASK_QUEUE_DDL = """
CREATE TABLE IF NOT EXISTS arch_task_queue (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        VARCHAR(50) NOT NULL,
    task_type       VARCHAR(30) NOT NULL
                    CHECK (task_type IN ('IMMEDIATE','SCHEDULED','RECURRING',
                                         'QUEUED_FOR_CLAUDE','QUEUED_FOR_FOUNDER')),
    priority        INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    action_type     VARCHAR(50) NOT NULL,
    action_params   JSONB NOT NULL DEFAULT '{}',
    schedule_at     TIMESTAMPTZ,
    cron_expression VARCHAR(50),
    status          VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING','RUNNING','COMPLETED','FAILED',
                                      'WAITING_APPROVAL','CANCELLED','DEFERRED')),
    result          JSONB,
    error           TEXT,
    attempts        INTEGER NOT NULL DEFAULT 0,
    max_attempts    INTEGER NOT NULL DEFAULT 3,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    depends_on      UUID REFERENCES arch_task_queue(id)
);
CREATE INDEX IF NOT EXISTS idx_task_queue_status ON arch_task_queue(status, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_task_queue_agent ON arch_task_queue(agent_id, status);
CREATE INDEX IF NOT EXISTS idx_task_queue_schedule ON arch_task_queue(schedule_at)
    WHERE status = 'PENDING' AND task_type = 'SCHEDULED';
"""


async def create_task_queue_table(db):
    """Create the task queue table if it doesn't exist."""
    await db.execute(text(TASK_QUEUE_DDL))
    await db.commit()


async def enqueue_task(
    db, agent_id: str, title: str, action_type: str,
    action_params: dict, task_type: str = "IMMEDIATE",
    priority: int = 5, schedule_at: datetime = None,
    cron_expression: str = None, description: str = None,
) -> str:
    """Add a task to the queue. Returns task ID."""
    result = await db.execute(text(
        "INSERT INTO arch_task_queue "
        "(agent_id, task_type, priority, title, description, action_type, "
        " action_params, schedule_at, cron_expression, status) "
        "VALUES (:agent, :type, :priority, :title, :desc, :action_type, "
        " :params, :schedule, :cron, "
        " CASE WHEN :type = 'QUEUED_FOR_FOUNDER' THEN 'WAITING_APPROVAL' ELSE 'PENDING' END) "
        "RETURNING id::text"
    ), {
        "agent": agent_id, "type": task_type, "priority": priority,
        "title": title, "desc": description, "action_type": action_type,
        "params": json.dumps(action_params),
        "schedule": schedule_at, "cron": cron_expression,
    })
    task_id = result.scalar()
    await db.commit()
    log.info(f"[task_queue] Task enqueued: {task_id} ({agent_id}: {title})")
    return task_id


async def process_queue(db_factory, agents: dict):
    """Process all pending tasks in priority order. Runs continuously on the server."""
    from app.arch.executor import ArchExecutor

    async with db_factory() as db:
        # Get pending immediate tasks and scheduled tasks whose time has come
        rows = await db.execute(text("""
            SELECT id, agent_id, action_type, action_params, title, attempts, max_attempts
            FROM arch_task_queue
            WHERE status = 'PENDING'
              AND (task_type = 'IMMEDIATE'
                   OR (task_type = 'SCHEDULED' AND schedule_at <= now()))
              AND (depends_on IS NULL
                   OR depends_on IN (SELECT id FROM arch_task_queue WHERE status = 'COMPLETED'))
            ORDER BY priority ASC, created_at ASC
            LIMIT 10
        """))
        tasks = rows.fetchall()

        for task in tasks:
            task_id = str(task.id)
            agent_id = task.agent_id

            # Mark as running
            await db.execute(text(
                "UPDATE arch_task_queue SET status = 'RUNNING', started_at = now(), "
                "attempts = attempts + 1 WHERE id = cast(:tid as uuid)"
            ), {"tid": task_id})
            await db.commit()

            log.info(f"[task_queue] Executing: {task.title} ({agent_id})")

            try:
                executor = ArchExecutor(agent_id=agent_id, db_factory=db_factory)
                params = json.loads(task.action_params) if isinstance(task.action_params, str) else task.action_params

                # Route to the appropriate executor method
                handler_map = {
                    "run_command": lambda p: executor.run_command(p.get("command", "")),
                    "write_file": lambda p: executor.write_file(p["path"], p["content"]),
                    "browse_url": lambda p: executor.browse_url(p["url"]),
                    "post_content": lambda p: executor.post_content(p["platform"], p["content"], p.get("title")),
                    "generate_content": lambda p: executor.generate_content(p["prompt"], p.get("voice")),
                    "research_competitor": lambda p: executor.research_competitor(p["url"]),
                    "http_request": lambda p: executor.http_request(p["method"], p["url"], p.get("headers"), p.get("body")),
                    "task_plan": lambda p: executor.execute_task_plan(p.get("tasks", [])),
                }

                handler = handler_map.get(task.action_type)
                if handler:
                    result = await handler(params)
                    await db.execute(text(
                        "UPDATE arch_task_queue SET status = 'COMPLETED', "
                        "completed_at = now(), result = :result WHERE id = cast(:tid as uuid)"
                    ), {"tid": task_id, "result": json.dumps(result, default=str)})
                else:
                    await db.execute(text(
                        "UPDATE arch_task_queue SET status = 'FAILED', "
                        "error = :err WHERE id = cast(:tid as uuid)"
                    ), {"tid": task_id, "err": f"Unknown action type: {task.action_type}"})

                await db.commit()

            except Exception as e:
                error_msg = str(e)[:500]
                new_status = "FAILED" if task.attempts >= task.max_attempts else "PENDING"
                await db.execute(text(
                    "UPDATE arch_task_queue SET status = :status, error = :err "
                    "WHERE id = cast(:tid as uuid)"
                ), {"tid": task_id, "status": new_status, "err": error_msg})
                await db.commit()
                log.error(f"[task_queue] Task failed: {task.title} — {error_msg}")


async def run_task_queue_loop(db_factory, agents: dict):
    """Continuous loop that processes the task queue every 30 seconds.
    Runs as a background asyncio task on the server — works 24/7.
    """
    log.info("[task_queue] Autonomous task queue started — processing every 30s")
    while True:
        try:
            await process_queue(db_factory, agents)
        except Exception as e:
            log.error(f"[task_queue] Queue processing error: {e}")
        await asyncio.sleep(30)


# ── Tool definitions for agents to enqueue their own tasks ──

TASK_QUEUE_TOOLS = [
    {
        "name": "schedule_task",
        "description": "Schedule a task for autonomous execution. The task will run on the server even when the founder's PC is off. Use for: scheduling social media posts, recurring checks, batched work.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short task title"},
                "description": {"type": "string"},
                "action_type": {"type": "string", "enum": [
                    "run_command", "write_file", "browse_url", "post_content",
                    "generate_content", "research_competitor", "http_request", "task_plan",
                ]},
                "action_params": {"type": "object", "description": "Parameters for the action"},
                "task_type": {"type": "string", "enum": [
                    "IMMEDIATE", "SCHEDULED", "QUEUED_FOR_FOUNDER",
                ], "default": "IMMEDIATE"},
                "priority": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5,
                             "description": "1=highest priority, 10=lowest"},
                "schedule_at": {"type": "string", "format": "date-time",
                                "description": "ISO datetime for scheduled tasks"},
            },
            "required": ["title", "action_type", "action_params"],
        },
    },
    {
        "name": "list_my_tasks",
        "description": "List your pending, running, and recently completed tasks from the queue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status_filter": {"type": "string", "enum": ["all", "PENDING", "RUNNING", "COMPLETED", "FAILED"]},
            },
            "required": [],
        },
    },
]


# ── Agent Self-Scheduling Helper ──────────────────────────────────
async def agent_create_scheduled_task(db, agent_name: str, title: str, description: str,
                                       action_type: str, action_params: dict,
                                       schedule_at=None, cron_expression=None,
                                       priority: int = 5):
    """Allow an agent to create its own scheduled or recurring task.

    Usage by agents:
        - schedule_at: ISO datetime string for one-time execution
        - cron_expression: cron string for recurring execution (e.g., "0 */2 * * *")
        - If neither provided, executes immediately
    """
    task_type = "IMMEDIATE"
    if cron_expression:
        task_type = "RECURRING"
    elif schedule_at:
        task_type = "SCHEDULED"

    result = await db.execute(text("""
        INSERT INTO arch_task_queue (agent_id, task_type, priority, title, description,
                                     action_type, action_params, cron_expression, schedule_at,
                                     status, created_at)
        SELECT id, :task_type, :priority, :title, :desc,
               :action_type, :params, :cron, :schedule_at, 'PENDING', now()
        FROM arch_agents WHERE agent_name = :name
        RETURNING id::text
    """), {
        "task_type": task_type,
        "priority": priority,
        "title": title,
        "desc": description,
        "action_type": action_type,
        "params": json.dumps(action_params),
        "cron": cron_expression,
        "schedule_at": schedule_at,
        "name": agent_name,
    })
    row = result.fetchone()
    await db.commit()
    task_id = row.id if row else "unknown"
    logger.info(f"[{agent_name}] Self-scheduled task: {title} (type={task_type}, id={task_id})")
    return {"task_id": task_id, "task_type": task_type, "title": title}


# ── Aiocron Integration — async-native scheduling for recurring tasks ──
_active_crons = {}  # task_id -> aiocron handle

async def start_aiocron_task(task_id: str, cron_expr: str, callback):
    """Start an aiocron-based recurring task. Native asyncio, no thread pool."""
    try:
        import aiocron
        cron = aiocron.crontab(cron_expr, func=callback, start=True)
        _active_crons[task_id] = cron
        logger.info(f"[aiocron] Started recurring task {task_id}: {cron_expr}")
        return {"task_id": task_id, "cron": cron_expr, "status": "running"}
    except ImportError:
        logger.warning("[aiocron] aiocron not installed, falling back to APScheduler")
        return {"task_id": task_id, "error": "aiocron not available"}
    except Exception as e:
        logger.error(f"[aiocron] Failed to start {task_id}: {e}")
        return {"task_id": task_id, "error": str(e)}


def stop_aiocron_task(task_id: str) -> dict:
    """Stop an aiocron recurring task."""
    cron = _active_crons.pop(task_id, None)
    if cron:
        cron.stop()
        logger.info(f"[aiocron] Stopped task {task_id}")
        return {"task_id": task_id, "status": "stopped"}
    return {"task_id": task_id, "error": "not found"}


def list_aiocron_tasks() -> list:
    """List all active aiocron tasks."""
    return [{"task_id": tid, "running": c.is_running if hasattr(c, "is_running") else True}
            for tid, c in _active_crons.items()]
