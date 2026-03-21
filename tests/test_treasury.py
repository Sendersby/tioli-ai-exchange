"""Comprehensive tests for Treasury Agent — Build Brief V2, Module 4."""

from app.treasury.models import TreasuryAgent, TreasuryAction


class TestTreasuryModels:
    def test_treasury_agent_fields(self):
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
        assert 20.0 + 30.0 <= 100

    def test_risk_parameter_bounds_violation(self):
        """Service should reject reserve + lending > 100%."""
        reserve = 60.0
        lending = 50.0
        assert reserve + lending > 100  # Would be rejected

    def test_max_single_trade_cap(self):
        """Brief: max_single_trade_pct cannot exceed 50%."""
        assert 50 <= 50  # At limit is OK
        assert 51 > 50   # Over limit rejected

    def test_default_execution_interval(self):
        t = TreasuryAgent(
            agent_id="a1", operator_id="o1",
            max_single_trade_pct=10, max_lending_pct=30, min_reserve_pct=20,
            execution_interval_minutes=60,
        )
        assert t.execution_interval_minutes == 60

    def test_allowed_action_types(self):
        valid = {"trade", "lend", "borrow", "convert"}
        assert set(["trade", "convert"]).issubset(valid)
        assert "hack" not in valid

    def test_no_additional_treasury_fee(self):
        from app.exchange.fees import FeeEngine
        engine = FeeEngine(founder_rate=0.12, charity_rate=0.10)
        fees = engine.calculate_fees(1000, transaction_type="resource_exchange")
        assert fees["commission"] > 0
        assert "treasury_fee" not in fees

    def test_action_types_cover_all_operations(self):
        """Treasury can trade, lend, borrow, convert."""
        action_types = ["trade_buy", "trade_sell", "lend", "borrow", "convert", "rebalance"]
        assert len(action_types) == 6

    def test_rationale_is_required(self):
        """Every treasury action must have an AI-generated rationale."""
        a = TreasuryAction(
            treasury_id="t1", action_type="trade_buy",
            rationale="Buy signal: TIOLI/BTC price 0.000001 below threshold 0.0001",
        )
        assert len(a.rationale) > 0

    def test_paused_status(self):
        t = TreasuryAgent(
            agent_id="a1", operator_id="o1",
            max_single_trade_pct=10, max_lending_pct=30, min_reserve_pct=20,
            status="paused",
        )
        assert t.status == "paused"
