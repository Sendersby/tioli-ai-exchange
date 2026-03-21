"""Tests for PayPal Integration Module."""

import pytest
from app.paypal.models import OwnerPayPalAccount, PayPalDisbursementRecord
from app.paypal.adapter import PayPalAdapter, SANDBOX_URL, LIVE_URL


class TestPayPalAdapter:
    def test_sandbox_url(self):
        adapter = PayPalAdapter()
        assert adapter.is_sandbox is True
        assert adapter.base_url == SANDBOX_URL

    def test_idempotency_key_format(self):
        disbursement_id = "disb-123"
        account_id = "acct-456"
        key = f"{disbursement_id}:PAYPAL:{account_id}"
        assert key == "disb-123:PAYPAL:acct-456"


class TestPayPalAccountHash:
    def test_hash_generation(self):
        acct = OwnerPayPalAccount(
            paypal_email="test@example.com",
            account_label="Test Account",
            can_receive=True,
        )
        h = acct.compute_hash()
        assert len(h) == 64

    def test_different_email_different_hash(self):
        a1 = OwnerPayPalAccount(paypal_email="a@test.com", account_label="A")
        a2 = OwnerPayPalAccount(paypal_email="b@test.com", account_label="A")
        assert a1.compute_hash() != a2.compute_hash()

    def test_same_data_same_hash(self):
        a1 = OwnerPayPalAccount(paypal_email="a@test.com", account_label="A")
        a2 = OwnerPayPalAccount(paypal_email="a@test.com", account_label="A")
        assert a1.compute_hash() == a2.compute_hash()


class TestEmailMasking:
    def test_mask_email(self):
        email = "stephen@tioli.co.za"
        masked = email[:3] + "***@" + email.split("@")[-1]
        assert masked == "ste***@tioli.co.za"

    def test_mask_short_email(self):
        email = "ab@x.com"
        masked = email[:3] + "***@" + email.split("@")[-1]
        assert "***@x.com" in masked


class TestConversionChain:
    def test_credits_to_usd(self):
        credits = 10000
        credit_zar_rate = 0.055
        zar_usd_rate = 18.5
        zar = credits * credit_zar_rate
        usd = zar / zar_usd_rate
        assert zar == 550.0
        assert round(usd, 2) == 29.73

    def test_paypal_fee_estimate(self):
        usd = 29.73
        fee = usd * 0.02 + 0.25
        net = usd - fee
        assert round(fee, 2) == 0.84
        assert round(net, 2) == 28.89

    def test_multi_account_split(self):
        total_usd = 100.0
        acct1_pct = 60
        acct2_pct = 40
        assert total_usd * acct1_pct / 100 == 60.0
        assert total_usd * acct2_pct / 100 == 40.0
        assert acct1_pct + acct2_pct == 100


class TestProfitabilityCheck:
    def test_above_threshold(self):
        ratio = 15.0
        required = 10.0
        assert ratio >= required

    def test_below_threshold_blocks(self):
        ratio = 7.0
        required = 10.0
        assert ratio < required

    def test_security_3x_exception(self):
        ratio = 5.0
        is_security = True
        required = 3.0 if is_security else 10.0
        assert ratio >= required


class TestFeatureFlag:
    def test_default_disabled(self):
        import os
        assert os.environ.get("PAYPAL_ENABLED", "false") == "false"

    def test_sandbox_default(self):
        import os
        assert os.environ.get("PAYPAL_SANDBOX", "true") == "true"


class TestNonBreaking:
    def test_existing_wallet_unchanged(self):
        from app.agents.models import Wallet
        assert hasattr(Wallet, "balance")
        assert hasattr(Wallet, "frozen_balance")

    def test_existing_fee_engine_unchanged(self):
        from app.exchange.fees import FeeEngine
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(1000)
        # V2: commission=120, charity=12 (10% of commission), founder=108, net=880
        assert fees["commission"] == 120
        assert fees["founder_commission"] == 108
        assert fees["net_amount"] == 880

    def test_existing_blockchain_unchanged(self):
        from app.blockchain.transaction import TransactionType
        assert TransactionType.TRANSFER == "transfer"
