"""Agentis Payment & Settlement Infrastructure — Database Models (Module 4).

Payment rails, autonomous agent payment engine, standing orders, debit orders,
beneficiary management, fraud detection.

ADDITIVE ONLY. No existing tables modified.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Float, String, Boolean, Integer, Text,
    ForeignKey, Index, JSON, CheckConstraint, Date,
)

from app.database.db import Base


class AgentisPayment(Base):
    """Payment instruction records — internal and external."""
    __tablename__ = "agentis_payments"

    payment_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_account_id = Column(String, ForeignKey("agentis_accounts.account_id"), nullable=False)
    member_id = Column(String, ForeignKey("agentis_members.member_id"), nullable=False)
    agent_id = Column(String, nullable=True)
    mandate_id = Column(String, nullable=True)

    beneficiary_id = Column(String, ForeignKey("agentis_beneficiaries.beneficiary_id"),
                            nullable=True)

    payment_type = Column(String(30), nullable=False)
    # INTERNAL, EFT, INSTANT_EFT, CRYPTO, PAYPAL
    # Phase 1: INTERNAL only; Phase 2: EFT, INSTANT_EFT; Phase 3: CRYPTO, PAYPAL

    amount = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False, default="ZAR")
    amount_zar = Column(Float, nullable=False)

    fee_amount = Column(Float, nullable=False, default=0)
    # R0 internal, R5 EFT, R10 instant EFT

    reference = Column(String(200), nullable=False)
    description = Column(String(500), nullable=True)

    # For internal transfers
    destination_account_id = Column(String, nullable=True)
    destination_member_id = Column(String, nullable=True)

    # For external payments
    external_psp = Column(String(30), nullable=True)
    # PEACH_PAYMENTS, OZOW, PAYPAL, VALR, LUNO
    external_psp_ref = Column(String(200), nullable=True)

    # Confirmation flow (high-value payments)
    requires_confirmation = Column(Boolean, nullable=False, default=False)
    confirmation_requested_at = Column(DateTime(timezone=True), nullable=True)
    confirmation_expires_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    confirmation_3fa_ref = Column(String(100), nullable=True)

    # Compliance metadata
    fica_category = Column(String(30), nullable=True)
    high_value_flag = Column(Boolean, nullable=False, default=False)
    blockchain_hash = Column(String(100), nullable=True)

    # Status tracking
    status = Column(String(20), nullable=False, default="pending")
    # pending, pending_confirmation, processing, completed, failed, cancelled, reversed
    failure_reason = Column(String(200), nullable=True)

    idempotency_key = Column(String(200), unique=True, nullable=True)

    initiated_at = Column(DateTime(timezone=True), nullable=False,
                          default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_payments_member", "member_id"),
        Index("ix_payments_agent", "agent_id"),
        Index("ix_payments_status", "status"),
        Index("ix_payments_type", "payment_type"),
        Index("ix_payments_initiated", "initiated_at"),
    )


class AgentisBeneficiary(Base):
    """Approved payment beneficiaries — agents may only pay to approved beneficiaries."""
    __tablename__ = "agentis_beneficiaries"

    beneficiary_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    member_id = Column(String, ForeignKey("agentis_members.member_id"), nullable=False)

    beneficiary_type = Column(String(20), nullable=False)
    # AGENTIS_MEMBER, SA_BANK, INTERNATIONAL_BANK, PAYPAL, CRYPTO_WALLET, PLATFORM_ACCOUNT

    display_name = Column(String(200), nullable=False)

    # SA bank details (encrypted in production)
    account_number = Column(String(100), nullable=True)
    bank_code = Column(String(20), nullable=True)
    branch_code = Column(String(20), nullable=True)

    # International
    swift_code = Column(String(20), nullable=True)
    iban = Column(String(50), nullable=True)

    # PayPal
    paypal_email = Column(String(200), nullable=True)

    # Crypto
    crypto_address = Column(String(200), nullable=True)
    crypto_network = Column(String(20), nullable=True)

    # Internal Agentis member
    agentis_member_id = Column(String, nullable=True)
    agentis_account_id = Column(String, nullable=True)

    # Sanctions screening
    sanctions_cleared_at = Column(DateTime(timezone=True), nullable=True)
    sanctions_status = Column(String(20), nullable=False, default="pending")
    # pending, cleared, flagged

    added_by = Column(String(20), nullable=False, default="member")
    # member, agent
    operator_3fa_ref = Column(String(100), nullable=True)

    # Usage tracking
    first_payment_at = Column(DateTime(timezone=True), nullable=True)
    last_payment_at = Column(DateTime(timezone=True), nullable=True)
    total_payments = Column(Integer, nullable=False, default=0)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_beneficiaries_member", "member_id"),
        Index("ix_beneficiaries_type", "beneficiary_type"),
        Index("ix_beneficiaries_sanctions", "sanctions_status"),
    )


class AgentisStandingOrder(Base):
    """Recurring payment instructions — essential for AI agents making periodic payments."""
    __tablename__ = "agentis_standing_orders"

    so_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("agentis_accounts.account_id"), nullable=False)
    member_id = Column(String, ForeignKey("agentis_members.member_id"), nullable=False)
    agent_id = Column(String, nullable=True)
    mandate_id = Column(String, nullable=True)

    beneficiary_id = Column(String, ForeignKey("agentis_beneficiaries.beneficiary_id"),
                            nullable=False)

    amount = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False, default="ZAR")
    reference = Column(String(200), nullable=False)

    frequency = Column(String(20), nullable=False)
    # DAILY, WEEKLY, MONTHLY, QUARTERLY, ANNUALLY

    day_of_month = Column(Integer, nullable=True)
    # 1-28 for monthly/quarterly/annual
    day_of_week = Column(Integer, nullable=True)
    # 1-7 for weekly (1=Monday)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    # NULL = indefinite

    executions_completed = Column(Integer, nullable=False, default=0)
    last_executed_at = Column(DateTime(timezone=True), nullable=True)
    next_execution_at = Column(DateTime(timezone=True), nullable=False)

    failure_count_consecutive = Column(Integer, nullable=False, default=0)
    # Suspend at 3 consecutive failures

    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(20), nullable=False, default="member")
    operator_3fa_ref = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_so_account", "account_id"),
        Index("ix_so_member", "member_id"),
        Index("ix_so_next", "next_execution_at"),
        Index("ix_so_active", "is_active"),
    )


class AgentisPaymentConfirmation(Base):
    """High-value payment confirmation records."""
    __tablename__ = "agentis_payment_confirmations"

    confirmation_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id = Column(String, ForeignKey("agentis_payments.payment_id"), nullable=False)

    requested_at = Column(DateTime(timezone=True), nullable=False,
                          default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    # 30 minutes from request

    notification_sent = Column(Boolean, nullable=False, default=False)
    notification_channel = Column(String(20), nullable=True)
    # webhook, sms, email

    confirmed = Column(Boolean, nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    confirmation_3fa_ref = Column(String(100), nullable=True)

    expired = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_confirmations_payment", "payment_id"),
    )


class AgentisFraudEvent(Base):
    """Fraud detection events — synchronous on every payment initiation."""
    __tablename__ = "agentis_fraud_events"

    fraud_event_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id = Column(String, nullable=True)
    member_id = Column(String, nullable=False)
    agent_id = Column(String, nullable=True)
    account_id = Column(String, nullable=True)

    rule_triggered = Column(String(50), nullable=False)
    # VELOCITY, NEW_BENEFICIARY, GEO_ANOMALY, ROUND_NUMBER_STRUCTURING,
    # DORMANT_ACTIVATION, MANDATE_BREACH

    rule_description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, default="medium")
    # low, medium, high, critical

    action_taken = Column(String(30), nullable=False)
    # ALLOWED, HELD, BLOCKED, ESCALATED

    details = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_fraud_member", "member_id"),
        Index("ix_fraud_rule", "rule_triggered"),
        Index("ix_fraud_severity", "severity"),
    )
