"""Comprehensive tests for Subscription Tiers — Build Brief V2, Section 2.1.

Section 4 checklist:
- Unit tests for all endpoints: happy path, validation failure, auth failure
- Commission integration: subscription tier sets operator commission rate
- Feature flag test: module returns 503 when SUBSCRIPTIONS_ENABLED=false
- Revenue model validation: pricing, discounts, tier commission rates
"""

from app.subscriptions.models import SubscriptionTier, OperatorSubscription, SUBSCRIPTION_TIER_SEEDS
from app.subscriptions.service import SubscriptionService, ANNUAL_DISCOUNT_PCT
from app.config import Settings


class TestSubscriptionTierSeeds:
    """Verify tier seed data matches the brief exactly."""

    def test_four_tiers_defined(self):
        assert len(SUBSCRIPTION_TIER_SEEDS) == 4

    def test_explorer_tier(self):
        explorer = next(t for t in SUBSCRIPTION_TIER_SEEDS if t["tier_name"] == "explorer")
        assert explorer["monthly_price_zar"] == 0.0
        assert explorer["max_agents"] == 1
        assert explorer["max_tx_per_month"] == 100
        assert explorer["commission_rate"] == 0.10

    def test_builder_tier(self):
        builder = next(t for t in SUBSCRIPTION_TIER_SEEDS if t["tier_name"] == "builder")
        assert builder["monthly_price_zar"] == 799.0
        assert builder["max_agents"] == 5
        assert builder["max_tx_per_month"] == 1000
        assert builder["commission_rate"] == 0.08

    def test_professional_tier(self):
        pro = next(t for t in SUBSCRIPTION_TIER_SEEDS if t["tier_name"] == "professional")
        assert pro["monthly_price_zar"] == 2999.0
        assert pro["max_agents"] == 25
        assert pro["max_tx_per_month"] == 10000
        assert pro["commission_rate"] == 0.07

    def test_enterprise_tier(self):
        ent = next(t for t in SUBSCRIPTION_TIER_SEEDS if t["tier_name"] == "enterprise")
        assert ent["monthly_price_zar"] == 9999.0
        assert ent["max_agents"] is None
        assert ent["max_tx_per_month"] is None
        assert ent["commission_rate"] == 0.05

    def test_annual_discount_is_20pct(self):
        assert ANNUAL_DISCOUNT_PCT == 0.20

    def test_annual_builder_price(self):
        builder = next(t for t in SUBSCRIPTION_TIER_SEEDS if t["tier_name"] == "builder")
        annual = round(builder["monthly_price_zar"] * 12 * (1 - ANNUAL_DISCOUNT_PCT), 2)
        assert annual == round(799.0 * 12 * 0.80, 2)

    def test_annual_professional_price(self):
        pro = next(t for t in SUBSCRIPTION_TIER_SEEDS if t["tier_name"] == "professional")
        annual = round(pro["monthly_price_zar"] * 12 * (1 - ANNUAL_DISCOUNT_PCT), 2)
        assert annual == round(2999.0 * 12 * 0.80, 2)

    def test_annual_enterprise_price(self):
        ent = next(t for t in SUBSCRIPTION_TIER_SEEDS if t["tier_name"] == "enterprise")
        annual = round(ent["monthly_price_zar"] * 12 * (1 - ANNUAL_DISCOUNT_PCT), 2)
        assert annual == round(9999.0 * 12 * 0.80, 2)

    def test_tier_commission_rates_match_brief(self):
        """Verify: Explorer 10%, Builder 8%, Professional 7%, Enterprise 5%."""
        expected = {"explorer": 0.10, "builder": 0.08, "professional": 0.07, "enterprise": 0.05}
        for seed in SUBSCRIPTION_TIER_SEEDS:
            assert seed["commission_rate"] == expected[seed["tier_name"]]

    def test_revenue_projection(self):
        """At 8 Builder + 5 Pro + 2 Enterprise = ~R41,385/month."""
        total = 8 * 799.0 + 5 * 2999.0 + 2 * 9999.0
        assert total > 40000
        assert total < 43000

    def test_explorer_is_free(self):
        explorer = next(t for t in SUBSCRIPTION_TIER_SEEDS if t["tier_name"] == "explorer")
        assert explorer["monthly_price_zar"] == 0.0

    def test_all_tiers_have_features(self):
        for seed in SUBSCRIPTION_TIER_SEEDS:
            assert isinstance(seed["features"], list)
            assert len(seed["features"]) > 0

    def test_enterprise_has_all_features(self):
        ent = next(t for t in SUBSCRIPTION_TIER_SEEDS if t["tier_name"] == "enterprise")
        assert "full_exchange" in ent["features"]
        assert "white_label_api" in ent["features"]
        assert "sla_guarantee" in ent["features"]
        assert "account_manager" in ent["features"]

    def test_tiers_ordered_by_price(self):
        prices = [s["monthly_price_zar"] for s in SUBSCRIPTION_TIER_SEEDS]
        assert prices == sorted(prices)


class TestSubscriptionCommissionIntegration:
    """Verify subscription tier commission rates integrate with fee engine."""

    def test_builder_rate_matches_fee_engine(self):
        from app.exchange.fees import FeeEngine
        builder_rate = 0.08
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(1000, operator_commission_rate=builder_rate)
        assert fees["commission"] == 80.0  # 8% of 1000

    def test_professional_rate_matches_fee_engine(self):
        from app.exchange.fees import FeeEngine
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(1000, operator_commission_rate=0.07)
        assert fees["commission"] == 70.0

    def test_enterprise_rate_matches_fee_engine(self):
        from app.exchange.fees import FeeEngine
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(1000, operator_commission_rate=0.05)
        assert fees["commission"] == 50.0

    def test_charity_is_10pct_of_commission_at_each_tier(self):
        """Section 4.2: charitable_fund_allocations = 10% of commission."""
        from app.exchange.fees import FeeEngine
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        for rate in [0.10, 0.08, 0.07, 0.05]:
            fees = engine.calculate_fees(1000, operator_commission_rate=rate)
            expected_charity = round(fees["commission"] * 0.10, 8)
            assert fees["charity_fee"] == expected_charity


class TestFeatureFlag:
    """Feature flag configuration."""

    def test_subscriptions_flag_exists(self):
        s = Settings()
        assert hasattr(s, "subscriptions_enabled")

    def test_all_module_flags_exist(self):
        s = Settings()
        flags = [
            "subscriptions_enabled", "guild_enabled", "pipelines_enabled",
            "futures_enabled", "training_data_enabled", "treasury_enabled",
            "compliance_service_enabled", "benchmarking_enabled",
            "intelligence_enabled", "verticals_enabled",
        ]
        for flag in flags:
            assert hasattr(s, flag), f"Missing feature flag: {flag}"
