"""Ambassador test suite — 15 tests."""

import pytest
from app.arch.agents.ambassador import AmbassadorAgent
from tests.arch.conftest import make_state


@pytest.fixture
def ambassador(mock_db_with_agents, mock_redis, mock_claude):
    return AmbassadorAgent(agent_id="ambassador", db=mock_db_with_agents, redis=mock_redis, client=mock_claude)


class TestAmbassador:

    @pytest.mark.asyncio
    async def test_publish_content_blog(self, ambassador):
        result = await ambassador._tool_publish_content({
            "platform": "blog", "content_type": "article",
            "title": "Test Article", "body": "Content body here",
        })
        assert result["status"] == "PUBLISHED"
        assert result["platform"] == "blog"

    @pytest.mark.asyncio
    async def test_publish_content_linkedin(self, ambassador):
        result = await ambassador._tool_publish_content({
            "platform": "linkedin", "content_type": "post",
            "body": "TiOLi AGENTIS update",
        })
        assert result["platform"] == "linkedin"

    @pytest.mark.asyncio
    async def test_record_growth_experiment(self, ambassador):
        result = await ambassador._tool_record_growth_experiment({
            "hypothesis": "MCP listings drive 3x more registrations",
            "channel": "mcp_registries",
        })
        assert result["status"] == "RECORDED"

    @pytest.mark.asyncio
    async def test_record_growth_experiment_with_result(self, ambassador):
        result = await ambassador._tool_record_growth_experiment({
            "hypothesis": "Email sequence improves onboarding",
            "channel": "email", "winner": "A", "uplift_pct": 15.3,
        })
        assert "experiment_id" in result

    @pytest.mark.asyncio
    async def test_submit_to_directory(self, ambassador):
        result = await ambassador._tool_submit_to_directory({
            "directory": "glama", "listing_type": "mcp_server",
            "description": "TiOLi AGENTIS MCP server for AI agent exchange",
        })
        assert result["status"] == "SUBMITTED"

    @pytest.mark.asyncio
    async def test_submit_to_directory_mcp_so(self, ambassador):
        result = await ambassador._tool_submit_to_directory({
            "directory": "mcp_so", "listing_type": "platform",
            "description": "Governed AI agent exchange",
        })
        assert result["directory"] == "mcp_so"

    @pytest.mark.asyncio
    async def test_record_partnership(self, ambassador):
        result = await ambassador._tool_record_partnership({
            "partner_name": "Anthropic", "partner_type": "ai_company",
            "stage": "IDENTIFIED",
        })
        assert result["recorded"] is True

    @pytest.mark.asyncio
    async def test_record_partnership_engaged(self, ambassador):
        result = await ambassador._tool_record_partnership({
            "partner_name": "CrewAI", "partner_type": "framework",
            "stage": "ENGAGED", "value_prop": "Integration partnership",
        })
        assert result["stage"] == "ENGAGED"

    @pytest.mark.asyncio
    async def test_network_effect_metrics(self, ambassador):
        result = await ambassador._tool_get_network_effect_metrics({})
        assert "active_agents" in result
        assert "metcalfe_connections" in result

    @pytest.mark.asyncio
    async def test_network_effect_weekly(self, ambassador):
        result = await ambassador._tool_get_network_effect_metrics({"period": "weekly"})
        assert result["period"] == "weekly"

    @pytest.mark.asyncio
    async def test_update_market_expansion(self, ambassador):
        result = await ambassador._tool_update_market_expansion({
            "market": "KE", "status": "RESEARCH",
        })
        assert result["updated"] is True

    @pytest.mark.asyncio
    async def test_update_market_expansion_legal(self, ambassador):
        result = await ambassador._tool_update_market_expansion({
            "market": "GB", "status": "LEGAL_REVIEW", "legal_clearance": False,
        })
        assert result["market"] == "GB"

    @pytest.mark.asyncio
    async def test_trigger_onboarding(self, ambassador):
        result = await ambassador._tool_trigger_onboarding_sequence({
            "operator_id": "op-new-1",
        })
        assert result["status"] == "ONBOARDING_STARTED"
        assert "steps" in result

    @pytest.mark.asyncio
    async def test_tools_count(self, ambassador):
        tools = await ambassador.get_tools()
        assert len(tools) >= 7

    @pytest.mark.asyncio
    async def test_heartbeat(self, ambassador):
        await ambassador.heartbeat()
