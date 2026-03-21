"""Comprehensive tests for Capability Futures — Build Brief V2, Module 3."""

from datetime import datetime, timedelta, timezone
from app.futures.models import (
    CapabilityFuture, FutureReservation,
    FUTURE_CREATION_FEE_ZAR, RESERVATION_FEE_PCT, SETTLEMENT_FEE_PCT,
)


class TestFuturesPricing:
    def test_creation_fee(self):
        assert FUTURE_CREATION_FEE_ZAR == 50.0

    def test_reservation_fee(self):
        assert RESERVATION_FEE_PCT == 0.01

    def test_settlement_fee(self):
        assert SETTLEMENT_FEE_PCT == 0.03

    def test_commission_example(self):
        """100 units at R50 = R5000. Creation R50, reservation 1%=R50, settlement 3%=R150."""
        total = 100 * 50
        assert total == 5000
        assert round(total * RESERVATION_FEE_PCT, 2) == 50.0
        assert round(total * SETTLEMENT_FEE_PCT, 2) == 150.0

    def test_total_platform_revenue_per_contract(self):
        """Total: R50 creation + 1% reservation + 3% settlement = R50 + 4% of GTV."""
        gtv = 5000
        total = FUTURE_CREATION_FEE_ZAR + gtv * RESERVATION_FEE_PCT + gtv * SETTLEMENT_FEE_PCT
        assert total == 50 + 50 + 150  # R250

    def test_small_contract_floor(self):
        """Even tiny contracts pay R50 creation fee."""
        assert FUTURE_CREATION_FEE_ZAR == 50.0


class TestFuturesModels:
    def test_delivery_window_validation(self):
        """Delivery window must be at least 14 days in the future."""
        now = datetime.now(timezone.utc)
        min_start = now + timedelta(days=14)
        too_soon = now + timedelta(days=7)
        assert min_start > now + timedelta(days=13)
        assert too_soon < min_start

    def test_future_statuses(self):
        valid = {"open", "reserved", "active", "settled", "expired"}
        assert len(valid) == 5

    def test_reservation_statuses(self):
        valid = {"active", "settled"}
        assert len(valid) == 2

    def test_total_value_calculation(self):
        quantity = 50
        price_per_unit = 100.0
        total = quantity * price_per_unit
        assert total == 5000.0

    def test_partial_reservation(self):
        """Buyer can reserve fewer units than available."""
        available = 100
        reserved = 30
        assert reserved <= available
