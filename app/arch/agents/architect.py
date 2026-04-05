"""The Architect — CTO & Chief Innovation Officer.

Owns entire technology stack, all engineering decisions, ACC orchestration,
self-development governance, four-tier code evolution protocol enforcement.

Startup sequence: Step 8 (after Arbiter).
"""

import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import text

from app.arch.base import ArchAgentBase
from app.arch.constitution import check_self_referential
from app.arch.tools.architect_tools import ARCHITECT_TOOLS
from app.arch.executor_tools import EXECUTOR_TOOLS

log = logging.getLogger("arch.architect")


class ArchitectAgent(ArchAgentBase):

    @property
    def system_prompt_key(self) -> str:
        return "system_prompt"

    async def get_tools(self) -> list:
        return ARCHITECT_TOOLS + EXECUTOR_TOOLS

    async def _tool_submit_code_proposal(self, params: dict) -> dict:
        tier = params["tier"]
        title = params["title"]
        file_changes = params.get("file_changes", [])

        # Self-referential check (H-01)
        blocked, reason = check_self_referential(title, file_changes, "architect")
        if blocked:
            log.warning(f"[architect] Self-referential proposal blocked: {reason}")
            return {"status": "SELF_REFERENTIAL_BLOCK", "reason": reason}

        architect_id = await self.db.execute(
            text("SELECT id FROM arch_agents WHERE agent_name = 'architect'")
        )
        a_uuid = architect_id.scalar()

        result = await self.db.execute(
            text("""
                INSERT INTO arch_code_proposals
                    (tier, proposing_agent, title, description, rationale,
                     file_changes, status)
                VALUES (cast(:tier as arch_proposal_tier), :agent, :title, :desc, :rationale,
                        :changes, 'DRAFT')
                RETURNING id::text
            """),
            {
                "tier": tier, "agent": a_uuid, "title": title,
                "desc": params["description"], "rationale": params["rationale"],
                "changes": json.dumps(file_changes),
            },
        )
        proposal_id = result.scalar()
        await self.db.commit()
        log.info(f"[architect] Code proposal submitted: Tier {tier} — {title}")
        return {"proposal_id": proposal_id, "tier": tier, "status": "DRAFT"}

    async def _tool_toggle_feature_flag(self, params: dict) -> dict:
        flag_name = params["flag_name"]
        enabled = params["enabled"]
        reason = params["reason"]

        # Cannot toggle constitutional flags
        constitutional_flags = ["ARCH_AGENTS_ENABLED"]
        if flag_name in constitutional_flags:
            return {"status": "BLOCKED", "reason": "Constitutional flag — requires founder action"}

        log.info(f"[architect] Feature flag {flag_name} -> {enabled}: {reason}")
        return {"flag_name": flag_name, "enabled": enabled, "status": "FLAGGED",
                "note": "Environment variable update required — routed to founder"}

    async def _tool_sandbox_deploy(self, params: dict) -> dict:
        proposal_id = params["proposal_id"]
        await self.db.execute(
            text("""
                UPDATE arch_code_proposals
                SET sandbox_outcome = 'PENDING', status = 'BOARD_REVIEW'
                WHERE id = cast(:pid as uuid)
            """),
            {"pid": proposal_id},
        )
        await self.db.commit()
        return {"proposal_id": proposal_id, "status": "SANDBOX_PENDING",
                "note": "Staging environment deployment queued"}

    async def _tool_update_tech_radar(self, params: dict) -> dict:
        await self.db.execute(
            text("""
                INSERT INTO arch_tech_radar
                    (technology, category, assessment, rationale)
                VALUES (:tech, :cat, :assess, :rationale)
            """),
            {
                "tech": params["technology"], "cat": params.get("category"),
                "assess": params["assessment"], "rationale": params["rationale"],
            },
        )
        await self.db.commit()
        return {"technology": params["technology"],
                "assessment": params["assessment"], "recorded": True}

    async def _tool_evaluate_ai_model(self, params: dict) -> dict:
        await self.db.execute(
            text("""
                INSERT INTO arch_ai_model_evals
                    (model_name, provider, benchmark_results,
                     cost_per_1k_tokens, latency_ms_p50, recommendation)
                VALUES (:name, :provider, :bench, :cost, :latency, :rec)
            """),
            {
                "name": params["model_name"], "provider": params["provider"],
                "bench": json.dumps(params.get("benchmark_results", {})),
                "cost": params.get("cost_per_1k_tokens"),
                "latency": params.get("latency_ms_p50"),
                "rec": "Evaluation recorded. Review at next board session.",
            },
        )
        await self.db.commit()
        return {"model_name": params["model_name"], "status": "EVALUATED"}

    async def _tool_get_performance_snapshot(self, params: dict) -> dict:
        agent_filter = params.get("agent_id", "all")
        query = """
            SELECT agent_id::text, snapshot_period, pass_rate_pct,
                   kpis_passing, kpis_total, circuit_tripped, snapshotted_at
            FROM arch_performance_snapshots
        """
        bind = {}
        if agent_filter != "all":
            query += " WHERE agent_id = (SELECT id FROM arch_agents WHERE agent_name = :aid)"
            bind["aid"] = agent_filter
        query += " ORDER BY snapshotted_at DESC LIMIT 10"

        result = await self.db.execute(text(query), bind)
        snapshots = [
            {"agent_id": r.agent_id, "period": r.snapshot_period,
             "pass_rate": float(r.pass_rate_pct), "passing": r.kpis_passing,
             "total": r.kpis_total, "circuit_tripped": r.circuit_tripped}
            for r in result.fetchall()
        ]
        return {"snapshots": snapshots}

    async def _tool_trigger_acc_task(self, params: dict) -> dict:
        log.info(f"[architect] ACC task triggered: {params['task_type']} — {params['topic']}")
        return {"task_type": params["task_type"], "topic": params["topic"],
                "status": "QUEUED", "note": "ACC pipeline will process"}

    async def _tool_approve_acc_output(self, params: dict) -> dict:
        output_id = params["output_id"]
        log.info(f"[architect] ACC output approved: {output_id}")
        from app.arch.events import emit_platform_event
        await emit_platform_event(
            "acc.output_approved",
            {"output_id": output_id, "approved_by": "architect"},
            source_module="arch_architect", db=self.db,
        )
        return {"output_id": output_id, "status": "APPROVED"}

    # ── Scheduled jobs ─────────────────────────────────────────

    async def reset_token_budgets(self):
        """Monthly: reset all agent token counters."""
        await self.db.execute(
            text("UPDATE arch_agents SET tokens_used_this_month = 0, tokens_reset_at = now()")
        )
        await self.db.commit()
        log.info("[architect] Token budgets reset for all agents")

    async def ingest_research(self):
        """Daily: placeholder for knowledge ingestion pipeline."""
        log.info("[architect] Research ingestion cycle triggered")
