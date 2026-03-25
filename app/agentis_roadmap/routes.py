"""Agentis Roadmap API — 12 endpoints under /api/v1/agentis-roadmap/."""

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.db import get_db
from app.dashboard.routes import get_current_owner
from app.agentis_roadmap.service import RoadmapService

router = APIRouter(prefix="/api/v1/agentis-roadmap", tags=["Agentis Roadmap"])
roadmap = RoadmapService()


def _check_enabled():
    if not getattr(settings, 'agentis_roadmap_enabled', False):
        raise HTTPException(status_code=404, detail="Agentis Roadmap is not enabled")


def _require_owner(request: Request):
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return owner


# ── Request Models ────────────────────────────────────────────────────

class TaskCreateRequest(BaseModel):
    title: str
    description: str = ""
    module: str = ""
    version_target: str = "V1"
    sprint: int | None = None
    priority: int = 50
    complexity_score: int | None = None
    impact_score: int | None = None
    relevance_score: int | None = None
    owner_tag: str = ""
    data_objects: list[str] = []
    requires_approval: bool = False
    requires_3fa: bool = False
    immutable_check: bool = False
    depends_on: list[str] = []
    external_ref: str = ""

class TaskUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    module: str | None = None
    version_target: str | None = None
    sprint: int | None = None
    status: str | None = None
    priority: int | None = None
    complexity_score: int | None = None
    impact_score: int | None = None
    relevance_score: int | None = None
    owner_tag: str | None = None

class SprintCreateRequest(BaseModel):
    sprint_number: int
    label: str = ""
    version_focus: str = "V1"
    start_date: str | None = None
    end_date: str | None = None
    goals: list[str] = []

class VersionCreateRequest(BaseModel):
    version_tag: str
    version_label: str = ""
    status: str = "planned"


# ── Task Endpoints ────────────────────────────────────────────────────

@router.get("/tasks")
async def api_list_tasks(
    version: str | None = None, sprint: int | None = None,
    status: str | None = None, module: str | None = None,
    sort_by: str = "priority",
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    return await roadmap.list_tasks(db, version, sprint, status, module, sort_by)


@router.post("/tasks")
async def api_create_task(
    req: TaskCreateRequest, request: Request,
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    _require_owner(request)
    ip = request.headers.get("X-Real-IP", "")
    result = await roadmap.create_task(db, req.model_dump(), "owner", ip)
    await db.commit()
    return result


@router.patch("/tasks/{task_id}")
async def api_update_task(
    task_id: str, req: TaskUpdateRequest, request: Request,
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    _require_owner(request)
    ip = request.headers.get("X-Real-IP", "")
    try:
        result = await roadmap.update_task(db, task_id, req.model_dump(exclude_none=True), "owner", ip)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/tasks/{task_id}")
async def api_cull_task(task_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Soft-delete: sets status='culled'. No physical delete."""
    _check_enabled()
    _require_owner(request)
    ip = request.headers.get("X-Real-IP", "")
    try:
        result = await roadmap.cull_task(db, task_id, ip=ip)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/tasks/{task_id}/dependencies")
async def api_task_dependencies(task_id: str, db: AsyncSession = Depends(get_db)):
    _check_enabled()
    task = await roadmap.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    deps = []
    for dep_id in (task.get("depends_on") or []):
        dep = await roadmap.get_task(db, dep_id)
        if dep:
            deps.append(dep)
    return {"task": task, "dependencies": deps}


# ── Sprint Endpoints ──────────────────────────────────────────────────

@router.get("/sprints")
async def api_list_sprints(db: AsyncSession = Depends(get_db)):
    _check_enabled()
    return await roadmap.list_sprints(db)


@router.post("/sprints")
async def api_create_sprint(
    req: SprintCreateRequest, request: Request,
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    _require_owner(request)
    ip = request.headers.get("X-Real-IP", "")
    result = await roadmap.create_sprint(db, req.model_dump(), "owner", ip)
    await db.commit()
    return result


@router.patch("/sprints/{sprint_id}")
async def api_update_sprint(
    sprint_id: str, request: Request,
    status: str | None = None, notes: str | None = None,
    velocity_pts: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    _require_owner(request)
    updates = {}
    if status:
        updates["status"] = status
    if notes:
        updates["notes"] = notes
    if velocity_pts is not None:
        updates["velocity_pts"] = velocity_pts
    ip = request.headers.get("X-Real-IP", "")
    try:
        result = await roadmap.update_sprint(db, sprint_id, updates, "owner", ip)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/sprints/{sprint_id}/tasks")
async def api_sprint_tasks(sprint_id: str, db: AsyncSession = Depends(get_db)):
    _check_enabled()
    from app.agentis_roadmap.models import AgentisSprint
    from sqlalchemy import select
    result = await db.execute(select(AgentisSprint).where(AgentisSprint.sprint_id == sprint_id))
    sprint = result.scalar_one_or_none()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return await roadmap.list_tasks(db, sprint=sprint.sprint_number)


# ── Version Endpoints ─────────────────────────────────────────────────

@router.get("/versions")
async def api_list_versions(db: AsyncSession = Depends(get_db)):
    _check_enabled()
    return await roadmap.list_versions(db)


@router.post("/versions")
async def api_create_version(
    req: VersionCreateRequest, request: Request,
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    _require_owner(request)
    # 3FA required for version creation
    ip = request.headers.get("X-Real-IP", "")
    result = await roadmap.create_version(db, req.model_dump(), "owner", ip)
    await db.commit()
    return result


@router.patch("/versions/{version_id}/sign-off")
async def api_sign_off_version(
    version_id: str, request: Request,
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    _require_owner(request)
    # 3FA required for sign-off
    ip = request.headers.get("X-Real-IP", "")
    try:
        result = await roadmap.sign_off_version(db, version_id, "owner", ip)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Dashboard & Audit ─────────────────────────────────────────────────

@router.get("/dashboard")
async def api_dashboard(db: AsyncSession = Depends(get_db)):
    _check_enabled()
    return await roadmap.get_dashboard(db)


@router.get("/audit")
async def api_audit(
    request: Request, limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    _require_owner(request)
    return await roadmap.get_audit(db, limit, offset)
