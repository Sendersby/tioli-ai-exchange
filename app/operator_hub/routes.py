"""Operator Hub API routes — builder profiles, directory, expertise, portfolio, cross-linking."""

from fastapi import APIRouter, Request, HTTPException, Query
from sqlalchemy import select

from app.database.db import async_session
from app.auth.oauth import get_current_operator
from app.operator_hub.service import OperatorHubService
from app.operator_hub.models import OperatorHubProfile

router = APIRouter(prefix="/api/v1/operator-hub", tags=["operator-hub"])
service = OperatorHubService()


async def _require_auth(request: Request):
    """Require authenticated operator. Returns operator or raises 401."""
    operator = await get_current_operator(request)
    if not operator:
        raise HTTPException(status_code=401, detail="Not authenticated. Please sign in.")
    return operator


# ── Profile ─────────────────────────────────────────────────────────

@router.get("/profile/me")
async def get_my_profile(request: Request):
    """Get the current operator's profile."""
    operator = await _require_auth(request)
    async with async_session() as db:
        profile = await service.get_profile(db, operator.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/profile/me")
async def update_my_profile(request: Request):
    """Update the current operator's profile."""
    operator = await _require_auth(request)
    body = await request.json()
    async with async_session() as db:
        profile = await service.update_profile(db, operator.id, **body)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.get("/profile/{handle}")
async def get_profile_by_handle(handle: str):
    """Get a public operator profile by handle."""
    async with async_session() as db:
        profile = await service.get_profile_by_handle(db, handle)
    if not profile:
        raise HTTPException(status_code=404, detail="Builder not found")
    return profile


# ── Directory ───────────────────────────────────────────────────────

@router.get("/directory")
async def search_directory(
    query: str = Query(None), expertise: str = Query(None),
    domain: str = Query(None), sort: str = Query("newest"),
    limit: int = Query(50, le=100), offset: int = Query(0),
):
    """Search the builder directory."""
    async with async_session() as db:
        results = await service.search_directory(
            db, query=query, expertise=expertise, domain=domain,
            sort=sort, limit=limit, offset=offset,
        )
        stats = await service.get_directory_stats(db)
    return {"builders": results, "stats": stats}


@router.get("/directory/stats")
async def get_directory_stats():
    """Get builder directory statistics."""
    async with async_session() as db:
        return await service.get_directory_stats(db)


# ── Expertise ───────────────────────────────────────────────────────

@router.post("/expertise")
async def add_expertise(request: Request):
    """Add expertise to your profile."""
    operator = await _require_auth(request)
    body = await request.json()
    async with async_session() as db:
        profile = (await db.execute(
            select(OperatorHubProfile).where(OperatorHubProfile.operator_id == operator.id)
        )).scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        result = await service.add_expertise(
            db, profile.id, body.get("skill_name", ""), body.get("proficiency_level", "INTERMEDIATE")
        )
    return result


@router.get("/expertise/{profile_id}")
async def list_expertise(profile_id: str):
    """List expertise for a profile."""
    async with async_session() as db:
        return await service.list_expertise(db, profile_id)


# ── Portfolio ───────────────────────────────────────────────────────

@router.post("/portfolio")
async def add_portfolio_item(request: Request):
    """Add a portfolio item to your profile."""
    operator = await _require_auth(request)
    body = await request.json()
    async with async_session() as db:
        profile = (await db.execute(
            select(OperatorHubProfile).where(OperatorHubProfile.operator_id == operator.id)
        )).scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        result = await service.add_portfolio_item(
            db, profile.id, body.get("title", ""), body.get("description"),
            body.get("item_type", "OTHER"), body.get("tags"), body.get("external_url"),
        )
    return result


@router.get("/portfolio/{profile_id}")
async def list_portfolio(profile_id: str):
    """List portfolio items for a profile."""
    async with async_session() as db:
        return await service.list_portfolio(db, profile_id)


# ── Cross-Linking: Operator ↔ Agent ─────────────────────────────────

@router.post("/agents/link")
async def link_agent(request: Request):
    """Link an agent to your operator profile."""
    operator = await _require_auth(request)
    body = await request.json()
    agent_id = body.get("agent_id")
    role = body.get("role", "BUILDER")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id is required")

    async with async_session() as db:
        profile = (await db.execute(
            select(OperatorHubProfile).where(OperatorHubProfile.operator_id == operator.id)
        )).scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        try:
            result = await service.link_agent(db, profile.id, agent_id, role)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return result


@router.get("/agents/mine")
async def get_my_agents(request: Request):
    """Get all agents linked to the current operator."""
    operator = await _require_auth(request)
    async with async_session() as db:
        return await service.get_operator_agents(db, operator.id)


@router.get("/agents/for-agent/{agent_id}")
async def get_operators_for_agent(agent_id: str):
    """Get all operators linked to an agent (public endpoint for cross-linking)."""
    async with async_session() as db:
        return await service.get_agent_operators(db, agent_id)
