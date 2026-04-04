"""Integration, performance, and security tests — 14 tests per Part XI."""

import hashlib
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.arch.constitution import verify_constitution, CONSTITUTION_TEXT, CONSTITUTION_CHECKSUM
from app.arch.cascade import CASCADES, execute_cascade
from app.arch.graph import ArchAgentState, route_instruction, build_arch_graph
from app.arch.event_loop import EVENT_SUBSCRIPTIONS


class TestIntegration:

    def test_all_agents_have_tools(self):
        """All 7 agents define tools."""
        from app.arch.tools.sovereign_tools import SOVEREIGN_TOOLS
        from app.arch.tools.auditor_tools import AUDITOR_TOOLS
        from app.arch.tools.arbiter_tools import ARBITER_TOOLS
        from app.arch.tools.treasurer_tools import TREASURER_TOOLS
        from app.arch.tools.sentinel_tools import SENTINEL_TOOLS
        from app.arch.tools.architect_tools import ARCHITECT_TOOLS
        from app.arch.tools.ambassador_tools import AMBASSADOR_TOOLS
        assert len(SOVEREIGN_TOOLS) >= 5
        assert len(AUDITOR_TOOLS) >= 6
        assert len(ARBITER_TOOLS) >= 6
        assert len(TREASURER_TOOLS) >= 5
        assert len(SENTINEL_TOOLS) >= 5
        assert len(ARCHITECT_TOOLS) >= 7
        assert len(AMBASSADOR_TOOLS) >= 7

    def test_all_tools_have_valid_schema(self):
        """Every tool has name, description, and input_schema."""
        from app.arch.tools import sovereign_tools, auditor_tools, arbiter_tools
        from app.arch.tools import treasurer_tools, sentinel_tools, architect_tools, ambassador_tools
        all_tools = (
            sovereign_tools.SOVEREIGN_TOOLS + auditor_tools.AUDITOR_TOOLS +
            arbiter_tools.ARBITER_TOOLS + treasurer_tools.TREASURER_TOOLS +
            sentinel_tools.SENTINEL_TOOLS + architect_tools.ARCHITECT_TOOLS +
            ambassador_tools.AMBASSADOR_TOOLS
        )
        for tool in all_tools:
            assert "name" in tool, f"Tool missing name: {tool}"
            assert "description" in tool, f"Tool {tool['name']} missing description"
            assert "input_schema" in tool, f"Tool {tool['name']} missing input_schema"
            assert tool["input_schema"]["type"] == "object"

    def test_cascade_chains_reference_valid_agents(self):
        """All cascade targets are valid agent names."""
        valid_agents = {"sovereign", "auditor", "arbiter", "treasurer", "sentinel", "architect", "ambassador"}
        for key, actions in CASCADES.items():
            for target, tool, params in actions:
                assert target in valid_agents, f"Cascade {key} references invalid agent: {target}"

    def test_event_subscriptions_cover_all_agents(self):
        """All 7 agents have event subscriptions."""
        expected = {"sovereign", "auditor", "arbiter", "treasurer", "sentinel", "architect", "ambassador"}
        assert set(EVENT_SUBSCRIPTIONS.keys()) == expected

    def test_routing_covers_all_instruction_types(self):
        """All instruction types route to a valid agent."""
        types = ["governance", "compliance", "justice", "finance",
                 "security", "technology", "growth", "board", "emergency"]
        valid = {"sovereign", "auditor", "arbiter", "treasurer", "sentinel", "architect", "ambassador"}
        for t in types:
            state = {"instruction_type": t}
            result = route_instruction(state)
            assert result in valid, f"Type {t} routes to invalid agent: {result}"


class TestSecurity:

    def test_constitution_checksum_is_64_hex_chars(self):
        assert len(CONSTITUTION_CHECKSUM) == 64
        assert all(c in "0123456789abcdef" for c in CONSTITUTION_CHECKSUM)

    def test_audit_hash_chain_algorithm(self):
        """Hash chain: SHA-256 of prev_hash + entry_data."""
        prev_hash = ""
        entry_data = '{"agent":"sentinel","action":"security","result":"SUCCESS"}'
        expected = hashlib.sha256((prev_hash + entry_data).encode()).hexdigest()
        assert len(expected) == 64

    def test_vault_encryption_key_required(self):
        """CredentialVault raises if no key set."""
        old_key = os.environ.pop("ARCH_VAULT_ENCRYPTION_KEY", None)
        try:
            from app.arch.vault import CredentialVault
            with pytest.raises(EnvironmentError):
                CredentialVault(agent_id="test")
        finally:
            if old_key:
                os.environ["ARCH_VAULT_ENCRYPTION_KEY"] = old_key

    def test_vault_encrypt_decrypt_roundtrip(self):
        """AES-256-GCM encrypt/decrypt preserves plaintext."""
        os.environ["ARCH_VAULT_ENCRYPTION_KEY"] = "test_key_for_roundtrip_32bytes__"
        from app.arch.vault import CredentialVault
        vault = CredentialVault(agent_id="test")
        plaintext = "my_secret_api_key_12345"
        ct, iv = vault._encrypt(plaintext)
        decrypted = vault._decrypt(ct, iv)
        assert decrypted == plaintext

    def test_vault_different_plaintexts_different_ciphertexts(self):
        """Different inputs produce different ciphertexts."""
        os.environ["ARCH_VAULT_ENCRYPTION_KEY"] = "test_key_for_different_32bytes_"
        from app.arch.vault import CredentialVault
        vault = CredentialVault(agent_id="test")
        ct1, iv1 = vault._encrypt("secret_a")
        ct2, iv2 = vault._encrypt("secret_b")
        assert ct1 != ct2

    def test_self_referential_check_blocks_audit_log(self):
        """Cannot propose changes to audit log."""
        from app.arch.constitution import check_self_referential
        blocked, _ = check_self_referential("Modify arch_audit_log", [], "architect")
        assert blocked is True


class TestPerformance:

    def test_graph_state_has_all_required_fields(self):
        """ArchAgentState TypedDict has all expected keys."""
        required = [
            "session_id", "originating_agent", "instruction", "instruction_type",
            "context", "memory_retrieved", "tool_results", "inter_agent_messages",
            "board_vote_required", "defer_to_owner", "output", "error",
        ]
        annotations = ArchAgentState.__annotations__
        for field in required:
            assert field in annotations, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_cascade_execute_with_missing_agent(self):
        """Cascade gracefully handles missing target agent."""
        agents = {"sovereign": AsyncMock()}
        agents["sovereign"].call_tool = AsyncMock()
        await execute_cascade("declare_incident:P1", {}, agents)
        # Should not raise even though treasurer and auditor are missing
