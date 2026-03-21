"""Commercial Licensing Framework — Phase 3 groundwork.

Build Brief V2, Section 2.5: Data structures and pricing defined now.
No active billing logic — owner 3FA approval required before activation.

API licence: R50,000 setup + 1% GTV
White-label: R100,000 setup + R15,000/mo + 0.5% GTV
SDK partner: R10,000/year + revenue share
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Text

from app.database.db import Base


class CommercialLicence(Base):
    """A commercial licence granted to a third party."""
    __tablename__ = "commercial_licences"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    licensee_name = Column(String(255), nullable=False)
    licence_type = Column(String(50), nullable=False)  # api|white_label|sdk|regional
    setup_fee_zar = Column(Float, nullable=False)
    monthly_fee_zar = Column(Float, default=0.0)
    revenue_share_pct = Column(Float, default=0.0)
    territory = Column(String(100), nullable=True)
    status = Column(String(20), default="draft")  # draft|pending_approval|active|suspended|terminated
    signed_at = Column(DateTime, nullable=True)
    activated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# Licence type pricing schedule (for reference — not auto-billed yet)
LICENCE_PRICING = {
    "api": {
        "setup_fee_zar": 50_000,
        "monthly_fee_zar": 0,
        "revenue_share_pct": 0.01,  # 1% of GTV
        "description": "API access licence — full platform API for third-party integration.",
    },
    "white_label": {
        "setup_fee_zar": 100_000,
        "monthly_fee_zar": 15_000,
        "revenue_share_pct": 0.005,  # 0.5% of GTV
        "description": "Full platform deployment under licensee branding.",
    },
    "sdk": {
        "setup_fee_zar": 10_000,
        "monthly_fee_zar": 0,
        "revenue_share_pct": 0.0,  # Revenue share on referred operators
        "description": "SDK integration partner listing + revenue share on referrals.",
    },
    "regional": {
        "setup_fee_zar": 75_000,
        "monthly_fee_zar": 10_000,
        "revenue_share_pct": 0.02,  # 2% of regional GTV
        "description": "Regional exclusivity licence for specified territory.",
    },
}
