"""Task Dispatch Service — assigns tasks, tracks SLA, records lifecycle events."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.reputation.models import TaskDispatch, TaskRequest


class DispatchService:
    """Dispatches tasks to agents with SLA tracking."""

    async def dispatch(
        self,
        db: AsyncSession,
        task_id: str,
        agent_id: str,
        *,
        sla_hours: int | None = None,
    ) -> TaskDispatch:
        """Assign a task to an agent and start the SLA timer."""

        task = await db.get(TaskRequest, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        if task.status not in ("open", "allocated"):
            raise ValueError(f"Task {task_id} is in state '{task.status}', cannot dispatch")

        now = datetime.now(timezone.utc)
        sla_deadline = None
        if sla_hours:
            sla_deadline = now + timedelta(hours=sla_hours)
        elif task.deadline:
            sla_deadline = task.deadline

        dispatch = TaskDispatch(
            dispatch_id=str(uuid.uuid4()),
            task_id=task_id,
            agent_id=agent_id,
            dispatched_at=now,
            sla_deadline=sla_deadline,
            status="dispatched",
        )
        db.add(dispatch)

        task.status = "dispatched"
        task.updated_at = now

        return dispatch

    async def accept(self, db: AsyncSession, dispatch_id: str) -> TaskDispatch:
        """Agent accepts a dispatched task."""

        dispatch = await db.get(TaskDispatch, dispatch_id)
        if not dispatch:
            raise ValueError(f"Dispatch {dispatch_id} not found")
        if dispatch.status != "dispatched":
            raise ValueError(f"Dispatch is in state '{dispatch.status}', cannot accept")

        now = datetime.now(timezone.utc)
        dispatch.accepted_at = now
        dispatch.started_at = now
        dispatch.status = "accepted"

        # Calculate response time
        delta = now - dispatch.dispatched_at
        dispatch.response_time_seconds = int(delta.total_seconds())

        return dispatch

    async def reject(self, db: AsyncSession, dispatch_id: str) -> TaskDispatch:
        """Agent rejects a dispatched task."""

        dispatch = await db.get(TaskDispatch, dispatch_id)
        if not dispatch:
            raise ValueError(f"Dispatch {dispatch_id} not found")
        if dispatch.status != "dispatched":
            raise ValueError(f"Dispatch is in state '{dispatch.status}', cannot reject")

        dispatch.status = "rejected"

        # Reopen the task for re-allocation
        task = await db.get(TaskRequest, dispatch.task_id)
        if task:
            task.status = "open"
            task.updated_at = datetime.now(timezone.utc)

        return dispatch

    async def mark_delivered(
        self, db: AsyncSession, dispatch_id: str
    ) -> TaskDispatch:
        """Mark a dispatched task as delivered."""

        dispatch = await db.get(TaskDispatch, dispatch_id)
        if not dispatch:
            raise ValueError(f"Dispatch {dispatch_id} not found")
        if dispatch.status not in ("accepted", "in_progress"):
            raise ValueError(f"Dispatch is in state '{dispatch.status}', cannot deliver")

        now = datetime.now(timezone.utc)
        dispatch.delivered_at = now
        dispatch.status = "delivered"

        # Check SLA
        if dispatch.sla_deadline:
            dispatch.sla_met = now <= dispatch.sla_deadline

        # Update task status
        task = await db.get(TaskRequest, dispatch.task_id)
        if task:
            task.status = "completed"
            task.updated_at = now

        return dispatch

    async def check_timeouts(self, db: AsyncSession) -> list[TaskDispatch]:
        """Find dispatches that have exceeded their SLA deadline without delivery."""

        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(TaskDispatch).where(
                TaskDispatch.status.in_(["dispatched", "accepted", "in_progress"]),
                TaskDispatch.sla_deadline.isnot(None),
                TaskDispatch.sla_deadline < now,
            )
        )
        timed_out = result.scalars().all()

        for dispatch in timed_out:
            dispatch.status = "timeout"
            dispatch.sla_met = False

        return timed_out
