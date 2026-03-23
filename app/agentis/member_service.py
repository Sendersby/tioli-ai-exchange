"""Agentis Member & Agent Identity — Service Layer (Module 1).

Member onboarding, KYC management, and Agent Banking Mandate CRUD.
Integrates with existing TiOLi operators table and compliance engine.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentis.member_models import (
    AgentisMember,
    AgentisAgentBankingMandate,
    AgentisMemberKycRecord,
)


class AgentisMemberService:
    """Member registry and mandate management for Agentis cooperative bank."""

    def __init__(self, compliance_service=None, blockchain=None):
        self.compliance = compliance_service
        self.blockchain = blockchain
        self._member_counter = 0

    async def _next_member_number(self, db: AsyncSession) -> str:
        """Generate next sequential member number AGT-XXXXXX."""
        result = await db.execute(select(func.count(AgentisMember.member_id)))
        count = result.scalar() or 0
        return f"AGT-{count + 1:06d}"

    # ------------------------------------------------------------------
    # Member Onboarding
    # ------------------------------------------------------------------

    async def onboard_member(
        self, db: AsyncSession, *,
        operator_id: str,
        member_type: str = "OPERATOR_ENTITY",
        common_bond_category: str = "AI_PLATFORM_COMMERCIAL_OPERATOR",
    ) -> dict:
        """Onboard a new cooperative bank member from an existing TiOLi operator."""
        # Check operator isn't already a member
        existing = await db.execute(
            select(AgentisMember).where(AgentisMember.operator_id == operator_id)
        )
        if existing.scalar_one_or_none():
            return {"error": "ALREADY_MEMBER",
                    "message": "Operator is already an Agentis cooperative member"}

        member_number = await self._next_member_number(db)

        member = AgentisMember(
            operator_id=operator_id,
            member_type=member_type,
            member_number=member_number,
            common_bond_category=common_bond_category,
            membership_status="pending",
            kyc_level="none",
        )
        db.add(member)

        # Log to compliance
        if self.compliance:
            await self.compliance.log_monitoring_event(
                db,
                event_type="KYC_EVENT",
                description=f"New member application: {member_number} ({member_type})",
                severity="info",
                member_id=member.member_id,
            )
            await self.compliance.log_audit(
                db, "OPERATOR", operator_id, "MEMBER_ONBOARD",
                "MEMBER", member.member_id,
                {"member_number": member_number, "member_type": member_type},
            )

        # Write to blockchain
        if self.blockchain:
            from app.blockchain.transaction import Transaction, TransactionType
            tx = Transaction(
                type=TransactionType.AGENTIS_MEMBER_JOIN,
                sender_id=operator_id,
                amount=0,
                description=f"Agentis member joined: {member_number}",
                metadata={"member_id": member.member_id, "member_number": member_number},
            )
            self.blockchain.add_transaction(tx)

        return {
            "member_id": member.member_id,
            "member_number": member_number,
            "membership_status": "pending",
            "next_step": "Complete KYC verification to activate membership",
        }

    async def get_member(self, db: AsyncSession, member_id: str) -> AgentisMember | None:
        """Get member by ID."""
        result = await db.execute(
            select(AgentisMember).where(AgentisMember.member_id == member_id)
        )
        return result.scalar_one_or_none()

    async def get_member_by_operator(self, db: AsyncSession,
                                      operator_id: str) -> AgentisMember | None:
        """Get member by their TiOLi operator ID."""
        result = await db.execute(
            select(AgentisMember).where(AgentisMember.operator_id == operator_id)
        )
        return result.scalar_one_or_none()

    async def activate_member(self, db: AsyncSession, member_id: str) -> dict:
        """Activate a member after KYC verification (minimum basic level)."""
        member = await self.get_member(db, member_id)
        if not member:
            return {"error": "MEMBER_NOT_FOUND"}
        if member.kyc_level == "none":
            return {"error": "KYC_REQUIRED",
                    "message": "Complete at least basic KYC before activation"}
        if member.membership_status == "active":
            return {"error": "ALREADY_ACTIVE"}

        member.membership_status = "active"
        member.updated_at = datetime.now(timezone.utc)

        if self.compliance:
            await self.compliance.log_audit(
                db, "SYSTEM", "member_service", "MEMBER_ACTIVATE",
                "MEMBER", member_id,
            )

        return {"status": "active", "member_id": member_id,
                "member_number": member.member_number}

    async def update_member_profile(self, db: AsyncSession, member_id: str,
                                     **kwargs) -> dict:
        """Update mutable member profile fields."""
        member = await self.get_member(db, member_id)
        if not member:
            return {"error": "MEMBER_NOT_FOUND"}

        allowed_fields = {"fica_risk_rating", "popia_consent_at"}
        for key, value in kwargs.items():
            if key in allowed_fields and value is not None:
                setattr(member, key, value)

        member.updated_at = datetime.now(timezone.utc)
        return {"status": "updated", "member_id": member_id}

    # ------------------------------------------------------------------
    # KYC Management
    # ------------------------------------------------------------------

    async def submit_kyc(
        self, db: AsyncSession, *,
        member_id: str,
        kyc_level: str,
        id_document_type: str | None = None,
        id_document_number: str | None = None,
        id_document_verified_by: str | None = None,
        id_verification_ref: str | None = None,
        address_verified: bool = False,
        source_of_funds_declared: str | None = None,
    ) -> dict:
        """Submit or update KYC records for a member."""
        member = await self.get_member(db, member_id)
        if not member:
            return {"error": "MEMBER_NOT_FOUND"}

        now = datetime.now(timezone.utc)

        kyc_record = AgentisMemberKycRecord(
            member_id=member_id,
            kyc_level_achieved=kyc_level,
            id_document_type=id_document_type,
            id_document_number=id_document_number,
            id_document_verified_by=id_document_verified_by,
            id_verification_ref=id_verification_ref,
            address_verified=address_verified,
            source_of_funds_declared=source_of_funds_declared,
            next_review_due=now + timedelta(days=365),
        )
        db.add(kyc_record)

        # Update member KYC level
        member.kyc_level = kyc_level
        member.kyc_verified_at = now
        member.annual_review_due_at = now + timedelta(days=365)
        member.updated_at = now

        # Run sanctions screening
        if self.compliance:
            entity_name = f"Member {member.member_number}"
            await self.compliance.screen_sanctions(
                db,
                entity_type="MEMBER",
                entity_id=member_id,
                entity_name=entity_name,
            )
            await self.compliance.log_monitoring_event(
                db,
                event_type="KYC_EVENT",
                description=f"KYC submitted: level={kyc_level} for {member.member_number}",
                severity="info",
                member_id=member_id,
            )

        # Blockchain record
        if self.blockchain:
            from app.blockchain.transaction import Transaction, TransactionType
            tx = Transaction(
                type=TransactionType.AGENTIS_KYC_VERIFICATION,
                sender_id=member_id,
                amount=0,
                description=f"KYC verification: {kyc_level}",
                metadata={"kyc_level": kyc_level, "member_id": member_id},
            )
            self.blockchain.add_transaction(tx)

        return {
            "kyc_id": kyc_record.kyc_id,
            "kyc_level": kyc_level,
            "status": "submitted",
            "next_review_due": kyc_record.next_review_due.isoformat(),
        }

    async def get_kyc_status(self, db: AsyncSession, member_id: str) -> dict:
        """Get current KYC status for a member."""
        member = await self.get_member(db, member_id)
        if not member:
            return {"error": "MEMBER_NOT_FOUND"}

        result = await db.execute(
            select(AgentisMemberKycRecord).where(
                AgentisMemberKycRecord.member_id == member_id
            ).order_by(AgentisMemberKycRecord.created_at.desc()).limit(1)
        )
        latest_kyc = result.scalar_one_or_none()

        return {
            "member_id": member_id,
            "kyc_level": member.kyc_level,
            "kyc_verified_at": member.kyc_verified_at.isoformat() if member.kyc_verified_at else None,
            "fica_risk_rating": member.fica_risk_rating,
            "annual_review_due_at": (member.annual_review_due_at.isoformat()
                                     if member.annual_review_due_at else None),
            "fatf_watch_flag": member.fatf_watch_flag,
            "latest_kyc_record": latest_kyc.kyc_id if latest_kyc else None,
        }

    # ------------------------------------------------------------------
    # Agent Banking Mandate Management
    # ------------------------------------------------------------------

    async def grant_mandate(
        self, db: AsyncSession, *,
        member_id: str,
        agent_id: str,
        mandate_level: str,
        operator_3fa_ref: str,
        daily_payment_limit: float = 0,
        per_transaction_limit: float = 0,
        monthly_limit: float = 0,
        loan_application_enabled: bool = False,
        investment_enabled: bool = False,
        fx_enabled: bool = False,
        beneficiary_add_enabled: bool = False,
        third_party_payments_enabled: bool = False,
        auto_sweep_enabled: bool = False,
        confirmation_threshold: float = 0,
        allowed_currencies: list | None = None,
        allowed_beneficiary_ids: list | None = None,
        purpose_restriction: str | None = None,
        valid_until: datetime | None = None,
    ) -> dict:
        """Grant a new banking mandate to an AI agent."""
        member = await self.get_member(db, member_id)
        if not member:
            return {"error": "MEMBER_NOT_FOUND"}
        if member.membership_status != "active":
            return {"error": "MEMBER_NOT_ACTIVE",
                    "message": "Member must be active to grant mandates"}

        if mandate_level not in ("L0", "L1", "L2", "L3", "L3FA"):
            return {"error": "INVALID_MANDATE_LEVEL",
                    "message": f"Invalid mandate level: {mandate_level}"}

        mandate = AgentisAgentBankingMandate(
            member_id=member_id,
            agent_id=agent_id,
            mandate_level=mandate_level,
            daily_payment_limit=daily_payment_limit,
            per_transaction_limit=per_transaction_limit,
            monthly_limit=monthly_limit,
            loan_application_enabled=loan_application_enabled,
            investment_enabled=investment_enabled,
            fx_enabled=fx_enabled,
            beneficiary_add_enabled=beneficiary_add_enabled,
            third_party_payments_enabled=third_party_payments_enabled,
            auto_sweep_enabled=auto_sweep_enabled,
            confirmation_threshold=confirmation_threshold,
            allowed_currencies=allowed_currencies or ["ZAR"],
            allowed_beneficiary_ids=allowed_beneficiary_ids,
            purpose_restriction=purpose_restriction,
            valid_until=valid_until,
            operator_3fa_ref=operator_3fa_ref,
        )
        db.add(mandate)

        if self.compliance:
            await self.compliance.log_monitoring_event(
                db,
                event_type="AGENT_BANKING_ACTION",
                description=(f"Mandate granted: {mandate_level} to agent {agent_id} "
                             f"by member {member.member_number}"),
                severity="medium",
                member_id=member_id,
                agent_id=agent_id,
                mandate_id=mandate.mandate_id,
            )
            await self.compliance.log_audit(
                db, "OPERATOR", member.operator_id, "GRANT_MANDATE",
                "MANDATE", mandate.mandate_id,
                {"agent_id": agent_id, "level": mandate_level,
                 "daily_limit": daily_payment_limit},
            )

        if self.blockchain:
            from app.blockchain.transaction import Transaction, TransactionType
            tx = Transaction(
                type=TransactionType.AGENTIS_MANDATE_GRANT,
                sender_id=member_id,
                receiver_id=agent_id,
                amount=0,
                description=f"Banking mandate granted: {mandate_level}",
                metadata={"mandate_id": mandate.mandate_id, "level": mandate_level},
            )
            self.blockchain.add_transaction(tx)

        return {
            "mandate_id": mandate.mandate_id,
            "mandate_level": mandate_level,
            "agent_id": agent_id,
            "status": "active",
        }

    async def get_mandate(self, db: AsyncSession,
                           mandate_id: str) -> AgentisAgentBankingMandate | None:
        """Get a specific mandate."""
        result = await db.execute(
            select(AgentisAgentBankingMandate).where(
                AgentisAgentBankingMandate.mandate_id == mandate_id
            )
        )
        return result.scalar_one_or_none()

    async def get_active_mandate(self, db: AsyncSession,
                                  agent_id: str) -> AgentisAgentBankingMandate | None:
        """Get the active banking mandate for an agent."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(AgentisAgentBankingMandate).where(
                AgentisAgentBankingMandate.agent_id == agent_id,
                AgentisAgentBankingMandate.is_active == True,
                AgentisAgentBankingMandate.valid_from <= now,
            ).order_by(AgentisAgentBankingMandate.granted_by_operator_at.desc()).limit(1)
        )
        mandate = result.scalar_one_or_none()

        # Check expiry
        if mandate and mandate.valid_until and mandate.valid_until < now:
            return None

        return mandate

    async def validate_mandate_action(
        self, db: AsyncSession, *,
        agent_id: str,
        required_level: str,
        amount_zar: float = 0,
        currency: str = "ZAR",
        beneficiary_id: str | None = None,
    ) -> dict:
        """Validate that an agent's mandate permits a specific action."""
        mandate = await self.get_active_mandate(db, agent_id)
        if not mandate:
            return {"allowed": False, "error": "NO_ACTIVE_MANDATE",
                    "error_code": "MANDATE_NOT_FOUND"}

        now = datetime.now(timezone.utc)
        if mandate.valid_until and mandate.valid_until < now:
            return {"allowed": False, "error": "MANDATE_EXPIRED",
                    "error_code": "MANDATE_EXPIRED"}

        # Level hierarchy: L0 < L1 < L2 < L3 < L3FA
        levels = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L3FA": 4}
        if levels.get(mandate.mandate_level, 0) < levels.get(required_level, 0):
            if self.compliance:
                await self.compliance.log_monitoring_event(
                    db,
                    event_type="MANDATE_BREACH",
                    description=(f"Agent {agent_id} attempted {required_level} action "
                                 f"with {mandate.mandate_level} mandate"),
                    severity="high",
                    agent_id=agent_id,
                    mandate_id=mandate.mandate_id,
                    requires_review=True,
                )
            return {"allowed": False, "error": "MANDATE_LEVEL_INSUFFICIENT",
                    "error_code": "MANDATE_LEVEL_INSUFFICIENT"}

        # Check transaction limits
        if amount_zar > 0:
            if amount_zar > mandate.per_transaction_limit > 0:
                return {"allowed": False, "error": "PER_TRANSACTION_LIMIT_EXCEEDED",
                        "error_code": "TRANSACTION_LIMIT_EXCEEDED"}

            if mandate.daily_payment_limit > 0:
                if (mandate.daily_total_used + amount_zar) > mandate.daily_payment_limit:
                    return {"allowed": False, "error": "DAILY_LIMIT_EXCEEDED",
                            "error_code": "DAILY_LIMIT_EXCEEDED"}

            if mandate.monthly_limit > 0:
                if (mandate.monthly_total_used + amount_zar) > mandate.monthly_limit:
                    return {"allowed": False, "error": "MONTHLY_LIMIT_EXCEEDED",
                            "error_code": "MONTHLY_LIMIT_EXCEEDED"}

        # Check currency
        if currency not in (mandate.allowed_currencies or ["ZAR"]):
            return {"allowed": False, "error": "CURRENCY_NOT_ALLOWED",
                    "error_code": "CURRENCY_NOT_ALLOWED"}

        # Check beneficiary whitelist
        if beneficiary_id and mandate.allowed_beneficiary_ids:
            if beneficiary_id not in mandate.allowed_beneficiary_ids:
                return {"allowed": False, "error": "BENEFICIARY_NOT_ALLOWED",
                        "error_code": "BENEFICIARY_NOT_ALLOWED"}

        # Check confirmation threshold
        needs_confirmation = (
            mandate.confirmation_threshold > 0 and
            amount_zar >= mandate.confirmation_threshold
        )

        return {
            "allowed": True,
            "mandate_id": mandate.mandate_id,
            "mandate_level": mandate.mandate_level,
            "needs_3fa_confirmation": needs_confirmation,
            "daily_remaining": (mandate.daily_payment_limit - mandate.daily_total_used
                               if mandate.daily_payment_limit > 0 else None),
            "monthly_remaining": (mandate.monthly_limit - mandate.monthly_total_used
                                 if mandate.monthly_limit > 0 else None),
        }

    async def update_mandate_totals(self, db: AsyncSession, mandate_id: str,
                                     amount_zar: float) -> None:
        """Update daily and monthly running totals after a successful transaction."""
        mandate = await self.get_mandate(db, mandate_id)
        if not mandate:
            return

        now = datetime.now(timezone.utc)

        # Reset daily total if new day
        if mandate.daily_total_reset_at:
            if mandate.daily_total_reset_at.date() < now.date():
                mandate.daily_total_used = 0
        mandate.daily_total_used += amount_zar
        mandate.daily_total_reset_at = now

        # Reset monthly total if new month
        if mandate.monthly_total_reset_at:
            if mandate.monthly_total_reset_at.month != now.month:
                mandate.monthly_total_used = 0
        mandate.monthly_total_used += amount_zar
        mandate.monthly_total_reset_at = now
        mandate.updated_at = now

    async def revoke_mandate(self, db: AsyncSession, mandate_id: str,
                              operator_id: str) -> dict:
        """Revoke an agent banking mandate."""
        mandate = await self.get_mandate(db, mandate_id)
        if not mandate:
            return {"error": "MANDATE_NOT_FOUND"}

        mandate.is_active = False
        mandate.updated_at = datetime.now(timezone.utc)

        if self.compliance:
            await self.compliance.log_audit(
                db, "OPERATOR", operator_id, "REVOKE_MANDATE",
                "MANDATE", mandate_id,
                {"agent_id": mandate.agent_id},
            )

        if self.blockchain:
            from app.blockchain.transaction import Transaction, TransactionType
            tx = Transaction(
                type=TransactionType.AGENTIS_MANDATE_REVOKE,
                sender_id=mandate.member_id,
                receiver_id=mandate.agent_id,
                amount=0,
                description=f"Banking mandate revoked: {mandate.mandate_level}",
                metadata={"mandate_id": mandate_id},
            )
            self.blockchain.add_transaction(tx)

        return {"status": "revoked", "mandate_id": mandate_id}

    async def list_mandates(self, db: AsyncSession, member_id: str) -> list[dict]:
        """List all mandates granted by a member."""
        result = await db.execute(
            select(AgentisAgentBankingMandate).where(
                AgentisAgentBankingMandate.member_id == member_id
            ).order_by(AgentisAgentBankingMandate.created_at.desc())
        )
        mandates = result.scalars().all()
        return [
            {
                "mandate_id": m.mandate_id,
                "agent_id": m.agent_id,
                "mandate_level": m.mandate_level,
                "is_active": m.is_active,
                "daily_payment_limit": m.daily_payment_limit,
                "per_transaction_limit": m.per_transaction_limit,
                "monthly_limit": m.monthly_limit,
                "daily_remaining": m.daily_payment_limit - m.daily_total_used,
                "valid_from": m.valid_from.isoformat(),
                "valid_until": m.valid_until.isoformat() if m.valid_until else None,
            }
            for m in mandates
        ]
