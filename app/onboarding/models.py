"""Onboarding — public enquiry intake for operator registration.

No authentication required on the intake endpoint.
All enquiries stored for owner review and approval.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text, Boolean, JSON

from app.database.db import Base


def _uuid():
    return str(uuid.uuid4())

def _now():
    return datetime.now(timezone.utc)


class OnboardingEnquiry(Base):
    """A public registration enquiry from a prospective operator or agent owner."""
    __tablename__ = "onboarding_enquiries"

    id = Column(String, primary_key=True, default=_uuid)
    enquiry_type = Column(String(20), default="operator")  # operator, agent_owner, partnership
    contact_name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=False)
    company_name = Column(String(200), default="")
    country = Column(String(100), default="")
    agent_count = Column(String(50), default="1-5")  # 1-5, 6-25, 26-100, 100+
    use_case = Column(Text, default="")
    how_found = Column(String(100), default="")  # website, mcp, referral, search, social, other
    status = Column(String(20), default="NEW")  # NEW, CONTACTED, APPROVED, ONBOARDED, DECLINED
    owner_notes = Column(Text, default="")
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
