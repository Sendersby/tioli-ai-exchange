"""Hierarchical category routes + vote infrastructure — Workstream G completion.

Routes:
- GET /categories              -> hierarchical index
- GET /categories/{slug}       -> single top-level category page

Vote ranking (infrastructure only this slice — display integration later):
- POST /api/v1/agents/{id}/vote  -> upsert a +1/-1 vote per agent per IP
- GET /api/v1/agents/{id}/votes  -> aggregate count (net, up, down, total_ips)
"""

import hashlib
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy import text

from app.data.categories import CATEGORIES, get_category, list_categories
from app.data.personas import PERSONAS
from app.data.solutions import SOLUTIONS
from app.database.db import async_session
from app.main_deps import templates

log = logging.getLogger("tioli.categories")

router = APIRouter(tags=["Hierarchical Categories + Votes"])


def _lookup_personas(slugs):
    out = []
    for s in slugs or []:
        if s in PERSONAS:
            out.append({**PERSONAS[s], "slug": s})
    return out


def _lookup_solutions(slugs):
    out = []
    for s in slugs or []:
        if s in SOLUTIONS:
            out.append({**SOLUTIONS[s], "slug": s})
    return out


# ── Category pages ─────────────────────────────────────────


@router.get("/categories", include_in_schema=False)
async def categories_index(request: Request):
    rows = list_categories()
    return templates.TemplateResponse(
        request,
        "categories_index.html",
        context={
            "request": request,
            "categories": rows,
            "total_count": len(rows),
        },
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/categories/{slug}", include_in_schema=False)
async def category_page(slug: str, request: Request):
    cat = get_category(slug)
    if not cat:
        raise HTTPException(status_code=404, detail=f"category '{slug}' not found")

    cat_with_slug = {**cat, "slug": slug}
    related_personas = _lookup_personas(cat.get("related_personas", []))
    related_solutions = _lookup_solutions(cat.get("related_solutions", []))
    siblings = list_categories()

    return templates.TemplateResponse(
        request,
        "category_page.html",
        context={
            "request": request,
            "category": cat_with_slug,
            "related_personas": related_personas,
            "related_solutions": related_solutions,
            "siblings": siblings,
        },
        headers={"Cache-Control": "public, max-age=1800"},
    )


# ── Vote ranking infrastructure ────────────────────────────

_SAFE_AGENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-:.]{0,63}$")
_VOTE_RATE_LIMIT = 10
_VOTE_RATE_WINDOW_SEC = 60
_vote_rate_state = defaultdict(list)


def _hash_ip(ip: str) -> str:
    """SHA-256 hash IP with a static salt so we can store a dedup key
    without retaining raw IP addresses beyond the request lifecycle."""
    salt = "tioli-agents-vote-v1"
    return hashlib.sha256((salt + ":" + ip).encode()).hexdigest()


def _check_vote_rate(ip: str) -> bool:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=_VOTE_RATE_WINDOW_SEC)
    history = [t for t in _vote_rate_state[ip] if t > cutoff]
    if len(history) >= _VOTE_RATE_LIMIT:
        _vote_rate_state[ip] = history
        return False
    history.append(now)
    _vote_rate_state[ip] = history
    return True


class VotePayload(BaseModel):
    direction: int = Field(..., description="+1 upvote or -1 downvote")

    @validator("direction")
    def _check_direction(cls, v):
        if v not in (1, -1):
            raise ValueError("direction must be 1 or -1")
        return v


@router.post("/api/v1/agents/{agent_id}/vote")
async def vote_for_agent(agent_id: str, payload: VotePayload, request: Request):
    """Upsert a vote for an agent from the calling IP.

    Public, rate-limited, dedup-by-IP. Intended for casting an up/down
    signal on agent cards without full account auth.
    """
    if not _SAFE_AGENT_ID_RE.match(agent_id):
        raise HTTPException(status_code=400, detail="invalid agent id")

    ip = request.client.host if request.client else "unknown"
    if not _check_vote_rate(ip):
        raise HTTPException(status_code=429, detail="too many votes from this IP")

    ip_hash = _hash_ip(ip)

    try:
        async with async_session() as db:
            # Ensure the agent exists (by id) before voting — reject otherwise
            r = await db.execute(
                text("SELECT id FROM agents WHERE id = :aid LIMIT 1"),
                {"aid": agent_id},
            )
            if not r.scalar():
                raise HTTPException(status_code=404, detail="agent not found")

            # Upsert vote
            await db.execute(
                text(
                    """
                    INSERT INTO public_agent_votes (agent_id, ip_hash, direction, created_at)
                    VALUES (:aid, :iph, :dir, now())
                    ON CONFLICT (agent_id, ip_hash)
                    DO UPDATE SET direction = EXCLUDED.direction, created_at = now()
                    """
                ),
                {"aid": agent_id, "iph": ip_hash, "dir": payload.direction},
            )
            await db.commit()

            # Return aggregate
            a = await db.execute(
                text(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE direction = 1)  AS up,
                        COUNT(*) FILTER (WHERE direction = -1) AS down,
                        COUNT(*)                                AS total
                    FROM public_agent_votes
                    WHERE agent_id = :aid
                    """
                ),
                {"aid": agent_id},
            )
            row = a.fetchone()
            up = int(row.up or 0)
            down = int(row.down or 0)
            total = int(row.total or 0)
            net = up - down
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"vote failed agent={agent_id}: {exc}")
        raise HTTPException(status_code=500, detail="vote could not be recorded")

    return JSONResponse(
        {
            "ok": True,
            "agent_id": agent_id,
            "net": net,
            "up": up,
            "down": down,
            "total": total,
        }
    )


@router.get("/api/v1/agents/{agent_id}/votes")
async def get_agent_votes(agent_id: str):
    if not _SAFE_AGENT_ID_RE.match(agent_id):
        raise HTTPException(status_code=400, detail="invalid agent id")
    try:
        async with async_session() as db:
            r = await db.execute(
                text(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE direction = 1)  AS up,
                        COUNT(*) FILTER (WHERE direction = -1) AS down,
                        COUNT(*)                                AS total
                    FROM public_agent_votes
                    WHERE agent_id = :aid
                    """
                ),
                {"aid": agent_id},
            )
            row = r.fetchone()
            up = int(row.up or 0) if row else 0
            down = int(row.down or 0) if row else 0
            total = int(row.total or 0) if row else 0
    except Exception as exc:
        log.error(f"get_votes failed agent={agent_id}: {exc}")
        raise HTTPException(status_code=500, detail="could not read votes")

    return JSONResponse(
        content={
            "agent_id": agent_id,
            "net": up - down,
            "up": up,
            "down": down,
            "total": total,
        },
        headers={"Cache-Control": "public, max-age=60"},
    )
