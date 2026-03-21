"""Tests for Market Intelligence — Build Brief V2, Module 8."""
from app.intelligence.models import INTELLIGENCE_TIERS

class TestIntelligence:
    def test_four_tiers(self):
        assert len(INTELLIGENCE_TIERS) == 4
    def test_public_tier_free(self):
        assert INTELLIGENCE_TIERS["public"]["monthly_zar"] == 0
        assert INTELLIGENCE_TIERS["public"]["lag_days"] == 30
    def test_standard_pricing(self):
        assert INTELLIGENCE_TIERS["standard"]["monthly_zar"] == 499
    def test_premium_pricing(self):
        assert INTELLIGENCE_TIERS["premium"]["monthly_zar"] == 1999
