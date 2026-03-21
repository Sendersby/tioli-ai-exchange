"""Tests for Capability Futures — Build Brief V2, Module 3."""
from app.futures.models import FUTURE_CREATION_FEE_ZAR, RESERVATION_FEE_PCT, SETTLEMENT_FEE_PCT

class TestFuturesModels:
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
        assert FUTURE_CREATION_FEE_ZAR == 50
        assert round(total * RESERVATION_FEE_PCT, 2) == 50.0
        assert round(total * SETTLEMENT_FEE_PCT, 2) == 150.0
