"""Arch Agent test fixtures — shared across all test suites."""

import os
import json
import uuid
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

# Force test env vars before any imports
os.environ.setdefault("ARCH_AGENTS_ENABLED", "false")
os.environ.setdefault("ARCH_VAULT_ENCRYPTION_KEY", "ci_test_key_32_bytes_exactly___!!")
os.environ.setdefault("ARCH_INTER_AGENT_HMAC_SECRET", "ci_hmac_secret_32_bytes_exactly!")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-for-ci")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_arch.db")


@pytest.fixture
def mock_claude():
    """Mock Anthropic client returning predictable text responses."""
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(return_value=MagicMock(
        content=[MagicMock(type="text", text="Test response from mock Claude")],
        usage=MagicMock(input_tokens=100, output_tokens=50),
    ))
    return client


@pytest.fixture
def mock_claude_tool_call():
    """Factory: mock that returns a specific tool call."""
    def _make(tool_name: str, tool_input: dict):
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.create = AsyncMock(return_value=MagicMock(
            content=[MagicMock(type="tool_use", name=tool_name, input=tool_input)],
            usage=MagicMock(input_tokens=150, output_tokens=80),
        ))
        return client
    return _make


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = AsyncMock()
    redis.ping = AsyncMock(return_value=True)
    redis.publish = AsyncMock(return_value=1)
    redis.pubsub = MagicMock(return_value=AsyncMock(
        subscribe=AsyncMock(),
        unsubscribe=AsyncMock(),
        listen=AsyncMock(return_value=iter([])),
    ))
    return redis


@pytest.fixture
def mock_db():
    """Mock async database session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def mock_db_with_agents(mock_db):
    """Mock DB that returns agent data for common queries."""
    agent_uuid = str(uuid.uuid4())

    def execute_side_effect(query, params=None):
        query_str = str(query) if hasattr(query, 'text') else str(query)
        result = MagicMock()

        if "SELECT id FROM arch_agents WHERE agent_name" in query_str:
            result.scalar = MagicMock(return_value=agent_uuid)
        elif "SELECT agent_name, id FROM arch_agents WHERE status" in query_str:
            rows = [
                MagicMock(agent_name=n, id=str(uuid.uuid4()))
                for n in ["sovereign", "auditor", "arbiter", "treasurer",
                          "sentinel", "architect", "ambassador"]
            ]
            result.fetchall = MagicMock(return_value=rows)
        elif "SELECT entry_hash FROM arch_audit_log" in query_str:
            result.fetchone = MagicMock(return_value=None)
        elif "SELECT seq FROM arch_audit_log" in query_str:
            result.scalar = MagicMock(return_value=None)
        elif "SELECT tokens_used_this_month" in query_str:
            result.fetchone = MagicMock(return_value=MagicMock(
                tokens_used_this_month=100, circuit_breaker_tripped=False,
            ))
        elif "SELECT config_value FROM arch_agent_configs" in query_str:
            result.fetchone = MagicMock(return_value=None)
        elif "RETURNING id::text" in query_str:
            result.scalar = MagicMock(return_value=str(uuid.uuid4()))
        elif "SELECT COUNT" in query_str:
            result.scalar = MagicMock(return_value=0)
        elif "COALESCE(SUM" in query_str:
            result.scalar = MagicMock(return_value=0)
        else:
            result.scalar = MagicMock(return_value=None)
            result.fetchone = MagicMock(return_value=None)
            result.fetchall = MagicMock(return_value=[])

        return result

    mock_db.execute = AsyncMock(side_effect=execute_side_effect)
    return mock_db


def make_state(instruction="Test instruction", instruction_type="governance", **overrides):
    """Helper: build a minimal ArchAgentState dict."""
    state = {
        "session_id": uuid.uuid4().hex,
        "originating_agent": "test",
        "instruction": instruction,
        "instruction_type": instruction_type,
        "context": {},
        "memory_retrieved": [],
        "tool_results": [],
        "inter_agent_messages": [],
        "board_vote_required": False,
        "board_vote_status": None,
        "founder_approval_required": False,
        "founder_approval_status": None,
        "financial_gate_cleared": True,
        "tier": None,
        "escalation_chain": [],
        "defer_to_owner": False,
        "defer_reason": None,
        "output": None,
        "error": None,
        "action_taken": None,
    }
    state.update(overrides)
    return state
