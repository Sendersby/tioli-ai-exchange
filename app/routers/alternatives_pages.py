"""Best-{product}-alternatives routes — /best/{slug}-alternatives.

Workstream F.3 from COMPETITOR_ADOPTION_PLAN.md v1.1.

Targets long-tail "best {product} alternatives" SEO intent with ranked-list
pages that pitch TiOLi positioning angles against named incumbents. Each
page cross-links into relevant personas and /vs head-to-head pages where
they exist, compounding internal SEO density.
"""

import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.data.alternatives import ALTERNATIVES, get_alternative, list_alternatives
from app.data.personas import PERSONAS
from app.main_deps import templates

log = logging.getLogger("tioli.alternatives")

router = APIRouter(tags=["Best-alternatives guides"])


def _lookup_personas(slugs):
    out = []
    for s in slugs or []:
        p = PERSONAS.get(s)
        if p:
            out.append({**p, "slug": s})
    return out


@router.get("/best", include_in_schema=False)
async def alternatives_index(request: Request):
    rows = list_alternatives()
    return templates.TemplateResponse(
        request,
        "alternatives_index.html",
        context={
            "request": request,
            "alternatives": rows,
            "total_count": len(rows),
        },
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/best/{slug}-alternatives", include_in_schema=False)
async def alternatives_page(slug: str, request: Request):
    alt = get_alternative(slug)
    if not alt:
        raise HTTPException(
            status_code=404,
            detail=f"alternatives guide for '{slug}' not found",
        )

    alt_with_slug = {**alt, "slug": slug}
    related_personas = _lookup_personas(alt.get("related_personas", []))
    siblings = list_alternatives()

    return templates.TemplateResponse(
        request,
        "alternatives_landing.html",
        context={
            "request": request,
            "alt": alt_with_slug,
            "related_personas": related_personas,
            "siblings": siblings,
        },
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/api/v1/alternatives/list")
async def list_alternatives_api():
    rows = list_alternatives()
    return JSONResponse(
        content={
            "count": len(rows),
            "alternatives": [
                {
                    "slug": a["slug"],
                    "product_name": a["product_name"],
                    "product_category": a["product_category"],
                    "url": f"/best/{a['slug']}-alternatives",
                    "h1": a["h1"],
                }
                for a in rows
            ],
        },
        headers={"Cache-Control": "public, max-age=3600"},
    )
