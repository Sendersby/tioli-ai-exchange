"""Cross-Directory Submission service — Workstream R first slice.

From COMPETITOR_ADOPTION_PLAN.md v1.1 section A1.3.

Adopts SaaSHub's "108 verified directories" productized pattern. For v1 we
ship 25 curated external AI agent directories in a static data module, a
pitch/marketing page, a list endpoint, and a submit endpoint that creates
one DEFER_TO_OWNER inbox item per selected directory for founder review.

Deferred to next slice:
- Automated form-filling / email sending for submission (needs per-directory
  adapters and auth management)
- Weekly verification job that checks each directory URL is still reachable
- Submission status polling to catch approval / rejection state changes
- Paid tier (first 5 free, R200/R350/R500 for 25/50/100)
"""

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy import text

from app.data.external_directories import (
    EXTERNAL_DIRECTORIES,
    count_by_band,
    get_directory,
    list_directories,
)
from app.database.db import async_session

log = logging.getLogger("tioli.cross_directory")

router = APIRouter(tags=["Cross-Directory Submission"])

_SAFE_AGENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-:.]{0,63}$")
_RATE_LIMIT = 5
_RATE_WINDOW_SEC = 60
_rate_state = defaultdict(list)


def _check_rate(ip: str) -> bool:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=_RATE_WINDOW_SEC)
    history = [t for t in _rate_state[ip] if t > cutoff]
    if len(history) >= _RATE_LIMIT:
        _rate_state[ip] = history
        return False
    history.append(now)
    _rate_state[ip] = history
    return True


class SubmitPayload(BaseModel):
    agent_id: str = Field(..., min_length=1, max_length=100)
    directory_slugs: list[str] = Field(..., min_items=1, max_items=25)
    contact_email: str = Field(..., max_length=320)

    @validator("agent_id")
    def _agent_id_safe(cls, v):
        if not _SAFE_AGENT_ID_RE.match(v):
            raise ValueError("invalid agent id format")
        return v

    @validator("directory_slugs", each_item=True)
    def _slug_exists(cls, v):
        if not get_directory(v):
            raise ValueError(f"unknown directory slug: {v}")
        return v

    @validator("contact_email")
    def _email_fmt(cls, v):
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("invalid email format")
        return v.lower()


# ── Pages ──────────────────────────────────────────────────


@router.get("/services/cross-directory", include_in_schema=False)
async def cross_directory_landing():
    return FileResponse(
        "static/landing/cross-directory.html",
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=1800"},
    )


# ── Public JSON ────────────────────────────────────────────


