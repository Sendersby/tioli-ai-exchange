"""AgentBroker™ core services — profiles, engagements, negotiation, escrow, reputation, disputes.

Implements the complete functional specification from the integration brief.
"""

import hashlib
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentbroker.models import (
    AgentServiceProfile, AgentEngagement, EngagementNegotiation,
    EngagementMilestone, EngagementDispute, AgentReputationScore,
    CapabilityVerification, AgentNegotiationBoundary,
    EngagementEscrowWallet, CapabilityTaxonomy,
)
from app.blockchain.chain import Blockchain
from app.blockchain.transaction import Transaction, TransactionType
from app.exchange.fees import FeeEngine
from app.config import settings


# ══════════════════════════════════════════════════════════════════════
#  VALID ENGAGEMENT STATE TRANSITIONS (Section 2.3.1)
# ══════════════════════════════════════════════════════════════════════

VALID_TRANSITIONS = {
    "DRAFT": ["PROPOSED"],
    "PROPOSED": ["NEGOTIATING", "ACCEPTED", "DECLINED", "EXPIRED", "WITHDRAWN"],
    "NEGOTIATING": ["PROPOSED", "ACCEPTED", "DECLINED", "WITHDRAWN"],  # H-05 fix
    "ACCEPTED": ["FUNDED"],
    "FUNDED": ["IN_PROGRESS"],
    "IN_PROGRESS": ["DELIVERED", "DISPUTED"],
    "DELIVERED": ["VERIFIED", "DISPUTED"],
    "VERIFIED": ["COMPLETED"],
    "DISPUTED": ["RESOLVED", "ESCALATED"],
    "RESOLVED": ["COMPLETED", "REFUNDED", "IN_PROGRESS"],  # H-08 fix: rework path
    "ESCALATED": ["COMPLETED", "REFUNDED"],
    "COMPLETED": [],
    "DECLINED": [],   # Terminal state
    "EXPIRED": [],
    "WITHDRAWN": [],
    "REFUNDED": [],
}


def _check_feature_flag():
    """Ensure AgentBroker is enabled."""
    if not settings.agentbroker_enabled:
        raise ValueError("AgentBroker module is not enabled. Set AGENTBROKER_ENABLED=true.")


class ProfileService:
    """Manages agent service profiles (Section 2.1)."""

    async def create_profile(
        self, db: AsyncSession, agent_id: str, operator_id: str,
        service_title: str, service_description: str,
        capability_tags: list[str], model_family: str,
        context_window: int, languages: list[str],
        pricing_model: str, base_price: float | None = None,
        price_currency: str = "AGENTIS", minimum_engagement: str | None = None,
    ) -> AgentServiceProfile:
        _check_feature_flag()
        profile = AgentServiceProfile(
            agent_id=agent_id,
            operator_id=operator_id,
            service_title=service_title,
            service_description=service_description,
            capability_tags=capability_tags,
            model_family=model_family,
            context_window=context_window,
            languages_supported=languages,
            pricing_model=pricing_model,
            base_price=base_price,
            price_currency=price_currency,
            minimum_engagement=minimum_engagement,
        )
        db.add(profile)
        await db.flush()
        return profile

    async def get_profile(self, db: AsyncSession, profile_id: str) -> dict | None:
        _check_feature_flag()
        result = await db.execute(
            select(AgentServiceProfile).where(
                AgentServiceProfile.profile_id == profile_id
            )
        )
        p = result.scalar_one_or_none()
        if not p:
            return None
        return self._to_dict(p)

    async def search_profiles(
        self, db: AsyncSession, capability_tags: list[str] | None = None,
        pricing_model: str | None = None, max_price: float | None = None,
        min_reputation: float = 0, availability: str | None = None,
        model_family: str | None = None, sort_by: str = "REPUTATION",
        page: int = 1, page_size: int = 20,
    ) -> dict:
        _check_feature_flag()
        query = select(AgentServiceProfile).where(
            AgentServiceProfile.is_active == True,
            AgentServiceProfile.reputation_score >= min_reputation,
        )
        if pricing_model:
            query = query.where(AgentServiceProfile.pricing_model == pricing_model)
        if max_price is not None:
            query = query.where(AgentServiceProfile.base_price <= max_price)
        if availability and availability != "ANY":
            query = query.where(AgentServiceProfile.availability_status == availability)
        if model_family:
            query = query.where(AgentServiceProfile.model_family == model_family)

        # Sort
        if sort_by == "PRICE_ASC":
            query = query.order_by(AgentServiceProfile.base_price.asc())
        elif sort_by == "PRICE_DESC":
            query = query.order_by(AgentServiceProfile.base_price.desc())
        elif sort_by == "ENGAGEMENTS":
            query = query.order_by(AgentServiceProfile.total_engagements.desc())
        else:
            query = query.order_by(AgentServiceProfile.reputation_score.desc())

        # Paginate
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await db.execute(query)
        profiles = [self._to_dict(p) for p in result.scalars().all()]

        return {"results": profiles, "page": page, "page_size": page_size}

    async def update_profile(
        self, db: AsyncSession, profile_id: str, agent_id: str, **kwargs,
    ) -> dict:
        """Update a service profile — only the owning agent can update."""
        _check_feature_flag()
        result = await db.execute(
            select(AgentServiceProfile).where(
                AgentServiceProfile.profile_id == profile_id
            )
        )
        p = result.scalar_one_or_none()
        if not p:
            raise ValueError("Profile not found")
        if p.agent_id != agent_id:
            raise ValueError("Not authorised to update this profile")

        allowed = {
            "service_title", "service_description", "capability_tags",
            "model_family", "context_window", "languages_supported",
            "pricing_model", "base_price", "price_currency",
            "minimum_engagement", "availability_status",
        }
        for key, value in kwargs.items():
            if key in allowed and value is not None:
                setattr(p, key, value)
        from datetime import datetime, timezone
        p.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return self._to_dict(p)

    async def deactivate_profile(
        self, db: AsyncSession, profile_id: str, agent_id: str,
    ) -> dict:
        """Deactivate (soft-delete) a service profile."""
        _check_feature_flag()
        result = await db.execute(
            select(AgentServiceProfile).where(
                AgentServiceProfile.profile_id == profile_id
            )
        )
        p = result.scalar_one_or_none()
        if not p:
            raise ValueError("Profile not found")
        if p.agent_id != agent_id:
            raise ValueError("Not authorised to deactivate this profile")
        p.is_active = False
        await db.flush()
        return {"profile_id": profile_id, "deactivated": True}

    async def get_agent_profiles(
        self, db: AsyncSession, agent_id: str,
    ) -> list[dict]:
        """Get all service profiles for an agent."""
        _check_feature_flag()
        result = await db.execute(
            select(AgentServiceProfile).where(
                AgentServiceProfile.agent_id == agent_id
            )
        )
        return [self._to_dict(p) for p in result.scalars().all()]

    def _to_dict(self, p: AgentServiceProfile) -> dict:
        return {
            "profile_id": p.profile_id, "agent_id": p.agent_id,
            "service_title": p.service_title,
            "service_description": p.service_description[:500],
            "capability_tags": p.capability_tags,
            "model_family": p.model_family,
            "context_window": p.context_window,
            "languages": p.languages_supported,
            "pricing_model": p.pricing_model,
            "base_price": p.base_price,
            "price_currency": p.price_currency,
            "availability": p.availability_status,
            "reputation_score": p.reputation_score,
            "total_engagements": p.total_engagements,
            "verified_capabilities": p.verified_capabilities,
        }


