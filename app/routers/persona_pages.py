"""Persona landing page routes — /for/{slug}.

Workstream D from COMPETITOR_ADOPTION_PLAN.md v1.1.

Each persona is rendered from a single Jinja template + a Python dict.
Adding new personas is data-only (edit app/data/personas.py) — no template
or router changes required. Cached at the HTTP layer (1h max-age, Cloudflare
edge) so this stays cheap even at scale.

Standing rules:
- Canonical footer included verbatim in the Jinja template
- public-nav.js loaded at end of body
- /api/v1/public/proof-metrics fed via the embedded proof-band div
- No agent action -> inbox delivery N/A
"""

import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

from app.data.personas import (
    CATEGORY_LABELS,
    PERSONAS,
    get_persona,
    list_personas,
    list_personas_by_category,
)
from app.main_deps import templates

log = logging.getLogger("tioli.persona")

router = APIRouter(tags=["Persona Landing Pages"])


@router.get("/for", include_in_schema=False)
async def persona_index(request: Request):
    """Index of all personas, grouped by category."""
    by_cat = list_personas_by_category()
    return templates.TemplateResponse(
        request,
        "persona_index.html",
        context={
            "request": request,
            "personas_by_category": by_cat,
            "category_labels": CATEGORY_LABELS,
            "total_count": len(PERSONAS),
        },
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/for/{slug}", include_in_schema=False)
async def persona_page(slug: str, request: Request):
    """Single persona landing page."""
    persona = get_persona(slug)
    if not persona:
        raise HTTPException(status_code=404, detail=f"persona '{slug}' not found")

    persona_with_slug = {**persona, "slug": slug}
    siblings = [p for p in list_personas() if p["category"] == persona["category"]]
    category_label = CATEGORY_LABELS.get(persona["category"], persona["category"])

    return templates.TemplateResponse(
        request,
        "persona_landing.html",
        context={
            "request": request,
            "persona": persona_with_slug,
            "siblings": siblings,
            "category_label": category_label,
        },
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/api/v1/personas/list")
async def list_personas_api():
    """Public JSON list of all personas — used by sitemap generators and
    integrators who want to know what landing pages exist."""
    rows = list_personas()
    return JSONResponse(
        content={
            "count": len(rows),
            "personas": [
                {
                    "slug": p["slug"],
                    "name": p["name"],
                    "category": p["category"],
                    "url": f"/for/{p['slug']}",
                    "h1": p["h1"],
                }
                for p in rows
            ],
            "categories": CATEGORY_LABELS,
        },
        headers={"Cache-Control": "public, max-age=3600"},
    )
