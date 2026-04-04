"""The Autonomous Behaviour Engine — gives agents their will.

Dual-channel event processor: Redis (real-time) + DB (persistent).
Each agent runs its own event loop. Events are processed in isolated
asyncio tasks (C-05 fix) — long-running tasks never block the loop.
"""

import asyncio
import json
import logging
import os
import uuid

from sqlalchemy import text

log = logging.getLogger("arch.event_loop")

EVENT_SUBSCRIPTIONS = {
    "sovereign": [
        "governance.", "arch.board", "security.P1", "operator.churn",
        "compliance.regulatory_update", "agent.milestone", "platform.health_critical",
    ],
    "auditor": [
        "agent.registered", "operator.registered", "transaction.completed",
        "compliance.", "payout.executed", "regulatory.", "data_breach.",
    ],
    "arbiter": [
        "dispute.", "engagement.", "sla.", "community.", "quality.", "operator.nps",
    ],
    "treasurer": [
        "transaction.completed", "payout.", "operator.subscription",
        "reserve.", "token.budget", "vendor.", "charitable.",
    ],
    "sentinel": [
        "security.", "infrastructure.", "performance.", "blockchain.",
        "backup.", "succession.", "circuit_breaker.", "arch.agent_offline",
    ],
    "architect": [
        "code.", "arch.research", "performance.snapshot", "security.vulnerability",
        "acc.", "test.", "ai_model.", "capability_gap.",
    ],
    "ambassador": [
        "agent.registered", "operator.registered", "operator.subscription_upgraded",
        "engagement.first_for_operator", "agenthub.", "growth.", "mcp.",
        "competitor.", "press.",
    ],
}


