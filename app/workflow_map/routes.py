"""Workflow Map API routes — owner-only endpoints for the platform workflow map."""

from fastapi import APIRouter, Request, HTTPException

from app.database.db import async_session
from app.dashboard.routes import get_current_owner
from app.workflow_map.service import WorkflowMapService

router = APIRouter(prefix="/api/v1/owner/workflow-map", tags=["Workflow Map"])
service = WorkflowMapService()


def _require_owner(request: Request):
    """Require authenticated owner. Returns owner dict or raises 401."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return owner


@router.get("/graph")
async def get_graph(request: Request):
    """Complete node and edge graph for the D3 renderer."""
    _require_owner(request)
    async with async_session() as db:
        return await service.get_graph(db)


@router.get("/node/{node_id}")
async def get_node_detail(node_id: str, request: Request):
    """Full detail for a single node — connected nodes, edges, status history."""
    _require_owner(request)
    async with async_session() as db:
        result = await service.get_node_detail(db, node_id)
    if not result:
        raise HTTPException(status_code=404, detail="Node not found")
    return result


@router.get("/status-summary")
async def get_status_summary(request: Request):
    """Lightweight summary for the stats bar — polled every 60 seconds."""
    _require_owner(request)
    async with async_session() as db:
        return await service.get_status_summary(db)


@router.get("/enrichment")
async def get_enrichment(request: Request):
    """Enrichment data: health, traffic, revenue, phases, deps, activity, agent counts."""
    _require_owner(request)
    async with async_session() as db:
        return await service.get_enrichment_data(db)


@router.patch("/node/{node_id}/status")
async def update_node_status(node_id: str, request: Request):
    """Update a node's status. Requires owner auth + 3FA token."""
    _require_owner(request)

    # Require 3FA token for status changes
    body = await request.json()
    tfa_token = body.get("tfa_token") or request.headers.get("X-3FA-Token")
    if tfa_token:
        from app.auth.three_factor import three_factor_store
        if not three_factor_store.validate_and_consume(tfa_token):
            raise HTTPException(status_code=403, detail="Invalid or expired 3FA token")
    else:
        raise HTTPException(status_code=403, detail="3FA token required for status changes")

    new_status = body.get("status")
    reason = body.get("reason", "")

    if new_status not in ("ACTIVE", "RESTRICTED", "INACTIVE", "PLANNED", "DEPRECATED"):
        raise HTTPException(status_code=400, detail="Invalid status value")

    async with async_session() as db:
        result = await service.update_node_status(db, node_id, new_status, reason)
    if not result:
        raise HTTPException(status_code=404, detail="Node not found")
    return result
