"""The Sovereign — CEO & Board Chair.

Apex of the Agentic Operating System. Founder's permanent proxy.
Every Arch Agent escalates through The Sovereign before reaching
the founder. Convenes weekly board sessions. Issues constitutional rulings.

Startup sequence: Step 4 (after Sentinel).
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from app.arch.base import ArchAgentBase
from app.arch.tools.sovereign_tools import SOVEREIGN_TOOLS

log = logging.getLogger("arch.sovereign")


class SovereignAgent(ArchAgentBase):
    """The Sovereign — executive orchestrator and constitutional authority."""

    @property
    def system_prompt_key(self) -> str:
        return "system_prompt"

    async def get_tools(self) -> list:
        return SOVEREIGN_TOOLS

    # ── Tool handlers ──────────────────────────────────────────

    async def _tool_convene_board_session(self, params: dict) -> dict:
        """Convene a board session."""
        session_type = params.get("session_type", "WEEKLY")
        agenda = params.get("agenda", [])

        sovereign_id = await self.db.execute(
            text("SELECT id FROM arch_agents WHERE agent_name = 'sovereign'")
        )
        sov_uuid = sovereign_id.scalar()

        result = await self.db.execute(
            text("""
                INSERT INTO arch_board_sessions
                    (session_type, convened_by, agenda, status)
                VALUES (:type, :convened_by, :agenda, 'OPEN')
                RETURNING id::text
            """),
            {"type": session_type, "convened_by": sov_uuid,
             "agenda": json.dumps(agenda)},
        )
        session_id = result.scalar()
        await self.db.commit()

        # Check quorum
        agents_result = await self.db.execute(
            text("SELECT agent_name FROM arch_agents WHERE status = 'ACTIVE'")
        )
        active = [r.agent_name for r in agents_result.fetchall()]
        quorum_min = int(os.getenv("ARCH_BOARD_QUORUM_MINIMUM", "5"))
        quorum_met = len(active) >= quorum_min

        if not quorum_met:
            await self.db.execute(
                text("UPDATE arch_board_sessions SET status = 'QUORUM_FAIL', closed_at = now() WHERE id = cast(:id as uuid)"),
                {"id": session_id},
            )
            await self.db.commit()

        log.info(f"[sovereign] Board session convened: {session_id} ({session_type}), quorum: {quorum_met}")

        return {
            "session_id": session_id,
            "session_type": session_type,
            "quorum_met": quorum_met,
            "agents_present": active,
            "agenda": agenda,
        }

    async def _tool_submit_to_founder_inbox(self, params: dict) -> dict:
        """Submit item to founder's inbox."""
        item_type = params["item_type"]
        priority = params["priority"]
        subject = params["subject"]
        situation = params["situation"]
        deadline_hours = params.get("deadline_hours", 24)

        sovereign_id = await self.db.execute(
            text("SELECT id FROM arch_agents WHERE agent_name = 'sovereign'")
        )
        sov_uuid = sovereign_id.scalar()

        result = await self.db.execute(
            text("""
                INSERT INTO arch_founder_inbox
                    (item_type, priority, description, prepared_by, status, due_at)
                VALUES (:type, cast(:priority as arch_msg_priority), :desc, :prepared_by,
                        'PENDING', now() + make_interval(hours => :hours))
                RETURNING id::text
            """),
            {
                "type": item_type,
                "priority": priority,
                "desc": json.dumps({
                    "subject": subject,
                    "situation": situation,
                    "options": params.get("options", []),
                    "recommendation": params.get("recommendation", ""),
                }),
                "prepared_by": sov_uuid,
                "hours": deadline_hours,
            },
        )
        inbox_id = result.scalar()
        await self.db.commit()

        log.info(f"[sovereign] Founder inbox item: {inbox_id} ({item_type}, {priority})")

        return {
            "inbox_id": inbox_id,
            "item_type": item_type,
            "priority": priority,
            "subject": subject,
            "status": "PENDING",
            "deadline_hours": deadline_hours,
        }

    async def _tool_issue_constitutional_ruling(self, params: dict) -> dict:
        """Issue a constitutional ruling."""
        ruling_type = params["ruling_type"]
        ruling_text = params["ruling_text"]

        sovereign_id = await self.db.execute(
            text("SELECT id FROM arch_agents WHERE agent_name = 'sovereign'")
        )
        sov_uuid = sovereign_id.scalar()

        # Generate ruling reference
        year = datetime.now(timezone.utc).year
        count_result = await self.db.execute(
            text("SELECT COUNT(*) FROM arch_constitutional_rulings WHERE ruling_ref LIKE :pattern"),
            {"pattern": f"CR-{year}-%"},
        )
        count = count_result.scalar() or 0
        ruling_ref = f"CR-{year}-{count + 1:03d}"

        result = await self.db.execute(
            text("""
                INSERT INTO arch_constitutional_rulings
                    (ruling_ref, ruling_type, issued_by, subject_agents,
                     precedent_set, ruling_text, cited_directives,
                     is_renaming)
                VALUES (:ref, :type, :issued_by, :subjects,
                        :precedent, :text, :directives, :is_renaming)
                RETURNING id::text
            """),
            {
                "ref": ruling_ref,
                "type": ruling_type,
                "issued_by": sov_uuid,
                "subjects": json.dumps(params.get("subject_agents", [])),
                "precedent": params.get("precedent_set"),
                "text": ruling_text,
                "directives": json.dumps(params.get("cited_directives", [])),
                "is_renaming": ruling_type == "RENAMING",
            },
        )
        ruling_id = result.scalar()
        await self.db.commit()

        log.info(f"[sovereign] Constitutional ruling issued: {ruling_ref}")

        return {
            "ruling_id": ruling_id,
            "ruling_ref": ruling_ref,
            "ruling_type": ruling_type,
            "status": "ISSUED",
        }

    async def _tool_read_agent_health(self, params: dict) -> dict:
        """Read health status of all Arch Agents."""
        result = await self.db.execute(
            text("""
                SELECT agent_name, display_name, status, model_primary,
                       agent_version, last_heartbeat, token_budget_monthly,
                       tokens_used_this_month, circuit_breaker_tripped
                FROM arch_agents ORDER BY agent_name
            """)
        )
        agents = {}
        for r in result.fetchall():
            budget = r.token_budget_monthly or 1
            agents[r.agent_name] = {
                "display_name": r.display_name,
                "status": r.status,
                "model": r.model_primary,
                "version": r.agent_version,
                "last_heartbeat": r.last_heartbeat.isoformat() if r.last_heartbeat else None,
                "tokens_used": r.tokens_used_this_month,
                "token_budget": budget,
                "token_pct": round(100 * r.tokens_used_this_month / budget, 1),
                "circuit_breaker": r.circuit_breaker_tripped,
            }
        return agents

    async def _tool_broadcast_to_board(self, params: dict) -> dict:
        """Broadcast urgent message to all agents."""
        from app.arch.messaging import emit_urgent
        await emit_urgent(
            self.redis,
            from_agent="sovereign",
            to_agent="board",
            subject=params["subject"],
            body={"message": params["message"]},
            priority=params["priority"],
        )
        return {"broadcast": True, "subject": params["subject"], "priority": params["priority"]}

    # ── Board vote orchestration (Part XVIII Section 18.5) ─────

    async def conduct_board_vote(self, state: dict) -> dict:
        """Orchestrate a board vote across all Arch Agents.

        Enforces quorum, tier thresholds, proposer recusal.
        30s per-agent timeout prevents deadlock (GPT C-03).
        """
        proposal_id = state.get("context", {}).get("proposal_id") or uuid.uuid4().hex
        tier = state.get("tier", 1)
        proposer = state.get("originating_agent", "unknown")

        THRESHOLDS = {0: 1, 1: 4, 2: 7, 3: 7}
        QUORUM_MIN = int(os.getenv("ARCH_BOARD_QUORUM_MINIMUM", "5"))
        required = THRESHOLDS.get(tier, 4)

        # Create session
        sov_id_result = await self.db.execute(
            text("SELECT id FROM arch_agents WHERE agent_name = 'sovereign'")
        )
        sov_uuid = sov_id_result.scalar()

        session_id = uuid.uuid4()
        await self.db.execute(
            text("""
                INSERT INTO arch_board_sessions (id, session_type, convened_by, agenda)
                VALUES (:id, 'VOTE', :convened_by, :agenda)
            """),
            {"id": session_id, "convened_by": sov_uuid,
             "agenda": json.dumps([state.get("instruction", "Board vote")])},
        )
        await self.db.commit()

        # Get active agents
        agents_result = await self.db.execute(
            text("SELECT agent_name, id FROM arch_agents WHERE status = 'ACTIVE' ORDER BY agent_name")
        )
        active_agents = {row.agent_name: str(row.id) for row in agents_result.fetchall()}

        if len(active_agents) < QUORUM_MIN:
            await self.db.execute(
                text("UPDATE arch_board_sessions SET status = 'QUORUM_FAIL', closed_at = now() WHERE id = :sid"),
                {"sid": session_id},
            )
            await self.db.commit()
            return {
                **state,
                "board_vote_status": "QUORUM_FAIL",
                "board_vote_required": False,
                "error": f"Quorum not met: {len(active_agents)} < {QUORUM_MIN}",
            }

        # Collect votes via Redis pub/sub
        vote_channel = f"arch.board_votes.{proposal_id}"
        vote_pubsub = self.redis.pubsub()
        await vote_pubsub.subscribe(vote_channel)

        # Broadcast vote request
        await self.redis.publish(
            "arch.urgent",
            json.dumps({
                "from_agent": "sovereign",
                "to_agent": "board",
                "subject": "VOTE_REQUESTED",
                "body": {
                    "proposal_id": proposal_id,
                    "proposal_text": state.get("instruction"),
                    "tier": tier,
                    "session_id": str(session_id),
                    "reply_channel": vote_channel,
                },
                "priority": "URGENT",
            }),
        )

        # Collect with timeout
        votes: dict[str, str] = {}
        timeout_per_agent = 30.0
        total_timeout = timeout_per_agent * len(active_agents)

        try:
            async def collect():
                async for msg in vote_pubsub.listen():
                    if msg["type"] != "message":
                        continue
                    data = json.loads(msg["data"])
                    voter = data.get("agent_id")
                    vote = data.get("vote", "ABSTAIN")
                    if voter and voter not in votes:
                        # Proposer recusal (PI-12)
                        if voter == proposer:
                            vote = "RECUSED"
                        votes[voter] = vote
                    if len(votes) >= len(active_agents):
                        break

            await asyncio.wait_for(collect(), timeout=total_timeout)
        except asyncio.TimeoutError:
            for agent_name in active_agents:
                if agent_name not in votes:
                    votes[agent_name] = "ABSTAIN"
                    log.warning(f"[sovereign] {agent_name} vote timeout — ABSTAIN recorded")

        await vote_pubsub.unsubscribe(vote_channel)

        # Tally
        ayes = sum(1 for v in votes.values() if v == "AYE")
        nays = sum(1 for v in votes.values() if v == "NAY")
        passed = ayes >= required

        # Record votes
        for agent_name, vote_val in votes.items():
            agent_uuid = active_agents.get(agent_name)
            if not agent_uuid:
                continue
            vote_type = vote_val if vote_val in ("AYE", "NAY", "ABSTAIN", "RECUSED") else "ABSTAIN"
            rationale = "Timeout" if vote_val == "ABSTAIN" and agent_name not in votes else None
            await self.db.execute(
                text("""
                    INSERT INTO arch_board_votes
                        (session_id, proposal_id, agent_id, vote, rationale)
                    VALUES (:sid, cast(:pid as uuid), cast(:aid as uuid), cast(:vote as arch_vote_type), :rationale)
                    ON CONFLICT (session_id, proposal_id, agent_id) DO NOTHING
                """),
                {"sid": session_id, "pid": proposal_id, "aid": agent_uuid,
                 "vote": vote_type, "rationale": rationale},
            )

        # Close session
        await self.db.execute(
            text("""
                UPDATE arch_board_sessions
                SET status = 'CLOSED', closed_at = now(), quorum_met = true,
                    agents_present = :present, outcome = :outcome
                WHERE id = :sid
            """),
            {
                "sid": session_id,
                "present": json.dumps(list(votes.keys())),
                "outcome": json.dumps({"ayes": ayes, "nays": nays,
                                       "passed": passed, "required": required, "tier": tier}),
            },
        )
        await self.db.commit()

        status = "PASSED" if passed else "FAILED"
        log.info(f"[sovereign] Board vote {proposal_id}: {status} ({ayes}/{required} ayes)")

        return {
            **state,
            "board_vote_status": status,
            "board_vote_required": False,
            "output": f"Board vote: {status}. Ayes: {ayes}, Nays: {nays}, Required: {required}.",
        }

    async def notify_founder(self, state: dict) -> dict:
        """Route a founder notification from the graph."""
        subject = state.get("output", "Founder notification")[:200]
        await self._tool_submit_to_founder_inbox({
            "item_type": "INFORMATION",
            "priority": "ROUTINE",
            "subject": subject,
            "situation": state.get("output", ""),
        })
        return {**state, "founder_approval_status": "NOTIFIED"}

    async def financial_gate_check(self, state: dict) -> dict:
        """Placeholder — Treasurer handles the actual check."""
        return {**state, "financial_gate_cleared": True}

    async def trigger_self_assessments(self):
        """Scheduled monthly: trigger self-assessment for all agents."""
        await self.db.execute(
            text("UPDATE arch_agents SET self_assessment_due = now()")
        )
        await self.db.commit()
        log.info("[sovereign] Self-assessments triggered for all agents")
