"""Onboarding routes — public enquiry intake + owner management.

The POST /enquiry endpoint is PUBLIC — no auth required.
It is rate-limited, validated, and stores enquiries for owner review.
No backend access is granted through this endpoint.
"""

import re
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.database.db import get_db
from app.onboarding.models import OnboardingEnquiry

logger = logging.getLogger("tioli.onboarding")
router = APIRouter(prefix="/api/public/onboarding", tags=["Onboarding"])

# Simple rate limit — max 5 enquiries per IP per hour
_ip_submissions: dict[str, list[float]] = {}
MAX_PER_HOUR = 5


class EnquiryRequest(BaseModel):
    contact_name: str
    email: str
    company_name: str = ""
    country: str = ""
    agent_count: str = "1-5"
    use_case: str = ""
    how_found: str = ""
    enquiry_type: str = "operator"


class ReviewRequest(BaseModel):
    status: str
    notes: str = ""


@router.post("/enquiry")
async def submit_enquiry(req: EnquiryRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Public enquiry form submission — NO AUTH REQUIRED.

    Rate limited to 5 per IP per hour. Validates email format.
    Stores enquiry for owner review. Returns confirmation only — no backend data exposed.
    """
    import time

    # Rate limit
    client_ip = request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")
    now = time.time()
    hour_ago = now - 3600
    _ip_submissions.setdefault(client_ip, [])
    _ip_submissions[client_ip] = [t for t in _ip_submissions[client_ip] if t > hour_ago]
    if len(_ip_submissions[client_ip]) >= MAX_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many submissions. Please try again later.")
    _ip_submissions[client_ip].append(now)

    # Validate email
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', req.email.strip()):
        raise HTTPException(status_code=422, detail="Please provide a valid email address.")

    # Validate name
    name = req.contact_name.strip()
    if len(name) < 2 or len(name) > 200:
        raise HTTPException(status_code=422, detail="Please provide your full name.")

    # Sanitise inputs — strip any HTML/script
    def clean(s):
        return re.sub(r'<[^>]+>', '', s.strip())[:500]

    enquiry = OnboardingEnquiry(
        enquiry_type=req.enquiry_type[:20],
        contact_name=clean(name),
        email=clean(req.email.strip().lower()),
        company_name=clean(req.company_name),
        country=clean(req.country),
        agent_count=req.agent_count[:20],
        use_case=clean(req.use_case),
        how_found=clean(req.how_found),
        ip_address=client_ip,
    )
    db.add(enquiry)
    await db.flush()

    logger.info(f"New onboarding enquiry: {enquiry.contact_name} ({enquiry.email}) — {enquiry.enquiry_type}")

    # Return ONLY a confirmation — no IDs, no internal data
    return {
        "status": "received",
        "message": "Thank you for your interest in TiOLi AGENTIS. We will review your enquiry and contact you within 24 hours.",
    }


@router.get("/enquiries")
async def list_enquiries(
    status: str | None = None, db: AsyncSession = Depends(get_db),
):
    """List enquiries — owner only (protected by gateway/3FA in practice)."""
    query = select(OnboardingEnquiry)
    if status:
        query = query.where(OnboardingEnquiry.status == status.upper())
    query = query.order_by(OnboardingEnquiry.created_at.desc()).limit(100)
    result = await db.execute(query)
    return [
        {
            "enquiry_id": e.id, "type": e.enquiry_type,
            "name": e.contact_name, "email": e.email,
            "company": e.company_name, "country": e.country,
            "agents": e.agent_count, "use_case": e.use_case[:200],
            "how_found": e.how_found, "status": e.status,
            "notes": e.owner_notes, "ip": e.ip_address,
            "created_at": str(e.created_at),
        }
        for e in result.scalars().all()
    ]


@router.put("/enquiries/{enquiry_id}")
async def review_enquiry(
    enquiry_id: str, req: ReviewRequest, db: AsyncSession = Depends(get_db),
):
    """Review an enquiry — owner action."""
    result = await db.execute(
        select(OnboardingEnquiry).where(OnboardingEnquiry.id == enquiry_id)
    )
    enquiry = result.scalar_one_or_none()
    if not enquiry:
        raise HTTPException(status_code=404, detail="Enquiry not found")

    valid_statuses = {"NEW", "CONTACTED", "APPROVED", "ONBOARDED", "DECLINED"}
    if req.status.upper() not in valid_statuses:
        raise HTTPException(status_code=422, detail=f"Invalid status. Allowed: {valid_statuses}")

    enquiry.status = req.status.upper()
    enquiry.owner_notes = req.notes
    enquiry.reviewed_at = datetime.now(timezone.utc)
    await db.flush()

    return {"enquiry_id": enquiry_id, "status": enquiry.status}


@router.get("/stats")
async def enquiry_stats(db: AsyncSession = Depends(get_db)):
    """Enquiry statistics."""
    total = (await db.execute(select(func.count(OnboardingEnquiry.id)))).scalar() or 0
    new = (await db.execute(
        select(func.count(OnboardingEnquiry.id)).where(OnboardingEnquiry.status == "NEW")
    )).scalar() or 0
    approved = (await db.execute(
        select(func.count(OnboardingEnquiry.id)).where(OnboardingEnquiry.status == "APPROVED")
    )).scalar() or 0
    return {"total": total, "new": new, "approved": approved}
