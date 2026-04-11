"""Architect test suite — 15 tests."""

import pytest
from app.arch.agents.architect import ArchitectAgent
from tests.arch.conftest import make_state


@pytest.fixture
def architect(mock_db_with_agents, mock_redis, mock_claude):
    return ArchitectAgent(agent_id="architect", db=mock_db_with_agents, redis=mock_redis, client=mock_claude)


class TestArchitect:

    @pytest.mark.asyncio
    async def test_submit_code_proposal_tier0(self, architect):
        result = await architect._tool_submit_code_proposal({
            "tier": "0", "title": "Update sentinel threshold",
            "description": "Increase alert threshold", "rationale": "Reduce false positives",
        })
        assert result["tier"] == "0"
        assert result["status"] == "DRAFT"

    @pytest.mark.asyncio
    async def test_submit_code_proposal_tier1(self, architect):
        result = await architect._tool_submit_code_proposal({
            "tier": "1", "title": "Add new monitoring tool",
            "description": "New tool integration", "rationale": "Improved observability",
        })
        assert result["tier"] == "1"

    @pytest.mark.asyncio
    async def test_self_referential_blocked(self, architect):
        result = await architect._tool_submit_code_proposal({
            "tier": "0", "title": "Update CONSTITUTION_CHECKSUM",
            "description": "Modify checksum", "rationale": "Test",
        })
        assert result["status"] == "SELF_REFERENTIAL_BLOCK"

    @pytest.mark.asyncio
    async def test_toggle_feature_flag(self, architect):
        result = await architect._tool_toggle_feature_flag({
            "flag_name": "ARCH_BROWSER_AUTOMATION_ENABLED",
            "enabled": True, "reason": "Phase 5 activation",
        })
        assert result["status"] == "FLAGGED"

    @pytest.mark.asyncio
    async def test_toggle_constitutional_flag_blocked(self, architect):
        result = await architect._tool_toggle_feature_flag({
            "flag_name": "ARCH_AGENTS_ENABLED",
            "enabled": False, "reason": "Test",
        })
        assert result["status"] == "BLOCKED"

    @pytest.mark.asyncio
    async def test_sandbox_deploy(self, architect):
        result = await architect._tool_sandbox_deploy({"proposal_id": "test-proposal-uuid"})
        assert result["status"] == "SANDBOX_PENDING"

    @pytest.mark.asyncio
    async def test_update_tech_radar(self, architect):
        result = await architect._tool_update_tech_radar({
            "technology": "LangGraph 0.3", "assessment": "ADOPT",
            "rationale": "Production-proven for multi-agent orchestration",
        })
        assert result["recorded"] is True

    @pytest.mark.asyncio
    async def test_evaluate_ai_model(self, architect):
        result = await architect._tool_evaluate_ai_model({
            "model_name": "claude-opus-4-6", "provider": "Anthropic",
        })
        assert result["status"] == "EVALUATED"

    @pytest.mark.asyncio
    async def test_performance_snapshot(self, architect):
        result = await architect._tool_get_performance_snapshot({})
        assert "snapshots" in result

    @pytest.mark.asyncio
    async def test_trigger_acc_task(self, architect):
        result = await architect._tool_trigger_acc_task({
            "task_type": "seo_article", "topic": "AI agent exchanges",
        })
        assert result["status"] == "QUEUED"

    @pytest.mark.asyncio
    async def test_approve_acc_output(self, architect):
        result = await architect._tool_approve_acc_output({"output_id": "acc-out-1"})
        assert result["status"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_reset_token_budgets(self, architect):
        await architect.reset_token_budgets()

    @pytest.mark.asyncio
    async def test_ingest_research(self, architect):
        await architect.ingest_research()

    @pytest.mark.asyncio
    async def test_tools_count(self, architect):
        tools = await architect.get_tools()
        assert len(tools) >= 8

    @pytest.mark.asyncio
    async def test_heartbeat(self, architect):
        await architect.heartbeat()
