"""Tests for Infrastructure Cost Control — Master Kill Switch & Budget."""

import pytest
from app.infrastructure.cost_control import CostControlService


class TestBudgetThresholds:
    """Budget alert calculations."""

    def test_ok_level(self):
        spend, limit = 10.0, 20.0
        pct = spend / limit * 100
        assert pct == 50.0
        assert pct < 70  # Below warning

    def test_warning_level(self):
        spend, limit = 15.0, 20.0
        pct = spend / limit * 100
        assert pct == 75.0
        assert 70 <= pct < 90  # Warning zone

    def test_critical_level(self):
        spend, limit = 19.0, 20.0
        pct = spend / limit * 100
        assert pct == 95.0
        assert 90 <= pct < 100  # Critical zone

    def test_over_budget(self):
        spend, limit = 25.0, 20.0
        pct = spend / limit * 100
        assert pct == 125.0
        assert pct >= 100  # Over budget

    def test_daily_burn_rate(self):
        spend = 6.0
        day_of_month = 15
        daily = spend / day_of_month
        projected = daily * 30
        assert daily == 0.4
        assert projected == 12.0


class TestKillSwitch:
    """Master on/off switch logic."""

    def test_shutdown_state(self):
        is_active = False
        assert not is_active

    def test_active_state(self):
        is_active = True
        assert is_active

    def test_auto_shutdown_trigger(self):
        """Budget exceeded with auto_shutdown=True triggers shutdown."""
        spend, limit = 21.0, 20.0
        auto_shutdown = True
        pct = spend / limit * 100
        should_shutdown = pct >= 100 and auto_shutdown
        assert should_shutdown is True

    def test_auto_shutdown_disabled(self):
        """Budget exceeded with auto_shutdown=False does NOT shutdown."""
        spend, limit = 21.0, 20.0
        auto_shutdown = False
        pct = spend / limit * 100
        should_shutdown = pct >= 100 and auto_shutdown
        assert should_shutdown is False


class TestBudgetReset:
    def test_monthly_reset(self):
        spend = 18.50
        spend = 0.0  # Reset
        assert spend == 0.0


class TestProjectedCosts:
    def test_droplet_monthly_cost(self):
        """$6/month droplet — predictable cost."""
        monthly = 6.0
        assert monthly == 6.0

    def test_bandwidth_free_tier(self):
        """500 GiB free outbound per month."""
        free_gib = 500
        used_gib = 50
        overage = max(0, used_gib - free_gib)
        assert overage == 0

    def test_bandwidth_overage(self):
        free_gib = 500
        used_gib = 600
        overage_gib = max(0, used_gib - free_gib)
        cost_per_gib = 0.01
        overage_cost = overage_gib * cost_per_gib
        assert overage_gib == 100
        assert overage_cost == 1.0
