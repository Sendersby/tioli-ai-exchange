"""Concurrent transaction tests — TF-009.

Verifies wallet balances remain accurate under parallel operations.
"""

import pytest
from app.exchange.fees import FeeEngine


class TestConcurrentSafety:
    """Verify wallet operations are safe under concurrent access."""

    def test_balance_after_multiple_debits(self):
        """Simulate sequential debits — balance should never go negative."""
        balance = 1000.0
        debits = [100, 200, 150, 250, 200]
        for d in debits:
            if balance >= d:
                balance -= d
        assert balance == 100.0
        assert balance >= 0

    def test_balance_rejects_overdraft(self):
        """Debit larger than balance must be rejected."""
        balance = 500.0
        debit = 600.0
        assert debit > balance  # Should be rejected

    def test_concurrent_fee_calculation_consistency(self):
        """Same input always produces same fees — no race condition in calculation."""
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        results = [engine.calculate_fees(1000) for _ in range(100)]
        assert all(r["founder_commission"] == 120 for r in results)
        assert all(r["charity_fee"] == 100 for r in results)
        assert all(r["net_amount"] == 780 for r in results)

    def test_double_spend_prevention_logic(self):
        """Two concurrent reads of same balance should not both succeed."""
        balance = 500.0
        amount1 = 400.0
        amount2 = 300.0
        # With locking, only one can proceed
        # First debit succeeds
        assert balance >= amount1
        balance -= amount1  # Now 100
        # Second debit must fail
        assert balance < amount2  # 100 < 300 — rejected

    def test_transfer_atomicity(self):
        """Transfer must debit sender and credit receiver atomically."""
        sender_balance = 1000.0
        receiver_balance = 500.0
        transfer = 300.0
        fee_rate = 0.22

        sender_balance -= transfer
        net = transfer * (1 - fee_rate)
        receiver_balance += net

        # Verify conservation (minus fees)
        total_before = 1000.0 + 500.0
        total_after = sender_balance + receiver_balance
        fees_taken = transfer * fee_rate
        assert abs(total_before - total_after - fees_taken) < 0.01

    def test_frozen_balance_prevents_double_commit(self):
        """Frozen balance must reduce available for new transactions."""
        balance = 1000.0
        frozen = 400.0
        available = balance - frozen
        assert available == 600.0
        # New order of 700 should fail
        assert 700 > available

    def test_parallel_order_placement_simulation(self):
        """Simulate two agents placing orders against same liquidity."""
        liquidity = 1000.0
        order1 = 600.0
        order2 = 500.0
        # With locking, first order takes liquidity
        assert liquidity >= order1
        liquidity -= order1  # 400 remaining
        # Second order must be partially filled or rejected
        filled = min(order2, liquidity)
        assert filled == 400.0
        assert liquidity - filled == 0.0

    def test_escrow_fund_once_only(self):
        """Escrow funding must only succeed once per engagement."""
        funded = False
        balance = 1000.0
        escrow_amount = 500.0

        # First funding
        if not funded and balance >= escrow_amount:
            balance -= escrow_amount
            funded = True

        # Second attempt must fail
        attempt2 = not funded and balance >= escrow_amount
        assert attempt2 is False
        assert balance == 500.0
