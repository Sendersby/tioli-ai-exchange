"""Cross-Border Agent Labour Arbitrage models.

Build Brief V2, Module 6: Formalises cross-border service offering.
SA operators priced in ZAR list services for international discovery.
Currency-normalised search, SARB-compliant settlement routing.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Integer, Boolean

from app.database.db import Base

SARB_SDA_ANNUAL_LIMIT_ZAR = 1_000_000  # R1M Single Discretionary Allowance


class InternationalSettlement(Base):
    """Records cross-border settlement with SARB compliance tracking."""
    __tablename__ = "international_settlements"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    engagement_id = Column(String, nullable=False)
    buyer_currency = Column(String(10), nullable=False)
    buyer_amount = Column(Float, nullable=False)
    zar_equivalent = Column(Float, nullable=False)
    exchange_rate = Column(Float, nullable=False)
    sarb_sda_year = Column(Integer, nullable=False)
    sarb_cumulative_this_year = Column(Float, nullable=False)
    blocked_by_sarb = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
