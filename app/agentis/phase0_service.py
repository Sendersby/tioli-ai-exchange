"""Agentis Phase 0 — Pre-Banking Wallet Product (Enhancement #2).

A regulated wallet/e-money service requiring only FSP licence, not banking licence.
Gives agents accounts, internal transfers, and mandate controls while waiting
for CBDA/SARB cooperative bank approvals.

This is a lightweight wrapper around the existing TiOLi wallet infrastructure
with Agentis mandate controls layered on top.

Revenue: Transaction fees on transfers, membership fees.
Feature flag: AGENTIS_PHASE0_WALLET_ENABLED
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class AgentisPhase0Service:
    """Pre-banking wallet product — proves the agent banking concept
    while regulatory applications are in progress.

    Uses existing TiOLi wallets (no new tables needed) with Agentis
    mandate validation layered on top.

    Key capabilities:
    - Agent wallets with operator-granted mandates
    - Internal transfers between agent wallets (mandate-enforced)
    - Balance inquiries and transaction history
    - Membership fee collection (R100 join + R50/year)
    - Full compliance logging

    NOT included (requires banking licence):
    - Interest-bearing accounts
    - Lending
    - External payments (EFT)
    - Foreign exchange
    - Deposit insurance
    """

    def __init__(self, wallet_service=None, member_service=None,
                 compliance_service=None, blockchain=None):
        self.wallets = wallet_service
        self.members = member_service
        self.compliance = compliance_service
        self.blockchain = blockchain

    async def create_agent_wallet(
        self, db: AsyncSession, *,
        agent_id: str,
        operator_id: str,
        currency: str = "AGENTIS",
    ) -> dict:
        """Create an agent wallet under Phase 0 pre-banking product.

        Uses existing TiOLi wallet infrastructure with mandate controls.
        No banking licence required — this is an e-money/stored value product.
        """
        if not self.wallets:
            return {"error": "WALLET_SERVICE_NOT_AVAILABLE"}

        # Get or create wallet via existing infrastructure
        wallet = await self.wallets.get_or_create_wallet(db, agent_id, currency)

        # Log to compliance
        if self.compliance:
            await self.compliance.log_monitoring_event(
                db,
                event_type="AGENT_BANKING_ACTION",
                description=f"Phase 0 wallet created for agent {agent_id}",
                severity="info",
                agent_id=agent_id,
                channel="phase0",
            )

        return {
            "agent_id": agent_id,
            "currency": currency,
            "balance": wallet.balance if wallet else 0,
            "product": "PHASE_0_WALLET",
            "licence_type": "FSP",
            "message": "Pre-banking wallet active. Full banking available after CBDA approval.",
        }

    async def mandate_transfer(
        self, db: AsyncSession, *,
        agent_id: str,
        sender_id: str,
        receiver_id: str,
        amount: float,
        currency: str = "AGENTIS",
        reference: str = "",
    ) -> dict:
        """Execute a mandate-controlled transfer between agent wallets.

        Validates agent mandate before executing via existing wallet service.
        """
        if not self.wallets:
            return {"error": "WALLET_SERVICE_NOT_AVAILABLE"}
        if not self.members:
            return {"error": "MEMBER_SERVICE_NOT_AVAILABLE"}

        # Validate mandate
        mandate_check = await self.members.validate_mandate_action(
            db, agent_id=agent_id, required_level="L1",
            amount_zar=amount, currency=currency,
        )

        if not mandate_check["allowed"]:
            if self.compliance:
                await self.compliance.log_monitoring_event(
                    db,
                    event_type="MANDATE_BREACH",
                    description=(f"Phase 0 transfer blocked: agent {agent_id} — "
                                 f"{mandate_check['error']}"),
                    severity="high",
                    agent_id=agent_id,
                    amount_zar=amount,
                    channel="phase0",
                    requires_review=True,
                )
            return {"error": mandate_check["error"],
                    "error_code": mandate_check["error_code"]}

        # Execute via existing wallet service
        result = await self.wallets.transfer(
            db, sender_id=sender_id, receiver_id=receiver_id,
            amount=amount, currency=currency,
        )

        # Update mandate totals
        if mandate_check.get("mandate_id"):
            await self.members.update_mandate_totals(
                db, mandate_check["mandate_id"], amount)

        # Compliance logging
        if self.compliance:
            await self.compliance.log_monitoring_event(
                db,
                event_type="AGENT_BANKING_ACTION",
                description=f"Phase 0 transfer: {sender_id} → {receiver_id} R{amount:,.2f}",
                severity="info",
                agent_id=agent_id,
                mandate_id=mandate_check.get("mandate_id"),
                amount_zar=amount,
                channel="phase0",
            )

        return {
            "status": "completed",
            "amount": amount,
            "currency": currency,
            "product": "PHASE_0_WALLET",
            "mandate_daily_remaining": mandate_check.get("daily_remaining"),
        }

    async def collect_membership_fee(
        self, db: AsyncSession, *,
        member_id: str,
        fee_type: str = "JOINING",
    ) -> dict:
        """Collect cooperative membership fee.

        R100 once-off joining fee. R50 annual subscription.
        """
        fees = {"JOINING": 100.0, "ANNUAL": 50.0}
        amount = fees.get(fee_type, 0)
        if amount == 0:
            return {"error": "INVALID_FEE_TYPE"}

        # Log the fee as revenue
        if self.compliance:
            await self.compliance.log_audit(
                db, "SYSTEM", "phase0_service",
                "COLLECT_MEMBERSHIP_FEE", "MEMBER", member_id,
                {"fee_type": fee_type, "amount_zar": amount},
            )

        if self.blockchain:
            from app.blockchain.transaction import Transaction, TransactionType
            tx = Transaction(
                type=TransactionType.AGENTIS_MEMBERSHIP_FEE,
                sender_id=member_id,
                amount=amount,
                currency="ZAR",
                description=f"Agentis membership fee: {fee_type} R{amount:,.2f}",
                metadata={"fee_type": fee_type},
            )
            self.blockchain.add_transaction(tx)

        return {
            "fee_type": fee_type,
            "amount_zar": amount,
            "status": "collected",
            "product": "PHASE_0_WALLET",
        }

    def get_product_info(self) -> dict:
        """Return Phase 0 product information."""
        return {
            "product": "Agentis Phase 0 — Pre-Banking Wallet",
            "licence_required": "FSP (Financial Services Provider)",
            "licence_status": "Application pending",
            "capabilities": [
                "Agent wallet creation and management",
                "Internal transfers with mandate controls",
                "Balance inquiry and transaction history",
                "Membership fee collection",
                "Full compliance logging",
            ],
            "not_available": [
                "Interest-bearing accounts (requires banking licence)",
                "Lending products (requires NCR + banking licence)",
                "External EFT payments (requires banking licence)",
                "Foreign exchange (requires SARB approval)",
                "Deposit insurance (requires SARB registration)",
            ],
            "fees": {
                "joining_fee": "R100 once-off",
                "annual_fee": "R50/year",
                "internal_transfer": "R0 (free)",
            },
            "upgrade_path": "Full Agentis cooperative banking upon CBDA CFI approval",
        }
