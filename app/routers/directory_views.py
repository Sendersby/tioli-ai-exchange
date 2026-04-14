"""Directory view variants + tag pages — Workstream G first slice.

From COMPETITOR_ADOPTION_PLAN.md v1.1.

Ships 5 new public routes that all read from the existing `agents` table:

- GET /directory/list           -> compact list view
- GET /directory/map            -> bubble-chart view by platform
- GET /directory/timeline       -> chronological registration view
- GET /tags                     -> index of all platforms (used as tags)
- GET /tag/{slug}               -> all agents on that platform

The existing /directory (served by pages.py as a static HTML file) is NOT
touched — these are additive variants that give the directory 4 total
indexable view URLs plus a tag dimension.

Standing rules:
- Canonical footer present in each Jinja template verbatim
- public-nav.js loaded with current cache-bust
- Inbox delivery N/A (read-only public)
"""

import logging
import re
import unicodedata
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database.db import async_session
from app.main_deps import templates

log = logging.getLogger("tioli.directory_views")

router = APIRouter(tags=["Directory Views + Tags"])


def slugify(value: str) -> str:
    """Lowercase, normalise, replace non-alphanumerics with hyphens."""
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value


async def _load_agents(limit: int = 500) -> list[dict]:
    """Load approved, active agents from the DB. Cached by HTTP headers."""
    async with async_session() as db:
        r = await db.execute(
            text(
                """
                SELECT id, name, platform, description, created_at, is_house_agent
                FROM agents
                WHERE is_active = true AND is_approved = true
                ORDER BY created_at DESC NULLS LAST
                LIMIT :lim
                """
            ),
            {"lim": limit},
        )
        rows = []
        for row in r.fetchall():
            rows.append(
                {
                    "id": row.id,
                    "name": row.name,
                    "platform": row.platform or "unknown",
                    "platform_slug": slugify(row.platform or "unknown"),
                    "description": (row.description or "")[:220],
                    "created_at": row.created_at,
                    "is_house_agent": bool(row.is_house_agent),
                }
            )
        return rows


def _aggregate_platforms(agents: list[dict]) -> list[dict]:
    """Count agents by platform; return sorted list of {platform, slug, count}."""
    counts = {}
    for a in agents:
        key = a["platform_slug"]
        if key not in counts:
            counts[key] = {"slug": key, "name": a["platform"], "count": 0}
        counts[key]["count"] += 1
    rows = sorted(counts.values(), key=lambda x: -x["count"])
    return rows


def _group_by_month(agents: list[dict]) -> list[dict]:
    """Group agents by YYYY-MM of created_at, descending."""
    groups: dict[str, list] = {}
    for a in agents:
        dt = a.get("created_at")
        if not dt:
            key = "Unknown"
        else:
            try:
                key = dt.strftime("%B %Y")
            except Exception:
                key = "Unknown"
        groups.setdefault(key, []).append(a)
    ordered = []
    for key in sorted(
        groups.keys(),
        key=lambda k: datetime.strptime(k, "%B %Y") if k != "Unknown" else datetime(1970, 1, 1),
        reverse=True,
    ):
        ordered.append({"label": key, "agents": groups[key]})
    return ordered


# ── Directory view variants ─────────────────────────────────


@router.get("/directory/list", include_in_schema=False)
async def directory_list(request: Request):
    agents = await _load_agents()
    return templates.TemplateResponse(
        request,
        "directory_list.html",
        context={
            "request": request,
            "agents": agents,
            "total_count": len(agents),
            "view": "list",
        },
        headers={"Cache-Control": "public, max-age=900"},
    )


@router.get("/directory/map", include_in_schema=False)
async def directory_map(request: Request):
    agents = await _load_agents()
    platforms = _aggregate_platforms(agents)
    return templates.TemplateResponse(
        request,
        "directory_map.html",
        context={
            "request": request,
            "platforms": platforms,
            "total_agents": len(agents),
            "total_platforms": len(platforms),
            "view": "map",
        },
        headers={"Cache-Control": "public, max-age=900"},
    )


@router.get("/directory/timeline", include_in_schema=False)
async def directory_timeline(request: Request):
    agents = await _load_agents()
    groups = _group_by_month(agents)
    return templates.TemplateResponse(
        request,
        "directory_timeline.html",
        context={
            "request": request,
            "groups": groups,
            "total_count": len(agents),
            "view": "timeline",
        },
        headers={"Cache-Control": "public, max-age=900"},
    )


# ── Tag surface ─────────────────────────────────────────────


@router.get("/tags", include_in_schema=False)
async def tags_index(request: Request):
    agents = await _load_agents()
    platforms = _aggregate_platforms(agents)
    return templates.TemplateResponse(
        request,
        "tag_index.html",
        context={
            "request": request,
            "tags": platforms,
            "total_tags": len(platforms),
            "total_agents": len(agents),
        },
        headers={"Cache-Control": "public, max-age=900"},
    )


@router.get("/tag/{slug}", include_in_schema=False)
async def tag_page(slug: str, request: Request):
    slug = slug.lower().strip()
    agents = await _load_agents()
    platforms = _aggregate_platforms(agents)
    platform_meta = next((p for p in platforms if p["slug"] == slug), None)
    if not platform_meta:
        raise HTTPException(status_code=404, detail=f"tag '{slug}' has no agents")

    tag_agents = [a for a in agents if a["platform_slug"] == slug]
    return templates.TemplateResponse(
        request,
        "tag_page.html",
        context={
            "request": request,
            "tag": platform_meta,
            "agents": tag_agents,
            "sibling_tags": [p for p in platforms if p["slug"] != slug][:12],
        },
        headers={"Cache-Control": "public, max-age=900"},
    )


@router.get("/api/v1/tags/list")
async def api_tags_list():
    agents = await _load_agents()
    platforms = _aggregate_platforms(agents)
    return JSONResponse(
        content={
            "count": len(platforms),
            "tags": [
                {
                    "slug": p["slug"],
                    "name": p["name"],
                    "count": p["count"],
                    "url": f"/tag/{p['slug']}",
                }
                for p in platforms
            ],
        },
        headers={"Cache-Control": "public, max-age=900"},
    )
