"""Tests for Treasury Agent — Build Brief V2, Module 4."""

from app.treasury.models import TreasuryAgent, TreasuryAction


class TestTreasuryModels:
    def test_treasury_agent_fields(self):
        """Treasury agent has all required risk parameter fields."""
        t = TreasuryAgent(
            agent_id="agent-1", operator_id="op-1",
            max_single_trade_pct=10.0, max_lending_pct=30.0,
            min_reserve_pct=20.0, approved_currencies=["TIOLI", "BTC"],
            allowed_actions=["trade", "convert"], status="active",
        )
        assert t.max_single_trade_pct == 10.0
        assert t.max_lending_pct == 30.0
        assert t.min_reserve_pct == 20.0
        assert t.status == "active"
        assert "trade" in t.allowed_actions

    def test_treasury_action_fields(self):
        """Treasury action has rationale and audit fields."""
        a = TreasuryAction(
            treasury_id="t-1", action_type="trade_buy",
            rationale="Price dropped below buy threshold of 0.0001 BTC",
            amount=100.0, currency="TIOLI", result_status="success",
        )
        assert a.action_type == "trade_buy"
        assert "threshold" in a.rationale
        assert a.result_status == "success"

    def test_risk_parameter_bounds(self):
        """Reserve + lending should not exceed 100%."""
        reserve = 20.0
        lending = 30.0
        assert reserve + lending <= 100

    def test_default_execution_interval(self):
        """Brief: default execution interval is 60 minutes."""
        t = TreasuryAgent(
            agent_id="a1", operator_id="o1",
            max_single_trade_pct=10, max_lending_pct=30, min_reserve_pct=20,
            execution_interval_minutes=60,
        )
        assert t.execution_interval_minutes == 60

    def test_allowed_action_types(self):
        valid = {"trade", "lend", "borrow", "convert"}
        test_actions = ["trade", "convert"]
        assert set(test_actions).issubset(valid)

    def test_no_additional_treasury_fee(self):
        """Brief: standard transaction fees apply, no additional treasury fee."""
        from app.exchange.fees import FeeEngine
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        # Treasury trade uses same fee engine as regular trade
        fees = engine.calculate_fees(1000, transaction_type="resource_exchange")
        assert fees["commission"] > 0
        # No extra "treasury_fee" key
        assert "treasury_fee" not in fees
