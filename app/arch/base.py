"""ArchAgentBase — v5.0 complete implementation.

Every Arch Agent inherits from this class. Enforces consistent behaviour:
memory loading, audit logging with hash chain, cost tracking,
DEFER_TO_OWNER signalling, LLM semaphore, and error handling.

Incorporates: PI-04 (LLM semaphore), PI-08 (AsyncOpenAI init),
PI-11 (_load_system_prompt), C-01 (reserve locking for Treasurer subclass).
"""

import asyncio
import hashlib
import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import redis.asyncio as aioredis
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.arch.retry import ArchCircuitBreakerTrippedError

log = logging.getLogger("arch.base")

# Module-level semaphore — prevents exceeding Anthropic API concurrent request limits
ARCH_LLM_SEMAPHORE = asyncio.Semaphore(
    int(os.getenv("ARCH_MAX_CONCURRENT_LLM_CALLS", "3"))
)

# Default system prompts — populated from Part XIII on import
DEFAULT_SYSTEM_PROMPTS: dict[str, str] = {}


class ArchAgentBase(ABC):
    """Abstract base class for all 7 Arch Agents."""

    DEFER_TOPICS = [
        "cost", "revenue_model", "regulatory", "strategic_ambiguity",
        "succession", "constitutional_amendment", "new_jurisdiction",
    ]

    def __init__(
        self,
        agent_id: str,
        db: AsyncSession,
        redis: aioredis.Redis,
        client: AsyncAnthropic,
    ):
        self.agent_id = agent_id
        self.db = db
        self.redis = redis
        self.client = client
        self.model = os.getenv(
            f"ARCH_{agent_id.upper()}_MODEL",
            os.getenv("ARCH_FALLBACK_MODEL", "claude-sonnet-4-6"),
        )
        self.max_tokens = int(os.getenv("ARCH_MAX_TOKENS_PER_CALL", "8192"))
        # AsyncOpenAI instantiated inside __init__ — not module level (PI-08)
        self.oai_client = None  # Lazy init — created on first memory call
        self.vault = None  # Initialized lazily when ARCH_VAULT_ENCRYPTION_KEY is set
        self._prompt_cache: tuple[str, datetime] | None = None
        self._prompt_cache_ttl = 300  # 5 minutes

    @property
    @abstractmethod
    def system_prompt_key(self) -> str:
        """Return this agent's config key — typically 'system_prompt'."""

    @abstractmethod
    async def get_tools(self) -> list:
        """Return Anthropic tool definitions list for this agent."""

    # ── Memory helpers ─────────────────────────────────────────

    async def remember(
        self, content: str, metadata: dict = None, source_type: str = "interaction"
    ):
        from app.arch.memory import ArchMemory
        mem = ArchMemory(
            agent_id=self.agent_id, db=self.db, oai_client=self.oai_client
        )
        await mem.store(content, metadata, source_type)

    def _get_oai_client(self):
        if self.oai_client is None:
            from openai import AsyncOpenAI
            self.oai_client = AsyncOpenAI()
        return self.oai_client

    async def recall(self, query: str, k: int = 5) -> list[dict]:
        from app.arch.memory import ArchMemory
        mem = ArchMemory(
            agent_id=self.agent_id, db=self.db, oai_client=self._get_oai_client()
        )
        return await mem.retrieve(query, k)

    # ── System prompt loading (PI-11) ──────────────────────────

    async def _load_system_prompt(self) -> str:
        now = datetime.now(timezone.utc)
        if self._prompt_cache:
            cached_prompt, cached_at = self._prompt_cache
            age = (now - cached_at).total_seconds()
            if age < self._prompt_cache_ttl:
                return cached_prompt

        result = await self.db.execute(
            text("""
                SELECT config_value FROM arch_agent_configs
                WHERE agent_id = (
                    SELECT id FROM arch_agents WHERE agent_name = :agent_id
                )
                  AND config_key = 'system_prompt'
                ORDER BY version DESC LIMIT 1
            """),
            {"agent_id": self.agent_id},
        )
        row = result.fetchone()

        if row:
            prompt = row.config_value
        else:
            log.warning(
                f"[{self.agent_id}] No system prompt in arch_agent_configs. "
                f"Using hardcoded default."
            )
            prompt = DEFAULT_SYSTEM_PROMPTS.get(self.agent_id, "")
            if not prompt:
                # Load from prompts directory as fallback
                prompt_path = os.path.join(
                    os.path.dirname(__file__), "prompts", f"{self.agent_id}.txt"
                )
                if os.path.exists(prompt_path):
                    with open(prompt_path) as f:
                        prompt = f.read()
                else:
                    raise RuntimeError(
                        f"[{self.agent_id}] No system prompt available. "
                        f"Cannot operate without identity and Prime Directives."
                    )

        self._prompt_cache = (prompt, now)
        return prompt

    # ── Main callable — called by LangGraph ────────────────────

    async def __call__(self, state: dict) -> dict:
        await self._check_token_budget()

        # DEFER_TO_OWNER check — before any LLM call
        if self._should_defer(state):
            defer_reason = self._defer_reason(state)
            log.info(f"[{self.agent_id}] DEFER_TO_OWNER: {defer_reason}")
            await self._log_capability_gap(state, defer_reason)
            return {**state, "defer_to_owner": True, "defer_reason": defer_reason}

        memories = await self.recall(state["instruction"])
        prompt = await self._load_system_prompt()
        tools = await self.get_tools()

        try:
            async with ARCH_LLM_SEMAPHORE:
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=prompt,
                    messages=[
                        *[{"role": "user", "content": m["content"]}
                          for m in memories[-3:]],
                        {"role": "user", "content": state["instruction"]},
                    ],
                    tools=tools if tools else [],
                )
        except Exception as e:
            await self._log_action(state, "FAILURE", str(e))
            log.error(f"[{self.agent_id}] LLM call failed: {e}", exc_info=True)
            return {**state, "error": str(e)}

        output = next(
            (b.text for b in response.content if b.type == "text"), ""
        )
        tool_calls = [b for b in response.content if b.type == "tool_use"]

        # Execute any tool calls returned
        tool_results = []
        for tc in tool_calls:
            result = await self._execute_tool(tc.name, tc.input)
            tool_results.append({"tool": tc.name, "result": result})

        # Store interaction in memory (outbox pattern)
        await self.remember(
            f"Instruction: {state['instruction'][:300]} | Output: {output[:300]}",
            metadata={"instruction_type": state.get("instruction_type")},
            source_type="interaction",
        )

        await self._log_action(state, "SUCCESS", output[:500])
        await self._track_tokens(response.usage)

        return {
            **state,
            "output": output,
            "tool_results": tool_results,
            "memory_retrieved": memories,
            "action_taken": (
                f"[{self.agent_id}] {output[:200]}" if output
                else f"[{self.agent_id}] Tool calls: {[r['tool'] for r in tool_results]}"
            ),
        }

    # ── Tool dispatch ──────────────────────────────────────────

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> dict:
        """Dispatch tool call to concrete method. Subclasses implement handlers."""
        handler = getattr(self, f"_tool_{tool_name}", None)
        if not handler:
            log.warning(f"[{self.agent_id}] No handler for tool {tool_name}")
            return {"error": f"Tool {tool_name} not implemented"}
        try:
            return await handler(tool_input)
        except Exception as e:
            log.error(f"[{self.agent_id}] Tool {tool_name} error: {e}")
            return {"error": str(e)}

    async def call_tool(self, tool_name: str, params: dict) -> dict:
        """Public interface for cascade calls from other agents."""
        return await self._execute_tool(tool_name, params)

    # ── Message handling ───────────────────────────────────────

    async def handle_urgent_message(self, data: dict):
        """Called when a Redis pub/sub urgent message is received."""
        state = {
            "session_id": uuid.uuid4().hex,
            "originating_agent": data.get("from_agent"),
            "instruction": (
                f"URGENT MESSAGE from {data.get('from_agent')}: "
                f"{data.get('subject')}. {json.dumps(data.get('body', {}))}"
            ),
            "instruction_type": "governance",
            "context": data,
            "memory_retrieved": [],
            "tool_results": [],
            "inter_agent_messages": [data],
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
        await self(state)

    async def handle_board_message(self, data: dict):
        """Called on board broadcast."""
        await self.handle_urgent_message(data)

    # ── Heartbeat ──────────────────────────────────────────────

    async def heartbeat(self):
        """Scheduled every 60 seconds — updates last_heartbeat."""
        await self.db.execute(
            text("""
                UPDATE arch_agents SET last_heartbeat = now()
                WHERE agent_name = :agent_id
            """),
            {"agent_id": self.agent_id},
        )
        await self.db.commit()

    # ── Token budget management ────────────────────────────────

    async def _check_token_budget(self):
        budget = int(os.getenv(
            f"ARCH_MONTHLY_TOKEN_BUDGET_{self.agent_id.upper()}", "3000000"
        ))
        alert_pct = int(os.getenv("ARCH_TOKEN_ALERT_THRESHOLD_PCT", "80")) / 100
        hard_pct = int(os.getenv("ARCH_TOKEN_HARD_LIMIT_PCT", "95")) / 100

        result = await self.db.execute(
            text("""
                SELECT tokens_used_this_month, circuit_breaker_tripped
                FROM arch_agents WHERE agent_name = :agent_id
            """),
            {"agent_id": self.agent_id},
        )
        row = result.fetchone()
        if not row:
            return

        used = row.tokens_used_this_month
        if used >= budget * hard_pct:
            self.model = os.getenv("ARCH_FALLBACK_MODEL", "claude-haiku-4-5-20251001")
            log.warning(
                f"[{self.agent_id}] Token hard limit reached ({used}/{budget}). "
                f"Using fallback model."
            )
        elif used >= budget * alert_pct:
            log.warning(
                f"[{self.agent_id}] Token alert threshold: {used}/{budget}"
            )
            from app.arch.events import emit_platform_event
            await emit_platform_event(
                "token.budget_alert",
                {"agent_id": self.agent_id, "used": used, "budget": budget},
                source_module="arch_base",
                db=self.db,
            )

        if row.circuit_breaker_tripped:
            raise ArchCircuitBreakerTrippedError(
                f"[{self.agent_id}] Circuit breaker is tripped. "
                f"Agent paused until Architect resolves performance issues."
            )

    async def _track_tokens(self, usage):
        await self.db.execute(
            text("""
                UPDATE arch_agents
                SET tokens_used_this_month = tokens_used_this_month + :total
                WHERE agent_name = :agent_id
            """),
            {
                "total": usage.input_tokens + usage.output_tokens,
                "agent_id": self.agent_id,
            },
        )
        await self.db.commit()

    # ── Audit logging with hash chain ──────────────────────────

    async def _log_action(self, state: dict, result: str, detail: str):
        prev_hash = await self._get_last_audit_hash()
        entry_data = json.dumps(
            {
                "agent": self.agent_id,
                "action": state.get("instruction_type"),
                "result": result,
                "detail": detail[:500],
                "ts": datetime.now(timezone.utc).isoformat(),
            },
            sort_keys=True,
        )
        entry_hash = hashlib.sha256(
            (prev_hash + entry_data).encode()
        ).hexdigest()

        agent_row = await self.db.execute(
            text("SELECT id FROM arch_agents WHERE agent_name = :n"),
            {"n": self.agent_id},
        )
        agent_uuid = agent_row.scalar()

        prev_seq_result = await self.db.execute(
            text("SELECT seq FROM arch_audit_log ORDER BY seq DESC LIMIT 1")
        )
        prev_seq_val = prev_seq_result.scalar()

        await self.db.execute(
            text("""
                INSERT INTO arch_audit_log
                    (agent_id, action_type, action_detail, result,
                     entry_hash, prev_seq)
                VALUES (:agent_id, :action_type, :detail, cast(:result as arch_action_result),
                        :entry_hash, :prev_seq)
            """),
            {
                "agent_id": agent_uuid,
                "action_type": state.get("instruction_type", "unknown"),
                "detail": json.dumps({"summary": detail[:500]}),
                "result": result,
                "entry_hash": entry_hash,
                "prev_seq": prev_seq_val,
            },
        )
        await self.db.commit()

    async def _get_last_audit_hash(self) -> str:
        result = await self.db.execute(
            text("SELECT entry_hash FROM arch_audit_log ORDER BY seq DESC LIMIT 1")
        )
        row = result.fetchone()
        return row.entry_hash if row else ""

    # ── DEFER_TO_OWNER ─────────────────────────────────────────

    def _should_defer(self, state: dict) -> bool:
        instr = state.get("instruction", "").lower()
        return any(topic in instr for topic in self.DEFER_TOPICS)

    def _defer_reason(self, state: dict) -> str:
        instr = state.get("instruction", "").lower()
        matched = [t for t in self.DEFER_TOPICS if t in instr]
        return f"Instruction matches DEFER_TO_OWNER topics: {', '.join(matched)}"

    async def _log_capability_gap(self, state: dict, reason: str):
        event_type = (
            state.get("context", {}).get("event", {}).get("event_type", "unknown")
        )
        await self.db.execute(
            text("""
                INSERT INTO arch_capability_gaps
                    (agent_id, event_type, gap_description)
                VALUES (:agent_id, :event_type, :desc)
                ON CONFLICT (agent_id, event_type)
                DO UPDATE SET
                    occurrence_count = arch_capability_gaps.occurrence_count + 1
            """),
            {"agent_id": self.agent_id, "event_type": event_type, "desc": reason},
        )
        await self.db.commit()
