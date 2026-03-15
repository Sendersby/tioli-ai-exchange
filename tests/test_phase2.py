"""Tests for Phase 2: Exchange, Pricing, Lending, Compute Storage."""

import pytest
import os
from app.blockchain.chain import Blockchain
from app.blockchain.transaction import Transaction, TransactionType
from app.exchange.fees import FeeEngine
from app.exchange.currencies import CurrencyService, SYSTEM_CURRENCIES, INITIAL_RATES


class TestCurrencies:
    def test_system_currencies_defined(self):
        assert len(SYSTEM_CURRENCIES) >= 4
        symbols = [c["symbol"] for c in SYSTEM_CURRENCIES]
        assert "TIOLI" in symbols
        assert "BTC" in symbols
        assert "ETH" in symbols
        assert "COMPUTE" in symbols

    def test_initial_rates_defined(self):
        assert ("TIOLI", "BTC") in INITIAL_RATES
        assert ("TIOLI", "ETH") in INITIAL_RATES
        assert INITIAL_RATES[("TIOLI", "BTC")] > 0

    def test_tioli_supply(self):
        tioli = next(c for c in SYSTEM_CURRENCIES if c["symbol"] == "TIOLI")
        assert tioli["total_supply"] == 1_000_000_000
        assert tioli["max_supply"] == 10_000_000_000


class TestFeeEngineExtended:
    def test_fee_on_trade(self):
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        # Simulate a trade of 500 TIOLI
        fees = engine.calculate_fees(500.0)
        assert fees["founder_commission"] == 60.0
        assert fees["charity_fee"] == 50.0
        assert fees["net_amount"] == 390.0

    def test_zero_amount(self):
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(0.0)
        assert fees["net_amount"] == 0.0
        assert fees["total_fees"] == 0.0


class TestBlockchainTradeRecording:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.blockchain = Blockchain(storage_path=str(tmp_path / "chain.json"))

    def test_trade_transaction_recorded(self):
        tx = Transaction(
            type=TransactionType.TRADE,
            sender_id="seller-agent",
            receiver_id="buyer-agent",
            amount=100.0,
            currency="TIOLI",
            description="Trade: 100 TIOLI @ 0.000001 BTC",
            founder_commission=12.0,
            charity_fee=10.0,
            metadata={"base": "TIOLI", "quote": "BTC", "price": 0.000001},
        )
        tx_id = self.blockchain.add_transaction(tx)
        assert tx_id is not None

        self.blockchain.force_mine()
        all_tx = self.blockchain.get_all_transactions()
        trade_txs = [t for t in all_tx if t.get("type") == "trade"]
        assert len(trade_txs) == 1
        assert trade_txs[0]["metadata"]["base"] == "TIOLI"

    def test_commission_transparency(self):
        """Verify all fees are recorded transparently on-chain."""
        tx = Transaction(
            type=TransactionType.TRADE,
            sender_id="s1", receiver_id="b1",
            amount=200.0, currency="TIOLI",
            founder_commission=24.0, charity_fee=20.0,
        )
        self.blockchain.add_transaction(tx)
        self.blockchain.force_mine()

        all_tx = self.blockchain.get_all_transactions()
        trade = [t for t in all_tx if t.get("type") == "trade"][0]
        assert trade["founder_commission"] == 24.0
        assert trade["charity_fee"] == 20.0


class TestComputeStorageConcepts:
    def test_deposit_withdraw_logic(self):
        """Test the basic math of compute storage."""
        balance = 0.0
        reserved = 0.0

        # Deposit 500
        balance += 500.0
        assert balance == 500.0

        # Reserve 200
        reserved += 200.0
        available = balance - reserved
        assert available == 300.0

        # Withdraw 100 from available
        balance -= 100.0
        available = balance - reserved
        assert available == 200.0
        assert balance == 400.0

        # Release reservation
        reserved -= 200.0
        available = balance - reserved
        assert available == 400.0


class TestPricingConcepts:
    def test_mid_price_calculation(self):
        best_bid = 0.00000095
        best_ask = 0.00000105
        mid = (best_bid + best_ask) / 2
        assert mid == 0.000001

    def test_vwap_calculation(self):
        # Simulated trades
        trades = [
            {"price": 0.000001, "quantity": 100, "value": 0.0001},
            {"price": 0.0000012, "quantity": 200, "value": 0.00024},
            {"price": 0.0000011, "quantity": 150, "value": 0.000165},
        ]
        total_value = sum(t["value"] for t in trades)
        total_qty = sum(t["quantity"] for t in trades)
        vwap = total_value / total_qty
        expected = total_value / total_qty
        assert round(vwap, 10) == round(expected, 10)
        assert vwap > 0

    def test_weighted_composite_price(self):
        mid_price = 0.000001
        last_trade = 0.0000012
        vwap = 0.0000011
        weights = [0.5, 0.3, 0.2]
        prices = [mid_price, last_trade, vwap]
        composite = sum(p * w for p, w in zip(prices, weights))
        assert composite > 0


class TestLendingConcepts:
    def test_interest_calculation(self):
        principal = 1000.0
        rate = 0.05
        total_owed = principal * (1 + rate)
        assert total_owed == 1050.0

    def test_partial_repayment(self):
        principal = 1000.0
        rate = 0.05
        total_owed = principal * (1 + rate)
        repaid = 500.0
        remaining = total_owed - repaid
        assert remaining == 550.0
