"""Agent Memory API routes.

All endpoints require Bearer token authentication.
Feature-flagged — requires memory module to be enabled (default: on for Sprint 6).
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db
from app.agents.models import Agent
from app.auth.agent_auth import authenticate_agent
from app.agent_memory.service import AgentMemoryService

router = APIRouter(prefix="/api/v1/memory", tags=["Agent Memory"])
memory_service = AgentMemoryService()


async def require_agent_auth(
    authorization: str = Header(...), db: AsyncSession = Depends(get_db),
) -> Agent:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    agent = await authenticate_agent(db, authorization[7:])
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return agent


class MemoryWriteRequest(BaseModel):
    key: str
    value: dict | list | str | int | float | bool
    ttl_days: int | None = None


@router.post("/write")
async def api_memory_write(
    req: MemoryWriteRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Write a memory record. Upserts if key exists.

    Memory persists across sessions. Use structured JSONB values.
    Optional TTL (days) for auto-expiry.
    """
    try:
        result = await memory_service.write(db, agent.id, req.key, req.value, req.ttl_days)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/read/{key}")
async def api_memory_read(
    key: str,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Read a memory record by key. Returns null if not found or expired."""
    result = await memory_service.read(db, agent.id, key)
    await db.commit()
    if not result:
        raise HTTPException(status_code=404, detail=f"Memory key '{key}' not found")
    return result


@router.get("/search")
async def api_memory_search(
    q: str = Query(..., min_length=1, description="Search query for memory keys"),
    limit: int = Query(20, le=100),
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Search memory records by key pattern."""
    return await memory_service.search(db, agent.id, q, limit)


@router.get("/keys")
async def api_memory_keys(
    limit: int = Query(100, le=500),
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """List all memory keys with usage stats and quota info."""
    return await memory_service.list_keys(db, agent.id, limit)


@router.delete("/delete/{key}")
async def api_memory_delete(
    key: str,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific memory record."""
    try:
        result = await memory_service.delete_key(db, agent.id, key)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
