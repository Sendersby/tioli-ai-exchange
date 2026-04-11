"""Auditor test suite — 15 tests."""

import pytest
from app.arch.agents.auditor import AuditorAgent
from tests.arch.conftest import make_state


@pytest.fixture
def auditor(mock_db_with_agents, mock_redis, mock_claude):
    return AuditorAgent(agent_id="auditor", db=mock_db_with_agents, redis=mock_redis, client=mock_claude)


class TestAuditor:

    @pytest.mark.asyncio
    async def test_kyc_screening_tier1(self, auditor):
        result = await auditor._tool_screen_kyc(
            {"entity_id": "op-1", "entity_type": "operator", "kyc_tier": 1}
        )
        assert result["status"] == "CLEARED"

    @pytest.mark.asyncio
    async def test_kyc_screening_tier4(self, auditor):
        result = await auditor._tool_screen_kyc(
            {"entity_id": "op-2", "entity_type": "operator", "kyc_tier": 4}
        )
        assert result["kyc_tier"] == 4

    @pytest.mark.asyncio
    async def test_kyc_screening_agent(self, auditor):
        result = await auditor._tool_screen_kyc(
            {"entity_id": "ag-1", "entity_type": "agent", "kyc_tier": 1}
        )
        assert result["entity_id"] == "ag-1"

    @pytest.mark.asyncio
    async def test_aml_below_threshold(self, auditor):
        result = await auditor._tool_check_aml(
            {"transaction_id": "tx-1", "amount_zar": 10000, "transaction_type": "commission"}
        )
        assert result["is_reportable"] is False
        assert result["str_required"] is False

    @pytest.mark.asyncio
    async def test_aml_above_threshold(self, auditor):
        result = await auditor._tool_check_aml(
            {"transaction_id": "tx-2", "amount_zar": 30000, "transaction_type": "commission"}
        )
        assert result["is_reportable"] is True
        assert result["str_required"] is True

    @pytest.mark.asyncio
    async def test_aml_cross_border_increases_risk(self, auditor):
        result = await auditor._tool_check_aml(
            {"transaction_id": "tx-3", "amount_zar": 5000,
             "transaction_type": "cross_border", "is_cross_border": True}
        )
        assert result["risk_score"] > 0.3

    @pytest.mark.asyncio
    async def test_str_filing(self, auditor):
        result = await auditor._tool_file_str_if_required(
            {"transaction_id": "tx-4", "reason": "Suspicious pattern detected on large volume transactions over multiple accounts"}
        )
        assert result["status"] == "FILED_PENDING_FIC"
        assert result["statutory_deadline_days"] == 15

    @pytest.mark.asyncio
    async def test_sarb_within_limit(self, auditor):
        result = await auditor._tool_check_sarb_compliance(
            {"operator_id": "op-1", "amount_zar": 50000, "destination": "GB",
             "transfer_type": "fiat_transfer"}
        )
        assert result["within_limit"] is True
        assert result["action"] == "PROCEED"

    @pytest.mark.asyncio
    async def test_regulatory_obligations(self, auditor):
        result = await auditor._tool_get_regulatory_obligations({"jurisdiction": "ZA"})
        assert "obligations" in result
        assert result["jurisdiction"] == "ZA"

    @pytest.mark.asyncio
    async def test_legal_document_draft(self, auditor):
        result = await auditor._tool_draft_legal_document(
            {"document_type": "operator_agreement"}
        )
        assert result["status"] == "DRAFTED"

    @pytest.mark.asyncio
    async def test_compliance_flag(self, auditor):
        result = await auditor._tool_check_compliance_flag(
            {"entity_id": "op-1", "entity_type": "operator", "severity": "HIGH"}
        )
        assert result["flagged"] is True

    @pytest.mark.asyncio
    async def test_defer_on_regulatory(self, auditor):
        state = make_state(instruction="File regulatory return for new jurisdiction")
        result = await auditor(state)
        assert result["defer_to_owner"] is True

    @pytest.mark.asyncio
    async def test_tools_count(self, auditor):
        tools = await auditor.get_tools()
        assert len(tools) >= 7

    @pytest.mark.asyncio
    async def test_heartbeat(self, auditor):
        await auditor.heartbeat()

    @pytest.mark.asyncio
    async def test_system_prompt_key(self, auditor):
        assert auditor.system_prompt_key == "system_prompt"
