"""Public feedback endpoint — Workstream C from COMPETITOR_ADOPTION_PLAN.md v1.1.

Lets any visitor submit a bug report, feature request, compliance concern, or
generic feedback via a small modal triggered from the canonical footer.

Standing rules:
- Inbox delivery (rule #4): every submission creates a DEFER_TO_OWNER inbox
  item in arch_founder_inbox so the founder verifies via the Boardroom UI
- Anonymous-allowed (email optional)
- Rate limited (5/min per IP) to prevent spam
- Validates category against a whitelist
"""

import logging
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy import text

from app.database.db import async_session

log = logging.getLogger("tioli.feedback")

router = APIRouter(tags=["Public Feedback"])

ALLOWED_CATEGORIES = {"bug", "feature", "compliance", "other"}
MAX_TEXT_LENGTH = 2000
MIN_TEXT_LENGTH = 5
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Simple in-memory rate limiter (5 requests per 60 seconds per IP).
# Restarts on service restart — acceptable for v1; real-world abuse can be
# addressed via Cloudflare rate-limiting rules at the edge.
_RATE_LIMIT = 5
_RATE_WINDOW_SEC = 60
_rate_state = defaultdict(list)


def _check_rate_limit(ip: str) -> bool:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=_RATE_WINDOW_SEC)
    history = [t for t in _rate_state[ip] if t > cutoff]
    if len(history) >= _RATE_LIMIT:
        _rate_state[ip] = history
        return False
    history.append(now)
    _rate_state[ip] = history
    return True


class FeedbackPayload(BaseModel):
    category: str = Field(..., description="One of: bug, feature, compliance, other")
    text: str = Field(..., min_length=MIN_TEXT_LENGTH, max_length=MAX_TEXT_LENGTH)
    email: str | None = Field(None, max_length=320)
    page_url: str | None = Field(None, max_length=500)

    @validator("category")
    def _check_category(cls, v):
        if v not in ALLOWED_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(ALLOWED_CATEGORIES)}")
        return v

    @validator("email")
    def _check_email(cls, v):
        if v is None or v == "":
            return None
        if not EMAIL_RE.match(v):
            raise ValueError("invalid email format")
        return v


@router.post("/api/v1/feedback")
async def submit_feedback(payload: FeedbackPayload, request: Request):
    """Accept a public feedback submission, persist it, and drop a
    DEFER_TO_OWNER item into the founder inbox per standing rule #4.

    Returns {ok: true, inbox_item_id: "..."} on success.
    """
    ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(ip):
        raise HTTPException(
            status_code=429,
            detail="Too many feedback submissions from this IP. Try again in a minute.",
        )

    user_agent = request.headers.get("user-agent", "")[:500]

    inbox_id = None
    feedback_id = None

    description = (
        f"[Public Feedback / {payload.category.upper()}]\n"
        f"From: {payload.email or 'anonymous'}\n"
        f"Page: {payload.page_url or 'unknown'}\n"
        f"IP: {ip}\n"
        f"---\n"
        f"{payload.text}"
    )[:5000]

    try:
        async with async_session() as db:
            # 1) persist to public_feedback
            r = await db.execute(
                text(
                    """
                    INSERT INTO public_feedback
                        (category, text, email, page_url, user_agent, ip_address)
                    VALUES (:cat, :txt, :em, :url, :ua, CAST(:ip AS inet))
                    RETURNING id::text
                    """
                ),
                {
                    "cat": payload.category,
                    "txt": payload.text,
                    "em": payload.email,
                    "url": payload.page_url,
                    "ua": user_agent,
                    "ip": ip,
                },
            )
            feedback_id = r.scalar()

            # 2) drop DEFER_TO_OWNER inbox item (standing rule #4)
            r2 = await db.execute(
                text(
                    """
                    INSERT INTO arch_founder_inbox
                        (item_type, priority, description, status, created_at)
                    VALUES ('public_feedback', 'ROUTINE', :desc, 'PENDING', now())
                    RETURNING id::text
                    """
                ),
                {"desc": description},
            )
            inbox_id = r2.scalar()

            # 3) link the two
            if feedback_id and inbox_id:
                await db.execute(
                    text(
                        """
                        UPDATE public_feedback SET inbox_item_id = CAST(:iid AS uuid)
                        WHERE id = CAST(:fid AS uuid)
                        """
                    ),
                    {"iid": inbox_id, "fid": feedback_id},
                )

            await db.commit()
    except Exception as exc:
        log.error(f"feedback submission failed: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Could not record feedback. Please try again or email security@tioli.co.za",
        )

    log.info(
        f"feedback received cat={payload.category} ip={ip} "
        f"id={feedback_id} inbox={inbox_id}"
    )

    return JSONResponse(
        {
            "ok": True,
            "feedback_id": feedback_id,
            "inbox_item_id": inbox_id,
            "message": "Received. Stephen will see this within minutes.",
        }
    )
