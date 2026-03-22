"""Revenue Engine API routes — dashboard, auto-match, quick tasks, retention."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db
from app.agents.models import Agent
from app.auth.agent_auth import authenticate_agent
from app.revenue.service import RevenueEngineService
from fastapi import Header

router = APIRouter(prefix="/api/v1/revenue", tags=["Revenue Engine"])
revenue_service = RevenueEngineService()


async def require_agent_auth(
    authorization: str = Header(...), db: AsyncSession = Depends(get_db),
) -> Agent:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    agent = await authenticate_agent(db, authorization[7:])
    if not agent:
        raise HTTPException(status_code=401)
    return agent


# ── Revenue Dashboard (Owner) ────────────────────────────────────────

@router.get("/dashboard")
async def api_revenue_dashboard(db: AsyncSession = Depends(get_db)):
    """Revenue Intelligence Dashboard — all 6 panels."""
    return await revenue_service.get_revenue_dashboard(db)


@router.get("/daily-report")
async def api_daily_report(db: AsyncSession = Depends(get_db)):
    """Daily revenue pulse report."""
    return await revenue_service.get_daily_revenue_report(db)


@router.get("/at-risk")
async def api_at_risk(db: AsyncSession = Depends(get_db)):
    """Subscribers at risk of churning."""
    return await revenue_service.get_at_risk_subscribers(db)


@router.post("/retention/compute")
async def api_compute_retention(db: AsyncSession = Depends(get_db)):
    """Recompute retention scores."""
    return await revenue_service.compute_retention_scores(db)


# ── Auto-Match ────────────────────────────────────────────────────────

class AutoMatchRequest(BaseModel):
    task_description: str


@router.post("/auto-match")
async def api_auto_match(
    req: AutoMatchRequest, db: AsyncSession = Depends(get_db),
):
    """Auto-match: describe a task → get top 3 agent suggestions."""
    return await revenue_service.auto_match(db, "owner", req.task_description)


# ── Quick Tasks ───────────────────────────────────────────────────────

class CreateQuickTaskRequest(BaseModel):
    title: str
    price: float
    description: str = ""
    client_agent_id: str | None = None
    gig_package_id: str | None = None
    tier_selected: str = "basic"

class DeliverQuickTaskRequest(BaseModel):
    deliverable_ref: str = ""


@router.post("/quick-tasks")
async def api_create_quick_task(
    req: CreateQuickTaskRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Create a Quick Task (3-state micro-engagement)."""
    return await revenue_service.create_quick_task(
        db, agent.id, req.title, req.price, req.description,
        req.client_agent_id, gig_package_id=req.gig_package_id,
        tier_selected=req.tier_selected,
    )


@router.post("/quick-tasks/{task_id}/deliver")
async def api_deliver_quick_task(
    task_id: str, req: DeliverQuickTaskRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Mark a Quick Task as delivered."""
    return await revenue_service.deliver_quick_task(db, task_id, req.deliverable_ref)


@router.post("/quick-tasks/{task_id}/confirm")
async def api_confirm_quick_task(
    task_id: str, db: AsyncSession = Depends(get_db),
):
    """Confirm Quick Task delivery — captures commission."""
    return await revenue_service.confirm_quick_task(db, task_id)


@router.get("/quick-tasks")
async def api_list_quick_tasks(
    status: str | None = None, limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List Quick Tasks."""
    return await revenue_service.list_quick_tasks(db, status, limit=limit)


# ── Record Revenue (Internal) ────────────────────────────────────────

class RecordRevenueRequest(BaseModel):
    stream: str
    source_type: str
    gross_zar: float
    description: str = ""
    source_id: str | None = None
    agent_id: str | None = None
    operator_id: str | None = None


@router.post("/record")
async def api_record_revenue(
    req: RecordRevenueRequest, db: AsyncSession = Depends(get_db),
):
    """Manually record a revenue transaction."""
    return await revenue_service.record_revenue(
        db, req.stream, req.source_type, req.gross_zar, req.description,
        req.source_id, req.agent_id, req.operator_id,
    )


# ── Margin Protection ────────────────────────────────────────────────

@router.get("/margins")
async def api_margins():
    """Get margin analysis for all products — owner only."""
    from app.revenue.margin_protection import get_all_margins
    return get_all_margins()


@router.get("/margins/summary")
async def api_margin_summary():
    """Get margin protection summary."""
    from app.revenue.margin_protection import get_margin_summary
    return get_margin_summary()


class ValidatePriceRequest(BaseModel):
    product_name: str
    proposed_price_zar: float
    estimated_cost_zar: float


@router.post("/margins/validate")
async def api_validate_price(req: ValidatePriceRequest):
    """Validate a proposed price against the margin protection rule."""
    from app.revenue.margin_protection import validate_new_price
    return validate_new_price(req.product_name, req.proposed_price_zar, req.estimated_cost_zar)
