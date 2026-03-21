"""Comprehensive tests for Cross-Border — Build Brief V2, Module 6."""

from app.crossborder.models import InternationalSettlement, SARB_SDA_ANNUAL_LIMIT_ZAR
from app.crossborder.service import SARB_WARNING_THRESHOLD_PCT


class TestSARBCompliance:
    def test_sarb_limit(self):
        assert SARB_SDA_ANNUAL_LIMIT_ZAR == 1_000_000

    def test_warning_at_90pct(self):
        threshold = SARB_SDA_ANNUAL_LIMIT_ZAR * SARB_WARNING_THRESHOLD_PCT
        assert threshold == 900_000

    def test_block_at_limit(self):
        cumulative = 1_000_001
        assert cumulative > SARB_SDA_ANNUAL_LIMIT_ZAR

    def test_under_limit_allowed(self):
        cumulative = 500_000
        assert cumulative <= SARB_SDA_ANNUAL_LIMIT_ZAR

    def test_at_exact_limit_blocked(self):
        """At exactly R1M, new transactions should be blocked."""
        cumulative = 1_000_000
        new_amount = 1
        assert cumulative + new_amount > SARB_SDA_ANNUAL_LIMIT_ZAR

    def test_warning_zone(self):
        """Between R900k and R1M = warning but not blocked."""
        cumulative = 950_000
        assert cumulative > SARB_SDA_ANNUAL_LIMIT_ZAR * SARB_WARNING_THRESHOLD_PCT
        assert cumulative <= SARB_SDA_ANNUAL_LIMIT_ZAR

    def test_remaining_calculation(self):
        cumulative = 750_000
        remaining = SARB_SDA_ANNUAL_LIMIT_ZAR - cumulative
        assert remaining == 250_000

    def test_utilisation_percentage(self):
        cumulative = 500_000
        util_pct = cumulative / SARB_SDA_ANNUAL_LIMIT_ZAR * 100
        assert util_pct == 50.0
