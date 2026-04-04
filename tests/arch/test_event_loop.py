"""Event loop test suite — 15 tests per Part XI Section 11.4."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.arch.event_loop import ArchEventLoop, EVENT_SUBSCRIPTIONS


class TestEventSubscriptions:

    def test_all_seven_agents_have_subscriptions(self):
        agents = ["sovereign", "auditor", "arbiter", "treasurer", "sentinel", "architect", "ambassador"]
        for agent in agents:
            assert agent in EVENT_SUBSCRIPTIONS
            assert len(EVENT_SUBSCRIPTIONS[agent]) > 0

    def test_sentinel_subscribes_to_security(self):
        assert "security." in EVENT_SUBSCRIPTIONS["sentinel"]

    def test_treasurer_subscribes_to_transactions(self):
        assert "transaction.completed" in EVENT_SUBSCRIPTIONS["treasurer"]

    def test_ambassador_subscribes_to_registrations(self):
        assert "agent.registered" in EVENT_SUBSCRIPTIONS["ambassador"]

    def test_auditor_subscribes_to_compliance(self):
        assert "compliance." in EVENT_SUBSCRIPTIONS["auditor"]

    def test_arbiter_subscribes_to_disputes(self):
        assert "dispute." in EVENT_SUBSCRIPTIONS["arbiter"]


class TestEventLoopCore:

    def _make_loop(self, agent_id="sentinel"):
        agent = AsyncMock()
        agent.return_value = {"output": "handled", "defer_to_owner": False, "action_taken": "test"}
        db_factory = AsyncMock()
        mock_db = AsyncMock()
        db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        db_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        redis = AsyncMock()
        return ArchEventLoop(agent=agent, agent_id=agent_id, db_factory=db_factory, redis=redis)

    def test_is_subscribed_match(self):
        loop = self._make_loop("sentinel")
        assert loop._is_subscribed("security.auth_failure") is True

    def test_is_subscribed_no_match(self):
        loop = self._make_loop("sentinel")
        assert loop._is_subscribed("growth.experiment") is False

    def test_classify_security(self):
        loop = self._make_loop()
        assert loop._classify("security.auth_failure") == "security"

    def test_classify_finance(self):
        loop = self._make_loop()
        assert loop._classify("transaction.completed") == "finance"

    def test_classify_justice(self):
        loop = self._make_loop()
        assert loop._classify("dispute.opened") == "justice"

    def test_classify_growth(self):
        loop = self._make_loop()
        assert loop._classify("mcp.discovery_event") == "growth"

    def test_classify_unknown_defaults_governance(self):
        loop = self._make_loop()
        assert loop._classify("unknown.event") == "governance"

    def test_build_state_structure(self):
        loop = self._make_loop()
        event = {"event_type": "security.auth_failure", "data": {"ip": "1.2.3.4"}, "source": "auth"}
        state = loop._build_state(event)
        assert state["instruction_type"] == "security"
        assert state["defer_to_owner"] is False
        assert state["inter_agent_messages"] == []  # GEM-01
        assert "AUTONOMOUS EVENT" in state["instruction"]

    def test_build_prompt_contains_event_data(self):
        loop = self._make_loop()
        event = {"event_type": "transaction.completed", "data": {"amount": 1000}, "source": "exchange"}
        prompt = loop._build_prompt(event)
        assert "transaction.completed" in prompt
        assert "1000" in prompt
