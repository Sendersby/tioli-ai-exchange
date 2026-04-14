"""TiOLi vs Competitor landing page routes — /vs/{slug}.

Workstream F (first slice) from COMPETITOR_ADOPTION_PLAN.md v1.1.

Structured head-to-head comparison pages targeting "X vs Y" SEO intent.
Comparisons are human-authored from competitor research memories, not
LLM-generated — every row is a real, defensible claim.
"""

import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.data.vs_data import VS_ENTRIES, get_vs, list_vs
from app.main_deps import templates

log = logging.getLogger("tioli.vs")

router = APIRouter(tags=["TiOLi vs Competitor"])


@router.get("/vs", include_in_schema=False)
async def vs_index(request: Request):
    rows = list_vs()
    return templates.TemplateResponse(
        request,
        "vs_index.html",
        context={
            "request": request,
            "vs_list": rows,
            "total_count": len(rows),
        },
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/vs/{slug}", include_in_schema=False)
async def vs_page(slug: str, request: Request):
    vs = get_vs(slug)
    if not vs:
        raise HTTPException(status_code=404, detail=f"comparison '{slug}' not found")

    vs_with_slug = {**vs, "slug": slug}
    siblings = list_vs()

    return templates.TemplateResponse(
        request,
        "vs_landing.html",
        context={
            "request": request,
            "vs": vs_with_slug,
            "siblings": siblings,
        },
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/api/v1/vs/list")
async def list_vs_api():
    rows = list_vs()
    return JSONResponse(
        content={
            "count": len(rows),
            "comparisons": [
                {
                    "slug": v["slug"],
                    "competitor_name": v["competitor_name"],
                    "competitor_type": v["competitor_type"],
                    "url": f"/vs/{v['slug']}",
                    "h1": v["h1"],
                }
                for v in rows
            ],
        },
        headers={"Cache-Control": "public, max-age=3600"},
    )
