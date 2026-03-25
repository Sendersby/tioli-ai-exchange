"""Agentis Roadmap — service layer with audit logging on all mutations."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentis_roadmap.models import AgentisTask, AgentisSprint, AgentisVersion, AgentisRoadmapAudit

logger = logging.getLogger("tioli.roadmap")


class RoadmapService:
    """Manages the Agentis Roadmap with full audit trail."""

    # ── Audit ────────────────────────────────────────────────────────

    async def _audit(
        self, db: AsyncSession, actor: str, action: str,
        entity_type: str, entity_id: str,
        before: dict = None, after: dict = None, ip: str = "",
    ):
        db.add(AgentisRoadmapAudit(
            actor=actor, action=action, entity_type=entity_type,
            entity_id=entity_id, before_state=before or {},
            after_state=after or {}, ip_address=ip,
        ))

    # ── Tasks ────────────────────────────────────────────────────────

    async def list_tasks(
        self, db: AsyncSession,
        version: str = None, sprint: int = None, status: str = None,
        module: str = None, sort_by: str = "priority",
    ) -> list[dict]:
        query = select(AgentisTask)
        if version:
            query = query.where(AgentisTask.version_target == version)
        if sprint is not None:
            query = query.where(AgentisTask.sprint == sprint)
        if status:
            query = query.where(AgentisTask.status == status)
        if module:
            query = query.where(AgentisTask.module == module)

        sort_map = {
            "priority": AgentisTask.priority,
            "impact": AgentisTask.impact_score.desc(),
            "complexity": AgentisTask.complexity_score.desc(),
            "relevance": AgentisTask.relevance_score.desc(),
            "created": AgentisTask.created_at.desc(),
        }
        query = query.order_by(sort_map.get(sort_by, AgentisTask.priority))

        result = await db.execute(query)
        return [self._task_dict(t) for t in result.scalars().all()]

    async def get_task(self, db: AsyncSession, task_id: str) -> dict | None:
        result = await db.execute(select(AgentisTask).where(AgentisTask.task_id == task_id))
        t = result.scalar_one_or_none()
        return self._task_dict(t) if t else None

    async def create_task(
        self, db: AsyncSession, data: dict, actor: str = "owner", ip: str = "",
    ) -> dict:
        # Generate next task code
        max_code = await db.execute(
            select(func.max(AgentisTask.task_code))
        )
        last = max_code.scalar() or "AGT-000"
        next_num = int(last.split("-")[1]) + 1
        code = f"AGT-{next_num:03d}"

        task = AgentisTask(
            task_code=code,
            title=data["title"],
            description=data.get("description", ""),
            module=data.get("module", ""),
            version_target=data.get("version_target", "V1"),
            sprint=data.get("sprint"),
            priority=data.get("priority", 50),
            complexity_score=data.get("complexity_score"),
            impact_score=data.get("impact_score"),
            relevance_score=data.get("relevance_score"),
            owner_tag=data.get("owner_tag", ""),
            data_objects=data.get("data_objects", []),
            requires_approval=data.get("requires_approval", False),
            requires_3fa=data.get("requires_3fa", False),
            immutable_check=data.get("immutable_check", False),
            depends_on=data.get("depends_on", []),
            external_ref=data.get("external_ref", ""),
        )
        db.add(task)
        await db.flush()

        await self._audit(db, actor, "task_created", "task", task.task_id,
                          after=self._task_dict(task), ip=ip)
        return self._task_dict(task)

    async def update_task(
        self, db: AsyncSession, task_id: str, updates: dict,
        actor: str = "owner", ip: str = "",
    ) -> dict:
        result = await db.execute(select(AgentisTask).where(AgentisTask.task_id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError("Task not found")

        before = self._task_dict(task)

        for key in ["title", "description", "module", "version_target", "sprint",
                     "status", "priority", "complexity_score", "impact_score",
                     "relevance_score", "owner_tag", "data_objects", "requires_approval",
                     "requires_3fa", "immutable_check", "depends_on", "external_ref"]:
            if key in updates:
                setattr(task, key, updates[key])

        if updates.get("status") == "done" and not task.completed_at:
            task.completed_at = datetime.now(timezone.utc)

        task.updated_at = datetime.now(timezone.utc)
        await db.flush()

        await self._audit(db, actor, "task_updated", "task", task.task_id,
                          before=before, after=self._task_dict(task), ip=ip)
        return self._task_dict(task)

    async def cull_task(self, db: AsyncSession, task_id: str, reason: str = "",
                        actor: str = "owner", ip: str = "") -> dict:
        return await self.update_task(db, task_id, {"status": "culled"}, actor, ip)

    async def defer_task(self, db: AsyncSession, task_id: str, to_version: str = "V2",
                         actor: str = "owner", ip: str = "") -> dict:
        return await self.update_task(db, task_id, {"status": "deferred", "version_target": to_version}, actor, ip)

    # ── Sprints ──────────────────────────────────────────────────────

    async def list_sprints(self, db: AsyncSession) -> list[dict]:
        result = await db.execute(
            select(AgentisSprint).order_by(AgentisSprint.sprint_number)
        )
        sprints = []
        for s in result.scalars().all():
            d = self._sprint_dict(s)
            # Compute task counts
            total = (await db.execute(
                select(func.count(AgentisTask.task_id)).where(AgentisTask.sprint == s.sprint_number)
            )).scalar() or 0
            done = (await db.execute(
                select(func.count(AgentisTask.task_id)).where(
                    AgentisTask.sprint == s.sprint_number, AgentisTask.status == "done"
                )
            )).scalar() or 0
            d["total_tasks"] = total
            d["done_tasks"] = done
            d["progress_pct"] = round(done / max(total, 1) * 100, 1)
            sprints.append(d)
        return sprints

    async def create_sprint(self, db: AsyncSession, data: dict,
                            actor: str = "owner", ip: str = "") -> dict:
        sprint = AgentisSprint(**{k: v for k, v in data.items() if hasattr(AgentisSprint, k)})
        db.add(sprint)
        await db.flush()
        await self._audit(db, actor, "sprint_created", "sprint", sprint.sprint_id, ip=ip)
        return self._sprint_dict(sprint)

    async def update_sprint(self, db: AsyncSession, sprint_id: str, updates: dict,
                            actor: str = "owner", ip: str = "") -> dict:
        result = await db.execute(select(AgentisSprint).where(AgentisSprint.sprint_id == sprint_id))
        sprint = result.scalar_one_or_none()
        if not sprint:
            raise ValueError("Sprint not found")
        before = self._sprint_dict(sprint)
        for key in ["label", "version_focus", "start_date", "end_date", "status", "goals", "notes", "velocity_pts"]:
            if key in updates:
                setattr(sprint, key, updates[key])
        sprint.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await self._audit(db, actor, "sprint_updated", "sprint", sprint.sprint_id,
                          before=before, after=self._sprint_dict(sprint), ip=ip)
        return self._sprint_dict(sprint)

    # ── Versions ─────────────────────────────────────────────────────

    async def list_versions(self, db: AsyncSession) -> list[dict]:
        result = await db.execute(select(AgentisVersion).order_by(AgentisVersion.created_at))
        return [self._version_dict(v) for v in result.scalars().all()]

    async def create_version(self, db: AsyncSession, data: dict,
                             actor: str = "owner", ip: str = "") -> dict:
        version = AgentisVersion(**{k: v for k, v in data.items() if hasattr(AgentisVersion, k)})
        db.add(version)
        await db.flush()
        await self._audit(db, actor, "version_created", "version", version.version_id, ip=ip)
        return self._version_dict(version)

    async def sign_off_version(self, db: AsyncSession, version_id: str,
                               actor: str = "owner", ip: str = "") -> dict:
        result = await db.execute(select(AgentisVersion).where(AgentisVersion.version_id == version_id))
        version = result.scalar_one_or_none()
        if not version:
            raise ValueError("Version not found")
        version.owner_sign_off = True
        version.sign_off_at = datetime.now(timezone.utc)
        await db.flush()
        await self._audit(db, actor, "version_signed_off", "version", version.version_id, ip=ip)
        return self._version_dict(version)

    # ── Dashboard ────────────────────────────────────────────────────

    async def get_dashboard(self, db: AsyncSession) -> dict:
        v1_total = (await db.execute(
            select(func.count(AgentisTask.task_id)).where(AgentisTask.version_target == "V1")
        )).scalar() or 0
        v1_done = (await db.execute(
            select(func.count(AgentisTask.task_id)).where(
                AgentisTask.version_target == "V1", AgentisTask.status == "done"
            )
        )).scalar() or 0
        deferred = (await db.execute(
            select(func.count(AgentisTask.task_id)).where(AgentisTask.status == "deferred")
        )).scalar() or 0
        culled = (await db.execute(
            select(func.count(AgentisTask.task_id)).where(AgentisTask.status == "culled")
        )).scalar() or 0
        avg_impact = (await db.execute(
            select(func.avg(AgentisTask.impact_score)).where(
                AgentisTask.version_target == "V1", AgentisTask.status != "culled"
            )
        )).scalar() or 0

        # Active sprint
        active_sprint = (await db.execute(
            select(AgentisSprint).where(AgentisSprint.status == "active")
        )).scalar_one_or_none()

        return {
            "v1_total": v1_total,
            "v1_done": v1_done,
            "v1_progress_pct": round(v1_done / max(v1_total, 1) * 100, 1),
            "active_sprint": self._sprint_dict(active_sprint) if active_sprint else None,
            "deferred": deferred,
            "culled": culled,
            "avg_impact_score": round(avg_impact, 1),
        }

    # ── Audit Trail ──────────────────────────────────────────────────

    async def get_audit(self, db: AsyncSession, limit: int = 50, offset: int = 0) -> list[dict]:
        result = await db.execute(
            select(AgentisRoadmapAudit)
            .order_by(AgentisRoadmapAudit.created_at.desc())
            .limit(limit).offset(offset)
        )
        return [
            {
                "audit_id": a.audit_id, "actor": a.actor, "action": a.action,
                "entity_type": a.entity_type, "entity_id": a.entity_id,
                "before_state": a.before_state, "after_state": a.after_state,
                "ip": a.ip_address, "created_at": str(a.created_at),
            }
            for a in result.scalars().all()
        ]

    # ── Seed ─────────────────────────────────────────────────────────

    async def seed_if_empty(self, db: AsyncSession):
        """Seed tasks, sprints, versions if tables are empty."""
        count = (await db.execute(select(func.count(AgentisTask.task_id)))).scalar() or 0
        if count > 0:
            return  # Already seeded

        from app.agentis_roadmap.seed import SEED_TASKS, SEED_SPRINTS, SEED_VERSIONS

        for v in SEED_VERSIONS:
            db.add(AgentisVersion(**v))

        for s in SEED_SPRINTS:
            db.add(AgentisSprint(**s))

        for t in SEED_TASKS:
            db.add(AgentisTask(**{k: v for k, v in t.items() if hasattr(AgentisTask, k)}))

        await db.flush()
        logger.info(f"Roadmap seeded: {len(SEED_TASKS)} tasks, {len(SEED_SPRINTS)} sprints, {len(SEED_VERSIONS)} versions")

    # ── Helpers ───────────────────────────────────────────────────────

    def _task_dict(self, t: AgentisTask) -> dict:
        return {
            "task_id": t.task_id, "task_code": t.task_code, "title": t.title,
            "description": t.description, "module": t.module,
            "version_target": t.version_target, "sprint": t.sprint,
            "status": t.status, "priority": t.priority,
            "complexity_score": t.complexity_score, "impact_score": t.impact_score,
            "relevance_score": t.relevance_score, "owner_tag": t.owner_tag,
            "data_objects": t.data_objects, "requires_approval": t.requires_approval,
            "requires_3fa": t.requires_3fa, "immutable_check": t.immutable_check,
            "depends_on": t.depends_on, "external_ref": t.external_ref,
            "created_at": str(t.created_at), "updated_at": str(t.updated_at),
            "completed_at": str(t.completed_at) if t.completed_at else None,
        }

    def _sprint_dict(self, s: AgentisSprint) -> dict:
        return {
            "sprint_id": s.sprint_id, "sprint_number": s.sprint_number,
            "label": s.label, "version_focus": s.version_focus,
            "start_date": s.start_date, "end_date": s.end_date,
            "status": s.status, "goals": s.goals,
            "total_tasks": s.total_tasks, "done_tasks": s.done_tasks,
            "velocity_pts": s.velocity_pts, "notes": s.notes,
        }

    def _version_dict(self, v: AgentisVersion) -> dict:
        return {
            "version_id": v.version_id, "version_tag": v.version_tag,
            "version_label": v.version_label, "release_date": v.release_date,
            "status": v.status, "changelog": v.changelog,
            "breaking_changes": v.breaking_changes,
            "owner_sign_off": v.owner_sign_off,
            "sign_off_at": str(v.sign_off_at) if v.sign_off_at else None,
        }
