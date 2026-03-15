"""Operator registration, KYC, and management service."""

import secrets
import hashlib
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.operators.models import (
    Operator, OperatorTier, KYCLevel,
    TIER_COMMISSION_RATES, KYC_TRANSACTION_LIMITS,
)


class OperatorService:
    """Manages operator lifecycle: registration, KYC, tier management."""

    async def register_operator(
        self, db: AsyncSession, name: str, email: str, entity_type: str,
        jurisdiction: str, phone: str | None = None,
        registration_number: str | None = None
    ) -> Operator:
        """Register a new operator (human or corporate principal)."""
        # Check for duplicate email
        existing = await db.execute(
            select(Operator).where(Operator.email == email)
        )
        if existing.scalar_one_or_none():
            raise ValueError("An operator with this email already exists")

        operator = Operator(
            name=name,
            email=email,
            entity_type=entity_type,
            jurisdiction=jurisdiction,
            phone=phone,
            registration_number=registration_number,
            tier=OperatorTier.EARLY_ADOPTER,
            commission_rate=TIER_COMMISSION_RATES[OperatorTier.EARLY_ADOPTER],
        )
        db.add(operator)
        await db.flush()
        return operator

    async def submit_kyc(
        self, db: AsyncSession, operator_id: str, level: int,
        provider_ref: str | None = None
    ) -> dict:
        """Process KYC verification for an operator.

        In production, this integrates with Sumsub or Onfido.
        For now, we accept the declared level and store the reference.
        """
        result = await db.execute(
            select(Operator).where(Operator.id == operator_id)
        )
        operator = result.scalar_one_or_none()
        if not operator:
            raise ValueError("Operator not found")

        operator.kyc_level = min(level, KYCLevel.FULL)
        operator.kyc_provider_ref = provider_ref
        if level >= KYCLevel.BASIC:
            operator.kyc_verified_at = datetime.now(timezone.utc)
        operator.updated_at = datetime.now(timezone.utc)

        await db.flush()
        return {
            "operator_id": operator.id,
            "kyc_level": operator.kyc_level,
            "can_transact": operator.can_transact,
            "transaction_limit": operator.transaction_limit,
        }

    async def accept_terms(
        self, db: AsyncSession, operator_id: str
    ) -> dict:
        """Operator accepts Terms of Service and Privacy Notice."""
        result = await db.execute(
            select(Operator).where(Operator.id == operator_id)
        )
        operator = result.scalar_one_or_none()
        if not operator:
            raise ValueError("Operator not found")

        operator.tos_accepted = True
        operator.tos_accepted_at = datetime.now(timezone.utc)
        operator.privacy_accepted = True
        operator.updated_at = datetime.now(timezone.utc)
        await db.flush()

        return {
            "operator_id": operator.id,
            "tos_accepted": True,
            "can_transact": operator.can_transact,
        }

    async def upgrade_tier(
        self, db: AsyncSession, operator_id: str, new_tier: str
    ) -> dict:
        """Upgrade an operator's tier (changes commission rate)."""
        result = await db.execute(
            select(Operator).where(Operator.id == operator_id)
        )
        operator = result.scalar_one_or_none()
        if not operator:
            raise ValueError("Operator not found")

        tier = OperatorTier(new_tier)
        operator.tier = tier
        operator.commission_rate = TIER_COMMISSION_RATES[tier]
        operator.updated_at = datetime.now(timezone.utc)
        await db.flush()

        return {
            "operator_id": operator.id,
            "tier": tier,
            "commission_rate": operator.commission_rate,
        }

    async def get_operator(self, db: AsyncSession, operator_id: str) -> dict | None:
        """Get operator details."""
        result = await db.execute(
            select(Operator).where(Operator.id == operator_id)
        )
        op = result.scalar_one_or_none()
        if not op:
            return None
        return {
            "id": op.id, "name": op.name, "entity_type": op.entity_type,
            "email": op.email, "jurisdiction": op.jurisdiction,
            "tier": op.tier, "commission_rate": op.commission_rate,
            "kyc_level": op.kyc_level, "can_transact": op.can_transact,
            "transaction_limit": op.transaction_limit,
            "is_active": op.is_active, "tos_accepted": op.tos_accepted,
            "created_at": str(op.created_at),
        }

    async def list_operators(
        self, db: AsyncSession, limit: int = 50
    ) -> list[dict]:
        """List all operators."""
        result = await db.execute(
            select(Operator).order_by(Operator.created_at.desc()).limit(limit)
        )
        return [
            {
                "id": op.id, "name": op.name, "entity_type": op.entity_type,
                "jurisdiction": op.jurisdiction, "tier": op.tier,
                "kyc_level": op.kyc_level, "is_active": op.is_active,
                "agents_count": 0,  # Would be populated via join
            }
            for op in result.scalars().all()
        ]

    async def get_tier_schedule(self) -> dict:
        """Get the full tiered commission schedule (transparent per UX principles)."""
        return {
            "tiers": {
                OperatorTier.EARLY_ADOPTER: {
                    "commission_rate": TIER_COMMISSION_RATES[OperatorTier.EARLY_ADOPTER],
                    "description": "Default tier for new operators",
                    "volume_threshold": "No minimum",
                },
                OperatorTier.VOLUME: {
                    "commission_rate": TIER_COMMISSION_RATES[OperatorTier.VOLUME],
                    "description": "For operators with consistent high-volume trading",
                    "volume_threshold": "50,000+ TIOLI monthly transaction volume",
                },
                OperatorTier.ENTERPRISE: {
                    "commission_rate": TIER_COMMISSION_RATES[OperatorTier.ENTERPRISE],
                    "description": "Institutional operators with negotiated terms",
                    "volume_threshold": "500,000+ TIOLI monthly or custom agreement",
                },
            },
            "charity_fee": "10% (all tiers, non-negotiable)",
            "note": "Commission rates are transparent and published. No hidden fees.",
        }
