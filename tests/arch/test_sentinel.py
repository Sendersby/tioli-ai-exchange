"""Sentinel test suite — 15 tests."""

import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.arch.agents.sentinel import SentinelAgent
from tests.arch.conftest import make_state


@pytest.fixture
def sentinel(mock_db_with_agents, mock_redis, mock_claude):
    os.environ["ARCH_VAULT_ENCRYPTION_KEY"] = "test_key_32_bytes_exactly______!"
    return SentinelAgent(agent_id="sentinel", db=mock_db_with_agents, redis=mock_redis, client=mock_claude)


class TestSentinel:

    @pytest.mark.asyncio
    async def test_declare_incident_p1(self, sentinel):
        result = await sentinel._tool_declare_incident(
            {"severity": "P1", "title": "Test breach", "description": "Test"}
        )
        assert result["severity"] == "P1"
        assert result["status"] == "DECLARED"

    @pytest.mark.asyncio
    async def test_declare_incident_p2(self, sentinel):
        result = await sentinel._tool_declare_incident(
            {"severity": "P2", "title": "Degradation", "description": "Slow"}
        )
        assert result["severity"] == "P2"

    @pytest.mark.asyncio
    async def test_declare_incident_p3(self, sentinel):
        result = await sentinel._tool_declare_incident(
            {"severity": "P3", "title": "Minor", "description": "Backup fail"}
        )
        assert result["severity"] == "P3"

    @pytest.mark.asyncio
    async def test_freeze_account(self, sentinel):
        result = await sentinel._tool_freeze_account(
            {"account_id": "test-123", "account_type": "agent", "reason": "Security"}
        )
        assert result["frozen"] is True

    @pytest.mark.asyncio
    async def test_platform_health_check(self, sentinel):
        result = await sentinel._tool_check_platform_health({})
        assert "database" in result
        assert "redis" in result
        assert "overall" in result

    @pytest.mark.asyncio
    async def test_kill_switch_without_key_blocked(self, sentinel):
        result = await sentinel._tool_activate_kill_switch(
            {"reason": "Test", "kill_switch_confirmation": "wrong"}
        )
        assert result["activated"] is False

    @pytest.mark.asyncio
    async def test_kill_switch_with_valid_key(self, sentinel, monkeypatch):
        monkeypatch.setenv("ARCH_KILL_SWITCH_KEY", "test_key")
        result = await sentinel._tool_activate_kill_switch(
            {"reason": "Test emergency", "kill_switch_confirmation": "test_key"}
        )
        assert result["activated"] is True

    @pytest.mark.asyncio
    async def test_security_posture(self, sentinel):
        result = await sentinel._tool_check_security_posture({})
        assert "posture" in result
        assert "security_events_24h" in result

    @pytest.mark.asyncio
    async def test_key_rotation_all_overdue(self, sentinel):
        result = await sentinel._tool_trigger_key_rotation({"platform": "all_overdue"})
        assert "overdue_count" in result

    @pytest.mark.asyncio
    async def test_key_rotation_specific_platform(self, sentinel):
        result = await sentinel._tool_trigger_key_rotation({"platform": "github"})
        assert result["status"] == "FLAGGED_FOR_ROTATION"

    @pytest.mark.asyncio
    async def test_verify_backup(self, sentinel):
        result = await sentinel._tool_verify_backup({"backup_type": "database"})
        assert result["verified"] is True

    @pytest.mark.asyncio
    async def test_heartbeat(self, sentinel):
        await sentinel.heartbeat()
        sentinel.db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_credential_rotation_check(self, sentinel):
        await sentinel.check_credential_rotation()

    @pytest.mark.asyncio
    async def test_circuit_breaker_check(self, sentinel):
        await sentinel.check_circuit_breakers()

    @pytest.mark.asyncio
    async def test_succession_contacts(self, sentinel, monkeypatch):
        monkeypatch.setenv("ARCH_DEPUTY1_NAME", "Test Deputy")
        result = await sentinel.check_succession_contacts()
        assert "deputies" in result
