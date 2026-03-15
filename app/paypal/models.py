"""PayPal Integration Module — all 6 new database tables.

ADDITIVE ONLY. No existing tables modified.
"""

import uuid
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Integer, Text, JSON, ForeignKey

from app.database.db import Base


class OwnerPayPalAccount(Base):
    """Registered PayPal accounts — versioned, audited (Section 3.1)."""
    __tablename__ = "owner_paypal_accounts"

    account_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    paypal_email = Column(String(200), nullable=False)  # Encrypted at rest in production
    paypal_merchant_id = Column(String(80), nullable=True)
    account_label = Column(String(100), nullable=False)
    can_receive = Column(Boolean, nullable=False, default=True)
    can_pay = Column(Boolean, nullable=False, default=False)
    billing_agreement_id = Column(String(200), nullable=True)
    billing_agreement_status = Column(String(40), nullable=True)
    billing_agreement_approved_at = Column(DateTime, nullable=True)
    receive_pct = Column(Float, nullable=False, default=0.0)
    expense_categories = Column(JSON, nullable=True)
    verified_by_3fa = Column(Boolean, nullable=False, default=False)
    verification_ref = Column(String, nullable=True)
    account_hash = Column(String(64), nullable=False, default="")
    previous_version_id = Column(String, nullable=True)
    change_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def compute_hash(self) -> str:
        data = json.dumps({
            "email": self.paypal_email, "label": self.account_label,
            "can_receive": self.can_receive, "can_pay": self.can_pay,
            "receive_pct": self.receive_pct,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()


class PayPalDisbursementRecord(Base):
    """Inbound commission payouts to owner PayPal (Section 3.2)."""
    __tablename__ = "paypal_disbursement_records"

    paypal_disbursement_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    disbursement_record_id = Column(String, nullable=False)
    account_id = Column(String, ForeignKey("owner_paypal_accounts.account_id"), nullable=False)
    paypal_email_sent_to = Column(String(200), nullable=False)
    credits_allocated = Column(Float, nullable=False)
    usd_amount_sent = Column(Float, nullable=False)
    credit_zar_rate_used = Column(Float, nullable=False)
    zar_usd_rate_used = Column(Float, nullable=False)
    paypal_payout_batch_id = Column(String(200), nullable=True)
    paypal_payout_item_id = Column(String(200), nullable=True)
    paypal_transaction_id = Column(String(200), nullable=True)
    paypal_fee_usd = Column(Float, nullable=True)
    status = Column(String(40), nullable=False, default="PENDING")
    failure_reason = Column(Text, nullable=True)
    initiated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


class PayPalOutboundPayment(Base):
    """Outbound expense payments from owner PayPal (Section 3.3)."""
    __tablename__ = "paypal_outbound_payments"

    outbound_payment_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("owner_paypal_accounts.account_id"), nullable=False)
    expense_category = Column(String(80), nullable=False)
    payee_name = Column(String(200), nullable=False)
    payee_paypal_email = Column(String(200), nullable=True)
    payee_url = Column(String(500), nullable=True)
    usd_amount = Column(Float, nullable=False)
    zar_equivalent = Column(Float, nullable=False)
    payment_type = Column(String(40), nullable=False)  # ONE_TIME, RECURRING_SUBSCRIPTION, AUTO_RENEWAL
    recurrence_schedule = Column(String(40), nullable=True)
    paypal_order_id = Column(String(200), nullable=True)
    paypal_capture_id = Column(String(200), nullable=True)
    paypal_subscription_id = Column(String(200), nullable=True)
    status = Column(String(40), nullable=False, default="PENDING")
    profitability_check_passed = Column(Boolean, nullable=False, default=False)
    profitability_ratio_at_time = Column(Float, nullable=True)
    three_fa_required = Column(Boolean, nullable=False, default=False)
    three_fa_ref = Column(String, nullable=True)
    initiated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    ledger_txn_id = Column(String(120), nullable=True)


class PayPalBillingAgreement(Base):
    """Billing agreements for recurring outbound payments (Section 3.4)."""
    __tablename__ = "paypal_billing_agreements"

    agreement_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("owner_paypal_accounts.account_id"), nullable=False)
    paypal_token = Column(String(200), nullable=True)
    paypal_agreement_id = Column(String(200), nullable=True)
    agreement_status = Column(String(40), nullable=False, default="PENDING_APPROVAL")
    approval_url = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    max_monthly_charge = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class PayPalWebhookEvent(Base):
    """Raw PayPal webhook events (Section 3.5)."""
    __tablename__ = "paypal_webhook_events"

    webhook_event_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    paypal_event_id = Column(String(200), nullable=False, unique=True)
    event_type = Column(String(200), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(200), nullable=True)
    raw_payload = Column(JSON, nullable=False)
    signature_verified = Column(Boolean, nullable=False, default=False)
    processed = Column(Boolean, nullable=False, default=False)
    processing_result = Column(Text, nullable=True)
    received_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, nullable=True)


class PayPalAccountAuditLog(Base):
    """Immutable audit log for PayPal account changes (Section 3.6)."""
    __tablename__ = "paypal_account_audit_log"

    audit_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    change_type = Column(String(60), nullable=False)
    account_id = Column(String, nullable=False)
    previous_hash = Column(String(64), nullable=True)
    new_hash = Column(String(64), nullable=False)
    verification_ref = Column(String, nullable=True)
    change_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
