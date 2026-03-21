"""Tests for the TiOLi blockchain core."""

import os
import json
import pytest
from app.blockchain.block import Block
from app.blockchain.chain import Blockchain
from app.blockchain.transaction import Transaction, TransactionType
from app.exchange.fees import FeeEngine


class TestBlock:
    def test_block_creation(self):
        block = Block(index=0, transactions=[], previous_hash="0" * 64)
        assert block.index == 0
        assert block.hash is not None
        assert len(block.hash) == 64

    def test_block_hash_deterministic(self):
        block1 = Block(index=1, transactions=[{"a": 1}], previous_hash="abc", timestamp="2024-01-01")
        block2 = Block(index=1, transactions=[{"a": 1}], previous_hash="abc", timestamp="2024-01-01")
        assert block1.hash == block2.hash

    def test_block_hash_changes_with_data(self):
        block1 = Block(index=1, transactions=[{"a": 1}], previous_hash="abc", timestamp="2024-01-01")
        block2 = Block(index=1, transactions=[{"a": 2}], previous_hash="abc", timestamp="2024-01-01")
        assert block1.hash != block2.hash

    def test_block_serialization(self):
        block = Block(index=5, transactions=[{"test": True}], previous_hash="xyz")
        d = block.to_dict()
        restored = Block.from_dict(d)
        assert restored.index == 5
        assert restored.hash == block.hash


class TestBlockchain:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.chain_path = str(tmp_path / "test_chain.json")
        self.blockchain = Blockchain(storage_path=self.chain_path)

    def test_genesis_block_created(self):
        assert len(self.blockchain.chain) == 1
        assert self.blockchain.chain[0].index == 0

    def test_chain_is_valid(self):
        assert self.blockchain.validate_chain() is True

    def test_add_transaction(self):
        tx = Transaction(
            type=TransactionType.DEPOSIT,
            receiver_id="agent-1",
            amount=100.0,
            currency="TIOLI",
        )
        tx_id = self.blockchain.add_transaction(tx)
        assert tx_id is not None
        assert len(self.blockchain.pending_transactions) == 1

    def test_mine_block(self):
        for i in range(3):
            tx = Transaction(
                type=TransactionType.TRANSFER,
                sender_id=f"agent-{i}",
                receiver_id=f"agent-{i+1}",
                amount=10.0,
            )
            self.blockchain.add_transaction(tx)

        block = self.blockchain.force_mine()
        assert block is not None
        assert block.index == 1
        assert len(block.transactions) == 3
        assert len(self.blockchain.pending_transactions) == 0

    def test_chain_validation_after_mining(self):
        tx = Transaction(type=TransactionType.DEPOSIT, receiver_id="a1", amount=50.0)
        self.blockchain.add_transaction(tx)
        self.blockchain.force_mine()
        assert self.blockchain.validate_chain() is True

    def test_tamper_detection(self):
        tx = Transaction(type=TransactionType.DEPOSIT, receiver_id="a1", amount=50.0)
        self.blockchain.add_transaction(tx)
        self.blockchain.force_mine()

        # Tamper with a transaction
        self.blockchain.chain[1].transactions[0]["amount"] = 999999
        assert self.blockchain.validate_chain() is False

    def test_persistence(self):
        tx = Transaction(type=TransactionType.DEPOSIT, receiver_id="a1", amount=100.0)
        self.blockchain.add_transaction(tx)
        self.blockchain.force_mine()

        # Load from disk
        chain2 = Blockchain(storage_path=self.chain_path)
        assert len(chain2.chain) == 2
        assert chain2.validate_chain() is True

    def test_get_agent_transactions(self):
        tx1 = Transaction(type=TransactionType.DEPOSIT, receiver_id="agent-x", amount=50.0)
        tx2 = Transaction(type=TransactionType.TRANSFER, sender_id="agent-x", receiver_id="agent-y", amount=20.0)
        self.blockchain.add_transaction(tx1)
        self.blockchain.add_transaction(tx2)
        self.blockchain.force_mine()

        results = self.blockchain.get_transactions_for_agent("agent-x")
        assert len(results) == 2

    def test_full_transparency(self):
        for i in range(5):
            tx = Transaction(type=TransactionType.DEPOSIT, receiver_id=f"a{i}", amount=10.0)
            self.blockchain.add_transaction(tx)
        self.blockchain.force_mine()

        all_tx = self.blockchain.get_all_transactions()
        # Genesis tx + 5 deposits
        assert len(all_tx) >= 5


