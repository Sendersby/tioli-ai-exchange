"""Solution / outcome landing page routes — /solutions/{slug}.

Workstream E from COMPETITOR_ADOPTION_PLAN.md v1.1.

Each outcome is rendered from a single Jinja template + a Python dict. Heavy
cross-linking to personas (Workstream D) and the trust centre (Workstream A)
so internal SEO density compounds as more pages land.
"""

import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.data.personas import PERSONAS
from app.data.solutions import SOLUTIONS, get_solution, list_solutions
from app.main_deps import templates

log = logging.getLogger("tioli.solutions")

router = APIRouter(tags=["Solution Landing Pages"])


def _lookup_personas(slugs: list) -> list[dict]:
    """Given a list of persona slugs, return their full dict entries for
    cross-linking. Silently skips unknown slugs to keep templates cheap."""
    out = []
    for s in slugs or []:
        p = PERSONAS.get(s)
        if p:
            out.append({**p, "slug": s})
    return out


@router.get("/solutions", include_in_schema=False)
async def solutions_index(request: Request):
    """Index of all solutions."""
    rows = list_solutions()
    return templates.TemplateResponse(
        request,
        "solution_index.html",
        context={
            "request": request,
            "solutions": rows,
            "total_count": len(rows),
        },
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/solutions/{slug}", include_in_schema=False)
async def solution_page(slug: str, request: Request):
    """Single solution / outcome landing page."""
    solution = get_solution(slug)
    if not solution:
        raise HTTPException(status_code=404, detail=f"solution '{slug}' not found")

    solution_with_slug = {**solution, "slug": slug}
    related_personas = _lookup_personas(solution.get("related_personas", []))
    siblings = list_solutions()

    return templates.TemplateResponse(
        request,
        "solution_landing.html",
        context={
            "request": request,
            "solution": solution_with_slug,
            "related_personas": related_personas,
            "siblings": siblings,
        },
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/api/v1/solutions/list")
async def list_solutions_api():
    """Public JSON list of all solutions."""
    rows = list_solutions()
    return JSONResponse(
        content={
            "count": len(rows),
            "solutions": [
                {
                    "slug": s["slug"],
                    "name": s["name"],
                    "url": f"/solutions/{s['slug']}",
                    "h1": s["h1"],
                    "related_personas": s.get("related_personas", []),
                }
                for s in rows
            ],
        },
        headers={"Cache-Control": "public, max-age=3600"},
    )
