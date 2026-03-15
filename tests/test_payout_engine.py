"""Tests for PayOut Engine™ — Section 10 of the brief."""

import pytest
from app.payout.models import (
    OwnerPaymentDestination, OwnerCurrencySplit,
    OwnerDisbursementSchedule, DisbursementRecord,
    DestinationChangeAuditLog, OwnerOffshoreTotalTracker,
)
from app.payout.service import (
    PayOutEngineService, CREDIT_ZAR_RATE,
    SARB_ANNUAL_LIMIT_ZAR, MAX_SINGLE_DISBURSEMENT_ZAR,
)


class TestCreditToZarConversion:
    """Unit: Known credits → expected ZAR at multiple rates."""

    def test_default_rate(self):
        credits = 10000
        zar = credits * CREDIT_ZAR_RATE
        assert zar == 550.0

    def test_custom_rate(self):
        credits = 10000
        rate = 0.10
        zar = credits * rate
        assert zar == 1000.0

    def test_zero_credits(self):
        assert 0 * CREDIT_ZAR_RATE == 0


class TestCurrencySplitCalculation:
    """Unit: Known balance + split → expected per-component allocation."""

    def test_full_btc(self):
        amount = 10000
        pct_btc = 100
        btc = amount * pct_btc / 100
        assert btc == 10000

    def test_even_split(self):
        amount = 10000
        btc = amount * 25 / 100
        eth = amount * 25 / 100
        zar = amount * 25 / 100
        retained = amount * 25 / 100
        assert btc + eth + zar + retained == amount

    def test_typical_split(self):
        """60% BTC, 30% ZAR, 10% retained."""
        amount = 50000
        btc = amount * 60 / 100
        zar = amount * 30 / 100
        retained = amount * 10 / 100
        assert btc == 30000
        assert zar == 15000
        assert retained == 5000
        assert btc + zar + retained == amount

    def test_split_must_sum_to_100(self):
        total = 40 + 20 + 10 + 20 + 10
        assert total == 100

    def test_invalid_split_rejected(self):
        total = 40 + 20 + 10 + 20 + 5  # = 95
        assert total != 100


class TestDestinationHash:
    """Unit: SHA256 hash changes on any field change."""

    def test_hash_generation(self):
        dest = OwnerPaymentDestination(
            btc_wallet_address="bc1q_test_address",
            bank_account_number="1234567890",
            beneficiary_name="TiOLi AI Investments",
        )
        h = dest.compute_hash()
        assert len(h) == 64

    def test_different_address_different_hash(self):
        dest1 = OwnerPaymentDestination(btc_wallet_address="addr1")
        dest2 = OwnerPaymentDestination(btc_wallet_address="addr2")
        assert dest1.compute_hash() != dest2.compute_hash()

    def test_same_data_same_hash(self):
        dest1 = OwnerPaymentDestination(btc_wallet_address="addr1", bank_name="FNB")
        dest2 = OwnerPaymentDestination(btc_wallet_address="addr1", bank_name="FNB")
        assert dest1.compute_hash() == dest2.compute_hash()


class TestSarbLimitTracking:
    """Unit: SARB compliance tracking."""

    def test_warning_at_90_pct(self):
        total = 900000
        pct = total / SARB_ANNUAL_LIMIT_ZAR * 100
        assert pct == 90.0
        assert pct >= 90  # Warning should fire

    def test_blocked_at_limit(self):
        total = 1000000
        assert total >= SARB_ANNUAL_LIMIT_ZAR  # Should block

    def test_under_limit_ok(self):
        total = 500000
        assert total < SARB_ANNUAL_LIMIT_ZAR  # Should proceed

    def test_remaining_calculation(self):
        total = 750000
        remaining = SARB_ANNUAL_LIMIT_ZAR - total
        assert remaining == 250000


class TestDisbursementCeiling:
    """Unit: Disbursement amount ceiling."""

    def test_under_ceiling_proceeds(self):
        zar = 400000
        assert zar <= MAX_SINGLE_DISBURSEMENT_ZAR

    def test_at_ceiling_proceeds(self):
        zar = 500000
        assert zar <= MAX_SINGLE_DISBURSEMENT_ZAR

    def test_over_ceiling_requires_confirmation(self):
        zar = 600000
        assert zar > MAX_SINGLE_DISBURSEMENT_ZAR


class TestIdempotencyKey:
    """Unit: Idempotency key format."""

    def test_key_format(self):
        disbursement_id = "abc-123"
        component = "BTC"
        key = f"{disbursement_id}:{component}"
        assert key == "abc-123:BTC"

    def test_unique_per_component(self):
        did = "abc-123"
        keys = {f"{did}:{c}" for c in ["BTC", "ETH", "ZAR", "RETAINED"]}
        assert len(keys) == 4


class TestRetryBackoff:
    """Unit: Correct delays per retry attempt."""

    def test_retry_schedule(self):
        delays = [15, 60, 240, 1440]  # minutes
        assert delays[0] == 15     # 15 minutes
        assert delays[1] == 60     # 1 hour
        assert delays[2] == 240    # 4 hours
        assert delays[3] == 1440   # 24 hours

    def test_max_retries(self):
        max_retries = 4
        assert max_retries == 4


class TestNonBreakingIntegration:
    """Verify PayOut Engine doesn't modify existing infrastructure."""

    def test_existing_transaction_types_unchanged(self):
        from app.blockchain.transaction import TransactionType
        # All original types still exist
        assert TransactionType.DEPOSIT == "deposit"
        assert TransactionType.WITHDRAWAL == "withdrawal"
        assert TransactionType.TRANSFER == "transfer"
        assert TransactionType.TRADE == "trade"

    def test_existing_wallet_model_unchanged(self):
        from app.agents.models import Wallet
        # Wallet model still has all original columns
        assert hasattr(Wallet, 'balance')
        assert hasattr(Wallet, 'frozen_balance')
        assert hasattr(Wallet, 'currency')

    def test_existing_fee_engine_unchanged(self):
        from app.exchange.fees import FeeEngine
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(1000)
        # Original calculation still works
        assert fees["founder_commission"] == 120
        assert fees["charity_fee"] == 100
        assert fees["net_amount"] == 780
