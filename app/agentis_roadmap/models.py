"""Agentis Roadmap — database models.

4 tables per the Build Brief v1.0:
- agentis_tasks: version-controlled development tasks with scoring
- agentis_sprints: sprint planning with velocity tracking
- agentis_versions: version milestones with owner sign-off
- agentis_roadmap_audit: immutable audit log for all mutations
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, Index
from app.database.db import Base

_uuid = lambda: str(uuid.uuid4())
_now = lambda: datetime.now(timezone.utc)


class AgentisTask(Base):
    """A versioned roadmap task with scoring and dependency tracking."""
    __tablename__ = "agentis_tasks"
    __table_args__ = (
        Index("ix_agentis_task_version", "version_target"),
        Index("ix_agentis_task_sprint", "sprint"),
        Index("ix_agentis_task_status", "status"),
    )

    task_id = Column(String, primary_key=True, default=_uuid)
    task_code = Column(String(20), unique=True, nullable=False)  # AGT-001
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    module = Column(String(100), default="")  # Offer Registry, Approval Layer, etc.
    version_target = Column(String(10), nullable=False)  # V1, V2, V3, WATCH
    sprint = Column(Integer, nullable=True)  # sprint number
    status = Column(String(30), default="backlog")  # backlog, in-progress, review, done, deferred, culled
    priority = Column(Integer, nullable=False, default=50)  # 1=highest, 100=lowest
    complexity_score = Column(Integer, nullable=True)  # 1-10
    impact_score = Column(Integer, nullable=True)  # 1-10
    relevance_score = Column(Integer, nullable=True)  # 1-10
    owner_tag = Column(String(100), default="")  # Claude Code, Stephen, External
    data_objects = Column(JSON, default=list)  # e.g. ['service_offer', 'pathway_state']
    requires_approval = Column(Boolean, default=False)
    requires_3fa = Column(Boolean, default=False)
    immutable_check = Column(Boolean, default=False)  # touches protected infrastructure
    depends_on = Column(JSON, default=list)  # array of task_ids
    external_ref = Column(String(255), default="")  # e.g. 'Build Brief v2.0 §3.1'
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class AgentisSprint(Base):
    """A sprint with velocity tracking and goal alignment."""
    __tablename__ = "agentis_sprints"

    sprint_id = Column(String, primary_key=True, default=_uuid)
    sprint_number = Column(Integer, unique=True, nullable=False)
    label = Column(String(100), default="")
    version_focus = Column(String(10), default="V1")
    start_date = Column(String(10), nullable=True)  # YYYY-MM-DD
    end_date = Column(String(10), nullable=True)
    status = Column(String(20), default="planned")  # planned, active, complete, skipped
    goals = Column(JSON, default=list)
    total_tasks = Column(Integer, default=0)
    done_tasks = Column(Integer, default=0)
    velocity_pts = Column(Integer, nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now)


class AgentisVersion(Base):
    """A version milestone with owner sign-off requirement."""
    __tablename__ = "agentis_versions"

    version_id = Column(String, primary_key=True, default=_uuid)
    version_tag = Column(String(20), unique=True, nullable=False)  # v1.0.0
    version_label = Column(String(100), default="")
    release_date = Column(String(10), nullable=True)
    status = Column(String(20), default="planned")  # planned, in-progress, rc, released, deprecated
    changelog = Column(Text, default="")
    breaking_changes = Column(Boolean, default=False)
    owner_sign_off = Column(Boolean, default=False)
    sign_off_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class AgentisRoadmapAudit(Base):
    """Immutable audit log for all roadmap mutations. No deletes or updates permitted."""
    __tablename__ = "agentis_roadmap_audit"

    audit_id = Column(String, primary_key=True, default=_uuid)
    actor = Column(String(100), nullable=False)
    action = Column(String(100), nullable=False)  # task_status_change, sprint_created, etc.
    entity_type = Column(String(50), default="")  # task, sprint, version
    entity_id = Column(String, default="")
    before_state = Column(JSON, default=dict)
    after_state = Column(JSON, default=dict)
    ip_address = Column(String(45), default="")
    created_at = Column(DateTime(timezone=True), default=_now)
