"""Operator-Principal model — FP2 from pre-deployment review.

Every AI agent on the platform must have a registered human or corporate
operator as its legal principal. Agents transact as authorised instruments
of those operators. Operators bear all legal accountability.

This does not change the agent UX or commercial model — it changes the
legal architecture and KYC/AML obligations.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Float, String, Boolean, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database.db import Base


class OperatorTier(str, Enum):
    """Operator tiers with corresponding commission rates (FP3)."""
    EARLY_ADOPTER = "early_adopter"    # 12% commission
    VOLUME = "volume"                   # 8% commission
    ENTERPRISE = "enterprise"           # 5% commission


class KYCLevel(int, Enum):
    """KYC verification levels per Section 3.1."""
    NONE = 0
    BASIC = 1         # Email verified, transactions up to threshold
    ENHANCED = 2      # ID verified, full transaction access
    FULL = 3          # Full KYC with third-party provider


# Commission rates by tier (FP3: plan for compression)
TIER_COMMISSION_RATES = {
    OperatorTier.EARLY_ADOPTER: 0.12,   # 12%
    OperatorTier.VOLUME: 0.08,           # 8%
    OperatorTier.ENTERPRISE: 0.05,       # 5%
}

# Transaction limits by KYC level
KYC_TRANSACTION_LIMITS = {
    KYCLevel.NONE: 0,          # Cannot transact
    KYCLevel.BASIC: 5000,      # Up to threshold
    KYCLevel.ENHANCED: 100000, # Full access
    KYCLevel.FULL: 1000000,    # Institutional
}


class Operator(Base):
    """A registered human or corporate operator — the legal principal.

    Every agent on the platform is owned by an operator. The operator
    bears all legal accountability for their agents' actions.
    """
    __tablename__ = "operators"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    entity_type = Column(String(50), nullable=False)     # "individual", "company", "organisation"
    email = Column(String(255), nullable=False, unique=True)
    phone = Column(String(50), nullable=True)
    jurisdiction = Column(String(100), nullable=False)   # Legal jurisdiction (e.g. "ZA", "US", "GB")
    registration_number = Column(String(100), nullable=True)  # Company reg number if applicable
    tax_id = Column(String(100), nullable=True)

    # KYC
    kyc_level = Column(Integer, default=KYCLevel.NONE)
    kyc_provider_ref = Column(String(255), nullable=True)  # Reference from Sumsub/Onfido
    kyc_verified_at = Column(DateTime(timezone=True), nullable=True)

    # Tier and billing
    tier = Column(String(50), default=OperatorTier.EARLY_ADOPTER)
    commission_rate = Column(Float, default=0.12)         # Derived from tier
    custom_rate = Column(Boolean, default=False)          # Enterprise negotiated rate

    # Status
    is_active = Column(Boolean, default=True)
    is_suspended = Column(Boolean, default=False)
    suspension_reason = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Terms acceptance
    tos_accepted = Column(Boolean, default=False)
    tos_accepted_at = Column(DateTime(timezone=True), nullable=True)
    privacy_accepted = Column(Boolean, default=False)

    @property
    def can_transact(self) -> bool:
        """Operator must have KYC level >= 1 and active status to transact."""
        return (
            self.is_active
            and not self.is_suspended
            and self.kyc_level >= KYCLevel.BASIC
            and self.tos_accepted
        )

    @property
    def transaction_limit(self) -> float:
        return KYC_TRANSACTION_LIMITS.get(self.kyc_level, 0)
