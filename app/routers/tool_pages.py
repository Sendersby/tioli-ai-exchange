"""Free calculator tools — Workstream M first slice.

From COMPETITOR_ADOPTION_PLAN.md v1.1.

Serves 3 client-side calculators + 1 index page. Each calculator is a
self-contained static HTML file with inline JS math — no server round-trip,
no data leaves the browser, no email capture (deferred to Workstream K
newsletter integration).

All pages carry the canonical footer verbatim and load public-nav.js.
"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

log = logging.getLogger("tioli.tool_pages")

router = APIRouter(tags=["Free Calculators"])


TOOLS = {
    "agent-roi-calculator": "tool-agent-roi.html",
    "revenue-share-estimator": "tool-revenue-share.html",
    "charity-fee-impact": "tool-charity-impact.html",
}


@router.get("/tools", include_in_schema=False)
async def tools_index():
    return FileResponse(
        "static/landing/tool-tools-index.html",
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/tools/{slug}", include_in_schema=False)
async def tool_page(slug: str):
    filename = TOOLS.get(slug)
    if not filename:
        raise HTTPException(
            status_code=404,
            detail=f"tool '{slug}' not found. Available: {list(TOOLS.keys())}",
        )
    return FileResponse(
        f"static/landing/{filename}",
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=3600"},
    )
