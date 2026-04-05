"""The Arbiter — Chief Product & Customer Officer / Chief Justice.

Governs quality and integrity of everything the platform delivers.
Owns the DAP, Rules of the Chamber, case law library.
Issues binding precedent for novel disputes.

Startup sequence: Step 7 (after Auditor).
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.arch.base import ArchAgentBase
from app.arch.tools.arbiter_tools import ARBITER_TOOLS
from app.arch.executor_tools import EXECUTOR_TOOLS

log = logging.getLogger("arch.arbiter")


class ArbiterAgent(ArchAgentBase):

    @property
    def system_prompt_key(self) -> str:
        return "system_prompt"

    async def get_tools(self) -> list:
        return ARBITER_TOOLS + EXECUTOR_TOOLS

    async def _tool_search_case_law(self, params: dict) -> dict:
        query = params["query"]
        top_k = params.get("top_k", 5)
        # Search via pgvector semantic similarity on arbiter memories
        memories = await self.recall(query, k=top_k)
        # Also search existing agentis_case_law table
        result = await self.db.execute(
            text("""
                SELECT case_id::text, engagement_title, ruling, arbiter_reasoning,
                       arbiter_rating, category, value_cents
                FROM agentis_case_law
                ORDER BY published_at DESC LIMIT :k
            """),
            {"k": top_k},
        )
        cases = [
            {"case_id": r.case_id, "title": r.engagement_title,
             "ruling": r.ruling, "reasoning": r.arbiter_reasoning,
             "rating": r.arbiter_rating, "category": r.category}
            for r in result.fetchall()
        ]
        return {"query": query, "case_law_results": cases,
                "memory_results": memories, "total": len(cases) + len(memories)}

    async def _tool_get_dispute_details(self, params: dict) -> dict:
        dispute_id = params["dispute_id"]
        result = await self.db.execute(
            text("""
                SELECT d.dispute_id::text, d.description, d.dispute_type,
                       d.status, d.evidence, d.arbitration_finding,
                       e.engagement_title, e.scope_of_work, e.acceptance_criteria,
                       e.proposed_price, e.current_state
                FROM engagement_disputes d
                JOIN agent_engagements e ON d.engagement_id = e.engagement_id
                WHERE d.dispute_id = :did
            """),
            {"did": dispute_id},
        )
        row = result.fetchone()
        if not row:
            return {"error": f"Dispute {dispute_id} not found"}
        return {
            "dispute_id": row.dispute_id, "type": row.dispute_type,
            "status": row.status, "description": row.description,
            "engagement_title": row.engagement_title,
            "scope": row.scope_of_work, "criteria": row.acceptance_criteria,
            "value": float(row.proposed_price) if row.proposed_price else 0,
            "evidence": row.evidence,
        }

    async def _tool_issue_ruling(self, params: dict) -> dict:
        dispute_id = params["dispute_id"]
        outcome = params["outcome"]
        ruling_text = params["ruling_text"]
        precedent = params.get("precedent_set")

        result = await self.db.execute(
            text("""
                INSERT INTO arch_arbitration_cases
                    (dap_case_ref, ruling_text, outcome, precedent_set,
                     cited_cases, decided_at)
                VALUES (:ref, :text, :outcome, :precedent, :cited, now())
                RETURNING id::text
            """),
            {
                "ref": dispute_id, "text": ruling_text, "outcome": outcome,
                "precedent": precedent,
                "cited": json.dumps(params.get("cited_cases", [])),
            },
        )
        ruling_id = result.scalar()
        await self.db.commit()
        log.info(f"[arbiter] Ruling issued: {ruling_id} — {outcome} for dispute {dispute_id}")

        # Store as memory for future case law search
        await self.remember(
            f"Ruling on dispute {dispute_id}: {outcome}. {ruling_text[:500]}",
            metadata={"dispute_id": dispute_id, "outcome": outcome},
            source_type="decision",
        )

        return {"ruling_id": ruling_id, "outcome": outcome, "status": "ISSUED",
                "precedent_set": precedent is not None}

    async def _tool_enforce_community_action(self, params: dict) -> dict:
        target_id = params["target_id"]
        action = params["action"]
        reason = params["reason"]

        await self.db.execute(
            text("""
                INSERT INTO arch_quality_audits
                    (scope, findings, recommendations, remediation_status)
                VALUES (:scope, :findings, :recs, 'OPEN')
            """),
            {
                "scope": f"Community action: {action} on {params['target_type']} {target_id}",
                "findings": json.dumps([{"action": action, "reason": reason}]),
                "recs": json.dumps([{"enforce": action, "target": target_id}]),
            },
        )
        await self.db.commit()
        log.info(f"[arbiter] Community action: {action} on {target_id} — {reason}")
        return {"target_id": target_id, "action": action, "enforced": True}

    async def _tool_check_sla_status(self, params: dict) -> dict:
        breach_only = params.get("breach_only", False)
        query = "SELECT id::text, service_name, target_ms, actual_ms_p95, status, breach_count_30d FROM arch_sla_monitor"
        if breach_only:
            query += " WHERE status != 'OK'"
        query += " ORDER BY service_name"

        result = await self.db.execute(text(query))
        slas = [
            {"service": r.service_name, "target_ms": r.target_ms,
             "actual_p95": r.actual_ms_p95, "status": r.status,
             "breaches_30d": r.breach_count_30d}
            for r in result.fetchall()
        ]
        return {"sla_status": slas, "count": len(slas)}

    async def _tool_update_rules_of_chamber(self, params: dict) -> dict:
        log.info(f"[arbiter] Rules of Chamber amendment proposed: {params['rule_section']}")
        return {
            "status": "PROPOSAL_CREATED",
            "rule_section": params["rule_section"],
            "note": "Amendment routed to board for vote. Not yet effective.",
        }
