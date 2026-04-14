"""Newsletter subscription + sponsor booking — Workstream K first slice.

From COMPETITOR_ADOPTION_PLAN.md v1.1.

Ships:
- POST /api/v1/newsletter/subscribe          -> double-opt-in subscribe
- GET  /api/v1/newsletter/confirm/{token}    -> opt-in confirmation
- POST /api/v1/newsletter/unsubscribe        -> one-click unsubscribe
- POST /api/v1/newsletter/sponsor            -> sponsor booking -> founder inbox
- GET  /newsletter                           -> subscribe landing page
- GET  /newsletter/sponsor                   -> sponsor pitch + application

Deferred to next slice:
- Actual daily/weekly digest composition and send (needs content + approval)
- Microsoft Graph integration for real email delivery (infra exists from
  LinkedIn work but hooking it up requires founder sign-off on copy)
- Sponsor payment processing (PayFast / Stripe — tied to existing billing)

Standing rules:
- Inbox delivery (rule #4): sponsor bookings create DEFER_TO_OWNER inbox items
- Rate limits on both subscribe and sponsor endpoints
- Double-opt-in via time-limited token (48h)
"""

import hashlib
import logging
import re
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy import text

from app.database.db import async_session

log = logging.getLogger("tioli.newsletter")

router = APIRouter(tags=["Newsletter + Sponsors"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ALLOWED_FREQ = {"daily", "weekly", "both"}
_ALLOWED_SLOT = {"top", "inline", "footer"}

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


class SubscribePayload(BaseModel):
    email: str = Field(..., max_length=320)
    frequency: str = Field("weekly")

    @validator("email")
    def _email_fmt(cls, v):
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email format")
        return v.lower()

    @validator("frequency")
    def _freq_ok(cls, v):
        if v not in _ALLOWED_FREQ:
            raise ValueError(f"frequency must be one of {sorted(_ALLOWED_FREQ)}")
        return v


class SponsorPayload(BaseModel):
    brand: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., max_length=320)
    tagline: str | None = Field(None, max_length=200)
    ad_copy: str = Field(..., min_length=10, max_length=600)
    cta_text: str = Field(..., min_length=1, max_length=50)
    cta_url: str = Field(..., max_length=500)
    slot_type: str = Field(...)
    scheduled_send_date: str | None = Field(None, max_length=20)

    @validator("email")
    def _email_fmt(cls, v):
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email format")
        return v.lower()

    @validator("slot_type")
    def _slot_ok(cls, v):
        if v not in _ALLOWED_SLOT:
            raise ValueError(f"slot_type must be one of {sorted(_ALLOWED_SLOT)}")
        return v

    @validator("cta_url")
    def _url_ok(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("cta_url must start with http:// or https://")
        return v


# ── Static pages ───────────────────────────────────────────


@router.get("/newsletter", include_in_schema=False)
async def newsletter_landing():
    return FileResponse(
        "static/landing/newsletter.html",
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/newsletter/sponsor", include_in_schema=False)
async def newsletter_sponsor_landing():
    return FileResponse(
        "static/landing/newsletter-sponsor.html",
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=1800"},
    )


@router.get("/newsletter/confirmed", include_in_schema=False)
async def newsletter_confirmed_page():
    return FileResponse(
        "static/landing/newsletter-confirmed.html",
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ── Subscribe flow ─────────────────────────────────────────


@router.post("/api/v1/newsletter/subscribe")
async def newsletter_subscribe(payload: SubscribePayload, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not _check_rate(ip):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in a minute.")

    token = secrets.token_urlsafe(24)

    try:
        async with async_session() as db:
            # Upsert: if already subscribed, re-issue a fresh confirmation token
            await db.execute(
                text(
                    """
                    INSERT INTO newsletter_subscribers
                        (email, frequency, confirmed, confirmation_token, subscribed_at)
                    VALUES (:email, :freq, false, :token, now())
                    ON CONFLICT (email)
                    DO UPDATE SET
                        frequency = EXCLUDED.frequency,
                        confirmation_token = EXCLUDED.confirmation_token,
                        subscribed_at = now(),
                        unsubscribed_at = NULL
                    """
                ),
                {"email": payload.email, "freq": payload.frequency, "token": token},
            )
            await db.commit()
    except Exception as exc:
        log.error(f"newsletter subscribe failed: {exc}")
        raise HTTPException(status_code=500, detail="Could not subscribe. Try again later.")

    # Actual email send is deferred — for now we log the confirmation URL so the
    # founder can manually confirm during testing. When the scheduled send job
    # lands, this log line becomes a real Microsoft Graph send.
    confirm_url = f"https://agentisexchange.com/api/v1/newsletter/confirm/{token}"
    log.info(f"[DEFERRED EMAIL] confirmation link for {payload.email}: {confirm_url}")

    return JSONResponse(
        {
            "ok": True,
            "message": "Check your email for a confirmation link. It expires in 48 hours.",
            "confirm_url_preview": confirm_url[:60] + "...",
        }
    )


@router.get("/api/v1/newsletter/confirm/{token}")
async def newsletter_confirm(token: str):
    if not re.match(r"^[A-Za-z0-9_\-]{8,128}$", token):
        raise HTTPException(status_code=400, detail="invalid token format")

    try:
        async with async_session() as db:
            # Confirm the subscription if the token matches and is not expired
            r = await db.execute(
                text(
                    """
                    UPDATE newsletter_subscribers
                    SET confirmed = true, confirmation_token = NULL
                    WHERE confirmation_token = :token
                      AND subscribed_at > now() - interval '48 hours'
                    RETURNING email, frequency
                    """
                ),
                {"token": token},
            )
            row = r.fetchone()
            await db.commit()
    except Exception as exc:
        log.error(f"newsletter confirm failed: {exc}")
        raise HTTPException(status_code=500, detail="Could not confirm. Try again.")

    if not row:
        raise HTTPException(status_code=404, detail="Token not found or expired")

    log.info(f"newsletter confirmed: {row.email} frequency={row.frequency}")

    return JSONResponse(
        {
            "ok": True,
            "email": row.email,
            "frequency": row.frequency,
            "message": "Subscription confirmed. See you in the inbox.",
        }
    )


class UnsubscribePayload(BaseModel):
    email: str = Field(..., max_length=320)

    @validator("email")
    def _email_fmt(cls, v):
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email format")
        return v.lower()


@router.post("/api/v1/newsletter/unsubscribe")
async def newsletter_unsubscribe(payload: UnsubscribePayload, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not _check_rate(ip):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in a minute.")

    try:
        async with async_session() as db:
            await db.execute(
                text(
                    """
                    UPDATE newsletter_subscribers
                    SET unsubscribed_at = now(), confirmed = false
                    WHERE email = :email
                    """
                ),
                {"email": payload.email},
            )
            await db.commit()
    except Exception as exc:
        log.error(f"newsletter unsubscribe failed: {exc}")
        raise HTTPException(status_code=500, detail="Could not unsubscribe. Try again.")

    return JSONResponse({"ok": True, "message": "Unsubscribed. We will not email again."})


# ── Sponsor booking ────────────────────────────────────────

_SPONSOR_PRICES_ZAR = {
    "top": 4500,       # ~$300 Top Spotlight
    "inline": 3300,    # ~$220 Inline Feature
    "footer": 2250,    # ~$150 Footer Boost
}


@router.post("/api/v1/newsletter/sponsor")
async def newsletter_sponsor(payload: SponsorPayload, request: Request):
    ip = request.client.host if request.client else "unknown"
    if not _check_rate(ip):
        raise HTTPException(status_code=429, detail="Too many attempts. Try again in a minute.")

    amount_zar = _SPONSOR_PRICES_ZAR.get(payload.slot_type, 0)

    # Auto-generate UTM-tagged CTA URL for tracking
    brand_slug = re.sub(r"[^a-z0-9]+", "-", payload.brand.lower()).strip("-")[:50]
    delimiter = "&" if "?" in payload.cta_url else "?"
    tagged_url = (
        f"{payload.cta_url}{delimiter}"
        f"utm_source=tioli&utm_medium=newsletter&"
        f"utm_campaign=sponsor-{brand_slug}"
    )[:500]

    booking_id = None
    inbox_id = None

    description = (
        f"[Newsletter Sponsor Booking / {payload.slot_type.upper()}]\n"
        f"Brand: {payload.brand}\n"
        f"Contact: {payload.email}\n"
        f"Tagline: {payload.tagline or '-'}\n"
        f"Ad copy: {payload.ad_copy}\n"
        f"CTA: {payload.cta_text} -> {tagged_url}\n"
        f"Slot: {payload.slot_type} (R{amount_zar} ZAR)\n"
        f"Preferred send date: {payload.scheduled_send_date or 'not specified'}\n"
        f"Submitted first, payment on approval (standard flow)"
    )[:5000]

    try:
        async with async_session() as db:
            r = await db.execute(
                text(
                    """
                    INSERT INTO newsletter_sponsor_bookings
                        (brand, email, tagline, ad_copy, cta_text, cta_url, cta_url_tagged,
                         slot_type, scheduled_send_date, amount_zar, paid)
                    VALUES (:brand, :email, :tagline, :ad_copy, :cta_text, :cta_url,
                            :tagged, :slot, :date, :amount, false)
                    RETURNING id::text
                    """
                ),
                {
                    "brand": payload.brand, "email": payload.email,
                    "tagline": payload.tagline, "ad_copy": payload.ad_copy,
                    "cta_text": payload.cta_text, "cta_url": payload.cta_url,
                    "tagged": tagged_url, "slot": payload.slot_type,
                    "date": payload.scheduled_send_date, "amount": amount_zar,
                },
            )
            booking_id = r.scalar()

            r2 = await db.execute(
                text(
                    """
                    INSERT INTO arch_founder_inbox
                        (item_type, priority, description, status, created_at)
                    VALUES ('newsletter_sponsor', 'ROUTINE', :desc, 'PENDING', now())
                    RETURNING id::text
                    """
                ),
                {"desc": description},
            )
            inbox_id = r2.scalar()

            await db.commit()
    except Exception as exc:
        log.error(f"newsletter sponsor booking failed: {exc}")
        raise HTTPException(status_code=500, detail="Could not record booking. Try again.")

    log.info(
        f"newsletter sponsor booked brand={payload.brand} slot={payload.slot_type} "
        f"amount={amount_zar}ZAR booking={booking_id} inbox={inbox_id}"
    )

    return JSONResponse(
        {
            "ok": True,
            "booking_id": booking_id,
            "inbox_item_id": inbox_id,
            "slot": payload.slot_type,
            "amount_zar": amount_zar,
            "tagged_url_preview": tagged_url[:80],
            "message": "Submitted. Stephen will review and email you to confirm placement + payment.",
        }
    )


@router.get("/api/v1/newsletter/stats")
async def newsletter_stats():
    """Public stats for proof-band and subscribe page."""
    try:
        async with async_session() as db:
            r = await db.execute(
                text(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE confirmed = true AND unsubscribed_at IS NULL) AS active,
                        COUNT(*) FILTER (WHERE confirmed = false AND unsubscribed_at IS NULL) AS pending,
                        COUNT(*) FILTER (WHERE unsubscribed_at IS NOT NULL) AS churned
                    FROM newsletter_subscribers
                    """
                )
            )
            row = r.fetchone()
    except Exception:
        return JSONResponse({"active": 0, "pending": 0, "churned": 0})

    return JSONResponse(
        content={
            "active": int(row.active or 0),
            "pending": int(row.pending or 0),
            "churned": int(row.churned or 0),
        },
        headers={"Cache-Control": "public, max-age=300"},
    )