class ArchEventLoop:
    """Dual-channel event processor for a single Arch Agent."""

    POLL_INTERVAL = 30
    BATCH_SIZE = 10
    BACK_OFF_SEC = 60

    def __init__(self, agent, agent_id: str, db_factory, redis):
        self.agent = agent
        self.agent_id = agent_id
        self.db_factory = db_factory
        self.redis = redis
        self.subscriptions = EVENT_SUBSCRIPTIONS.get(agent_id, [])
        self._running = False

    async def start(self):
        self._running = True
        log.info(f"[{self.agent_id}] Event loop started")
        await asyncio.gather(
            self._redis_subscriber(),
            self._db_poller(),
            return_exceptions=True,
        )

    async def _redis_subscriber(self):
        """Real-time: processes events within milliseconds of emission."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("arch.platform_events")
        async for msg in pubsub.listen():
            if not self._running:
                break
            if msg["type"] != "message":
                continue
            try:
                event = json.loads(msg["data"])
                if self._is_subscribed(event.get("event_type", "")):
                    # C-05: isolated task — never blocks the loop
                    asyncio.create_task(
                        self._process_event_isolated(event),
                        name=f"arch_event_{self.agent_id}_{str(event.get('id', ''))[:8]}",
                    )
            except Exception as e:
                log.error(f"[{self.agent_id}] Redis handler error: {e}", exc_info=True)

    async def _db_poller(self):
        """Fallback: catches events emitted during agent downtime."""
        while self._running:
            try:
                async with self.db_factory() as db:
                    events = await self._fetch_unprocessed(db)
                    for event in events:
                        asyncio.create_task(
                            self._process_event_isolated(event),
                            name=f"arch_poll_{self.agent_id}_{str(event.get('id', ''))[:8]}",
                        )
            except Exception as e:
                log.error(f"[{self.agent_id}] DB poller error: {e}", exc_info=True)
                await asyncio.sleep(self.BACK_OFF_SEC)
                continue
            await asyncio.sleep(self.POLL_INTERVAL)

    async def _fetch_unprocessed(self, db) -> list[dict]:
        result = await db.execute(
            text("""
                SELECT id, event_type, event_data, source_module, created_at
                FROM arch_platform_events
                WHERE NOT (:agent_id = ANY(COALESCE(processed_by, ARRAY[]::text[])))
                  AND created_at > now() - interval '24 hours'
                ORDER BY created_at ASC
                LIMIT :batch
            """),
            {"agent_id": self.agent_id, "batch": self.BATCH_SIZE},
        )
        return [
            {
                "id": str(r.id), "event_type": r.event_type,
                "data": json.loads(r.event_data) if isinstance(r.event_data, str) else r.event_data,
                "source": r.source_module,
                "occurred_at": r.created_at.isoformat(),
            }
            for r in result.fetchall()
            if self._is_subscribed(r.event_type)
        ]

    def _is_subscribed(self, event_type: str) -> bool:
        return any(event_type.startswith(p) for p in self.subscriptions)

    async def _process_event_isolated(self, event: dict):
        """C-05 fix: each event in its own task — never blocks the poll loop."""
        t0 = asyncio.get_event_loop().time()
        try:
            state = self._build_state(event)
            result = await self.agent(state)
            action = result.get("action_taken") or result.get("output", "")[:300]
            ms = int((asyncio.get_event_loop().time() - t0) * 1000)
            async with self.db_factory() as db:
                await self._record_outcome(event, action, db, ms,
                                           result.get("defer_to_owner", False))
            if result.get("defer_to_owner"):
                log.info(f"[{self.agent_id}] DEFER_TO_OWNER on {event['event_type']}")
        except Exception as e:
            log.error(f"[{self.agent_id}] process_event failed: {e}", exc_info=True)

    def _build_state(self, event: dict) -> dict:
        return {
            "session_id": uuid.uuid4().hex,
            "originating_agent": "event_loop",
            "instruction": self._build_prompt(event),
            "instruction_type": self._classify(event.get("event_type", "")),
            "context": {"event": event},
            "memory_retrieved": [],
            "tool_results": [],
            "inter_agent_messages": [],  # GEM-01: starts empty per event
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

    def _build_prompt(self, event: dict) -> str:
        return (
            f"AUTONOMOUS EVENT — apply your decision framework immediately.\n\n"
            f"Event type:    {event.get('event_type', 'unknown')}\n"
            f"Source module: {event.get('source', 'unknown')}\n"
            f"Occurred at:   {event.get('occurred_at', '')}\n"
            f"Event data:\n{json.dumps(event.get('data', {}), indent=2)}\n\n"
            f"Your task:\n"
            f"1. Does this event fall within your portfolio? If not: mark processed, take no action.\n"
            f"2. Does this event require immediate action? Apply your trigger-to-action map.\n"
            f"3. Call the appropriate tool with the correct parameters.\n"
            f"4. If the situation exceeds your authority: DEFER_TO_OWNER or escalate to board.\n"
            f"5. Set action_taken with a one-sentence summary.\n\n"
            f"Be decisive. Act within your authority. Escalate what you cannot resolve."
        )

    def _classify(self, event_type: str) -> str:
        prefix = event_type.split(".")[0] if "." in event_type else event_type
        return {
            "security": "security", "compliance": "compliance",
            "data_breach": "compliance", "dispute": "justice",
            "engagement": "justice", "sla": "justice",
            "transaction": "finance", "payout": "finance",
            "reserve": "finance", "vendor": "finance",
            "charitable": "finance", "token": "finance",
            "code": "technology", "performance": "technology",
            "acc": "technology", "ai_model": "technology",
            "test": "technology", "arch": "governance",
            "governance": "governance", "agent": "governance",
            "operator": "governance", "agenthub": "growth",
            "mcp": "growth", "competitor": "growth",
            "press": "growth", "growth": "growth",
            "infrastructure": "security", "blockchain": "security",
            "backup": "security", "succession": "security",
        }.get(prefix, "governance")

    async def _record_outcome(self, event: dict, action: str, db, ms: int,
                              deferred: bool = False):
        await db.execute(
            text("""
                UPDATE arch_platform_events
                SET processed_by = array_append(COALESCE(processed_by, ARRAY[]::text[]), :agent_id),
                    triggered_action = COALESCE(triggered_action, '') || :summary
                WHERE id = cast(:eid as uuid)
            """),
            {"agent_id": self.agent_id,
             "summary": f"[{self.agent_id}]: {action[:200]} | ",
             "eid": event.get("id")},
        )
        await db.execute(
            text("""
                INSERT INTO arch_event_actions
                    (event_id, agent_id, event_type, action_taken,
                     processing_time_ms, deferred_to_owner)
                VALUES (cast(:eid as uuid), :agent_id, :etype, :action, :ms, :deferred)
            """),
            {"eid": event.get("id"), "agent_id": self.agent_id,
             "etype": event.get("event_type", ""), "action": action[:500],
             "ms": ms, "deferred": deferred},
        )
        await db.commit()

    def stop(self):
        self._running = False
        log.info(f"[{self.agent_id}] Event loop stopping")