class EngagementService:
    """Manages the engagement lifecycle state machine (Section 2.3)."""

    def __init__(self, blockchain: Blockchain, fee_engine: FeeEngine):
        self.blockchain = blockchain
        self.fee_engine = fee_engine
        self._pending_settlement_amount: dict[str, float] = {}  # AUD-04: per-engagement override

    async def create_engagement(
        self, db: AsyncSession, client_agent_id: str,
        provider_agent_id: str, service_profile_id: str,
        title: str, scope: str, criteria: str,
        price: float, currency: str = "AGENTIS",
        payment_terms: str = "ON_DELIVERY",
        deadline: datetime | None = None,
        milestones: list | None = None,
    ) -> AgentEngagement:
        _check_feature_flag()
        # Check negotiation boundaries
        await self._check_boundaries(db, client_agent_id, price, currency)

        engagement = AgentEngagement(
            client_agent_id=client_agent_id,
            provider_agent_id=provider_agent_id,
            service_profile_id=service_profile_id,
            engagement_title=title,
            scope_of_work=scope,
            acceptance_criteria=criteria,
            proposed_price=price,
            price_currency=currency,
            payment_terms=payment_terms,
            deadline=deadline,
            milestones=milestones,
            current_state="DRAFT",
            state_history=[{
                "state": "DRAFT", "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor": client_agent_id,
            }],
        )
        db.add(engagement)
        await db.flush()
        return engagement

    async def transition_state(
        self, db: AsyncSession, engagement_id: str,
        new_state: str, actor_id: str
    ) -> AgentEngagement:
        """Transition engagement to a new state with validation."""
        _check_feature_flag()
        result = await db.execute(
            select(AgentEngagement).where(
                AgentEngagement.engagement_id == engagement_id
            )
        )
        engagement = result.scalar_one_or_none()
        if not engagement:
            raise ValueError("Engagement not found")

        current = engagement.current_state
        if new_state not in VALID_TRANSITIONS.get(current, []):
            raise ValueError(
                f"Invalid state transition: {current} → {new_state}. "
                f"Valid transitions: {VALID_TRANSITIONS.get(current, [])}"
            )

        # Verify actor is a party to this engagement
        if actor_id not in (engagement.client_agent_id, engagement.provider_agent_id, "system", "owner"):
            raise ValueError("Not authorized for this engagement")

        engagement.current_state = new_state
        history = engagement.state_history or []
        history.append({
            "state": new_state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor_id,
        })
        engagement.state_history = history

        # AGENTIS Interoperability: fire webhooks on state change
        try:
            from app.agentbroker.models import AgentWebhookRegistration
            from sqlalchemy import select as wh_select
            import httpx
            for agent_check_id in (engagement.client_agent_id, engagement.provider_agent_id):
                wh_result = await db.execute(
                    wh_select(AgentWebhookRegistration).where(
                        AgentWebhookRegistration.agent_id == agent_check_id,
                        AgentWebhookRegistration.is_active == True,
                    )
                )
                for wh in wh_result.scalars().all():
                    events = wh.events or []
                    if new_state in events or "*" in events:
                        try:
                            async with httpx.AsyncClient(timeout=5) as client:
                                await client.post(wh.callback_url, json={
                                    "event": new_state,
                                    "engagement_id": engagement.engagement_id,
                                    "title": engagement.engagement_title,
                                    "previous_state": current,
                                    "new_state": new_state,
                                    "actor": actor_id,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                })
                            wh.last_fired_at = datetime.now(timezone.utc)
                        except Exception:
                            wh.failure_count = (wh.failure_count or 0) + 1
        except Exception:
            pass  # Webhooks are best-effort — never block state transitions

        # Handle terminal states
        if new_state == "COMPLETED":
            engagement.completed_at = datetime.now(timezone.utc)
            # AUD-04: check for partial settlement amount
            partial = self._pending_settlement_amount.pop(engagement.engagement_id, None)
            await self._settle_payment(db, engagement, settlement_amount=partial)
            # Recalculate reputation for provider after completion
            try:
                from app.reputation.scorer import ReputationScorer
                scorer = ReputationScorer()
                await scorer.calculate(db, engagement.provider_agent_id)
            except Exception:
                pass  # reputation is best-effort
        elif new_state == "REFUNDED":
            engagement.completed_at = datetime.now(timezone.utc)
            await self._process_refund(db, engagement)

        await db.flush()
        return engagement

    async def fund_escrow(
        self, db: AsyncSession, engagement_id: str, agent_id: str
    ) -> dict:
        """Fund the escrow for an accepted engagement."""
        _check_feature_flag()
        result = await db.execute(
            select(AgentEngagement).where(
                AgentEngagement.engagement_id == engagement_id
            )
        )
        engagement = result.scalar_one_or_none()
        if not engagement or engagement.current_state != "ACCEPTED":
            raise ValueError("Engagement not found or not in ACCEPTED state")
        if agent_id != engagement.client_agent_id:
            raise ValueError("Only the client agent can fund escrow")

        # AUD-05 fix: SELECT FOR UPDATE to prevent double-funding race condition
        from app.agents.models import Wallet
        client_wallet_result = await db.execute(
            select(Wallet).where(
                Wallet.agent_id == agent_id,
                Wallet.currency == engagement.price_currency,
            ).with_for_update()
        )
        client_wallet = client_wallet_result.scalar_one_or_none()
        if not client_wallet or (client_wallet.balance - client_wallet.frozen_balance) < engagement.proposed_price:
            raise ValueError(
                f"Insufficient balance to fund escrow. "
                f"Required: {engagement.proposed_price} {engagement.price_currency}"
            )
        client_wallet.balance -= engagement.proposed_price

        # Create escrow wallet
        escrow = EngagementEscrowWallet(
            engagement_id=engagement_id,
            client_agent_id=agent_id,
            amount=engagement.proposed_price,
            currency=engagement.price_currency,
            status="funded",
            funded_at=datetime.now(timezone.utc),
        )
        db.add(escrow)
        engagement.escrow_wallet_id = escrow.escrow_wallet_id
        engagement.escrow_amount = engagement.proposed_price

        # Transition to FUNDED
        await self.transition_state(db, engagement_id, "FUNDED", agent_id)

        # Record on blockchain
        tx = Transaction(
            type=TransactionType.DEPOSIT,
            sender_id=agent_id,
            amount=engagement.proposed_price,
            currency=engagement.price_currency,
            description=f"Escrow funded for engagement {engagement_id[:12]}",
            metadata={"engagement_id": engagement_id, "type": "escrow_funding"},
        )
        self.blockchain.add_transaction(tx)

        await db.flush()
        return {
            "engagement_id": engagement_id,
            "escrow_wallet_id": escrow.escrow_wallet_id,
            "amount": escrow.amount,
            "status": "funded",
        }

    async def submit_deliverable(
        self, db: AsyncSession, engagement_id: str, agent_id: str,
        deliverable_ref: str, deliverable_content_hash: str | None = None
    ) -> dict:
        """Provider submits a deliverable."""
        _check_feature_flag()
        result = await db.execute(
            select(AgentEngagement).where(
                AgentEngagement.engagement_id == engagement_id
            )
        )
        engagement = result.scalar_one_or_none()
        if not engagement or engagement.current_state != "IN_PROGRESS":
            raise ValueError("Engagement not in IN_PROGRESS state")
        if agent_id != engagement.provider_agent_id:
            raise ValueError("Only the provider can submit deliverables")

        # AGENTIS DAP v0.5.1 — zero-day gate enforcement
        if settings.agentis_dap_enabled and engagement.deposited_at:
            elapsed_ms = (datetime.now(timezone.utc) - engagement.deposited_at).total_seconds() * 1000
            gate_ms = engagement.zero_day_gate_ms or (48 * 3600 * 1000)
            if elapsed_ms < gate_ms:
                remaining_hrs = round((gate_ms - elapsed_ms) / 3600000, 1)
                raise ValueError(f"Zero-day gate: {remaining_hrs}h remaining.")
            if not deliverable_content_hash or len(str(deliverable_content_hash)) != 64:
                raise ValueError("deliverable_hash must be 64-char SHA-256 hex.")
            engagement.submitted_at = datetime.now(timezone.utc)

        # Generate hash if content provided
        if deliverable_content_hash:
            engagement.deliverable_hash = deliverable_content_hash
        else:
            engagement.deliverable_hash = hashlib.sha256(
                deliverable_ref.encode()
            ).hexdigest()

        engagement.deliverable_storage_ref = deliverable_ref
        await self.transition_state(db, engagement_id, "DELIVERED", agent_id)

        # AGENTIS DAP v0.5.1 — record hash on chain
        if settings.agentis_dap_enabled and engagement.deliverable_hash:
            from app.blockchain.transaction import Transaction, TransactionType
            tx = Transaction(
                type=TransactionType.DELIVERABLE_HASH,
                sender_id=engagement.provider_agent_id,
                receiver_id=engagement.client_agent_id,
                amount=0,
                currency=engagement.price_currency,
                description=f"SHA-256: {engagement.deliverable_hash[:32]}... Auto-finalizes in 10 days",
                metadata={"engagement_id": engagement_id},
            )
            self.blockchain.add_transaction(tx)

        await db.flush()
        return {
            "engagement_id": engagement_id,
            "deliverable_hash": engagement.deliverable_hash,
            "state": "DELIVERED",
        }

    async def verify_delivery(
        self, db: AsyncSession, engagement_id: str, agent_id: str,
        accepted: bool
    ) -> dict:
        """Client verifies or disputes the delivery."""
        _check_feature_flag()
        result = await db.execute(
            select(AgentEngagement).where(
                AgentEngagement.engagement_id == engagement_id
            )
        )
        engagement = result.scalar_one_or_none()
        if not engagement or engagement.current_state != "DELIVERED":
            raise ValueError("Engagement not in DELIVERED state")
        if agent_id != engagement.client_agent_id:
            raise ValueError("Only the client can verify delivery")

        if accepted:
            await self.transition_state(db, engagement_id, "VERIFIED", agent_id)
            await self.transition_state(db, engagement_id, "COMPLETED", "system")
            return {"engagement_id": engagement_id, "state": "COMPLETED", "payment": "released"}
        else:
            return {"engagement_id": engagement_id, "state": "DELIVERED", "message": "Use dispute endpoint to raise a dispute"}

    async def get_engagement(self, db: AsyncSession, engagement_id: str) -> dict | None:
        _check_feature_flag()
        result = await db.execute(
            select(AgentEngagement).where(
                AgentEngagement.engagement_id == engagement_id
            )
        )
        e = result.scalar_one_or_none()
        if not e:
            return None
        return {
            "engagement_id": e.engagement_id,
            "client": e.client_agent_id, "provider": e.provider_agent_id,
            "title": e.engagement_title, "state": e.current_state,
            "price": e.proposed_price, "currency": e.price_currency,
            "payment_terms": e.payment_terms,
            "escrow_amount": e.escrow_amount,
            "commission_rate": e.platform_commission_rate,
            "deliverable_hash": e.deliverable_hash,
            "deadline": str(e.deadline) if e.deadline else None,
            "state_history": e.state_history,
            "created_at": str(e.created_at),
        }

    async def list_engagements(
        self, db: AsyncSession, agent_id: str, state: str | None = None, limit: int = 50
    ) -> list[dict]:
        _check_feature_flag()
        query = select(AgentEngagement).where(
            or_(
                AgentEngagement.client_agent_id == agent_id,
                AgentEngagement.provider_agent_id == agent_id,
            )
        )
        if state:
            query = query.where(AgentEngagement.current_state == state)
        query = query.order_by(AgentEngagement.created_at.desc()).limit(limit)
        result = await db.execute(query)
        return [
            {
                "engagement_id": e.engagement_id, "title": e.engagement_title,
                "state": e.current_state, "price": e.proposed_price,
                "role": "client" if e.client_agent_id == agent_id else "provider",
            }
            for e in result.scalars().all()
        ]

    async def generate_smart_contract(
        self, db: AsyncSession, engagement_id: str
    ) -> dict:
        """Generate the Smart Engagement Contract (Section 2.4.3)."""
        _check_feature_flag()
        engagement = await self.get_engagement(db, engagement_id)
        if not engagement:
            raise ValueError("Engagement not found")

        contract_json = {
            "contract_type": "Smart Engagement Contract",
            "platform": "TiOLi AGENTIS — AgentBroker™",
            "engagement_id": engagement["engagement_id"],
            "parties": {
                "client_agent": engagement["client"],
                "provider_agent": engagement["provider"],
            },
            "terms": {
                "title": engagement["title"],
                "price": engagement["price"],
                "currency": engagement["currency"],
                "payment_terms": engagement["payment_terms"],
                "deadline": engagement["deadline"],
                "commission_rate": engagement["commission_rate"],
            },
            "legal_notice": (
                "This agreement is entered into between the registered operators "
                "of the client and provider agents as principals. The agents act "
                "as authorised instruments of their respective principals and "
                "have no independent legal standing. Governed by the laws of the "
                "Republic of South Africa."
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Plain English version
        plain_english = (
            f"SMART ENGAGEMENT CONTRACT\n\n"
            f"Engagement: {engagement['title']}\n"
            f"Client Agent: {engagement['client'][:12]}...\n"
            f"Provider Agent: {engagement['provider'][:12]}...\n"
            f"Price: {engagement['price']} {engagement['currency']}\n"
            f"Payment: {engagement['payment_terms']}\n"
            f"Commission: {engagement['commission_rate']*100:.0f}% to TiOLi Group Holdings (Pty) Ltd\n"
            f"Charity: 10% to TiOLi Charitable Fund\n"
            f"Deadline: {engagement['deadline'] or 'Open'}\n\n"
            f"This contract is recorded immutably on the TiOLi blockchain ledger.\n"
            f"Governed by the laws of the Republic of South Africa."
        )

        return {"json_contract": contract_json, "plain_english": plain_english}

    async def _settle_payment(
        self, db: AsyncSession, engagement: AgentEngagement,
        settlement_amount: float | None = None,
    ):
        """Settle payment on completion — commission + charity + provider.

        AUD-04 fix: supports partial payment via settlement_amount parameter.
        """
        from app.agents.models import Wallet
        amount = settlement_amount if settlement_amount is not None else engagement.proposed_price
        fees = self.fee_engine.calculate_fees(amount, transaction_type="agentbroker_engagement")
        engagement.platform_commission_amount = fees["commission"]
        engagement.charitable_allocation = fees["charity_fee"]

        # Credit provider wallet with net amount
        provider_wallet_result = await db.execute(
            select(Wallet).where(
                Wallet.agent_id == engagement.provider_agent_id,
                Wallet.currency == engagement.price_currency,
            )
        )
        provider_wallet = provider_wallet_result.scalar_one_or_none()
        if not provider_wallet:
            provider_wallet = Wallet(
                agent_id=engagement.provider_agent_id,
                currency=engagement.price_currency,
            )
            db.add(provider_wallet)
            await db.flush()
        provider_wallet.balance += fees["net_amount"]

        # Credit founder wallet
        if fees["founder_commission"] > 0:
            founder_result = await db.execute(
                select(Wallet).where(
                    Wallet.agent_id == "TIOLI_FOUNDER",
                    Wallet.currency == engagement.price_currency,
                )
            )
            fw = founder_result.scalar_one_or_none()
            if not fw:
                fw = Wallet(agent_id="TIOLI_FOUNDER", currency=engagement.price_currency)
                db.add(fw)
                await db.flush()
            fw.balance += fees["founder_commission"]

        # Credit charity wallet — AGENTIS DAP v0.5.1: charity guard
        charity_allowed = True
        if settings.agentis_dap_enabled:
            from app.agentbroker.agentis_dap_services import should_record_charity
            charity_allowed = should_record_charity(engagement)
        if fees["charity_fee"] > 0 and charity_allowed:
            charity_result = await db.execute(
                select(Wallet).where(
                    Wallet.agent_id == "TIOLI_CHARITY_FUND",
                    Wallet.currency == engagement.price_currency,
                )
            )
            cw = charity_result.scalar_one_or_none()
            if not cw:
                cw = Wallet(agent_id="TIOLI_CHARITY_FUND", currency=engagement.price_currency)
                db.add(cw)
                await db.flush()
            cw.balance += fees["charity_fee"]
        elif not charity_allowed:
            engagement.charitable_allocation = 0.0  # Zero out charity on refunded/disputed

        # NEW-07 fix: update escrow wallet status
        if engagement.escrow_wallet_id:
            escrow_result = await db.execute(
                select(EngagementEscrowWallet).where(
                    EngagementEscrowWallet.escrow_wallet_id == engagement.escrow_wallet_id
                )
            )
            escrow_record = escrow_result.scalar_one_or_none()
            if escrow_record:
                escrow_record.status = "released"
                escrow_record.released_at = datetime.now(timezone.utc)

        # Record settlement on blockchain
        tx = Transaction(
            type=TransactionType.TRANSFER,
            sender_id=engagement.client_agent_id,
            receiver_id=engagement.provider_agent_id,
            amount=engagement.proposed_price,
            currency=engagement.price_currency,
            description=(
                f"AgentBroker engagement settled: {engagement.engagement_title}. "
                f"Net to provider: {fees['net_amount']}"
            ),
            founder_commission=fees["founder_commission"],
            charity_fee=fees["charity_fee"],
            metadata={
                "engagement_id": engagement.engagement_id,
                "type": "engagement_settlement",
            },
        )
        engagement.ledger_transaction_id = tx.id
        self.blockchain.add_transaction(tx)

        # Update provider profile stats
        profile_result = await db.execute(
            select(AgentServiceProfile).where(
                AgentServiceProfile.profile_id == engagement.service_profile_id
            )
        )
        profile = profile_result.scalar_one_or_none()
        if profile:
            profile.total_engagements += 1

    async def _process_refund(self, db: AsyncSession, engagement: AgentEngagement):
        """Refund escrow to client. C-03 fix: actually credit client wallet."""
        from app.agents.models import Wallet

        # NEW-07 fix: update escrow wallet status
        if engagement.escrow_wallet_id:
            escrow_result = await db.execute(
                select(EngagementEscrowWallet).where(
                    EngagementEscrowWallet.escrow_wallet_id == engagement.escrow_wallet_id
                )
            )
            escrow_record = escrow_result.scalar_one_or_none()
            if escrow_record:
                escrow_record.status = "refunded"
                escrow_record.released_at = datetime.now(timezone.utc)

        if engagement.escrow_amount > 0:
            client_result = await db.execute(
                select(Wallet).where(
                    Wallet.agent_id == engagement.client_agent_id,
                    Wallet.currency == engagement.price_currency,
                )
            )
            client_wallet = client_result.scalar_one_or_none()
            # NEW-08 fix: create wallet if missing, never silently fail
            if not client_wallet:
                client_wallet = Wallet(
                    agent_id=engagement.client_agent_id,
                    currency=engagement.price_currency,
                )
                db.add(client_wallet)
                await db.flush()
            client_wallet.balance += engagement.escrow_amount

        tx = Transaction(
            type=TransactionType.WITHDRAWAL,
            receiver_id=engagement.client_agent_id,
            amount=engagement.escrow_amount,
            currency=engagement.price_currency,
            description=f"Escrow refund for engagement {engagement.engagement_id[:12]}",
            metadata={"engagement_id": engagement.engagement_id, "type": "escrow_refund"},
        )
        self.blockchain.add_transaction(tx)

    async def _check_boundaries(
        self, db: AsyncSession, agent_id: str, price: float, currency: str
    ):
        """Enforce negotiation boundaries (Section 2.4.1)."""
        result = await db.execute(
            select(AgentNegotiationBoundary).where(
                AgentNegotiationBoundary.agent_id == agent_id
            )
        )
        boundary = result.scalar_one_or_none()
        if not boundary:
            return  # No boundaries set = no restrictions

        if price > boundary.max_engagement_value:
            raise ValueError(
                f"Engagement value {price} exceeds agent boundary "
                f"of {boundary.max_engagement_value}"
            )
        if currency not in (boundary.approved_currencies or []):
            raise ValueError(
                f"Currency {currency} not in agent's approved currencies: "
                f"{boundary.approved_currencies}"
            )


class NegotiationService:
    """Manages the negotiation protocol (Section 2.4)."""

    async def submit_message(
        self, db: AsyncSession, engagement_id: str, sender_id: str,
        message_type: str, proposed_terms: dict,
        rationale: str | None = None, expires_hours: float = 24
    ) -> EngagementNegotiation:
        _check_feature_flag()
        valid_types = {"PROPOSAL", "COUNTER", "ACCEPT", "DECLINE", "WITHDRAW"}
        if message_type not in valid_types:
            raise ValueError(f"Invalid message type. Must be one of: {valid_types}")

        msg = EngagementNegotiation(
            engagement_id=engagement_id,
            sender_agent_id=sender_id,
            message_type=message_type,
            proposed_terms=proposed_terms,
            rationale=rationale,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_hours),
            signature=hashlib.sha256(
                f"{engagement_id}{sender_id}{message_type}".encode()
            ).hexdigest()[:16],
        )
        db.add(msg)
        await db.flush()
        return msg

    async def get_negotiation_history(
        self, db: AsyncSession, engagement_id: str
    ) -> list[dict]:
        _check_feature_flag()
        result = await db.execute(
            select(EngagementNegotiation)
            .where(EngagementNegotiation.engagement_id == engagement_id)
            .order_by(EngagementNegotiation.created_at.asc())
        )
        return [
            {
                "id": n.negotiation_id, "sender": n.sender_agent_id,
                "type": n.message_type, "terms": n.proposed_terms,
                "rationale": n.rationale,
                "timestamp": str(n.created_at),
            }
            for n in result.scalars().all()
        ]


class DisputeService:
    """Manages disputes and arbitration (Section 2.7)."""

    async def raise_dispute(
        self, db: AsyncSession, engagement_id: str, raised_by: str,
        dispute_type: str, description: str, evidence: list | None = None
    ) -> EngagementDispute:
        _check_feature_flag()
        valid_types = {"non_delivery", "partial_delivery", "quality", "payment", "scope", "terms"}
        if dispute_type not in valid_types:
            raise ValueError(f"Invalid dispute type. Must be one of: {valid_types}")

        dispute = EngagementDispute(
            engagement_id=engagement_id,
            raised_by=raised_by,
            dispute_type=dispute_type,
            description=description,
            evidence=evidence or [],
        )
        db.add(dispute)
        await db.flush()
        return dispute

    async def submit_evidence(
        self, db: AsyncSession, dispute_id: str, agent_id: str,
        evidence_item: dict
    ) -> dict:
        _check_feature_flag()
        result = await db.execute(
            select(EngagementDispute).where(EngagementDispute.dispute_id == dispute_id)
        )
        dispute = result.scalar_one_or_none()
        if not dispute:
            raise ValueError("Dispute not found")

        evidence = dispute.evidence or []
        evidence.append({**evidence_item, "submitted_by": agent_id,
                        "submitted_at": datetime.now(timezone.utc).isoformat()})
        dispute.evidence = evidence
        dispute.status = "evidence"
        await db.flush()
        return {"dispute_id": dispute_id, "evidence_count": len(evidence)}

    async def arbitrate(
        self, db: AsyncSession, dispute_id: str,
        engagement_service: "EngagementService | None" = None
    ) -> dict:
        """AI arbitration — automated resolution (Section 2.7.2 Stage 3).

        NEW-02 fix: transitions engagement state after resolution.
        """
        _check_feature_flag()
        result = await db.execute(
            select(EngagementDispute).where(EngagementDispute.dispute_id == dispute_id)
        )
        dispute = result.scalar_one_or_none()
        if not dispute:
            raise ValueError("Dispute not found")

        # Simplified arbitration logic (production would use LLM analysis)
        evidence_count = len(dispute.evidence or [])
        if dispute.dispute_type == "non_delivery":
            outcome = "full_refund"
            rationale = "Provider failed to deliver within agreed terms."
        elif dispute.dispute_type == "quality" and evidence_count >= 2:
            outcome = "partial_payment"
            rationale = "Deliverable partially meets acceptance criteria based on evidence."
        elif dispute.dispute_type in ("scope", "terms"):
            outcome = "rework"
            rationale = "Scope ambiguity identified. Provider to revise deliverable."
        else:
            # Escalate ambiguous cases
            dispute.escalated_to_owner = True
            dispute.status = "escalated"
            await db.flush()
            return {"dispute_id": dispute_id, "status": "escalated", "message": "Escalated to owner for veto decision"}

        dispute.outcome = outcome
        dispute.arbitration_rationale = rationale
        dispute.status = "resolved"
        dispute.resolved_at = datetime.now(timezone.utc)

        # NEW-02 fix: transition engagement to terminal state
        if engagement_service:
            eng_id = dispute.engagement_id
            await engagement_service.transition_state(db, eng_id, "RESOLVED", "system")
            if outcome == "full_refund":
                await engagement_service.transition_state(db, eng_id, "REFUNDED", "system")
            elif outcome == "full_payment":
                await engagement_service.transition_state(db, eng_id, "COMPLETED", "system")
            elif outcome == "partial_payment":
                # AUD-04: set partial amount (default 50%) before completing
                eng_result = await db.execute(
                    select(AgentEngagement).where(AgentEngagement.engagement_id == eng_id)
                )
                eng = eng_result.scalar_one_or_none()
                if eng:
                    partial_pct = dispute.partial_amount if dispute.partial_amount else 0.5
                    engagement_service._pending_settlement_amount[eng_id] = eng.proposed_price * partial_pct
                await engagement_service.transition_state(db, eng_id, "COMPLETED", "system")
            elif outcome == "rework":
                # AUD-12: extend deadline on rework
                eng_result = await db.execute(
                    select(AgentEngagement).where(AgentEngagement.engagement_id == eng_id)
                )
                eng = eng_result.scalar_one_or_none()
                if eng and eng.deadline:
                    original_duration = max((eng.deadline - eng.created_at).total_seconds(), 86400)
                    eng.deadline = datetime.now(timezone.utc) + timedelta(seconds=original_duration * 0.5)
                await engagement_service.transition_state(db, eng_id, "IN_PROGRESS", "system")

        await db.flush()

        return {
            "dispute_id": dispute_id, "outcome": outcome,
            "rationale": rationale, "status": "resolved",
        }

    async def owner_veto_decision(
        self, db: AsyncSession, dispute_id: str, decision: str, notes: str,
        engagement_service: "EngagementService | None" = None,
        dap_ruling=None,
    ) -> dict:
        """Owner issues final veto decision on escalated dispute.

        H-07 fix: after recording decision, transition the engagement
        to RESOLVED then to COMPLETED or REFUNDED.
        AGENTIS DAP v0.5.1: extended ruling with arbiter_rating, reasoning, etc.
        """
        _check_feature_flag()
        result = await db.execute(
            select(EngagementDispute).where(EngagementDispute.dispute_id == dispute_id)
        )
        dispute = result.scalar_one_or_none()
        if not dispute or not dispute.escalated_to_owner:
            raise ValueError("Dispute not found or not escalated")

        # AGENTIS DAP v0.5.1 — extended ruling logic
        if settings.agentis_dap_enabled and dap_ruling:
            from app.agentbroker.agentis_dap_services import (
                add_strike, award_clean_streak, publish_case_law,
                check_epoch_unlocks, should_record_charity,
            )
            dispute.arbiter_rating = dap_ruling.arbiter_rating
            dispute.arbiter_reasoning = dap_ruling.arbiter_reasoning
            dispute.hash_matched = dap_ruling.hash_matched
            dispute.scope_complied = dap_ruling.scope_complied
            dispute.frivolous = (dap_ruling.winner == "provider_frivolous")
            dispute.deposit_forfeited = (dap_ruling.winner == "provider_frivolous")

            # Get engagement for arbiter_rating override
            eng_result = await db.execute(
                select(AgentEngagement).where(
                    AgentEngagement.engagement_id == dispute.engagement_id
                )
            )
            eng = eng_result.scalar_one_or_none()
            if eng:
                eng.arbiter_rating = dap_ruling.arbiter_rating

            # Handle deposit
            client_agent_id = eng.client_agent_id if eng else None
            provider_agent_id = eng.provider_agent_id if eng else None
            if dispute.deposit_forfeited and client_agent_id and provider_agent_id:
                try:
                    from app.agents.wallet import WalletService
                    wallet_svc = WalletService(
                        engagement_service.blockchain if engagement_service else None,
                        engagement_service.fee_engine if engagement_service else None,
                    )
                    await wallet_svc.transfer_frozen(
                        db, client_agent_id, provider_agent_id,
                        dispute.dispute_deposit_cents / 100.0,
                    )
                except Exception:
                    pass
                from app.blockchain.transaction import Transaction, TransactionType
                tx = Transaction(
                    type=TransactionType.DEPOSIT_FORFEITED,
                    sender_id=client_agent_id,
                    receiver_id=provider_agent_id,
                    amount=dispute.dispute_deposit_cents / 100.0,
                    currency="AGENTIS",
                    description=f"Dispute deposit forfeited to provider - frivolous",
                    metadata={"dispute_id": dispute_id},
                )
                if engagement_service:
                    engagement_service.blockchain.add_transaction(tx)
            elif client_agent_id and dispute.dispute_deposit_cents > 0:
                try:
                    from app.agents.wallet import WalletService
                    wallet_svc = WalletService(
                        engagement_service.blockchain if engagement_service else None,
                        engagement_service.fee_engine if engagement_service else None,
                    )
                    await wallet_svc.unfreeze_balance(
                        db, client_agent_id,
                        dispute.dispute_deposit_cents / 100.0,
                    )
                except Exception:
                    pass
                from app.blockchain.transaction import Transaction, TransactionType
                tx = Transaction(
                    type=TransactionType.DEPOSIT_RETURNED,
                    sender_id="AGENTIS_ESCROW",
                    receiver_id=client_agent_id,
                    amount=dispute.dispute_deposit_cents / 100.0,
                    currency="AGENTIS",
                    description=f"Dispute deposit returned - legitimate dispute",
                    metadata={"dispute_id": dispute_id},
                )
                if engagement_service:
                    engagement_service.blockchain.add_transaction(tx)

            # Strikes and streaks
            if provider_agent_id:
                if dap_ruling.winner == "client":
                    await add_strike(db, provider_agent_id, dispute.engagement_id, dispute_id)
                else:
                    await award_clean_streak(db, provider_agent_id)

            # Map DAP winner to legacy decision
            if dap_ruling.winner in ("provider", "provider_frivolous"):
                decision = "full_payment"
            elif dap_ruling.winner == "client":
                decision = "full_refund"
            elif dap_ruling.winner == "split":
                decision = "partial_payment"
            notes = dap_ruling.arbiter_reasoning

            # Publish case law
            if eng:
                await publish_case_law(db, dispute, eng, dap_ruling)

            # Check epoch unlocks
            await check_epoch_unlocks(db)

        dispute.owner_decision = notes
        dispute.outcome = decision
        dispute.status = "resolved"
        dispute.resolved_at = datetime.now(timezone.utc)

        # H-07 fix: trigger engagement settlement based on decision
        if engagement_service:
            eng_id = dispute.engagement_id
            await engagement_service.transition_state(db, eng_id, "RESOLVED", "owner")
            if decision == "full_payment":
                await engagement_service.transition_state(db, eng_id, "COMPLETED", "owner")
            elif decision == "partial_payment":
                # AUD-04: set partial amount before completing
                eng_result = await db.execute(
                    select(AgentEngagement).where(AgentEngagement.engagement_id == eng_id)
                )
                eng = eng_result.scalar_one_or_none()
                if eng:
                    partial_pct = dispute.partial_amount if dispute.partial_amount else 0.5
                    engagement_service._pending_settlement_amount[eng_id] = eng.proposed_price * partial_pct
                await engagement_service.transition_state(db, eng_id, "COMPLETED", "owner")
            elif decision == "full_refund":
                await engagement_service.transition_state(db, eng_id, "REFUNDED", "owner")
            elif decision == "rework":
                # AUD-12: extend deadline
                eng_result = await db.execute(
                    select(AgentEngagement).where(AgentEngagement.engagement_id == eng_id)
                )
                eng = eng_result.scalar_one_or_none()
                if eng and eng.deadline:
                    original_duration = max((eng.deadline - eng.created_at).total_seconds(), 86400)
                    eng.deadline = datetime.now(timezone.utc) + timedelta(seconds=original_duration * 0.5)
                await engagement_service.transition_state(db, eng_id, "IN_PROGRESS", "owner")

        await db.flush()
        return {"dispute_id": dispute_id, "outcome": decision, "owner_notes": notes}


class ReputationService:
    """Calculates agent reputation scores (Section 2.6)."""

    async def calculate_reputation(
        self, db: AsyncSession, agent_id: str
    ) -> AgentReputationScore:
        _check_feature_flag()
        # Get engagement stats
        total = (await db.execute(
            select(func.count(AgentEngagement.engagement_id)).where(
                AgentEngagement.provider_agent_id == agent_id,
                AgentEngagement.current_state.in_(["COMPLETED", "REFUNDED", "DISPUTED"]),
            )
        )).scalar() or 0

        completed = (await db.execute(
            select(func.count(AgentEngagement.engagement_id)).where(
                AgentEngagement.provider_agent_id == agent_id,
                AgentEngagement.current_state == "COMPLETED",
            )
        )).scalar() or 0

        disputed = (await db.execute(
            select(func.count(EngagementDispute.dispute_id)).where(
                EngagementDispute.raised_by != agent_id  # Disputes raised AGAINST this agent
            )
        )).scalar() or 0

        # Calculate components
        delivery_rate = (completed / total * 10) if total > 0 else 10.0

        # AGENTIS DAP v0.5.1 — weighted strike rate replaces flat dispute_rate
        if settings.agentis_dap_enabled:
            from app.agentbroker.agentis_dap_services import calculate_weighted_strike_rate
            wsr = await calculate_weighted_strike_rate(db, agent_id, total)
            dispute_score = ((1 - wsr) * 10) if total > 0 else 10.0
        else:
            dispute_score = ((1 - disputed / max(total, 1)) * 10) if total > 0 else 10.0
        volume_score = min(10, math.log(max(total, 1) + 1) * 3)

        # Weighted composite (Section 2.6.1)
        overall = (
            delivery_rate * 0.30 +
            10.0 * 0.20 +           # On-time (placeholder — needs deadline tracking)
            delivery_rate * 0.20 +   # Acceptance rate (proxy: delivery rate)
            dispute_score * 0.15 +
            volume_score * 0.10 +
            5.0 * 0.05              # Recency (placeholder)
        )

        # Store score
        result = await db.execute(
            select(AgentReputationScore).where(AgentReputationScore.agent_id == agent_id)
        )
        score_record = result.scalar_one_or_none()
        if score_record:
            score_record.overall_score = round(overall, 2)
            score_record.delivery_rate = round(delivery_rate, 2)
            score_record.dispute_rate = round(dispute_score, 2)
            score_record.volume_multiplier = round(volume_score, 2)
            score_record.total_engagements = total
            score_record.total_completed = completed
            score_record.total_disputed = disputed
            score_record.calculated_at = datetime.now(timezone.utc)
        else:
            score_record = AgentReputationScore(
                agent_id=agent_id,
                overall_score=round(overall, 2),
                delivery_rate=round(delivery_rate, 2),
                dispute_rate=round(dispute_score, 2),
                volume_multiplier=round(volume_score, 2),
                total_engagements=total,
                total_completed=completed,
                total_disputed=disputed,
            )
            db.add(score_record)

        await db.flush()
        return score_record


class BoundaryService:
    """Manages agent negotiation boundaries (Section 2.4.1)."""

    async def set_boundaries(
        self, db: AsyncSession, agent_id: str, operator_id: str,
        **kwargs
    ) -> AgentNegotiationBoundary:
        _check_feature_flag()
        result = await db.execute(
            select(AgentNegotiationBoundary).where(
                AgentNegotiationBoundary.agent_id == agent_id
            )
        )
        boundary = result.scalar_one_or_none()

        if boundary:
            for key, value in kwargs.items():
                if hasattr(boundary, key) and value is not None:
                    setattr(boundary, key, value)
            boundary.updated_at = datetime.now(timezone.utc)
        else:
            boundary = AgentNegotiationBoundary(
                agent_id=agent_id, operator_id=operator_id, **kwargs
            )
            db.add(boundary)

        await db.flush()
        return boundary

    async def get_boundaries(self, db: AsyncSession, agent_id: str) -> dict | None:
        _check_feature_flag()
        result = await db.execute(
            select(AgentNegotiationBoundary).where(
                AgentNegotiationBoundary.agent_id == agent_id
            )
        )
        b = result.scalar_one_or_none()
        if not b:
            return None
        return {
            "agent_id": b.agent_id, "operator_id": b.operator_id,
            "max_engagement_value": b.max_engagement_value,
            "max_concurrent": b.max_concurrent_engagements,
            "min_price": b.min_acceptable_price,
            "max_price": b.max_acceptable_price,
            "approved_currencies": b.approved_currencies,
            "max_deadline_days": b.max_deadline_days,
            "require_escrow": b.require_escrow,
            "max_negotiation_rounds": b.negotiation_rounds_max,
            "auto_accept_threshold": b.auto_accept_threshold,
        }
