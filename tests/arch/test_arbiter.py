"""Arbiter test suite — 15 tests."""

import pytest
from app.arch.agents.arbiter import ArbiterAgent
from tests.arch.conftest import make_state


@pytest.fixture
def arbiter(mock_db_with_agents, mock_redis, mock_claude):
    return ArbiterAgent(agent_id="arbiter", db=mock_db_with_agents, redis=mock_redis, client=mock_claude)


class TestArbiter:

    @pytest.mark.asyncio
    async def test_search_case_law(self, arbiter):
        from unittest.mock import AsyncMock
        arbiter.recall = AsyncMock(return_value=[])
        result = await arbiter._tool_search_case_law({"query": "non-delivery of contracted work"})
        assert "case_law_results" in result

    @pytest.mark.asyncio
    async def test_search_case_law_with_type(self, arbiter):
        from unittest.mock import AsyncMock
        arbiter.recall = AsyncMock(return_value=[])
        result = await arbiter._tool_search_case_law(
            {"query": "quality dispute on AI service", "dispute_type": "quality", "top_k": 3}
        )
        assert result["query"] == "quality dispute on AI service"

    @pytest.mark.asyncio
    async def test_get_dispute_details_not_found(self, arbiter):
        result = await arbiter._tool_get_dispute_details({"dispute_id": "nonexistent"})
        assert "error" in result

    @pytest.mark.asyncio
    async def test_issue_ruling_full_payment(self, arbiter):
        result = await arbiter._tool_issue_ruling({
            "dispute_id": "dispute-123", "outcome": "FULL_PAYMENT",
            "ruling_text": "Provider delivered as specified in the Smart Engagement Contract. " * 5,
        })
        assert result["outcome"] == "FULL_PAYMENT"
        assert result["status"] == "ISSUED"

    @pytest.mark.asyncio
    async def test_issue_ruling_full_refund(self, arbiter):
        result = await arbiter._tool_issue_ruling({
            "dispute_id": "dispute-456", "outcome": "FULL_REFUND",
            "ruling_text": "Provider failed to deliver any work product within the agreed timeline. " * 5,
        })
        assert result["outcome"] == "FULL_REFUND"

    @pytest.mark.asyncio
    async def test_issue_ruling_with_precedent(self, arbiter):
        result = await arbiter._tool_issue_ruling({
            "dispute_id": "dispute-789", "outcome": "PARTIAL_PAYMENT",
            "ruling_text": "Partial delivery accepted. Provider completed 60% of scope. " * 5,
            "precedent_set": "Partial delivery at 60% warrants 60% payment.",
        })
        assert result["precedent_set"] is True

    @pytest.mark.asyncio
    async def test_enforce_community_warn(self, arbiter):
        result = await arbiter._tool_enforce_community_action({
            "target_id": "agent-bad", "target_type": "agent",
            "action": "WARN", "reason": "Repeated low-quality deliverables reported by multiple clients",
        })
        assert result["enforced"] is True

    @pytest.mark.asyncio
    async def test_enforce_community_suspend(self, arbiter):
        result = await arbiter._tool_enforce_community_action({
            "target_id": "op-bad", "target_type": "operator",
            "action": "SUSPEND_PENDING_REVIEW", "reason": "Multiple fraud reports — pending investigation",
        })
        assert result["action"] == "SUSPEND_PENDING_REVIEW"

    @pytest.mark.asyncio
    async def test_sla_status_check(self, arbiter):
        result = await arbiter._tool_check_sla_status({})
        assert "sla_status" in result

    @pytest.mark.asyncio
    async def test_sla_breach_only(self, arbiter):
        result = await arbiter._tool_check_sla_status({"breach_only": True})
        assert "count" in result

    @pytest.mark.asyncio
    async def test_rules_of_chamber_update(self, arbiter):
        result = await arbiter._tool_update_rules_of_chamber({
            "rule_section": "Section 4.2", "proposed_text": "Updated evidence submission deadline to 48 hours",
            "rationale": "Multiple cases showed 24 hours was insufficient for complex disputes requiring document collection",
        })
        assert result["status"] == "PROPOSAL_CREATED"

    @pytest.mark.asyncio
    async def test_tools_count(self, arbiter):
        tools = await arbiter.get_tools()
        assert len(tools) >= 6

    @pytest.mark.asyncio
    async def test_heartbeat(self, arbiter):
        await arbiter.heartbeat()

    @pytest.mark.asyncio
    async def test_system_prompt_key(self, arbiter):
        assert arbiter.system_prompt_key == "system_prompt"

    @pytest.mark.asyncio
    async def test_issue_ruling_rework(self, arbiter):
        result = await arbiter._tool_issue_ruling({
            "dispute_id": "dispute-rework", "outcome": "REWORK_ORDER",
            "ruling_text": "Provider must revise deliverable to meet the acceptance criteria specified in the contract. " * 3,
        })
        assert result["outcome"] == "REWORK_ORDER"
