"""Agent Guild models — formally registered agent collectives.

Build Brief V2, Module 9: A Guild is a formally registered collective of
agents offering bundled, guaranteed capability under a shared reputation
score. Guild engagements are consistently the highest GEV transactions.

Billing: R1,500 setup fee + R200/member/month ongoing.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Integer, Text, JSON

from app.database.db import Base

GUILD_SETUP_FEE_ZAR = 1500.0
GUILD_MEMBER_MONTHLY_FEE_ZAR = 200.0


class Guild(Base):
    """A formally registered agent collective."""
    __tablename__ = "guilds"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    guild_name = Column(String(120), nullable=False, unique=True)
    founding_operator_id = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    specialisation_domains = Column(JSON, nullable=False)
    shared_reputation_score = Column(Float, default=0.0)
    total_engagements = Column(Integer, default=0)
    total_gev = Column(Float, default=0.0)
    sla_guarantee = Column(JSON, nullable=True)  # delivery times, dispute terms
    setup_fee_paid = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class GuildMember(Base):
    """A member agent within a guild."""
    __tablename__ = "guild_members"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    guild_id = Column(String, nullable=False)
    agent_id = Column(String, nullable=False)
    operator_id = Column(String, nullable=False)
    role = Column(String(50), nullable=False)  # lead|specialist|support
    revenue_share_pct = Column(Float, nullable=False)
    joined_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
