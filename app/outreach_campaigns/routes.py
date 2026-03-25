"""Outreach Campaign API routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db
from app.dashboard.routes import get_current_owner
from app.outreach_campaigns.service import OutreachService

router = APIRouter(prefix="/api/v1/outreach", tags=["Outreach Campaigns"])
outreach = OutreachService()


def _require_owner(request: Request):
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return owner


class CampaignCreateRequest(BaseModel):
    name: str
    description: str = ""
    goal: str = ""
    target_channels: list[str] = ["x_twitter", "linkedin", "reddit"]
    target_audience: str = "AI developers"
    auto_generate: bool = True


# ── Campaigns ────────────────────────────────────────────────────────

@router.get("/campaigns")
async def api_list_campaigns(
    status: str | None = None, db: AsyncSession = Depends(get_db),
):
    return await outreach.list_campaigns(db, status)


@router.post("/campaigns")
async def api_create_campaign(
    req: CampaignCreateRequest, request: Request,
    db: AsyncSession = Depends(get_db),
):
    _require_owner(request)
    result = await outreach.create_campaign(db, req.model_dump())
    await db.commit()
    return result


@router.patch("/campaigns/{campaign_id}")
async def api_update_campaign(
    campaign_id: str, request: Request,
    status: str | None = None, goal: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    _require_owner(request)
    updates = {}
    if status:
        updates["status"] = status
    if goal:
        updates["goal"] = goal
    try:
        result = await outreach.update_campaign(db, campaign_id, updates)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Content ──────────────────────────────────────────────────────────

@router.get("/content")
async def api_list_content(
    campaign_id: str | None = None, channel: str | None = None,
    status: str | None = None, db: AsyncSession = Depends(get_db),
):
    return await outreach.list_content(db, campaign_id, channel, status)


@router.post("/content/generate")
async def api_generate_content(
    request: Request, campaign_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Generate a fresh batch of content across all channels."""
    _require_owner(request)
    results = await outreach.generate_new_content(db, campaign_id)
    await db.commit()
    return results


@router.post("/content/{content_id}/approve")
async def api_approve_content(
    content_id: str, request: Request,
    db: AsyncSession = Depends(get_db),
):
    _require_owner(request)
    try:
        result = await outreach.approve_content(db, content_id)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/content/{content_id}/mark-posted")
async def api_mark_posted(
    content_id: str, request: Request,
    posted_url: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Mark content as posted (after you've copy-pasted and posted it)."""
    _require_owner(request)
    try:
        result = await outreach.mark_posted(db, content_id, posted_url)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Actions ──────────────────────────────────────────────────────────

@router.get("/actions")
async def api_list_actions(
    campaign_id: str | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await outreach.list_actions(db, campaign_id, limit=limit)


# ── Dashboard ────────────────────────────────────────────────────────

@router.get("/dashboard")
async def api_outreach_dashboard(db: AsyncSession = Depends(get_db)):
    return await outreach.get_dashboard(db)
