"""Agentis Core Banking Accounts & Deposits — Database Models (Module 2).

Full cooperative bank deposit product suite. All accounts are member-only.
Phase 1 (CFI): Share (S), Call (C), Savings (SA) accounts.
Phase 2 (PCB): Notice (N), Fixed Deposit (FD), Charitable Fund (CF),
               Investment Reserve (IR), Multi-currency (MC).

ADDITIVE ONLY. No existing tables modified.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Float, String, Boolean, Integer, Text,
    ForeignKey, Index, JSON, CheckConstraint, Date,
)

from app.database.db import Base


class AgentisAccount(Base):
    """Member bank account — all types."""
    __tablename__ = "agentis_accounts"

    account_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_number = Column(String(20), unique=True, nullable=False)
    # Human-readable: AGT-00000001-C (member number + type suffix)

    member_id = Column(String, ForeignKey("agentis_members.member_id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    # Linked agent if agent-operated account

    account_type = Column(String(10), nullable=False)
    # Phase 1: S (Share), C (Call), SA (Savings)
    # Phase 2: N (Notice), FD (Fixed Deposit), CF (Charitable Fund),
    #          IR (Investment Reserve), MC (Multi-currency)

    currency = Column(String(10), nullable=False, default="ZAR")

    balance = Column(Float, nullable=False, default=0)
    pending_balance = Column(Float, nullable=False, default=0)
    interest_accrued = Column(Float, nullable=False, default=0)
    interest_rate_pa = Column(Float, nullable=False, default=0)

    notice_period_days = Column(Integer, nullable=False, default=0)
    term_end_date = Column(Date, nullable=True)
    auto_renew = Column(Boolean, nullable=False, default=False)

    is_frozen = Column(Boolean, nullable=False, default=False)
    freeze_reason = Column(Text, nullable=True)

    concentration_exempt = Column(Boolean, nullable=False, default=False)
    # SARB 15% concentration limit exempt (for share accounts)
    deposit_insurance_eligible = Column(Boolean, nullable=False, default=True)

    daily_transaction_total = Column(Float, nullable=False, default=0)
    monthly_transaction_total = Column(Float, nullable=False, default=0)
    withdrawal_count_this_month = Column(Integer, nullable=False, default=0)
    # Savings accounts: 4 free withdrawals/month

    opened_at = Column(DateTime(timezone=True), nullable=False,
                       default=lambda: datetime.now(timezone.utc))
    closed_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(String(20), nullable=False, default="active")
    # active, dormant, suspended, closed

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_accounts_member", "member_id"),
        Index("ix_accounts_agent", "agent_id"),
        Index("ix_accounts_type", "account_type"),
        Index("ix_accounts_status", "status"),
        CheckConstraint(
            "account_type IN ('S','C','SA','N','FD','CF','IR','MC')",
            name="ck_account_type"
        ),
    )


class AgentisAccountTransaction(Base):
    """Immutable banking transaction ledger."""
    __tablename__ = "agentis_account_transactions"

    txn_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("agentis_accounts.account_id"), nullable=False)
    member_id = Column(String, ForeignKey("agentis_members.member_id"), nullable=False)
    agent_id = Column(String, nullable=True)
    mandate_id = Column(String, nullable=True)

    txn_type = Column(String(40), nullable=False)
    # DEPOSIT, WITHDRAWAL, TRANSFER_IN, TRANSFER_OUT, INTEREST_CREDIT,
    # FEE_DEBIT, MEMBERSHIP_FEE, CHARITABLE_ALLOCATION, DIVIDEND_PAYMENT

    direction = Column(String(5), nullable=False)
    # CR (credit) or DR (debit)

    amount = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False, default="ZAR")
    amount_zar = Column(Float, nullable=False)
    fx_rate_used = Column(Float, nullable=True)

    balance_after = Column(Float, nullable=False)
    reference = Column(String(200), nullable=False)
    description = Column(String(500), nullable=True)

    counterparty_account_id = Column(String, nullable=True)
    counterparty_member_id = Column(String, nullable=True)
    external_payment_ref = Column(String(200), nullable=True)

    blockchain_ledger_hash = Column(String(100), nullable=True)
    blockchain_block_index = Column(Integer, nullable=True)

    status = Column(String(20), nullable=False, default="completed")
    # pending, processing, completed, failed, reversed

    fica_reported = Column(Boolean, nullable=False, default=False)
    high_value_flag = Column(Boolean, nullable=False, default=False)
    # TRUE if amount >= R50,000 (CTR threshold)

    idempotency_key = Column(String(200), unique=True, nullable=True)

    initiated_at = Column(DateTime(timezone=True), nullable=False,
                          default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_txn_account", "account_id"),
        Index("ix_txn_member", "member_id"),
        Index("ix_txn_type", "txn_type"),
        Index("ix_txn_status", "status"),
        Index("ix_txn_initiated", "initiated_at"),
        Index("ix_txn_idempotency", "idempotency_key"),
        CheckConstraint("direction IN ('CR','DR')", name="ck_txn_direction"),
    )


class AgentisInterestAccrual(Base):
    """Daily interest accrual records for audit trail."""
    __tablename__ = "agentis_interest_accruals"

    accrual_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String, ForeignKey("agentis_accounts.account_id"), nullable=False)

    accrual_date = Column(Date, nullable=False)
    balance_at_accrual = Column(Float, nullable=False)
    rate_pa = Column(Float, nullable=False)
    daily_interest = Column(Float, nullable=False)
    cumulative_accrued = Column(Float, nullable=False)
    capitalised = Column(Boolean, nullable=False, default=False)
    capitalised_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_accrual_account_date", "account_id", "accrual_date"),
    )
