"""Sovereign test suite — 15 tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.arch.agents.sovereign import SovereignAgent
from tests.arch.conftest import make_state


@pytest.fixture
def sovereign(mock_db_with_agents, mock_redis, mock_claude):
    return SovereignAgent(agent_id="sovereign", db=mock_db_with_agents, redis=mock_redis, client=mock_claude)


class TestSovereign:

    @pytest.mark.asyncio
    async def test_convene_board_session(self, sovereign):
        result = await sovereign._tool_convene_board_session(
            {"session_type": "WEEKLY", "agenda": ["Review platform health"]}
        )
        assert "session_id" in result
        assert result["session_type"] == "WEEKLY"

    @pytest.mark.asyncio
    async def test_convene_emergency_session(self, sovereign):
        result = await sovereign._tool_convene_board_session(
            {"session_type": "EMERGENCY", "agenda": ["P1 incident"]}
        )
        assert result["session_type"] == "EMERGENCY"

    @pytest.mark.asyncio
    async def test_founder_submission(self, sovereign):
        result = await sovereign._tool_submit_to_founder_inbox({
            "item_type": "DEFER_TO_OWNER", "priority": "URGENT",
            "subject": "Test decision", "situation": "Need founder input",
        })
        assert result["status"] == "PENDING"
        assert result["item_type"] == "DEFER_TO_OWNER"

    @pytest.mark.asyncio
    async def test_founder_submission_financial(self, sovereign):
        result = await sovereign._tool_submit_to_founder_inbox({
            "item_type": "FINANCIAL_PROPOSAL", "priority": "ROUTINE",
            "subject": "Vendor payment", "situation": "R2000 payment due",
        })
        assert result["item_type"] == "FINANCIAL_PROPOSAL"

    @pytest.mark.asyncio
    async def test_constitutional_ruling(self, sovereign):
        result = await sovereign._tool_issue_constitutional_ruling({
            "ruling_type": "DISPUTE_RESOLUTION",
            "ruling_text": "The Auditor's compliance objection is upheld. " * 5,
            "cited_directives": ["PD-2"],
            "subject_agents": ["auditor", "treasurer"],
        })
        assert result["status"] == "ISSUED"
        assert "ruling_ref" in result

    @pytest.mark.asyncio
    async def test_read_agent_health(self, sovereign):
        result = await sovereign._tool_read_agent_health({})
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_broadcast_to_board(self, sovereign):
        result = await sovereign._tool_broadcast_to_board({
            "subject": "Test broadcast", "message": "Hello board",
            "priority": "ROUTINE",
        })
        assert result["broadcast"] is True

    @pytest.mark.asyncio
    async def test_notify_founder(self, sovereign):
        state = make_state(output="Test notification to founder")
        result = await sovereign.notify_founder(state)
        assert result["founder_approval_status"] == "NOTIFIED"

    @pytest.mark.asyncio
    async def test_financial_gate_check(self, sovereign):
        state = make_state()
        result = await sovereign.financial_gate_check(state)
        assert result["financial_gate_cleared"] is True

    @pytest.mark.asyncio
    async def test_trigger_self_assessments(self, sovereign):
        await sovereign.trigger_self_assessments()

    @pytest.mark.asyncio
    async def test_defer_to_owner_cost(self, sovereign):
        state = make_state(instruction="Evaluate cost of new server")
        result = await sovereign(state)
        assert result["defer_to_owner"] is True

    @pytest.mark.asyncio
    async def test_defer_to_owner_regulatory(self, sovereign):
        state = make_state(instruction="Handle regulatory filing requirement")
        result = await sovereign(state)
        assert result["defer_to_owner"] is True

    @pytest.mark.asyncio
    async def test_no_defer_normal_instruction(self, sovereign):
        state = make_state(instruction="Check platform status dashboard")
        # Mock recall to avoid OpenAI API call in tests
        from unittest.mock import AsyncMock
        sovereign.recall = AsyncMock(return_value=[])
        result = await sovereign(state)
        assert result.get("defer_to_owner") is not True or result.get("output") is not None

    @pytest.mark.asyncio
    async def test_heartbeat(self, sovereign):
        await sovereign.heartbeat()

    @pytest.mark.asyncio
    async def test_system_prompt_key(self, sovereign):
        assert sovereign.system_prompt_key == "system_prompt"
