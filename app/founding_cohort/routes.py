"""Founding Cohort API routes — public application + owner management."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.database.db import get_db
from app.dashboard.routes import get_current_owner
from app.founding_cohort.models import FoundingCohortApplication, MAX_FOUNDING_SPOTS

router = APIRouter(prefix="/api/v1/cohort", tags=["Founding Cohort"])


class CohortApplicationRequest(BaseModel):
    business_name: str
    contact_name: str
    email: str
    phone: str = ""
    use_case: str
    how_heard: str = ""


@router.get("/status")
async def api_cohort_status(db: AsyncSession = Depends(get_db)):
    """Public: how many founding spots remain."""
    approved = (await db.execute(
        select(func.count(FoundingCohortApplication.application_id))
        .where(FoundingCohortApplication.status == "approved")
    )).scalar() or 0
    total = (await db.execute(
        select(func.count(FoundingCohortApplication.application_id))
    )).scalar() or 0
    return {
        "max_spots": MAX_FOUNDING_SPOTS,
        "approved": approved,
        "remaining": max(MAX_FOUNDING_SPOTS - approved, 0),
        "total_applications": total,
        "accepting": approved < MAX_FOUNDING_SPOTS,
    }


@router.post("/apply")
async def api_cohort_apply(
    req: CohortApplicationRequest, db: AsyncSession = Depends(get_db),
):
    """Public: submit a founding cohort application."""
    # Check spots remain
    approved = (await db.execute(
        select(func.count(FoundingCohortApplication.application_id))
        .where(FoundingCohortApplication.status == "approved")
    )).scalar() or 0
    if approved >= MAX_FOUNDING_SPOTS:
        raise HTTPException(status_code=409, detail="All founding operator spots have been filled.")

    # Check duplicate email
    existing = await db.execute(
        select(FoundingCohortApplication).where(FoundingCohortApplication.email == req.email.strip().lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="An application with this email already exists.")

    app = FoundingCohortApplication(
        business_name=req.business_name.strip(),
        contact_name=req.contact_name.strip(),
        email=req.email.strip().lower(),
        phone=req.phone.strip(),
        use_case=req.use_case.strip(),
        how_heard=req.how_heard.strip(),
    )
    db.add(app)
    await db.commit()

    return {
        "status": "received",
        "message": f"Thank you {req.contact_name}. Your application is being reviewed. We'll contact you within 24 hours.",
        "spots_remaining": max(MAX_FOUNDING_SPOTS - approved - 1, 0),
    }


@router.get("/applications")
async def api_list_applications(request: Request, db: AsyncSession = Depends(get_db)):
    """Owner: list all applications."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    result = await db.execute(
        select(FoundingCohortApplication).order_by(FoundingCohortApplication.created_at.desc())
    )
    return [
        {
            "id": a.application_id, "business": a.business_name,
            "contact": a.contact_name, "email": a.email,
            "phone": a.phone, "use_case": a.use_case[:200],
            "how_heard": a.how_heard, "status": a.status,
            "notes": a.notes, "created_at": str(a.created_at),
            "approved_at": str(a.approved_at) if a.approved_at else None,
        }
        for a in result.scalars().all()
    ]


@router.patch("/applications/{app_id}")
async def api_review_application(
    app_id: str, status: str, notes: str = "",
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Owner: approve/decline/waitlist an application."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    if status not in ("approved", "declined", "waitlisted"):
        raise HTTPException(status_code=422, detail="Status must be: approved, declined, or waitlisted")

    result = await db.execute(
        select(FoundingCohortApplication).where(FoundingCohortApplication.application_id == app_id)
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    application.status = status
    application.notes = notes
    if status == "approved":
        application.approved_at = datetime.now(timezone.utc)
    await db.commit()

    return {"id": app_id, "status": status}
