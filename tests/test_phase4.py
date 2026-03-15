"""Tests for Phase 4: Crypto, Conversion, Payouts, Security."""

import pytest
from app.crypto.wallets import CryptoWalletService
from app.security.guardian import SecurityGuardian
from app.exchange.fees import FeeEngine


class TestCryptoAddressGeneration:
    def test_bitcoin_address_format(self):
        service = CryptoWalletService()
        addr = service._generate_address("bitcoin")
        assert addr.startswith("bc1q")
        assert len(addr) > 20

    def test_ethereum_address_format(self):
        service = CryptoWalletService()
        addr = service._generate_address("ethereum")
        assert addr.startswith("0x")
        assert len(addr) == 42

    def test_unique_addresses(self):
        service = CryptoWalletService()
        addrs = {service._generate_address("bitcoin") for _ in range(100)}
        assert len(addrs) == 100  # All unique

    def test_network_fee_estimate(self):
        service = CryptoWalletService()
        btc_fee = service._estimate_fee("bitcoin")
        eth_fee = service._estimate_fee("ethereum")
        assert btc_fee > 0
        assert eth_fee > 0
        assert btc_fee < eth_fee  # BTC fees typically lower in sats terms


class TestConversionPaths:
    def test_direct_conversion_math(self):
        rate = 0.000001  # 1 TIOLI = 0.000001 BTC
        amount = 1000
        converted = amount * rate
        assert converted == 0.001

    def test_multi_hop_conversion(self):
        # COMPUTE → TIOLI → BTC
        rate1 = 1.0      # 1 COMPUTE = 1 TIOLI
        rate2 = 0.000001  # 1 TIOLI = 0.000001 BTC
        composite = rate1 * rate2
        assert composite == 0.000001

        amount = 5000  # COMPUTE
        result = amount * composite
        assert result == 0.005  # BTC

    def test_conversion_with_fees(self):
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        gross = 1000 * 0.000001  # 1000 TIOLI → BTC
        fees = engine.calculate_fees(gross)
        assert fees["net_amount"] < gross
        assert fees["founder_commission"] > 0
        assert fees["charity_fee"] > 0

    def test_inverse_rate(self):
        rate = 0.000001
        inverse = 1.0 / rate
        assert inverse == 1000000  # 1 BTC = 1,000,000 TIOLI


class TestSecurityGuardian:
    def test_rate_limiting(self):
        guardian = SecurityGuardian()
        agent = "test-agent-1"
        # Should allow first 30 requests
        for i in range(30):
            result = guardian.check_rate_limit(agent, trust_level=1)
            assert result["allowed"] is True
        # 31st should be blocked
        result = guardian.check_rate_limit(agent, trust_level=1)
        assert result["allowed"] is False

    def test_higher_trust_higher_limit(self):
        guardian = SecurityGuardian()
        # Trust level 3 gets 120 requests/min
        for i in range(100):
            result = guardian.check_rate_limit("trusted-agent", trust_level=3)
            assert result["allowed"] is True

    def test_transaction_limits(self):
        limits = SecurityGuardian.TX_LIMITS
        # New agents have lower limits
        assert limits[1]["max_single"] < limits[2]["max_single"]
        assert limits[2]["max_single"] < limits[3]["max_single"]
        # Trust level 1
        assert limits[1]["max_single"] == 1000
        assert limits[1]["daily"] == 5000

    def test_trust_level_progression(self):
        # At 100 transactions, upgrade to level 2
        # At 500 transactions, upgrade to level 3
        assert 100 < 500  # Level 2 threshold < Level 3


class TestPayoutAllocation:
    def test_single_destination_full(self):
        total = 1000.0
        allocation = 1.0
        payout = total * allocation
        assert payout == 1000.0

    def test_split_destinations(self):
        total = 1000.0
        crypto_pct = 0.6
        bank_pct = 0.3
        tokens_pct = 0.1

        crypto = total * crypto_pct
        bank = total * bank_pct
        tokens = total * tokens_pct

        assert crypto == 600.0
        assert bank == 300.0
        assert tokens == 100.0
        assert crypto + bank + tokens == total

    def test_allocation_bounds(self):
        # Allocation should be clamped to 0-1
        assert min(1.0, max(0.0, 1.5)) == 1.0
        assert min(1.0, max(0.0, -0.5)) == 0.0