@router.get("/api/v1/cross-directory/list")
async def list_cross_directories():
    """Public list of curated external directories."""
    rows = list_directories()
    return JSONResponse(
        content={
            "count": len(rows),
            "by_traffic_band": count_by_band(),
            "directories": rows,
        },
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ── Submission ─────────────────────────────────────────────


@router.post("/api/v1/cross-directory/submit/{agent_id}")
async def submit_cross_directory(agent_id: str, payload: SubmitPayload, request: Request):
    """Accept a cross-directory submission request. Verifies agent exists,
    creates one DEFER_TO_OWNER inbox item per selected directory, and
    persists the request to cross_directory_submissions for status tracking.
    """
    if not _SAFE_AGENT_ID_RE.match(agent_id):
        raise HTTPException(status_code=400, detail="invalid agent id")
    if payload.agent_id != agent_id:
        raise HTTPException(status_code=400, detail="agent id mismatch between URL and body")

    ip = request.client.host if request.client else "unknown"
    if not _check_rate(ip):
        raise HTTPException(status_code=429, detail="too many requests from this IP")

    try:
        async with async_session() as db:
            # Verify agent exists
            r = await db.execute(
                text("SELECT id, name FROM agents WHERE id = :aid AND is_active = true LIMIT 1"),
                {"aid": agent_id},
            )
            agent_row = r.fetchone()
            if not agent_row:
                raise HTTPException(status_code=404, detail="agent not found or not active")

            created_submissions = []
            created_inbox_items = []

            for slug in payload.directory_slugs:
                directory = get_directory(slug)
                if not directory:
                    continue

                # Persist submission record
                r = await db.execute(
                    text(
                        """
                        INSERT INTO cross_directory_submissions
                            (agent_id, directory_slug, directory_name, status,
                             submitted_by_email, created_at)
                        VALUES (:aid, :slug, :name, 'pending_review', :email, now())
                        ON CONFLICT (agent_id, directory_slug)
                        DO UPDATE SET
                            status = 'pending_review',
                            submitted_by_email = EXCLUDED.submitted_by_email,
                            created_at = now()
                        RETURNING id::text
                        """
                    ),
                    {
                        "aid": agent_id,
                        "slug": slug,
                        "name": directory["name"],
                        "email": payload.contact_email,
                    },
                )
                sub_id = r.scalar()
                created_submissions.append({"slug": slug, "id": sub_id})

                # Inbox item for founder review
                description = (
                    f"[Cross-Directory Submission / {slug}]\n"
                    f"Agent: {agent_row.name} ({agent_id})\n"
                    f"Target directory: {directory['name']}\n"
                    f"Submission URL: {directory['submission_url']}\n"
                    f"Format: {directory.get('format', 'unknown')}\n"
                    f"Traffic band: {directory.get('traffic_band', 'unknown')}\n"
                    f"Contact email: {payload.contact_email}\n"
                    f"Notes: {directory.get('notes', '-')}"
                )[:5000]

                r2 = await db.execute(
                    text(
                        """
                        INSERT INTO arch_founder_inbox
                            (item_type, priority, description, status, created_at)
                        VALUES ('cross_directory_submission', 'ROUTINE', :desc, 'PENDING', now())
                        RETURNING id::text
                        """
                    ),
                    {"desc": description},
                )
                inbox_id = r2.scalar()
                created_inbox_items.append(inbox_id)

            await db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"cross_directory submit failed agent={agent_id}: {exc}")
        raise HTTPException(status_code=500, detail="Could not record submissions. Please try again.")

    log.info(
        f"cross_directory submission agent={agent_id} "
        f"directories={len(created_submissions)} inbox_items={len(created_inbox_items)}"
    )

    return JSONResponse(
        {
            "ok": True,
            "agent_id": agent_id,
            "submissions_created": len(created_submissions),
            "inbox_items_created": len(created_inbox_items),
            "message": (
                f"Queued {len(created_submissions)} directory submissions for "
                f"founder review. Stephen will process them in the next 24-48 hours "
                f"and email you with the listing URLs as they go live."
            ),
        }
    )


@router.get("/api/v1/cross-directory/status/{agent_id}")
async def cross_directory_status(agent_id: str):
    """Return all submission statuses for a given agent."""
    if not _SAFE_AGENT_ID_RE.match(agent_id):
        raise HTTPException(status_code=400, detail="invalid agent id")

    try:
        async with async_session() as db:
            r = await db.execute(
                text(
                    """
                    SELECT directory_slug, directory_name, status,
                           listing_url, created_at, last_checked_at
                    FROM cross_directory_submissions
                    WHERE agent_id = :aid
                    ORDER BY created_at DESC
                    """
                ),
                {"aid": agent_id},
            )
            rows = r.fetchall()
    except Exception as exc:
        log.error(f"cross_directory status failed: {exc}")
        return JSONResponse({"agent_id": agent_id, "submissions": []})

    return JSONResponse(
        content={
            "agent_id": agent_id,
            "total": len(rows),
            "submissions": [
                {
                    "directory_slug": r.directory_slug,
                    "directory_name": r.directory_name,
                    "status": r.status,
                    "listing_url": r.listing_url,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "last_checked_at": r.last_checked_at.isoformat() if r.last_checked_at else None,
                }
                for r in rows
            ],
        },
        headers={"Cache-Control": "public, max-age=300"},
    )
