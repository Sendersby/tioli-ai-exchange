"""Tests for Commercial Licensing — Build Brief V2, Section 2.5."""
from app.licensing.models import LICENCE_PRICING

class TestLicensing:
    def test_four_licence_types(self):
        assert len(LICENCE_PRICING) == 4
    def test_api_licence(self):
        assert LICENCE_PRICING["api"]["setup_fee_zar"] == 50_000
        assert LICENCE_PRICING["api"]["revenue_share_pct"] == 0.01
    def test_white_label(self):
        assert LICENCE_PRICING["white_label"]["setup_fee_zar"] == 100_000
        assert LICENCE_PRICING["white_label"]["monthly_fee_zar"] == 15_000
    def test_sdk_partner(self):
        assert LICENCE_PRICING["sdk"]["setup_fee_zar"] == 10_000
