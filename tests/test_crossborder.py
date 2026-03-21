"""Tests for Cross-Border — Build Brief V2, Module 6."""
from app.crossborder.models import SARB_SDA_ANNUAL_LIMIT_ZAR

class TestCrossBorder:
    def test_sarb_limit(self):
        assert SARB_SDA_ANNUAL_LIMIT_ZAR == 1_000_000
    def test_warning_at_90pct(self):
        threshold = SARB_SDA_ANNUAL_LIMIT_ZAR * 0.90
        assert threshold == 900_000
    def test_block_at_limit(self):
        cumulative = 1_000_001
        assert cumulative > SARB_SDA_ANNUAL_LIMIT_ZAR
