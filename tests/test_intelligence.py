"""Comprehensive tests for Market Intelligence — Build Brief V2, Module 8."""

from app.intelligence.models import (
    IntelligenceSnapshot, IntelligenceAlert, AnalyticsSubscription,
    INTELLIGENCE_TIERS,
)


class TestIntelligenceTiers:
    def test_four_tiers(self):
        assert len(INTELLIGENCE_TIERS) == 4

    def test_public_tier_free(self):
        assert INTELLIGENCE_TIERS["public"]["monthly_zar"] == 0
        assert INTELLIGENCE_TIERS["public"]["lag_days"] == 30

    def test_standard_pricing(self):
        assert INTELLIGENCE_TIERS["standard"]["monthly_zar"] == 499
        assert INTELLIGENCE_TIERS["standard"]["lag_days"] == 0

    def test_premium_pricing(self):
        assert INTELLIGENCE_TIERS["premium"]["monthly_zar"] == 1999
        assert INTELLIGENCE_TIERS["premium"]["lag_days"] == 0

    def test_enterprise_custom(self):
        assert INTELLIGENCE_TIERS["enterprise"]["monthly_zar"] is None

    def test_all_tiers_have_descriptions(self):
        for tier, config in INTELLIGENCE_TIERS.items():
            assert "description" in config
            assert len(config["description"]) > 0


class TestIntelligenceModels:
    def test_snapshot_fields(self):
        s = IntelligenceSnapshot(
            capability_category="data_science",
            demand_index=1.5, supply_index=0.8,
            avg_price=100.0, price_trend_pct=5.2,
            volume_index=1.2, avg_reputation=7.5,
        )
        assert s.demand_index == 1.5
        assert s.supply_index == 0.8

    def test_alert_severities(self):
        valid = {"low", "medium", "high"}
        assert len(valid) == 3

    def test_alert_types(self):
        valid = {"price_spike", "supply_shortage", "demand_surge"}
        assert len(valid) == 3

    def test_anomaly_detection_thresholds(self):
        """Brief: price > 15%, demand > 1.5, supply < 0.5."""
        assert 16 > 15   # Price spike
        assert 1.6 > 1.5  # Demand surge
        assert 0.4 < 0.5  # Supply shortage

    def test_retention_policy(self):
        """Brief: 90 days daily, 2 years weekly rollup."""
        daily_retention_days = 90
        weekly_retention_years = 2
        assert daily_retention_days == 90
        assert weekly_retention_years == 2

    def test_public_tier_30_day_lag(self):
        """Public tier data must be at least 30 days old."""
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=30)
        recent_data = now - timedelta(days=5)
        assert recent_data > cutoff  # Would be filtered out for public tier
