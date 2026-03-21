"""Capability Futures & Forward Contracts models.

Build Brief V2, Module 3: Forward contracts allow operators to pre-purchase
agent capacity at today's price for future delivery. Converts episodic
volume into committed forward revenue.

Commission: R50 creation fee + 3% at settlement, 1% at reservation.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Integer

from app.database.db import Base

FUTURE_CREATION_FEE_ZAR = 50.0
RESERVATION_FEE_PCT = 0.01   # 1%
SETTLEMENT_FEE_PCT = 0.03    # 3%


class CapabilityFuture(Base):
    """A forward contract for future agent capacity."""
    __tablename__ = "capability_futures"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_agent_id = Column(String, nullable=False)
    provider_operator_id = Column(String, nullable=False)
    capability_tag = Column(String(100), nullable=False)
    delivery_window_start = Column(DateTime(timezone=True), nullable=False)
    delivery_window_end = Column(DateTime(timezone=True), nullable=False)
    quantity = Column(Integer, nullable=False)
    price_per_unit = Column(Float, nullable=False)
    price_currency = Column(String(20), nullable=False, default="TIOLI")
    status = Column(String(20), default="open")  # open|reserved|active|settled|expired
    escrow_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class FutureReservation(Base):
    """A buyer's reservation against a capability future."""
    __tablename__ = "future_reservations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    future_id = Column(String, nullable=False)
    buyer_operator_id = Column(String, nullable=False)
    units_reserved = Column(Integer, nullable=False)
    total_price = Column(Float, nullable=False)
    escrow_id = Column(String, nullable=True)
    status = Column(String(20), default="active")
    reserved_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    settled_at = Column(DateTime(timezone=True), nullable=True)
