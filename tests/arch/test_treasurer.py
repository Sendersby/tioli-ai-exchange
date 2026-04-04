"""Treasurer test suite — 15 tests."""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from app.arch.agents.treasurer import TreasurerAgent
from tests.arch.conftest import make_state


@pytest.fixture
def treasurer(mock_db_with_agents, mock_redis, mock_claude):
    return TreasurerAgent(agent_id="treasurer", db=mock_db_with_agents, redis=mock_redis, client=mock_claude)


class TestTreasurer:

    @pytest.mark.asyncio
    async def test_reserve_status_calculation(self, treasurer):
        result = await treasurer._tool_check_reserve_status({})
        assert "floor_zar" in result
        assert "total_balance_zar" in result
        assert "headroom_zar" in result
        assert "ceiling_remaining_zar" in result

    @pytest.mark.asyncio
    async def test_reserve_breach_detection(self, treasurer):
        result = await treasurer._tool_check_reserve_status({})
        assert "would_breach_floor" in result
        assert "would_breach_ceiling" in result

    @pytest.mark.asyncio
    async def test_financial_proposal_submission(self, treasurer):
        result = await treasurer._tool_submit_financial_proposal({
            "proposal_type": "OPERATIONAL_EXPENSE",
            "amount_zar": 1000, "description": "Server upgrade for arch agents",
            "justification": "Current 4GB RAM is sufficient but monitoring shows we need headroom for all 7 agents",
        })
        assert result["status"] in ("FOUNDER_REVIEW", "BLOCKED")

    @pytest.mark.asyncio
    async def test_financial_report_generation(self, treasurer):
        result = await treasurer._tool_get_financial_report({"period": "monthly"})
        assert "total_platform_balance" in result
        assert "founder_commission_balance" in result
        assert result["period"] == "monthly"

    @pytest.mark.asyncio
    async def test_financial_report_ytd(self, treasurer):
        result = await treasurer._tool_get_financial_report({"period": "ytd"})
        assert result["period"] == "ytd"

    @pytest.mark.asyncio
    async def test_charitable_allocation_gross_base(self, treasurer):
        result = await treasurer._tool_record_charitable_allocation({
            "gross_commission_zar": 100.0, "trigger_transaction_id": "tx-test-123",
        })
        assert result["calculation_base"] == "gross_commission"
        assert result["charitable_allocated_zar"] == 10.0  # 10% of 100

    @pytest.mark.asyncio
    async def test_charitable_allocation_math(self, treasurer):
        result = await treasurer._tool_record_charitable_allocation({
            "gross_commission_zar": 80.0, "trigger_transaction_id": "tx-test-456",
        })
        assert result["charitable_allocated_zar"] == 8.0  # 10% of R80

    @pytest.mark.asyncio
    async def test_vendor_cost_recording(self, treasurer):
        result = await treasurer._tool_record_vendor_cost({
            "vendor_name": "DigitalOcean", "monthly_cost_zar": 700.0,
            "service_type": "infrastructure",
        })
        assert result["recorded"] is True

    @pytest.mark.asyncio
    async def test_financial_gate_check(self, treasurer):
        state = make_state(instruction_type="finance")
        result = await treasurer.financial_gate_check(state)
        assert "financial_gate_cleared" in result

    @pytest.mark.asyncio
    async def test_calculate_reserves_scheduled(self, treasurer):
        await treasurer.calculate_reserves()

    @pytest.mark.asyncio
    async def test_defer_on_revenue_model(self, treasurer):
        state = make_state(instruction="Change the revenue_model commission rates")
        result = await treasurer(state)
        assert result["defer_to_owner"] is True

    @pytest.mark.asyncio
    async def test_defer_on_cost_decision(self, treasurer):
        state = make_state(instruction="Approve cost of new vendor contract")
        result = await treasurer(state)
        assert result["defer_to_owner"] is True

    @pytest.mark.asyncio
    async def test_system_prompt_key(self, treasurer):
        assert treasurer.system_prompt_key == "system_prompt"

    @pytest.mark.asyncio
    async def test_heartbeat(self, treasurer):
        await treasurer.heartbeat()

    @pytest.mark.asyncio
    async def test_tools_returned(self, treasurer):
        tools = await treasurer.get_tools()
        assert len(tools) >= 5
        names = [t["name"] for t in tools]
        assert "check_reserve_status" in names
        assert "submit_financial_proposal" in names
