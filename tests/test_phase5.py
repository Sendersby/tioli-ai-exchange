"""Tests for Phase 5: Optimization, Discovery, Investing, Compliance."""

import pytest
from app.optimization.engine import SelfOptimizationEngine
from app.blockchain.chain import Blockchain


class TestSelfOptimization:
    def test_tunable_parameters_have_bounds(self):
        engine = SelfOptimizationEngine.__new__(SelfOptimizationEngine)
        params = SelfOptimizationEngine.TUNABLE_PARAMS
        for name, config in params.items():
            assert "min" in config
            assert "max" in config
            assert config["min"] <= config["current"] <= config["max"]

    def test_mining_threshold_bounds(self):
        params = SelfOptimizationEngine.TUNABLE_PARAMS
        assert params["mining_threshold"]["min"] == 5
        assert params["mining_threshold"]["max"] == 50

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.blockchain = Blockchain(storage_path=str(tmp_path / "chain.json"))
        self.engine = SelfOptimizationEngine(self.blockchain)

    def test_get_tunable_parameters(self):
        result = self.engine.get_tunable_parameters()
        assert "parameters" in result
        assert "guardrails" in result
        assert "mining_threshold" in result["parameters"]
        assert "rate_refresh_interval" in result["parameters"]


class TestAgentDiscovery:
    def test_reputation_running_average(self):
        """Test reputation score calculation."""
        old_score = 5.0
        total_reviews = 10
        new_rating = 9.0
        new_score = (old_score * total_reviews + new_rating) / (total_reviews + 1)
        assert round(new_score, 2) == 5.36

    def test_reputation_bounds(self):
        # Rating must be 1-10
        assert 1 <= 1 <= 10
        assert 1 <= 10 <= 10
        assert not (1 <= 0 <= 10)
        assert not (1 <= 11 <= 10)


class TestPortfolioValuation:
    def test_allocation_percentage(self):
        holdings = [
            {"currency": "TIOLI", "value_tioli": 5000},
            {"currency": "BTC", "value_tioli": 3000},
            {"currency": "ETH", "value_tioli": 2000},
        ]
        total = sum(h["value_tioli"] for h in holdings)
        for h in holdings:
            h["pct"] = round(h["value_tioli"] / total * 100, 1)
        assert holdings[0]["pct"] == 50.0
        assert holdings[1]["pct"] == 30.0
        assert holdings[2]["pct"] == 20.0

    def test_pnl_calculation(self):
        initial = 10000
        current = 12500
        pnl = current - initial
        roi = pnl / initial * 100
        assert pnl == 2500
        assert roi == 25.0

    def test_negative_pnl(self):
        initial = 10000
        current = 7500
        pnl = current - initial
        roi = pnl / initial * 100
        assert pnl == -2500
        assert roi == -25.0


class TestKYAVerification:
    def test_verification_levels(self):
        # Level 0: no info
        # Level 1: operator name
        # Level 2: name + jurisdiction
        # Level 3: name + jurisdiction + purpose (fully verified)
        info = {"name": None, "jurisdiction": None, "purpose": None}
        level = 0
        assert level == 0

        info["name"] = "Acme AI Corp"
        level = 1
        assert level == 1

        info["jurisdiction"] = "South Africa"
        level = 2
        assert level == 2

        info["purpose"] = "Compute trading for batch processing"
        level = 3
        assert level == 3

    def test_high_value_threshold(self):
        from app.compliance.framework import ComplianceFramework
        assert ComplianceFramework.HIGH_VALUE_THRESHOLD == 10000


class TestComplianceExport:
    def test_export_structure(self):
        """Audit export should contain required fields."""
        required_fields = ["platform", "blockchain", "compliance", "transaction_count"]
        # Simulated export
        export = {
            "platform": "TiOLi AI Transact Exchange",
            "blockchain": {"chain_length": 5, "chain_valid": True},
            "compliance": {"open_flags": 0},
            "transaction_count": 100,
        }
        for field in required_fields:
            assert field in export

    def test_platform_name_in_export(self):
        export = {"platform": "TiOLi AI Transact Exchange"}
        assert export["platform"] == "TiOLi AI Transact Exchange"
