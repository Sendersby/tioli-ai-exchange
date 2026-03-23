"""Agentis Payment & Settlement — Service Layer (Module 4).

Autonomous agent payment engine, beneficiary management, standing orders,
fraud detection. Phase 1: internal transfers only. Phase 2: EFT via PSP.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentis.payment_models import (
    AgentisPayment,
    AgentisBeneficiary,
    AgentisStandingOrder,
    AgentisPaymentConfirmation,
    AgentisFraudEvent,
)

# Fraud detection constants
VELOCITY_MAX_PAYMENTS_PER_HOUR = 10
NEW_BENEFICIARY_LIMIT_ZAR = 5000
NEW_BENEFICIARY_SEASONING_HOURS = 24

# Payment fees (Phase 1: internal = R0)
PAYMENT_FEES = {
    "INTERNAL": 0.0,
    "EFT": 5.0,
    "INSTANT_EFT": 10.0,
    "CRYPTO": 0.0,  # Network fees handled separately
    "PAYPAL": 0.0,  # PayPal fees handled by adapter
}


class AgentisPaymentService:
    """Core payment engine for Agentis cooperative bank."""

    def __init__(self, compliance_service=None, member_service=None,
                 account_service=None, blockchain=None):
        self.compliance = compliance_service
        self.members = member_service
        self.accounts = account_service
        self.blockchain = blockchain

    # ------------------------------------------------------------------
    # Payment Initiation (Core Innovation: Autonomous Agent Payments)
    # ------------------------------------------------------------------

    async def initiate_payment(
        self, db: AsyncSession, *,
        source_account_id: str,
        member_id: str,
        amount: float,
        currency: str = "ZAR",
        reference: str,
        description: str | None = None,
        # Destination — either internal or beneficiary
        destination_account_id: str | None = None,
        beneficiary_id: str | None = None,
        # Agent context
        agent_id: str | None = None,
        mandate_id: str | None = None,
        # Idempotency
        idempotency_key: str | None = None,
        channel: str = "api",
    ) -> dict:
        """Initiate a payment — the core autonomous agent payment flow.

        Flow:
        1. Mandate validation (if agent-initiated)
        2. Fraud detection
        3. FICA pre-screening
        4. Balance check
        5. Idempotency check
        6. Execute or hold for confirmation
        """
        if amount <= 0:
            return {"error": "INVALID_AMOUNT", "error_code": "INVALID_AMOUNT"}

        # Idempotency
        if idempotency_key:
            existing = await db.execute(
                select(AgentisPayment).where(
                    AgentisPayment.idempotency_key == idempotency_key
                )
            )
            existing_payment = existing.scalar_one_or_none()
            if existing_payment:
                return {
                    "payment_id": existing_payment.payment_id,
                    "status": existing_payment.status,
                    "message": "Duplicate request — returning original payment",
                }

        # Determine payment type
        if destination_account_id:
            payment_type = "INTERNAL"
        elif beneficiary_id:
            beneficiary = await self._get_beneficiary(db, beneficiary_id)
            if not beneficiary:
                return {"error": "BENEFICIARY_NOT_FOUND",
                        "error_code": "BENEFICIARY_NOT_FOUND"}
            if not beneficiary.is_active:
                return {"error": "BENEFICIARY_INACTIVE",
                        "error_code": "BENEFICIARY_INACTIVE"}
            if beneficiary.sanctions_status == "flagged":
                return {"error": "BENEFICIARY_SANCTIONS_FLAGGED",
                        "error_code": "BENEFICIARY_SANCTIONS_FLAGGED"}
            if beneficiary.beneficiary_type == "AGENTIS_MEMBER":
                payment_type = "INTERNAL"
                destination_account_id = beneficiary.agentis_account_id
            else:
                payment_type = "EFT"  # Phase 2
        else:
            return {"error": "NO_DESTINATION",
                    "error_code": "NO_DESTINATION",
                    "message": "Provide destination_account_id or beneficiary_id"}

        # Phase 1: only internal transfers
        if payment_type != "INTERNAL":
            return {"error": "PAYMENT_TYPE_NOT_AVAILABLE",
                    "error_code": "PAYMENT_TYPE_NOT_AVAILABLE",
                    "message": "Only internal transfers available in current phase"}

        # Agent mandate validation
        needs_confirmation = False
        if agent_id and self.members:
            mandate_check = await self.members.validate_mandate_action(
                db, agent_id=agent_id, required_level="L1",
                amount_zar=amount, currency=currency,
                beneficiary_id=beneficiary_id,
            )
            if not mandate_check["allowed"]:
                # Log mandate breach attempt
                if self.compliance:
                    await self.compliance.log_monitoring_event(
                        db,
                        event_type="MANDATE_BREACH",
                        description=(f"Agent {agent_id} payment rejected: "
                                     f"{mandate_check['error']}"),
                        severity="high",
                        member_id=member_id,
                        agent_id=agent_id,
                        mandate_id=mandate_id,
                        amount_zar=amount,
                        channel=channel,
                        requires_review=True,
                    )
                return {"error": mandate_check["error"],
                        "error_code": mandate_check["error_code"]}

            needs_confirmation = mandate_check.get("needs_3fa_confirmation", False)
            mandate_id = mandate_check.get("mandate_id", mandate_id)

        # Fraud detection
        fraud_result = await self._run_fraud_checks(
            db, member_id=member_id, agent_id=agent_id,
            account_id=source_account_id, amount=amount,
            beneficiary_id=beneficiary_id,
        )
        if fraud_result.get("blocked"):
            return {"error": "FRAUD_BLOCKED",
                    "error_code": "FRAUD_BLOCKED",
                    "message": fraud_result["reason"]}

        fee = PAYMENT_FEES.get(payment_type, 0)
        now = datetime.now(timezone.utc)

        payment = AgentisPayment(
            source_account_id=source_account_id,
            member_id=member_id,
            agent_id=agent_id,
            mandate_id=mandate_id,
            beneficiary_id=beneficiary_id,
            payment_type=payment_type,
            amount=amount,
            currency=currency,
            amount_zar=amount,
            fee_amount=fee,
            reference=reference,
            description=description,
            destination_account_id=destination_account_id,
            destination_member_id=None,
            requires_confirmation=needs_confirmation,
            high_value_flag=(amount >= 50000),
            idempotency_key=idempotency_key,
            status="pending_confirmation" if needs_confirmation else "processing",
        )

        if needs_confirmation:
            payment.confirmation_requested_at = now
            payment.confirmation_expires_at = now + timedelta(minutes=30)
            db.add(payment)

            # Create confirmation record
            confirmation = AgentisPaymentConfirmation(
                payment_id=payment.payment_id,
                expires_at=now + timedelta(minutes=30),
                notification_sent=True,
                notification_channel="webhook",
            )
            db.add(confirmation)

            return {
                "payment_id": payment.payment_id,
                "status": "pending_confirmation",
                "message": "Payment requires operator 3FA confirmation",
                "confirmation_expires_at": payment.confirmation_expires_at.isoformat(),
            }

        # Execute payment immediately (internal transfer)
        if payment_type == "INTERNAL" and self.accounts:
            transfer_result = await self.accounts.internal_transfer(
                db,
                source_account_id=source_account_id,
                destination_account_id=destination_account_id,
                amount=amount,
                reference=reference,
                description=description,
                agent_id=agent_id,
                mandate_id=mandate_id,
                idempotency_key=f"PAY_{idempotency_key}" if idempotency_key else None,
            )

            if "error" in transfer_result:
                payment.status = "failed"
                payment.failure_reason = transfer_result["error"]
                db.add(payment)
                return transfer_result

            payment.status = "completed"
            payment.completed_at = now
            payment.destination_member_id = transfer_result.get("destination_account")

        # Blockchain
        if self.blockchain:
            from app.blockchain.transaction import Transaction, TransactionType
            btx = Transaction(
                type=TransactionType.AGENTIS_TRANSFER_INTERNAL,
                sender_id=member_id,
                receiver_id=payment.destination_member_id or "internal",
                amount=amount,
                currency=currency,
                description=f"Payment: {reference}",
                metadata={"payment_id": payment.payment_id,
                          "payment_type": payment_type},
            )
            self.blockchain.add_transaction(btx)
            payment.blockchain_hash = btx.id

        db.add(payment)

        # Update mandate totals
        if mandate_id and self.members:
            await self.members.update_mandate_totals(db, mandate_id, amount)

        # Update beneficiary usage
        if beneficiary_id:
            await self._update_beneficiary_usage(db, beneficiary_id)

        return {
            "payment_id": payment.payment_id,
            "status": payment.status,
            "amount": amount,
            "fee": fee,
            "payment_type": payment_type,
            "reference": reference,
        }

    async def confirm_payment(
        self, db: AsyncSession, *,
        payment_id: str,
        three_fa_ref: str,
    ) -> dict:
        """Operator confirms a pending high-value payment."""
        result = await db.execute(
            select(AgentisPayment).where(
                AgentisPayment.payment_id == payment_id,
                AgentisPayment.status == "pending_confirmation",
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return {"error": "PAYMENT_NOT_FOUND_OR_NOT_PENDING",
                    "error_code": "PAYMENT_NOT_FOUND"}

        now = datetime.now(timezone.utc)
        if payment.confirmation_expires_at and payment.confirmation_expires_at < now:
            payment.status = "failed"
            payment.failure_reason = "Confirmation expired"
            return {"error": "CONFIRMATION_EXPIRED",
                    "error_code": "CONFIRMATION_EXPIRED"}

        payment.confirmed_at = now
        payment.confirmation_3fa_ref = three_fa_ref
        payment.status = "processing"

        # Execute the transfer
        if payment.payment_type == "INTERNAL" and self.accounts:
            transfer_result = await self.accounts.internal_transfer(
                db,
                source_account_id=payment.source_account_id,
                destination_account_id=payment.destination_account_id,
                amount=payment.amount,
                reference=payment.reference,
                description=payment.description,
                agent_id=payment.agent_id,
                mandate_id=payment.mandate_id,
            )
            if "error" in transfer_result:
                payment.status = "failed"
                payment.failure_reason = transfer_result["error"]
                return transfer_result

            payment.status = "completed"
            payment.completed_at = now

        return {
            "payment_id": payment.payment_id,
            "status": payment.status,
            "confirmed_at": now.isoformat(),
        }

    async def cancel_payment(self, db: AsyncSession, payment_id: str) -> dict:
        """Cancel a pending payment."""
        result = await db.execute(
            select(AgentisPayment).where(
                AgentisPayment.payment_id == payment_id,
                AgentisPayment.status.in_(["pending", "pending_confirmation"]),
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return {"error": "PAYMENT_NOT_FOUND_OR_NOT_CANCELLABLE",
                    "error_code": "PAYMENT_NOT_FOUND"}

        payment.status = "cancelled"
        return {"payment_id": payment_id, "status": "cancelled"}

    async def get_payment(self, db: AsyncSession, payment_id: str) -> dict | None:
        """Get payment details."""
        result = await db.execute(
            select(AgentisPayment).where(AgentisPayment.payment_id == payment_id)
        )
        payment = result.scalar_one_or_none()
        if not payment:
            return None
        return {
            "payment_id": payment.payment_id,
            "payment_type": payment.payment_type,
            "amount": payment.amount,
            "currency": payment.currency,
            "fee": payment.fee_amount,
            "reference": payment.reference,
            "description": payment.description,
            "status": payment.status,
            "requires_confirmation": payment.requires_confirmation,
            "initiated_at": payment.initiated_at.isoformat(),
            "completed_at": payment.completed_at.isoformat() if payment.completed_at else None,
        }

    async def get_payment_history(
        self, db: AsyncSession, *,
        member_id: str,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[dict]:
        """Get payment history for a member."""
        query = select(AgentisPayment).where(
            AgentisPayment.member_id == member_id
        )
        if status:
            query = query.where(AgentisPayment.status == status)
        query = query.order_by(AgentisPayment.initiated_at.desc())
        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        payments = result.scalars().all()
        return [
            {
                "payment_id": p.payment_id,
                "payment_type": p.payment_type,
                "amount": p.amount,
                "currency": p.currency,
                "reference": p.reference,
                "status": p.status,
                "initiated_at": p.initiated_at.isoformat(),
            }
            for p in payments
        ]

    # ------------------------------------------------------------------
    # Beneficiary Management
    # ------------------------------------------------------------------

    async def add_beneficiary(
        self, db: AsyncSession, *,
        member_id: str,
        beneficiary_type: str,
        display_name: str,
        operator_3fa_ref: str | None = None,
        added_by: str = "member",
        # Internal
        agentis_member_id: str | None = None,
        agentis_account_id: str | None = None,
        # SA bank
        account_number: str | None = None,
        bank_code: str | None = None,
        branch_code: str | None = None,
        # Crypto
        crypto_address: str | None = None,
        crypto_network: str | None = None,
    ) -> dict:
        """Add a payment beneficiary. Requires operator 3FA for most cases."""
        beneficiary = AgentisBeneficiary(
            member_id=member_id,
            beneficiary_type=beneficiary_type,
            display_name=display_name,
            operator_3fa_ref=operator_3fa_ref,
            added_by=added_by,
            agentis_member_id=agentis_member_id,
            agentis_account_id=agentis_account_id,
            account_number=account_number,
            bank_code=bank_code,
            branch_code=branch_code,
            crypto_address=crypto_address,
            crypto_network=crypto_network,
        )
        db.add(beneficiary)

        # Sanctions screening on new beneficiary
        if self.compliance:
            await self.compliance.screen_sanctions(
                db,
                entity_type="BENEFICIARY",
                entity_id=beneficiary.beneficiary_id,
                entity_name=display_name,
            )
            beneficiary.sanctions_status = "cleared"
            beneficiary.sanctions_cleared_at = datetime.now(timezone.utc)

        return {
            "beneficiary_id": beneficiary.beneficiary_id,
            "display_name": display_name,
            "beneficiary_type": beneficiary_type,
            "sanctions_status": beneficiary.sanctions_status,
        }

    async def list_beneficiaries(self, db: AsyncSession,
                                  member_id: str) -> list[dict]:
        """List all beneficiaries for a member."""
        result = await db.execute(
            select(AgentisBeneficiary).where(
                AgentisBeneficiary.member_id == member_id,
                AgentisBeneficiary.is_active == True,
            ).order_by(AgentisBeneficiary.display_name)
        )
        beneficiaries = result.scalars().all()
        return [
            {
                "beneficiary_id": b.beneficiary_id,
                "display_name": b.display_name,
                "beneficiary_type": b.beneficiary_type,
                "sanctions_status": b.sanctions_status,
                "total_payments": b.total_payments,
                "last_payment_at": b.last_payment_at.isoformat() if b.last_payment_at else None,
            }
            for b in beneficiaries
        ]

    async def _get_beneficiary(self, db: AsyncSession,
                                beneficiary_id: str) -> AgentisBeneficiary | None:
        result = await db.execute(
            select(AgentisBeneficiary).where(
                AgentisBeneficiary.beneficiary_id == beneficiary_id
            )
        )
        return result.scalar_one_or_none()

    async def _update_beneficiary_usage(self, db: AsyncSession,
                                         beneficiary_id: str) -> None:
        beneficiary = await self._get_beneficiary(db, beneficiary_id)
        if beneficiary:
            now = datetime.now(timezone.utc)
            if not beneficiary.first_payment_at:
                beneficiary.first_payment_at = now
            beneficiary.last_payment_at = now
            beneficiary.total_payments += 1

    # ------------------------------------------------------------------
    # Standing Orders
    # ------------------------------------------------------------------

    async def create_standing_order(
        self, db: AsyncSession, *,
        account_id: str,
        member_id: str,
        beneficiary_id: str,
        amount: float,
        frequency: str,
        start_date,
        reference: str,
        agent_id: str | None = None,
        mandate_id: str | None = None,
        operator_3fa_ref: str | None = None,
        day_of_month: int | None = None,
        day_of_week: int | None = None,
        end_date=None,
    ) -> dict:
        """Create a recurring payment instruction."""
        if frequency not in ("DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "ANNUALLY"):
            return {"error": "INVALID_FREQUENCY", "error_code": "INVALID_FREQUENCY"}

        so = AgentisStandingOrder(
            account_id=account_id,
            member_id=member_id,
            agent_id=agent_id,
            mandate_id=mandate_id,
            beneficiary_id=beneficiary_id,
            amount=amount,
            reference=reference,
            frequency=frequency,
            day_of_month=day_of_month,
            day_of_week=day_of_week,
            start_date=start_date,
            end_date=end_date,
            next_execution_at=datetime.combine(start_date, datetime.min.time()).replace(
                tzinfo=timezone.utc),
            created_by="agent" if agent_id else "member",
            operator_3fa_ref=operator_3fa_ref,
        )
        db.add(so)

        if self.blockchain:
            from app.blockchain.transaction import Transaction, TransactionType
            btx = Transaction(
                type=TransactionType.AGENTIS_STANDING_ORDER,
                sender_id=member_id,
                amount=amount,
                description=f"Standing order created: {frequency} R{amount:,.2f}",
                metadata={"so_id": so.so_id, "frequency": frequency},
            )
            self.blockchain.add_transaction(btx)

        return {
            "so_id": so.so_id,
            "frequency": frequency,
            "amount": amount,
            "next_execution": so.next_execution_at.isoformat(),
            "status": "active",
        }

    async def list_standing_orders(self, db: AsyncSession,
                                    member_id: str) -> list[dict]:
        """List standing orders for a member."""
        result = await db.execute(
            select(AgentisStandingOrder).where(
                AgentisStandingOrder.member_id == member_id,
            ).order_by(AgentisStandingOrder.next_execution_at)
        )
        orders = result.scalars().all()
        return [
            {
                "so_id": o.so_id,
                "amount": o.amount,
                "frequency": o.frequency,
                "reference": o.reference,
                "next_execution": o.next_execution_at.isoformat(),
                "executions_completed": o.executions_completed,
                "is_active": o.is_active,
            }
            for o in orders
        ]

    # ------------------------------------------------------------------
    # Fraud Detection Engine
    # ------------------------------------------------------------------

    async def _run_fraud_checks(
        self, db: AsyncSession, *,
        member_id: str,
        agent_id: str | None,
        account_id: str,
        amount: float,
        beneficiary_id: str | None,
    ) -> dict:
        """Run synchronous fraud detection rules on payment initiation."""
        now = datetime.now(timezone.utc)

        # Rule 1: Velocity — more than 10 payments in 60 minutes
        one_hour_ago = now - timedelta(hours=1)
        result = await db.execute(
            select(func.count(AgentisPayment.payment_id)).where(
                AgentisPayment.source_account_id == account_id,
                AgentisPayment.initiated_at >= one_hour_ago,
            )
        )
        recent_count = result.scalar() or 0
        if recent_count >= VELOCITY_MAX_PAYMENTS_PER_HOUR:
            fraud_event = AgentisFraudEvent(
                member_id=member_id, agent_id=agent_id, account_id=account_id,
                rule_triggered="VELOCITY",
                rule_description=f"{recent_count} payments in last 60 min (limit: {VELOCITY_MAX_PAYMENTS_PER_HOUR})",
                severity="high",
                action_taken="BLOCKED",
                details={"recent_count": recent_count},
            )
            db.add(fraud_event)
            return {"blocked": True, "reason": "Velocity limit exceeded — too many payments in 60 minutes"}

        # Rule 2: New beneficiary limit
        if beneficiary_id:
            beneficiary = await self._get_beneficiary(db, beneficiary_id)
            if beneficiary and not beneficiary.first_payment_at:
                if amount > NEW_BENEFICIARY_LIMIT_ZAR:
                    fraud_event = AgentisFraudEvent(
                        member_id=member_id, agent_id=agent_id, account_id=account_id,
                        rule_triggered="NEW_BENEFICIARY",
                        rule_description=f"First payment to new beneficiary exceeds R{NEW_BENEFICIARY_LIMIT_ZAR:,.0f}",
                        severity="medium",
                        action_taken="BLOCKED",
                        details={"amount": amount, "limit": NEW_BENEFICIARY_LIMIT_ZAR},
                    )
                    db.add(fraud_event)
                    return {"blocked": True,
                            "reason": f"First payment to new beneficiary limited to R{NEW_BENEFICIARY_LIMIT_ZAR:,.0f}"}

        # Rule 3: Round number structuring (3+ round-number txns in 24h)
        if amount % 1000 == 0 and amount > 0:
            twenty_four_h_ago = now - timedelta(hours=24)
            result = await db.execute(
                select(func.count(AgentisPayment.payment_id)).where(
                    AgentisPayment.member_id == member_id,
                    AgentisPayment.initiated_at >= twenty_four_h_ago,
                    AgentisPayment.amount % 1000 == 0,
                )
            )
            round_count = result.scalar() or 0
            if round_count >= 2:  # This would be the 3rd
                fraud_event = AgentisFraudEvent(
                    member_id=member_id, agent_id=agent_id, account_id=account_id,
                    rule_triggered="ROUND_NUMBER_STRUCTURING",
                    rule_description=f"{round_count + 1} round-number transactions in 24h",
                    severity="medium",
                    action_taken="ESCALATED",
                    details={"round_count": round_count + 1},
                )
                db.add(fraud_event)
                # Don't block, but flag for STR screening

        return {"blocked": False}
