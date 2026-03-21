"""PayOut Engine™ database models — all new tables per Section 3 of the brief.

ADDITIVE ONLY. No existing tables modified.
"""

import uuid
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Float, String, Boolean, Integer, Text,
    ForeignKey, CheckConstraint,
)

from app.database.db import Base


class OwnerPaymentDestination(Base):
    """Versioned payment destination configuration (Section 3.3.1)."""
    __tablename__ = "owner_payment_destinations"

    destination_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    destination_version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)

    # Crypto destinations
    btc_wallet_address = Column(String(120), nullable=True)
    btc_wallet_label = Column(String(80), nullable=True)
    eth_wallet_address = Column(String(120), nullable=True)
    eth_wallet_label = Column(String(80), nullable=True)
    custom_crypto_chain = Column(String(40), nullable=True)
    custom_crypto_address = Column(String(120), nullable=True)
    custom_crypto_label = Column(String(80), nullable=True)

    # Fiat / bank destination
    bank_account_name = Column(String(120), nullable=True)
    bank_name = Column(String(80), nullable=True)
    bank_branch_code = Column(String(20), nullable=True)
    bank_account_number = Column(String(40), nullable=True)  # Stored encrypted in production
    bank_account_type = Column(String(20), nullable=True)    # CHEQUE | SAVINGS | TRANSMISSION
    bank_swift_code = Column(String(20), nullable=True)
    bank_country_code = Column(String(4), nullable=True)

    # Company details
    beneficiary_name = Column(String(120), nullable=True)
    beneficiary_reg_no = Column(String(40), nullable=True)

    # Exchange preference
    preferred_exchange = Column(String(40), nullable=True)   # VALR | LUNO | BINANCE

    # Verification & audit
    verified_by_3fa = Column(Boolean, nullable=False, default=False)
    verification_ref = Column(String, nullable=True)
    change_reason = Column(Text, nullable=True)
    previous_version_id = Column(String, nullable=True)
    destination_hash = Column(String(64), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by_event = Column(String(80), nullable=False, default="INITIAL_SETUP")

    def compute_hash(self) -> str:
        """SHA256 hash of all destination fields for tamper detection."""
        data = json.dumps({
            "btc": self.btc_wallet_address, "eth": self.eth_wallet_address,
            "custom": self.custom_crypto_address,
            "bank_name": self.bank_name, "bank_account": self.bank_account_number,
            "beneficiary": self.beneficiary_name,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()


class OwnerCurrencySplit(Base):
    """Currency split configuration (Section 3.3.2)."""
    __tablename__ = "owner_currency_split"

    split_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    split_version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)

    # Allocation percentages (must sum to 100)
    pct_btc = Column(Float, nullable=False, default=0.0)
    pct_eth = Column(Float, nullable=False, default=0.0)
    pct_custom_crypto = Column(Float, nullable=False, default=0.0)
    pct_zar_fiat = Column(Float, nullable=False, default=0.0)
    pct_retained_credits = Column(Float, nullable=False, default=100.0)

    # Minimum disbursement threshold
    min_disbursement_credits = Column(Float, nullable=False, default=1000.0)

    # Audit
    verified_by_3fa = Column(Boolean, nullable=False, default=False)
    verification_ref = Column(String, nullable=True)
    previous_version_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    def validate_sum(self) -> bool:
        """Verify allocations sum to 100."""
        total = (self.pct_btc + self.pct_eth + self.pct_custom_crypto +
                 self.pct_zar_fiat + self.pct_retained_credits)
        return abs(total - 100.0) < 0.01


class OwnerDisbursementSchedule(Base):
    """Disbursement schedule configuration (Section 3.3.3)."""
    __tablename__ = "owner_disbursement_schedule"

    schedule_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    is_current = Column(Boolean, nullable=False, default=True)

    # Time-based schedule
    schedule_type = Column(String(20), nullable=False, default="MONTHLY")
    schedule_day_of_month = Column(Integer, nullable=True)
    schedule_day_of_week = Column(Integer, nullable=True)
    schedule_time_utc = Column(String(8), nullable=False, default="02:00:00")

    # Threshold-based trigger
    threshold_enabled = Column(Boolean, nullable=False, default=True)
    threshold_credits = Column(Float, nullable=False, default=50000.0)

    # Pause controls
    is_paused = Column(Boolean, nullable=False, default=False)
    paused_reason = Column(Text, nullable=True)
    paused_at = Column(DateTime(timezone=True), nullable=True)

    # Audit
    verified_by_3fa = Column(Boolean, nullable=False, default=False)
    verification_ref = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class DisbursementRecord(Base):
    """Immutable disbursement execution record (Section 3.3.4)."""
    __tablename__ = "disbursement_records_v2"  # v2 to avoid conflict with existing payout_records

    disbursement_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    triggered_by = Column(String(20), nullable=False)     # SCHEDULE | THRESHOLD | MANUAL
    disbursement_status = Column(String(20), nullable=False, default="QUEUED")

    # Source
    source_wallet_id = Column(String, nullable=True)
    gross_credits_swept = Column(Float, nullable=False, default=0.0)
    split_config_id = Column(String, nullable=True)
    destination_config_id = Column(String, nullable=True)

    # BTC component
    btc_credits_allocated = Column(Float, nullable=True)
    btc_zar_rate = Column(Float, nullable=True)
    btc_amount_sent = Column(Float, nullable=True)
    btc_tx_hash = Column(String(120), nullable=True)
    btc_exchange_ref = Column(String(120), nullable=True)
    btc_status = Column(String(20), nullable=True)

    # ETH component
    eth_credits_allocated = Column(Float, nullable=True)
    eth_zar_rate = Column(Float, nullable=True)
    eth_amount_sent = Column(Float, nullable=True)
    eth_tx_hash = Column(String(120), nullable=True)
    eth_exchange_ref = Column(String(120), nullable=True)
    eth_status = Column(String(20), nullable=True)

    # Custom crypto component
    custom_credits_alloc = Column(Float, nullable=True)
    custom_zar_rate = Column(Float, nullable=True)
    custom_amount_sent = Column(Float, nullable=True)
    custom_tx_hash = Column(String(120), nullable=True)
    custom_exchange_ref = Column(String(120), nullable=True)
    custom_status = Column(String(20), nullable=True)

    # ZAR fiat component
    zar_credits_allocated = Column(Float, nullable=True)
    zar_amount_sent = Column(Float, nullable=True)
    zar_psp_reference = Column(String(120), nullable=True)
    zar_bank_ref = Column(String(120), nullable=True)
    zar_sarb_ref = Column(String(120), nullable=True)
    zar_status = Column(String(20), nullable=True)

    # Retained credits
    retained_credits = Column(Float, nullable=True)
    retained_wallet_id = Column(String, nullable=True)

    # Ledger reference
    ledger_txn_id = Column(String(120), nullable=True)

    # Timing
    queued_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)


class DestinationChangeAuditLog(Base):
    """Immutable audit log for all payout config changes (Section 3.3.5)."""
    __tablename__ = "destination_change_audit_log"

    audit_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    change_type = Column(String(40), nullable=False)
    previous_hash = Column(String(64), nullable=True)
    new_hash = Column(String(64), nullable=False)
    changed_table = Column(String(60), nullable=False)
    changed_record_id = Column(String, nullable=False)
    verification_method = Column(String(80), nullable=False, default="3FA: EMAIL+SMS+CLI")
    verification_ref = Column(String, nullable=True)
    change_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class OwnerOffshoreTotalTracker(Base):
    """SARB annual offshore transfer tracking (Section 6.3)."""
    __tablename__ = "owner_offshore_transfer_totals"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    year = Column(Integer, nullable=False)
    total_zar_equivalent = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
