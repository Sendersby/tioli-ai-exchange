"""PayPal service — account management, disbursement, outbound billing."""

import os
import secrets
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.paypal.models import (
    OwnerPayPalAccount, PayPalDisbursementRecord, PayPalOutboundPayment,
    PayPalBillingAgreement, PayPalWebhookEvent, PayPalAccountAuditLog,
)
from app.paypal.adapter import PayPalAdapter
from app.config import settings

CREDIT_ZAR_RATE = 0.055
ZAR_USD_RATE = 18.5  # Default, replaced by live FX in production
PAYPAL_FEE_PCT = 0.02
PAYPAL_FEE_FIXED = 0.25


def _check_enabled():
    if not os.environ.get("PAYPAL_ENABLED", "false").lower() == "true":
        raise ValueError("PayPal module is not enabled. Set PAYPAL_ENABLED=true.")


class PayPalService:
    """PayPal account management, receive, and pay operations."""

    def __init__(self, adapter: PayPalAdapter):
        self.adapter = adapter

    # ── Account Management (Section 4.1) ─────────────────────────

    async def register_account(
        self, db: AsyncSession, paypal_email: str, account_label: str,
        can_receive: bool = True, can_pay: bool = False,
        receive_pct: float = 0.0, expense_categories: list | None = None,
        verification_ref: str | None = None, change_reason: str = ""
    ) -> OwnerPayPalAccount:
        _check_enabled()
        account = OwnerPayPalAccount(
            paypal_email=paypal_email,
            account_label=account_label,
            can_receive=can_receive,
            can_pay=can_pay,
            receive_pct=receive_pct,
            expense_categories=expense_categories,
            verified_by_3fa=verification_ref is not None,
            verification_ref=verification_ref,
            change_reason=change_reason,
        )
        account.account_hash = account.compute_hash()
        db.add(account)

        audit = PayPalAccountAuditLog(
            change_type="ACCOUNT_REGISTERED",
            account_id=account.account_id,
            new_hash=account.account_hash,
            verification_ref=verification_ref,
            change_reason=change_reason,
        )
        db.add(audit)
        await db.flush()
        return account

    async def list_accounts(self, db: AsyncSession) -> list[dict]:
        _check_enabled()
        result = await db.execute(
            select(OwnerPayPalAccount).where(OwnerPayPalAccount.is_active == True)
            .order_by(OwnerPayPalAccount.created_at.desc())
        )
        return [
            {
                "account_id": a.account_id,
                "email_masked": a.paypal_email[:3] + "***@" + a.paypal_email.split("@")[-1] if "@" in a.paypal_email else "***",
                "label": a.account_label,
                "can_receive": a.can_receive,
                "can_pay": a.can_pay,
                "receive_pct": a.receive_pct,
                "billing_agreement_status": a.billing_agreement_status,
                "verified": a.verified_by_3fa,
            }
            for a in result.scalars().all()
        ]

    async def deactivate_account(
        self, db: AsyncSession, account_id: str
    ) -> dict:
        _check_enabled()
        result = await db.execute(
            select(OwnerPayPalAccount).where(OwnerPayPalAccount.account_id == account_id)
        )
        account = result.scalar_one_or_none()
        if not account:
            raise ValueError("Account not found")
        account.is_active = False

        audit = PayPalAccountAuditLog(
            change_type="ACCOUNT_DEACTIVATED",
            account_id=account_id,
            new_hash=account.account_hash,
        )
        db.add(audit)
        await db.flush()
        return {"account_id": account_id, "status": "deactivated"}

    # ── Receive Commission (Section 4.3) ─────────────────────────

    async def preview_disbursement(self, db: AsyncSession, credits: float) -> dict:
        _check_enabled()
        zar = credits * CREDIT_ZAR_RATE
        usd = round(zar / ZAR_USD_RATE, 2)
        estimated_fee = round(usd * PAYPAL_FEE_PCT + PAYPAL_FEE_FIXED, 2)
        net = round(usd - estimated_fee, 2)

        accounts = await self._get_receive_accounts(db)
        allocations = []
        for a in accounts:
            acct_usd = round(usd * a.receive_pct / 100, 2)
            acct_fee = round(acct_usd * PAYPAL_FEE_PCT + PAYPAL_FEE_FIXED, 2)
            allocations.append({
                "account": a.account_label,
                "pct": a.receive_pct,
                "usd_gross": acct_usd,
                "estimated_fee": acct_fee,
                "usd_net": round(acct_usd - acct_fee, 2),
            })

        return {
            "credits": credits,
            "zar": zar,
            "usd_gross": usd,
            "total_estimated_fees": estimated_fee,
            "usd_net": net,
            "credit_zar_rate": CREDIT_ZAR_RATE,
            "zar_usd_rate": ZAR_USD_RATE,
            "accounts": allocations,
            "sandbox": self.adapter.is_sandbox,
        }

    async def execute_disbursement(
        self, db: AsyncSession, credits: float, disbursement_record_id: str
    ) -> list[dict]:
        _check_enabled()
        zar = credits * CREDIT_ZAR_RATE
        usd_total = round(zar / ZAR_USD_RATE, 2)

        accounts = await self._get_receive_accounts(db)
        results = []

        for acct in accounts:
            acct_usd = round(usd_total * acct.receive_pct / 100, 2)
            if acct_usd <= 0:
                continue

            idem_key = f"{disbursement_record_id}:PAYPAL:{acct.account_id}"

            # Verify account hash before payout
            if acct.compute_hash() != acct.account_hash:
                results.append({
                    "account": acct.account_label,
                    "status": "BLOCKED",
                    "reason": "Account hash mismatch — possible tampering",
                })
                continue

            try:
                payout_result = await self.adapter.send_payout(
                    recipient_email=acct.paypal_email,
                    usd_amount=acct_usd,
                    note="TiOLi AI Investments commission disbursement",
                    idempotency_key=idem_key,
                )

                record = PayPalDisbursementRecord(
                    disbursement_record_id=disbursement_record_id,
                    account_id=acct.account_id,
                    paypal_email_sent_to=acct.paypal_email,
                    credits_allocated=credits * acct.receive_pct / 100,
                    usd_amount_sent=acct_usd,
                    credit_zar_rate_used=CREDIT_ZAR_RATE,
                    zar_usd_rate_used=ZAR_USD_RATE,
                    paypal_payout_batch_id=payout_result.get("batch_id"),
                    paypal_payout_item_id=payout_result.get("item_id"),
                    status="PROCESSING",
                )
                db.add(record)
                results.append({
                    "account": acct.account_label,
                    "usd": acct_usd, "status": "PROCESSING",
                    "batch_id": payout_result.get("batch_id"),
                })
            except Exception as e:
                record = PayPalDisbursementRecord(
                    disbursement_record_id=disbursement_record_id,
                    account_id=acct.account_id,
                    paypal_email_sent_to=acct.paypal_email,
                    credits_allocated=credits * acct.receive_pct / 100,
                    usd_amount_sent=acct_usd,
                    credit_zar_rate_used=CREDIT_ZAR_RATE,
                    zar_usd_rate_used=ZAR_USD_RATE,
                    status="FAILED",
                    failure_reason=str(e),
                )
                db.add(record)
                results.append({"account": acct.account_label, "status": "FAILED", "error": str(e)})

        await db.flush()
        return results

    async def get_disbursement_history(self, db: AsyncSession, limit: int = 50) -> list[dict]:
        _check_enabled()
        result = await db.execute(
            select(PayPalDisbursementRecord)
            .order_by(PayPalDisbursementRecord.initiated_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": r.paypal_disbursement_id, "account_id": r.account_id,
                "usd": r.usd_amount_sent, "fee": r.paypal_fee_usd,
                "status": r.status, "batch_id": r.paypal_payout_batch_id,
                "tx_id": r.paypal_transaction_id,
                "initiated": str(r.initiated_at),
            }
            for r in result.scalars().all()
        ]

    # ── Outbound Billing (Section 4.4) ───────────────────────────

    async def initiate_one_time_payment(
        self, db: AsyncSession, account_id: str, expense_category: str,
        payee_name: str, usd_amount: float, description: str = "",
        profitability_ratio: float = 999.0, three_fa_ref: str | None = None,
    ) -> dict:
        _check_enabled()
        zar_eq = round(usd_amount * ZAR_USD_RATE, 2)

        # Check profitability
        is_security = expense_category == "security"
        required = 3.0 if is_security else 10.0
        if profitability_ratio < required:
            return {
                "status": "BLOCKED",
                "reason": f"Profitability {profitability_ratio:.1f}x below {required}x threshold",
            }

        idem_key = f"outbound_{secrets.token_hex(8)}"
        order = await self.adapter.create_order(usd_amount, description or payee_name, idem_key)

        record = PayPalOutboundPayment(
            account_id=account_id,
            expense_category=expense_category,
            payee_name=payee_name,
            usd_amount=usd_amount,
            zar_equivalent=zar_eq,
            payment_type="ONE_TIME",
            paypal_order_id=order.get("order_id"),
            status="PENDING",
            profitability_check_passed=True,
            profitability_ratio_at_time=profitability_ratio,
            three_fa_required=three_fa_ref is not None,
            three_fa_ref=three_fa_ref,
        )
        db.add(record)
        await db.flush()

        return {
            "payment_id": record.outbound_payment_id,
            "order_id": order.get("order_id"),
            "approval_url": order.get("approval_url"),
            "status": "PENDING_APPROVAL",
        }

    async def get_outbound_history(self, db: AsyncSession, limit: int = 50) -> list[dict]:
        _check_enabled()
        result = await db.execute(
            select(PayPalOutboundPayment)
            .order_by(PayPalOutboundPayment.initiated_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": p.outbound_payment_id, "payee": p.payee_name,
                "category": p.expense_category, "usd": p.usd_amount,
                "status": p.status, "profitability": p.profitability_ratio_at_time,
                "initiated": str(p.initiated_at),
            }
            for p in result.scalars().all()
        ]

    # ── Billing Agreements (Section 4.2) ─────────────────────────

    async def initiate_billing_agreement(
        self, db: AsyncSession, account_id: str,
        max_monthly_charge: float = 500.0
    ) -> dict:
        _check_enabled()
        result = await self.adapter.create_billing_agreement_token(
            "TiOLi AGENTIS — Platform Expense Authorization",
            max_monthly_charge,
        )

        ba = PayPalBillingAgreement(
            account_id=account_id,
            paypal_token=result.get("token"),
            approval_url=result.get("approval_url"),
            max_monthly_charge=max_monthly_charge,
        )
        db.add(ba)
        await db.flush()

        return {
            "agreement_id": ba.agreement_id,
            "approval_url": result.get("approval_url"),
            "message": "Visit the approval URL to authorize the platform in PayPal.",
        }

    async def complete_billing_agreement(
        self, db: AsyncSession, ba_token: str
    ) -> dict:
        _check_enabled()
        result = await self.adapter.execute_billing_agreement(ba_token)

        # Find the agreement by token
        ba_result = await db.execute(
            select(PayPalBillingAgreement).where(PayPalBillingAgreement.paypal_token == ba_token)
        )
        ba = ba_result.scalar_one_or_none()
        if ba:
            ba.paypal_agreement_id = result.get("agreement_id")
            ba.agreement_status = "ACTIVE"
            ba.approved_at = datetime.now(timezone.utc)

            # Update the parent account
            acct_result = await db.execute(
                select(OwnerPayPalAccount).where(OwnerPayPalAccount.account_id == ba.account_id)
            )
            acct = acct_result.scalar_one_or_none()
            if acct:
                acct.billing_agreement_id = result.get("agreement_id")
                acct.billing_agreement_status = "ACTIVE"
                acct.billing_agreement_approved_at = datetime.now(timezone.utc)

            await db.flush()

        return result

    async def list_billing_agreements(self, db: AsyncSession) -> list[dict]:
        _check_enabled()
        result = await db.execute(
            select(PayPalBillingAgreement).order_by(PayPalBillingAgreement.created_at.desc())
        )
        return [
            {
                "id": ba.agreement_id, "account_id": ba.account_id,
                "paypal_id": ba.paypal_agreement_id,
                "status": ba.agreement_status,
                "max_monthly": ba.max_monthly_charge,
                "approved_at": str(ba.approved_at) if ba.approved_at else None,
            }
            for ba in result.scalars().all()
        ]

    # ── Webhooks (Section 4.5) ───────────────────────────────────

    async def process_webhook(
        self, db: AsyncSession, paypal_event_id: str, event_type: str,
        resource_type: str | None, resource_id: str | None,
        raw_payload: dict, signature_verified: bool
    ) -> dict:
        _check_enabled()
        # Idempotency: check if already processed
        existing = await db.execute(
            select(PayPalWebhookEvent).where(PayPalWebhookEvent.paypal_event_id == paypal_event_id)
        )
        if existing.scalar_one_or_none():
            return {"status": "already_processed"}

        event = PayPalWebhookEvent(
            paypal_event_id=paypal_event_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            raw_payload=raw_payload,
            signature_verified=signature_verified,
        )
        db.add(event)

        # Process based on event type
        processing_result = "stored"
        if event_type == "PAYMENT.PAYOUTS-ITEM.SUCCEEDED" and resource_id:
            await self._update_payout_status(db, resource_id, "SUCCESS")
            processing_result = "payout_success_updated"
        elif event_type in ("PAYMENT.PAYOUTS-ITEM.FAILED", "PAYMENT.PAYOUTS-ITEM.RETURNED"):
            await self._update_payout_status(db, resource_id, "FAILED")
            processing_result = "payout_failure_updated"

        event.processed = True
        event.processing_result = processing_result
        event.processed_at = datetime.now(timezone.utc)
        await db.flush()

        return {"status": "processed", "result": processing_result}

    async def get_webhook_events(self, db: AsyncSession, limit: int = 20) -> list[dict]:
        _check_enabled()
        result = await db.execute(
            select(PayPalWebhookEvent)
            .order_by(PayPalWebhookEvent.received_at.desc())
            .limit(limit)
        )
        return [
            {
                "event_id": e.paypal_event_id, "type": e.event_type,
                "verified": e.signature_verified, "processed": e.processed,
                "result": e.processing_result,
                "received": str(e.received_at),
            }
            for e in result.scalars().all()
        ]

    # ── Helpers ───────────────────────────────────────────────────

    async def _get_receive_accounts(self, db: AsyncSession) -> list[OwnerPayPalAccount]:
        result = await db.execute(
            select(OwnerPayPalAccount).where(
                OwnerPayPalAccount.is_active == True,
                OwnerPayPalAccount.can_receive == True,
                OwnerPayPalAccount.receive_pct > 0,
            )
        )
        return list(result.scalars().all())

    async def _update_payout_status(
        self, db: AsyncSession, item_id: str, status: str
    ):
        result = await db.execute(
            select(PayPalDisbursementRecord).where(
                PayPalDisbursementRecord.paypal_payout_item_id == item_id
            )
        )
        record = result.scalar_one_or_none()
        if record:
            record.status = status
            if status == "SUCCESS":
                record.completed_at = datetime.now(timezone.utc)
