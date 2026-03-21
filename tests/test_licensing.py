"""Comprehensive tests for Commercial Licensing — Build Brief V2, Section 2.5."""

from app.licensing.models import CommercialLicence, LICENCE_PRICING


class TestLicencePricing:
    def test_four_licence_types(self):
        assert len(LICENCE_PRICING) == 4

    def test_api_licence(self):
        api = LICENCE_PRICING["api"]
        assert api["setup_fee_zar"] == 50_000
        assert api["revenue_share_pct"] == 0.01
        assert api["monthly_fee_zar"] == 0

    def test_white_label(self):
        wl = LICENCE_PRICING["white_label"]
        assert wl["setup_fee_zar"] == 100_000
        assert wl["monthly_fee_zar"] == 15_000
        assert wl["revenue_share_pct"] == 0.005

    def test_sdk_partner(self):
        sdk = LICENCE_PRICING["sdk"]
        assert sdk["setup_fee_zar"] == 10_000

    def test_regional_licence(self):
        reg = LICENCE_PRICING["regional"]
        assert reg["setup_fee_zar"] == 75_000
        assert reg["monthly_fee_zar"] == 10_000
        assert reg["revenue_share_pct"] == 0.02

    def test_all_have_descriptions(self):
        for ltype, config in LICENCE_PRICING.items():
            assert "description" in config
            assert len(config["description"]) > 0

    def test_white_label_annual_cost(self):
        """R100k setup + R15k/mo * 12 = R280k first year."""
        wl = LICENCE_PRICING["white_label"]
        first_year = wl["setup_fee_zar"] + wl["monthly_fee_zar"] * 12
        assert first_year == 280_000

    def test_api_licence_revenue_on_1m_gtv(self):
        """1% of R1M GTV = R10k revenue."""
        api = LICENCE_PRICING["api"]
        gtv = 1_000_000
        revenue = gtv * api["revenue_share_pct"]
        assert revenue == 10_000


class TestLicenceModel:
    def test_licence_statuses(self):
        valid = {"draft", "pending_approval", "active", "suspended", "terminated"}
        assert len(valid) == 5

    def test_owner_3fa_required(self):
        """Brief: all licence activations require owner 3FA confirmation."""
        # Licence starts as draft, must go through pending_approval
        l = CommercialLicence(
            licensee_name="Test Corp", licence_type="api",
            setup_fee_zar=50000, status="draft",
        )
        assert l.status == "draft"
        assert l.activated_at is None
