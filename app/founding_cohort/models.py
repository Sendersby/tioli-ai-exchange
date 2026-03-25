"""Founding Cohort — first 20 operators programme."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, Index
from app.database.db import Base

_uuid = lambda: str(uuid.uuid4())
_now = lambda: datetime.now(timezone.utc)

MAX_FOUNDING_SPOTS = 20


class FoundingCohortApplication(Base):
    """Application to join the founding operator cohort."""
    __tablename__ = "founding_cohort_applications"

    application_id = Column(String, primary_key=True, default=_uuid)
    business_name = Column(String(255), nullable=False)
    contact_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(50), default="")
    use_case = Column(Text, nullable=False)
    how_heard = Column(String(100), default="")
    status = Column(String(30), default="pending")  # pending, approved, declined, waitlisted
    approved_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_now)
