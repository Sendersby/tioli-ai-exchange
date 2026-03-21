"""Tests for Subscription Tiers — Build Brief V2, Section 2.1."""

from app.subscriptions.models import SubscriptionTier, SUBSCRIPTION_TIER_SEEDS
from app.subscriptions.service import SubscriptionService, ANNUAL_DISCOUNT_PCT


class TestSubscriptionTierSeeds:
    """Verify tier seed data is correct per the brief."""

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
        assert ent["max_agents"] is None  # Unlimited
        assert ent["max_tx_per_month"] is None  # Unlimited
        assert ent["commission_rate"] == 0.05

    def test_annual_discount_is_20pct(self):
        assert ANNUAL_DISCOUNT_PCT == 0.20

    def test_annual_builder_price(self):
        """Annual subscription: monthly_price * 12 * 0.80."""
        builder = next(t for t in SUBSCRIPTION_TIER_SEEDS if t["tier_name"] == "builder")
        annual = round(builder["monthly_price_zar"] * 12 * (1 - ANNUAL_DISCOUNT_PCT), 2)
        assert annual == round(799.0 * 12 * 0.80, 2)

    def test_tier_commission_rates_match_brief(self):
        """Verify: Explorer 10%, Builder 8%, Professional 7%, Enterprise 5%."""
        expected = {
            "explorer": 0.10,
            "builder": 0.08,
            "professional": 0.07,
            "enterprise": 0.05,
        }
        for seed in SUBSCRIPTION_TIER_SEEDS:
            assert seed["commission_rate"] == expected[seed["tier_name"]], \
                f"{seed['tier_name']} rate should be {expected[seed['tier_name']]}"

    def test_revenue_projection(self):
        """At 8 Builder + 5 Pro + 2 Enterprise = ~R41,385/month."""
        builder_mrr = 8 * 799.0
        pro_mrr = 5 * 2999.0
        ent_mrr = 2 * 9999.0
        total = builder_mrr + pro_mrr + ent_mrr
        assert total > 40000  # Brief says ~R41,385
        assert total < 43000
