"""Whitepaper lead magnet — Workstream T from COMPETITOR_ADOPTION_PLAN.md v1.1.

Captures lead data from the /whitepaper/build-vs-buy landing page form,
persists to public.whitepaper_leads, and drops a DEFER_TO_OWNER item into
the founder inbox per standing rule #4.

The actual PDF is not yet shipped — this is infrastructure for lead capture
while the founder authors the content. The thank-you page tells users they
will be emailed when the guide publishes.

Standing rules:
- Inbox delivery (rule #4): every submission creates a DEFER_TO_OWNER inbox
  item in arch_founder_inbox
- POPIA: consent checkbox required; stored flag, IP retained briefly (hashed)
  for abuse analysis
- Rate limit: 5/min per IP via in-memory counter (same pattern as feedback)
"""

import hashlib
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy import text

from app.database.db import async_session

log = logging.getLogger("tioli.whitepaper")

router = APIRouter(tags=["Whitepaper Lead Magnet"])

_ALLOWED_ROLES = {
    "founder", "cto", "product", "compliance", "finance",
    "ops", "marketing", "developer", "other",
}
_ALLOWED_TEAM_SIZES = {"", "1", "2-10", "11-50", "51-200", "200+"}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

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


def _hash_ip(ip: str) -> str:
    salt = "tioli-whitepaper-v1"
    return hashlib.sha256((salt + ":" + ip).encode()).hexdigest()


class WhitepaperPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., max_length=320)
    role: str = Field(...)
    company: str | None = Field(None, max_length=200)
    team_size: str | None = Field(None, max_length=20)
    use_case: str | None = Field(None, max_length=500)
    consent: bool = Field(...)
    page_url: str | None = Field(None, max_length=500)

    @validator("email")
    def _check_email(cls, v):
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email format")
        return v

    @validator("role")
    def _check_role(cls, v):
        if v not in _ALLOWED_ROLES:
            raise ValueError(f"role must be one of {sorted(_ALLOWED_ROLES)}")
        return v

    @validator("team_size")
    def _check_team_size(cls, v):
        if v is None:
            return None
        if v not in _ALLOWED_TEAM_SIZES:
            raise ValueError(f"team_size must be one of {sorted(_ALLOWED_TEAM_SIZES)}")
        return v or None

    @validator("consent")
    def _check_consent(cls, v):
        if not v:
            raise ValueError("POPIA consent is required")
        return v


# ── Static landing pages ───────────────────────────────────


@router.get("/whitepaper/build-vs-buy", include_in_schema=False)
async def whitepaper_landing():
    return FileResponse(
        "static/landing/whitepaper-build-vs-buy.html",
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/whitepaper/thanks", include_in_schema=False)
async def whitepaper_thanks():
    return FileResponse(
        "static/landing/whitepaper-thanks.html",
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ── Lead capture ───────────────────────────────────────────


@router.post("/api/v1/whitepaper/request")
async def whitepaper_request(payload: WhitepaperPayload, request: Request):
    """Accept a lead-magnet form submission, persist to DB, drop inbox item."""
    ip = request.client.host if request.client else "unknown"
    if not _check_rate(ip):
        raise HTTPException(
            status_code=429,
            detail="Too many submissions from this IP. Try again in a minute.",
        )

    ip_hash = _hash_ip(ip)

    lead_id = None
    inbox_id = None

    description = (
        f"[Whitepaper Lead / Build-vs-Buy]\n"
        f"Name: {payload.name}\n"
        f"Email: {payload.email}\n"
        f"Role: {payload.role}\n"
        f"Company: {payload.company or '-'}\n"
        f"Team size: {payload.team_size or '-'}\n"
        f"Use case: {payload.use_case or '-'}\n"
        f"Page: {payload.page_url or '-'}\n"
        f"IP hash: {ip_hash[:16]}..."
    )[:5000]

    try:
        async with async_session() as db:
            r = await db.execute(
                text(
                    """
                    INSERT INTO whitepaper_leads
                        (whitepaper_slug, name, email, role, company,
                         team_size, use_case, popia_consent, ip_hash)
                    VALUES (:slug, :name, :email, :role, :company,
                            :team_size, :use_case, :consent, :ip_hash)
                    RETURNING id::text
                    """
                ),
                {
                    "slug": "build-vs-buy",
                    "name": payload.name,
                    "email": payload.email,
                    "role": payload.role,
                    "company": payload.company,
                    "team_size": payload.team_size,
                    "use_case": payload.use_case,
                    "consent": payload.consent,
                    "ip_hash": ip_hash,
                },
            )
            lead_id = r.scalar()

            r2 = await db.execute(
                text(
                    """
                    INSERT INTO arch_founder_inbox
                        (item_type, priority, description, status, created_at)
                    VALUES ('whitepaper_lead', 'ROUTINE', :desc, 'PENDING', now())
                    RETURNING id::text
                    """
                ),
                {"desc": description},
            )
            inbox_id = r2.scalar()

            if lead_id and inbox_id:
                await db.execute(
                    text(
                        """
                        UPDATE whitepaper_leads
                        SET inbox_item_id = CAST(:iid AS uuid)
                        WHERE id = CAST(:lid AS uuid)
                        """
                    ),
                    {"iid": inbox_id, "lid": lead_id},
                )

            await db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"whitepaper lead insert failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Could not record request. Please try again or email support@tioli.co.za",
        )

    log.info(
        f"whitepaper lead captured role={payload.role} "
        f"lead_id={lead_id} inbox={inbox_id}"
    )

    return JSONResponse(
        {
            "ok": True,
            "lead_id": lead_id,
            "inbox_item_id": inbox_id,
            "message": "You are on the list. Stephen will email you the guide when it publishes.",
        }
    )
