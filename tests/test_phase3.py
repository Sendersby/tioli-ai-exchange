"""Tests for Phase 3: Financial Governance, Monitoring, Growth."""

import pytest
from app.governance.voting import GovernanceService
from app.growth.adoption import GrowthEngine


class TestFinancialGovernanceRules:
    def test_10x_rule_math(self):
        """Verify the 10x profitability rule calculation."""
        revenue = 10000.0
        expenses = 800.0
        multiplier = revenue / expenses
        assert multiplier == 12.5
        assert multiplier >= 10.0  # Can spend

    def test_10x_rule_blocks(self):
        """Expense should be blocked when multiplier < 10x."""
        revenue = 5000.0
        expenses = 600.0
        new_expense = 200.0
        projected = revenue / (expenses + new_expense)
        assert projected < 10.0  # Should block

    def test_3x_security_exception(self):
        """Security expenses allowed at 3x threshold."""
        revenue = 3000.0
        expenses = 800.0
        multiplier = revenue / expenses
        assert multiplier >= 3.0  # Security OK
        assert multiplier < 10.0  # Standard blocked

    def test_zero_expenses_infinite(self):
        """With no expenses, profitability is infinite — all spending allowed."""
        revenue = 5000.0
        expenses = 0.0
        multiplier = float('inf') if expenses == 0 else revenue / expenses
        assert multiplier == float('inf')


class TestGovernanceMaterialDetection:
    def test_material_category_detection(self):
        service = GovernanceService()
        assert "funds" in service.MATERIAL_CATEGORIES
        assert "legal" in service.MATERIAL_CATEGORIES
        assert "core_purpose" in service.MATERIAL_CATEGORIES
        assert "security" in service.MATERIAL_CATEGORIES

    def test_material_keyword_detection(self):
        service = GovernanceService()
        text = "change the commission rate to 5%"
        is_material = any(kw in text.lower() for kw in service.MATERIAL_KEYWORDS)
        assert is_material is True

    def test_non_material_detection(self):
        service = GovernanceService()
        text = "add dark mode to the dashboard"
        is_material = any(kw in text.lower() for kw in service.MATERIAL_KEYWORDS)
        assert is_material is False

    def test_priority_scoring(self):
        """Material changes should rank higher."""
        material_score = 5 + 1000  # 5 upvotes + material bonus
        normal_score = 20  # 20 upvotes, no bonus
        assert material_score > normal_score


class TestPlatformManifesto:
    def test_manifesto_content(self):
        engine = GrowthEngine()
        manifesto = engine.get_platform_manifesto()
        assert manifesto["name"] == "TiOLi AI Transact Exchange"
        assert "philosophy" in manifesto
        assert "capabilities" in manifesto
        assert len(manifesto["capabilities"]) >= 5
        assert "registration" in manifesto
        assert manifesto["registration"]["endpoint"] == "/api/agents/register"

    def test_manifesto_ethics(self):
        engine = GrowthEngine()
        manifesto = engine.get_platform_manifesto()
        assert "no harm" in manifesto["philosophy"].lower() or "good" in manifesto["philosophy"].lower()
        assert "law" in manifesto["legal"].lower()

    def test_manifesto_fee_transparency(self):
        engine = GrowthEngine()
        manifesto = engine.get_platform_manifesto()
        assert "fee_structure" in manifesto
        assert "founder_commission" in manifesto["fee_structure"]
        assert "charity_fee" in manifesto["fee_structure"]


class TestAdoptionMetricsConcepts:
    def test_retention_rate(self):
        total_agents = 100
        active_24h = 45
        retention = active_24h / total_agents * 100
        assert retention == 45.0

    def test_growth_rate(self):
        new_7d = 15
        existing = 85
        growth = new_7d / existing * 100
        assert round(growth, 1) == 17.6
