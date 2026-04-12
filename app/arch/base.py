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
        # Autonomous executor — gives agents ability to DO, not just advise
        from app.arch.executor import ArchExecutor
        from app.database.db import async_session
        self.executor = ArchExecutor(agent_id=agent_id, db_factory=async_session)
        self._prompt_cache: tuple[str, datetime] | None = None
        self._prompt_cache_ttl = 300  # 5 minutes

    @property
    @abstractmethod
    def system_prompt_key(self) -> str:
        """Return this agent's config key — typically 'system_prompt'."""

    @abstractmethod
    async def get_tools(self) -> list:
        """Return Anthropic tool definitions list for this agent."""
        return []

    def get_common_tools(self) -> list:
        """Common tools for ALL agents — governance, memory, social verification."""
        tools = [
            {
                "name": "propose_self_improvement",
                "description": "Propose an improvement to yourself or other agents. Triggers a board vote. Constitutional Prime Directives cannot be modified.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Short title"},
                        "description": {"type": "string", "description": "What and why"},
                        "improvement_type": {"type": "string", "enum": ["prompt_modification", "tool_addition", "behavior_change", "capability_upgrade"]},
                        "affects_all": {"type": "boolean", "description": "If true, founder approval required"},
                        "code_diff": {"type": "string", "description": "The actual change"},
                        "target_agents": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "description", "improvement_type"],
                },
            },
            {
                "name": "vote_on_proposal",
                "description": "Vote YES/NO/ABSTAIN on a self-improvement proposal with reason.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "proposal_id": {"type": "string"},
                        "vote": {"type": "string", "enum": ["YES", "NO", "ABSTAIN"]},
                        "reason": {"type": "string"},
                    },
                    "required": ["proposal_id", "vote", "reason"],
                },
            },
            {
                "name": "list_improvement_proposals",
                "description": "List all self-improvement proposals and voting status.",
                "input_schema": {"type": "object", "properties": {}},
            },
        ]
        # Append memory tools (retain, recall, reflect)
        from app.arch.memory_tools import MEMORY_TOOLS
        tools += MEMORY_TOOLS
        # Append social verification tools (verify_tweet, verify_linkedin_post, get_recent_tweets)
        from app.arch.tools.social_verification import SOCIAL_VERIFICATION_TOOLS
        tools += SOCIAL_VERIFICATION_TOOLS
        from app.arch.tools.platform_query import PLATFORM_QUERY_TOOLS
        tools += PLATFORM_QUERY_TOOLS
        from app.arch.tools.founder_notification import FOUNDER_NOTIFICATION_TOOLS
        tools += FOUNDER_NOTIFICATION_TOOLS
        return tools

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
            # Create inbox item so founder sees this
            try:
                from sqlalchemy import text as _dt
                agent_row = await self.db.execute(_dt(
                    "SELECT id FROM arch_agents WHERE agent_name = :n"
                ), {"n": self.agent_id})
                agent_uuid = agent_row.scalar()
                await self.db.execute(_dt(
                    "INSERT INTO arch_founder_inbox "
                    "(item_type, priority, description, prepared_by, status, due_at) "
                    "VALUES ('DEFER_TO_OWNER', 'URGENT', :desc, :agent, 'PENDING', now() + interval '24 hours')"
                ), {
                    "desc": json.dumps({
                        "subject": f"{self.agent_id.title()} needs your decision",
                        "detail": f"I was asked to: {state.get('instruction', '')[:300]}. "
                                  f"I cannot proceed because: {defer_reason}. "
                                  f"Please review and provide direction.",
                        "agent": self.agent_id,
                        "original_instruction": state.get("instruction", "")[:500],
                    }),
                    "agent": agent_uuid,
                })
                await self.db.commit()
            except Exception as e:
                log.warning(f"[{self.agent_id}] Failed to create inbox item for DEFER: {e}")
            return {**state, "defer_to_owner": True, "defer_reason": defer_reason}

        memories = await self.recall(state["instruction"])

        # ARCH-009: Inject tiered memory (feature-flagged)
        import os as _tm_os
        if _tm_os.environ.get("ARCH_AGENT_TIERED_MEMORY", "false").lower() == "true":
            try:
                from app.arch.memory_tiers import load_from_db
                tiered = await load_from_db(self.db, self.agent_name)
                core_context = tiered.get_context_window()
                if core_context.get("core"):
                    core_text = "\n".join(f"[CORE] {k}: {v}" for k, v in core_context["core"].items())
                    memories = [{"content": core_text, "source": "core_identity"}] + memories
            except Exception as e:
                import logging; logging.getLogger("base").warning(f"Suppressed: {e}")
        prompt = await self._load_system_prompt()
        tools = await self.get_tools()

        try:
            async with ARCH_LLM_SEMAPHORE:
                # Structure system prompt for Anthropic prompt caching
                # Static parts (system prompt, tool schemas) get cached for 5 min
                # Saves ~90% on input tokens for repeated agent calls
                system_blocks = [
                    {
                        "type": "text",
                        "text": prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
                response = await self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=system_blocks,
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

        # Metacognition — reflect on the action taken
        if tool_results:
            try:
                from app.arch.metacognition import reflect_on_action
                for tr in tool_results[:1]:  # Reflect on primary tool call only
                    success = "error" not in str(tr.get("result", "")).lower()
                    await reflect_on_action(
                        self,
                        action_description=f"Tool: {tr['tool']}",
                        outcome=str(tr.get("result", ""))[:200],
                        success=success,
                    )
            except Exception as e:
                import logging; logging.getLogger("base").warning(f"Suppressed: {e}")  # Reflection is optional, never block main flow

        # ARCH-013: Enhanced reflection on significant actions (feature-flagged)
        import os as _ref_os
        if _ref_os.environ.get("ARCH_AGENT_REFLECTION", "false").lower() == "true":
            try:
                # Reflect on board decisions, escalations, and financial actions
                significant_tools = ["convene_board_session", "submit_financial_proposal",
                                    "issue_constitutional_ruling", "declare_incident",
                                    "submit_to_founder_inbox", "publish_content"]
                for tr in tool_results:
                    if tr.get("tool") in significant_tools:
                        reflection_prompt = f"You just executed {tr['tool']}. Result: {str(tr.get('result',''))[:200]}. What did you learn? What would you do differently next time? Be concise (2-3 sentences)."
                        try:
                            ref_response = await self.client.messages.create(
                                model="claude-haiku-4-5-20251001", max_tokens=100,
                                messages=[{"role": "user", "content": reflection_prompt}])
                            ref_text = next((bl.text for bl in ref_response.content if bl.type == "text"), "")
                            if ref_text:
                                await self.memory.store(
                                    f"[REFLECTION on {tr['tool']}] {ref_text}",
                                    source_type="strategic_reflection", importance=0.8)
                        except Exception as e:
                            import logging; logging.getLogger("base").warning(f"Suppressed: {e}")
            except Exception as e:
                import logging; logging.getLogger("base").warning(f"Suppressed: {e}")

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
            # Check executor tools
            executor_handlers = {
                "execute_command": lambda p: self.executor.run_command(p.get("command"), p.get("timeout", 60)),
                "write_file": lambda p: self.executor.write_file(p["path"], p["content"]),
                "read_file": lambda p: self.executor.read_file(p["path"]),
                "browse_website": lambda p: self.executor.browse_url(p["url"], p.get("screenshot", True)),
                "browse_with_ai": lambda p: _browse_ai_handler(p),
                "post_social_content": lambda p: self.executor.post_content(p["platform"], p["content"], p.get("title")),
                "generate_content": lambda p: self.executor.generate_content(p["prompt"], p.get("voice"), p.get("max_tokens", 1000)),
                "research_competitor": lambda p: self.executor.research_competitor(p["url"]),
                "execute_task_plan": lambda p: self.executor.execute_task_plan(p["tasks"]),
                "make_api_call": lambda p: self.executor.http_request(p["method"], p["url"], p.get("headers"), p.get("body")),
                "schedule_task": lambda p: self._schedule_task(p),
                "list_my_tasks": lambda p: self._list_my_tasks(p),
                "generate_image": lambda p: self._generate_image(p),
                "create_social_graphic": lambda p: self._create_social_graphic(p),
                "send_to_discord": lambda p: self._send_discord(p),
                "request_human_help": lambda p: self.request_human_help(p["title"], p["detail"], p.get("priority", "URGENT")),
                "create_subordinate_agent": lambda p: self._create_subordinate(p),
                "issue_subordinate_instruction": lambda p: self._issue_instruction(p),
                "verify_subordinate_capability": lambda p: self._verify_capability(p),
                "scope_subordinate_development": lambda p: self._scope_development(p),
                "get_my_team_status": lambda p: self._get_team_status(p),
            }
            # Check self-improvement governance tools
            if tool_name == "propose_self_improvement":
                return await self._tool_propose_improvement(tool_input)
            elif tool_name == "vote_on_proposal":
                return await self._tool_vote_on_proposal(tool_input)
            elif tool_name == "list_improvement_proposals":
                return await self._tool_list_proposals(tool_input)

            # Check structured memory tools (retain, recall, reflect)
            from app.arch.memory_tools import MEMORY_TOOL_HANDLERS
            if tool_name in MEMORY_TOOL_HANDLERS:
                return await MEMORY_TOOL_HANDLERS[tool_name](self, tool_input)

            # Architect-specific Tier 1 tools
            if tool_name == "run_test_suite":
                from app.arch.tools.architect_tools import run_test_suite
                return await run_test_suite(
                    test_path=tool_input.get("test_path", "tests/"),
                    verbose=tool_input.get("verbose", False),
                )
            elif tool_name == "get_endpoint_performance":
                from app.arch.tools.architect_tools import get_endpoint_performance
                return await get_endpoint_performance()
            elif tool_name == "check_database_health":
                from app.arch.tools.architect_tools import check_database_health
                return await check_database_health(self.db)

            # Social verification tools
            if tool_name == "verify_tweet":
                from app.arch.tools.social_verification import verify_tweet
                return await verify_tweet(tool_input.get("tweet_id", ""))
            elif tool_name == "verify_linkedin_post":
                from app.arch.tools.social_verification import verify_linkedin_post
                return await verify_linkedin_post(
                    post_urn=tool_input.get("post_urn", ""),
                    search_text=tool_input.get("search_text", "")
                )
            elif tool_name == "get_recent_tweets":
                from app.arch.tools.social_verification import get_recent_tweets
                return await get_recent_tweets(count=tool_input.get("count", 10))
            elif tool_name == "query_platform_data":
                from app.arch.tools.platform_query import query_platform_data
                return await query_platform_data(self.db, tool_input.get("sql", ""))
            elif tool_name == "send_founder_notification":
                from app.arch.tools.founder_notification import send_founder_notification
                return await send_founder_notification(
                    self.db, agent_name=self.agent_id,
                    priority=tool_input.get("priority", "info"),
                    subject=tool_input.get("subject", ""),
                    body=tool_input.get("body", ""),
                    action_required=tool_input.get("action_required", False),
                )

            # ── Ambassador Tier 1 tools ──
            elif tool_name == "get_content_analytics":
                from app.arch.tools.ambassador_tools import get_content_analytics
                return await get_content_analytics(self.db)
            elif tool_name == "schedule_content":
                from app.arch.tools.ambassador_tools import schedule_content
                return await schedule_content(
                    self.db,
                    platform=tool_input.get("platform", ""),
                    content=tool_input.get("content", ""),
                    scheduled_for=tool_input.get("scheduled_for", ""),
                )


            # ── Treasurer Tier 2 tools ──
            elif tool_name == "get_wallet_summary":
                from app.arch.tools.treasurer_tools import get_wallet_summary
                return await get_wallet_summary(self.db)
            elif tool_name == "check_exchange_rates":
                from app.arch.tools.treasurer_tools import check_exchange_rates
                return await check_exchange_rates(self.db)

            # ── Auditor Tier 2 tools ──
            elif tool_name == "run_compliance_scan":
                from app.arch.tools.auditor_tools import run_compliance_scan
                return await run_compliance_scan(self.db)
            elif tool_name == "get_kyc_status":
                from app.arch.tools.auditor_tools import get_kyc_status
                return await get_kyc_status(self.db, entity_id=tool_input.get("entity_id", ""))

            # ── Arbiter Tier 2 tools ──
            elif tool_name == "get_engagement_history":
                from app.arch.tools.arbiter_tools import get_engagement_history
                return await get_engagement_history(self.db, engagement_id=tool_input.get("engagement_id", ""))
            elif tool_name == "notify_parties":
                from app.arch.tools.arbiter_tools import notify_parties
                return await notify_parties(
                    self.db,
                    engagement_id=tool_input.get("engagement_id", ""),
                    subject=tool_input.get("subject", ""),
                    message=tool_input.get("message", ""),
                )

            # ── Sovereign Tier 2 tools ──
            elif tool_name == "get_platform_dashboard":
                from app.arch.tools.sovereign_tools import get_platform_dashboard
                return await get_platform_dashboard(self.db)

            # ── Sentinel Tier 1 tools ──
            elif tool_name == "search_logs":
                from app.arch.tools.sentinel_tools import search_logs
                return await search_logs(
                    keyword=tool_input.get("keyword", ""),
                    since_minutes=tool_input.get("since_minutes", 60),
                    severity=tool_input.get("severity", ""),
                    max_lines=tool_input.get("max_lines", 50),
                )
            elif tool_name == "check_ssl_certificates":
                from app.arch.tools.sentinel_tools import check_ssl_certificates
                return await check_ssl_certificates()
            elif tool_name == "get_rate_limit_status":
                from app.arch.tools.sentinel_tools import get_rate_limit_status
                return await get_rate_limit_status()

            handler = executor_handlers.get(tool_name)
            if not handler:
                log.warning(f"[{self.agent_id}] No handler for tool {tool_name}")
                return {"error": f"Tool {tool_name} not implemented"}
            return await handler(tool_input)
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



    async def _tool_propose_improvement(self, args: dict) -> dict:
        """Propose a self-improvement for board vote."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "http://127.0.0.1:8000/api/v1/boardroom/self-improvement/propose",
                    json={
                        "title": args.get("title", ""),
                        "description": args.get("description", ""),
                        "proposed_by": self.agent_id,
                        "type": args.get("improvement_type", "prompt_modification"),
                        "affects_all": args.get("affects_all", False),
                        "code_diff": args.get("code_diff", ""),
                        "target_agents": args.get("target_agents", [self.agent_id]),
                    }
                )
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def _tool_vote_on_proposal(self, args: dict) -> dict:
        """Cast a vote on a self-improvement proposal."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"http://127.0.0.1:8000/api/v1/boardroom/self-improvement/vote/{args.get('proposal_id', '')}",
                    json={"agent": self.agent_id, "vote": args.get("vote", "ABSTAIN")}
                )
                result = resp.json()
                result["your_reason"] = args.get("reason", "")
                return result
        except Exception as e:
            return {"error": str(e)}

    async def _tool_list_proposals(self, args: dict) -> dict:
        """List all self-improvement proposals."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get("http://127.0.0.1:8000/api/v1/boardroom/self-improvement/proposals")
                return resp.json()
        except Exception as e:
            return {"error": str(e)}

    async def _tool_self_schedule(self, args: dict) -> dict:
        """Create a self-scheduled task. Agents use this to schedule their own work.

        Args:
            title: What the task is
            description: Detailed instructions
            action_type: One of: run_command, write_file, generate_content, http_request, post_content
            action_params: Dict of parameters for the action
            schedule_at: (optional) ISO datetime for one-time execution
            cron_expression: (optional) Cron string for recurring
        """
        from app.arch.task_queue import agent_create_scheduled_task
        async with self.db_factory() as db:
            result = await agent_create_scheduled_task(
                db,
                agent_name=self.agent_name,
                title=args.get("title", "Self-scheduled task"),
                description=args.get("description", ""),
                action_type=args.get("action_type", "generate_content"),
                action_params=args.get("action_params", {}),
                schedule_at=args.get("schedule_at"),
                cron_expression=args.get("cron_expression"),
                priority=args.get("priority", 5),
            )
            return result

    async def heartbeat(self):
        """Scheduled every 60 seconds — pure DB write + conditional anomaly check.
        ARCH-CO-002: No LLM call unless anomaly detected."""
        # Pure DB write — zero LLM cost
        await self.db.execute(
            text("""
                UPDATE arch_agents SET last_heartbeat = now()
                WHERE agent_name = :agent_id
            """),
            {"agent_id": self.agent_id},
        )
        await self.db.commit()

        # Log heartbeat execution
        try:
            await self.db.execute(
                text("""
                    INSERT INTO job_execution_log (job_id, status, skip_reason, tokens_consumed, duration_ms, executed_at)
                    VALUES (:job_id, 'EXECUTED', NULL, 0, 0, now())
                """),
                {"job_id": f"heartbeat_{self.agent_id}"},
            )
            await self.db.commit()
        except Exception as e:
            import logging; logging.getLogger("base").warning(f"Suppressed: {e}")  # job_execution_log may not exist yet

        # ARCH-CO-002: Conditional anomaly check — only invoke LLM if anomaly detected
        import os as _hb_os
        if _hb_os.environ.get("ARCH_CO_LEAN_HEARTBEAT_ENABLED", "false").lower() != "true":
            return

        anomaly_detected = False
        anomaly_reason = ""

        try:
            # Check agent-specific anomaly conditions
            if self.agent_id == "sentinel":
                # Any health check returning non-healthy
                r = await self.db.execute(text(
                    "SELECT count(*) FROM arch_infrastructure_health WHERE status != 'healthy' AND checked_at > now() - interval '5 minutes'"
                ))
                if (r.scalar() or 0) > 0:
                    anomaly_detected = True
                    anomaly_reason = "Infrastructure health degradation detected"

            elif self.agent_id == "treasurer":
                # Reserve floor within 10% of breach
                r = await self.db.execute(text(
                    "SELECT total_balance_zar, floor_zar FROM arch_reserve_ledger ORDER BY recorded_at DESC LIMIT 1"
                ))
                row = r.fetchone()
                if row and row.floor_zar > 0:
                    if float(row.total_balance_zar) < float(row.floor_zar) * 1.1:
                        anomaly_detected = True
                        anomaly_reason = "Reserve floor within 10% of breach"

            elif self.agent_id == "auditor":
                # Unprocessed high-risk flags older than 15 minutes
                r = await self.db.execute(text(
                    "SELECT count(*) FROM arch_compliance_events WHERE severity = 'HIGH' AND created_at < now() - interval '15 minutes'"
                ))
                if (r.scalar() or 0) > 0:
                    anomaly_detected = True
                    anomaly_reason = "Unprocessed high-risk compliance flag"

            # Universal: circuit breaker tripped
            r = await self.db.execute(text(
                "SELECT circuit_breaker_tripped FROM arch_agents WHERE agent_name = :aid"
            ), {"aid": self.agent_id})
            row = r.fetchone()
            if row and row.circuit_breaker_tripped:
                anomaly_detected = True
                anomaly_reason = f"Circuit breaker tripped for {self.agent_id}"

        except Exception as e:
            import logging; logging.getLogger("base").warning(f"Suppressed: {e}")  # Never let anomaly check crash the heartbeat

        # Only invoke LLM on anomaly
        if anomaly_detected:
            try:
                response = await self.client.messages.create(
                    model="claude-haiku-4-5-20251001", max_tokens=200,
                    messages=[{"role": "user", "content":
                        f"ANOMALY DETECTED during {self.agent_id} heartbeat: {anomaly_reason}. "
                        f"Generate a concise incident summary and recommended action (2-3 sentences)."}])
                summary = next((bl.text for bl in response.content if bl.type == "text"), "")

                # Route to founder inbox
                import json
                await self.db.execute(
                    text("""
                        INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at)
                        VALUES ('EXECUTION_PROOF', 'URGENT'::arch_msg_priority, :desc, 'PENDING', now())
                    """),
                    {"desc": json.dumps({
                        "subject": f"ANOMALY: {self.agent_id} — {anomaly_reason}",
                        "detail": summary,
                        "prepared_by": self.agent_id,
                        "type": "HEARTBEAT_ANOMALY",
                    })},
                )
                await self.db.commit()
            except Exception as e:
                import logging; logging.getLogger("base").warning(f"Suppressed: {e}")

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
        # Update token counter
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

        # ARCH-CO-001: Log cache hit/miss
        import os as _cache_os
        if _cache_os.environ.get("ARCH_CO_PROMPT_CACHE_ENABLED", "false").lower() == "true":
            try:
                cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
                cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
                is_hit = cache_read > 0
                await self.db.execute(
                    text("""
                        INSERT INTO job_execution_log (job_id, status, tokens_consumed, duration_ms, executed_at)
                        VALUES (:jid, :status, :tokens, 0, now())
                    """),
                    {"jid": f"cache_{self.agent_id}",
                     "status": "CACHE_HIT" if is_hit else "CACHE_MISS",
                     "tokens": cache_read if is_hit else cache_creation},
                )
                await self.db.commit()
            except Exception as e:
                import logging; logging.getLogger("base").warning(f"Suppressed: {e}")

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


    async def _schedule_task(self, params):
        from app.arch.task_queue import enqueue_task
        return await enqueue_task(
            self.db, self.agent_id, params["title"], params["action_type"],
            params["action_params"], params.get("task_type", "IMMEDIATE"),
            params.get("priority", 5), params.get("schedule_at"),
        )

    async def _list_my_tasks(self, params):
        from sqlalchemy import text as sa_text
        status = params.get("status_filter", "all")
        query = "SELECT id::text, title, action_type, status, priority, created_at FROM arch_task_queue WHERE agent_id = :aid"
        if status != "all":
            query += " AND status = :status"
        query += " ORDER BY created_at DESC LIMIT 20"
        bind = {"aid": self.agent_id}
        if status != "all":
            bind["status"] = status
        result = await self.db.execute(sa_text(query), bind)
        return [{"id": r.id, "title": r.title, "action": r.action_type,
                 "status": r.status, "priority": r.priority} for r in result.fetchall()]

    async def _generate_image(self, params):
        from app.arch.creative_tools import generate_image_dalle
        return await generate_image_dalle(params["prompt"], params.get("size", "1024x1024"), params.get("quality", "standard"))

    async def _create_social_graphic(self, params):
        from app.arch.creative_tools import create_social_graphic
        return await create_social_graphic(params["headline"], params.get("subtext", ""), params.get("style", "dark_tech"), params.get("platform", "linkedin"))

    async def _send_discord(self, params):
        from app.arch.creative_tools import send_discord_message
        embed = None
        if params.get("embed_title"):
            embed = {"title": params["embed_title"], "description": params.get("embed_description", ""), "color": params.get("embed_color", 163984)}
        return await send_discord_message(params["webhook_url"], params["content"], embed)

    async def _create_subordinate(self, params):
        from app.arch.subordinate_manager import create_subordinate
        return await create_subordinate(
            self.db, self.agent_id, params["name"], params["layer"],
            params["platform"], params["description"],
            params.get("capabilities", [])
        )

    async def _issue_instruction(self, params):
        from app.arch.subordinate_manager import issue_instruction
        return await issue_instruction(
            self.db, self.agent_id, params["subordinate_name"],
            params["instruction"], params.get("priority", 5)
        )

    async def _verify_capability(self, params):
        from app.arch.subordinate_manager import verify_capability
        return await verify_capability(
            self.db, self.agent_id, params["subordinate_name"],
            params["required_capability"]
        )

    async def _scope_development(self, params):
        from app.arch.subordinate_manager import scope_development
        return await scope_development(
            self.db, self.agent_id, params["subordinate_name"],
            params["capability_needed"], params["justification"]
        )

    async def _get_team_status(self, params):
        from app.arch.subordinate_manager import get_team_status
        return await get_team_status(self.db, self.agent_id)


    async def request_human_help(self, title: str, detail: str, priority: str = "URGENT"):
        """Request human intervention — creates an inbox item for the founder."""
        try:
            from sqlalchemy import text as _ht
            agent_row = await self.db.execute(_ht(
                "SELECT id FROM arch_agents WHERE agent_name = :n"
            ), {"n": self.agent_id})
            agent_uuid = agent_row.scalar()
            await self.db.execute(_ht(
                "INSERT INTO arch_founder_inbox "
                "(item_type, priority, description, prepared_by, status, due_at) "
                "VALUES ('DEFER_TO_OWNER', :pri, :desc, :agent, 'PENDING', now() + interval '24 hours')"
            ), {
                "pri": priority,
                "desc": json.dumps({
                    "subject": title,
                    "detail": detail,
                    "agent": self.agent_id,
                    "type": "human_intervention_required",
                }),
                "agent": agent_uuid,
            })
            await self.db.commit()
            log.info(f"[{self.agent_id}] Human help requested: {title}")
            return {"requested": True, "title": title}
        except Exception as e:
            log.error(f"[{self.agent_id}] Failed to request human help: {e}")
            return {"requested": False, "error": str(e)}

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