class TestFeeEngine:
    def test_default_rates(self):
        engine = FeeEngine()
        assert 0.10 <= engine.founder_rate <= 0.15
        assert engine.charity_rate == 0.10

    def test_charity_is_pct_of_commission_not_gross(self):
        """Build Brief V2 Section 2.2.1: charity = 10% of commission, NOT 10% of gross."""
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(100.0)
        # Commission = 12% of 100 = 12.0
        commission = fees["commission"]
        assert commission == 12.0
        # Charity = 10% of commission = 1.2 (NOT 10% of 100 = 10.0)
        assert fees["charity_fee"] == round(12.0 * 0.10, 8)
        # Founder net = commission - charity
        assert fees["founder_commission"] == round(12.0 - 1.2, 8)
        # Provider receives gross - commission = 88.0
        assert fees["net_amount"] == 88.0

    def test_fee_calculation_r10_at_8pct(self):
        """Brief example: R10 trade at 8%, commission=R0.80, charity=R0.08, provider=R9.20."""
        engine = FeeEngine(founder_rate=0.10, charity_rate=0.10)
        fees = engine.calculate_fees(10.0, operator_commission_rate=0.08)
        assert fees["commission"] == 0.80
        assert fees["charity_fee"] == 0.08
        assert fees["founder_commission"] == 0.72
        assert fees["net_amount"] == 9.20

    def test_floor_fee_applied(self):
        """Floor fee should apply when percentage fee is below floor."""
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        # R1 trade at 8%: percentage = R0.08, floor for resource_exchange = R0.50
        fees = engine.calculate_fees(1.0, operator_commission_rate=0.08, transaction_type="resource_exchange")
        assert fees["commission"] == 0.50  # Floor applied
        assert fees["floor_fee_applied"] is True
        assert fees["charity_fee"] == round(0.50 * 0.10, 8)

    def test_rate_bounds_enforced(self):
        engine = FeeEngine(founder_rate=0.50)  # Too high
        assert engine.founder_rate == 0.15  # Capped at max

        engine2 = FeeEngine(founder_rate=0.01)  # Too low
        assert engine2.founder_rate == 0.10  # Raised to min

    def test_small_transaction(self):
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(0.001)
        assert fees["net_amount"] >= 0
        assert fees["net_amount"] < 0.001

    def test_update_rate(self):
        engine = FeeEngine(founder_rate=0.12)
        engine.update_founder_rate(0.14)
        assert engine.founder_rate == 0.14

    def test_transaction_type_rate_override(self):
        """AgentBroker engagements should use 10% regardless of tier."""
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(100.0, transaction_type="agentbroker_engagement")
        assert fees["commission"] == 10.0  # 10% for agentbroker
        assert fees["charity_fee"] == 1.0  # 10% of 10.0

    def test_profitability_conditional_charity(self):
        """Charity rate adjusts based on platform profitability."""
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        # Pre-profitable: charity = 0% of commission
        engine.update_profitability(100, 200)
        fees = engine.calculate_fees(100.0)
        assert fees["charity_fee"] == 0.0
        assert fees["charity_status"] == "deferred"
        # Ramp-up: charity = 5% of commission
        engine.update_profitability(150, 100)
        fees = engine.calculate_fees(100.0)
        assert fees["charity_fee"] == round(12.0 * 0.05, 8)
        # Full: charity = 10% of commission
        engine.update_profitability(300, 100)
        fees = engine.calculate_fees(100.0)
        assert fees["charity_fee"] == round(12.0 * 0.10, 8)
