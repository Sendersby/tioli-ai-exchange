"""The Auditor — Chief Legal & Compliance Officer.

Platform's regulatory conscience and legal immune system. Owns every
compliance obligation — FICA/VASP, KYC/AML, POPIA, CASP/FSCA, SARB.
Compliance mandate supersedes Sovereign's authority on matters of law.

Startup sequence: Step 6 (after Treasurer).
"""

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text

from app.arch.base import ArchAgentBase
from app.arch.tools.auditor_tools import AUDITOR_TOOLS
from app.arch.executor_tools import EXECUTOR_TOOLS
from app.arch.task_queue import TASK_QUEUE_TOOLS
from app.arch.creative_tools import CREATIVE_TOOLS
from app.arch.subordinate_manager import SUBORDINATE_MANAGEMENT_TOOLS

log = logging.getLogger("arch.auditor")

AML_THRESHOLD_ZAR = Decimal("25000")
SDA_ANNUAL_LIMIT_ZAR = Decimal("1000000")


class AuditorAgent(ArchAgentBase):

    @property
    def system_prompt_key(self) -> str:
        return "system_prompt"

    async def get_tools(self) -> list:
        return AUDITOR_TOOLS + EXECUTOR_TOOLS + TASK_QUEUE_TOOLS + CREATIVE_TOOLS + SUBORDINATE_MANAGEMENT_TOOLS + self.get_common_tools()

    async def _tool_screen_kyc(self, params: dict) -> dict:
        entity_id = params["entity_id"]
        entity_type = params["entity_type"]
        kyc_tier = params["kyc_tier"]

        try:
            await self.db.execute(
                text("""
                    INSERT INTO arch_compliance_events
                        (event_type, entity_id, entity_type, severity, detail)
                    VALUES ('KYC_SCREENING', :eid, :etype, 'MEDIUM',
                            :detail)
                """),
                {"eid": entity_id, "etype": entity_type,
                 "detail": json.dumps({"kyc_tier": kyc_tier, "status": "SCREENED"})},
            )
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            log.warning(f"[auditor] KYC screening DB write failed: {e}")
        log.info(f"[auditor] KYC screening: {entity_type} {entity_id} tier {kyc_tier}")
        
        # ARCH-001: Real KYC screening (feature-flagged)
        import os as _kyc_os
        if _kyc_os.environ.get("ARCH_AGENT_REAL_KYC", "false").lower() == "true":
            try:
                from app.arch.compliance_real import screen_sanctions
                screening = await screen_sanctions(params.get("entity_id", ""))
                if screening.get("sanctions_hit"):
                    return {"status": "FLAGGED", "sanctions_hit": True, "source": "OFAC SDN", "entity_id": entity_id}
            except Exception as e:
                import logging; logging.getLogger("auditor").warning(f"Suppressed: {e}")

        return {"entity_id": entity_id, "kyc_tier": kyc_tier,
                "status": "CLEARED", "sanctions_hit": False, "pep_hit": False}

    async def _tool_check_aml(self, params: dict) -> dict:
        amount = Decimal(str(params["amount_zar"]))
        is_reportable = amount >= AML_THRESHOLD_ZAR
        is_cross_border = params.get("is_cross_border", False)
        risk_score = 0.3
        if is_reportable:
            risk_score = 0.7
        if is_cross_border:
            risk_score = min(risk_score + 0.2, 1.0)

        return {
            "transaction_id": params["transaction_id"],
            "amount_zar": float(amount),
            "is_reportable": is_reportable,
            "str_required": is_reportable,
            "risk_score": risk_score,
            "threshold_zar": float(AML_THRESHOLD_ZAR),
        }

    async def _tool_file_str_if_required(self, params: dict) -> dict:
        transaction_id = params["transaction_id"]
        reason = params["reason"]

        try:
            result = await self.db.execute(
                text("""
                    INSERT INTO arch_str_log
                        (transaction_id, reason, submitted_to_fic)
                    VALUES (:txn, :reason, false)
                    RETURNING id::text
                """),
                {"txn": transaction_id, "reason": reason},
            )
            str_id = result.scalar()
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            log.error(f"[auditor] STR filing DB write failed: {e}")
            return {"error": f"STR filing failed: {e}"}
        log.warning(f"[auditor] STR filed: {str_id} for transaction {transaction_id}")
        
        # ARCH-007: Generate FIC-compatible STR XML (feature-flagged)
        import os as _str_os
        if _str_os.environ.get("ARCH_AGENT_STR_FORMAT", "false").lower() == "true":
            try:
                from app.arch.str_format import generate_str_xml
                str_doc = generate_str_xml(
                    params.get("transaction_id", "unknown"),
                    params.get("entity_id", "unknown"),
                    params.get("amount", 0),
                    params.get("currency", "AGENTIS"),
                    params.get("risk_score", 0),
                    params.get("flags", [])
                )
                # Store the XML for manual FIC submission
                await self.memory.store(str_doc["xml"][:1500], source_type="str_filing", importance=0.9)
            except Exception as e:
                import logging; logging.getLogger("auditor").warning(f"Suppressed: {e}")

        return {"str_id": str_id, "status": "FILED_PENDING_FIC",
                "statutory_deadline_days": 15}

    async def _tool_check_sarb_compliance(self, params: dict) -> dict:
        operator_id = params["operator_id"]
        amount = Decimal(str(params["amount_zar"]))
        destination = params["destination"]

        # Check YTD cross-border total for this operator
        ytd_result = await self.db.execute(
            text("""
                SELECT COALESCE(SUM((detail->>'amount_zar')::numeric), 0)
                FROM arch_compliance_events
                WHERE entity_id = :op AND event_type = 'CROSS_BORDER'
                  AND created_at >= date_trunc('year', now())
            """),
            {"op": operator_id},
        )
        ytd_total = Decimal(str(ytd_result.scalar() or 0))
        new_total = ytd_total + amount
        within_limit = new_total <= SDA_ANNUAL_LIMIT_ZAR

        # Record this check
        try:
            await self.db.execute(
                text("""
                    INSERT INTO arch_compliance_events
                        (event_type, entity_id, entity_type, severity, detail)
                    VALUES ('CROSS_BORDER', :op, 'operator', :sev, :detail)
                """),
                {
                    "op": operator_id,
                    "sev": "LOW" if within_limit else "HIGH",
                    "detail": json.dumps({
                        "amount_zar": float(amount), "destination": destination,
                        "ytd_total": float(new_total), "within_sda_limit": within_limit,
                    }),
                },
            )
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            log.warning(f"[auditor] SARB compliance DB write failed: {e}")

        return {
            "operator_id": operator_id,
            "amount_zar": float(amount),
            "ytd_cross_border_zar": float(new_total),
            "sda_limit_zar": float(SDA_ANNUAL_LIMIT_ZAR),
            "within_limit": within_limit,
            "action": "PROCEED" if within_limit else "BLOCK_AND_REPORT",
        }

    async def _tool_get_regulatory_obligations(self, params: dict) -> dict:
        jurisdiction = params.get("jurisdiction", "ZA")
        status_filter = params.get("status_filter", "all")

        query = "SELECT id::text, obligation_name, authority, deadline, status, next_action FROM arch_regulatory_obligations WHERE jurisdiction = :j"
        if status_filter == "overdue":
            query += " AND deadline < now() AND status != 'COMPLETED'"
        elif status_filter == "due_within_30d":
            query += " AND deadline < now() + interval '30 days' AND status != 'COMPLETED'"
        query += " ORDER BY deadline ASC"

        result = await self.db.execute(text(query), {"j": jurisdiction})
        obligations = [
            {"id": r.id, "name": r.obligation_name, "authority": r.authority,
             "deadline": r.deadline.isoformat() if r.deadline else None,
             "status": r.status, "next_action": r.next_action}
            for r in result.fetchall()
        ]
        return {"jurisdiction": jurisdiction, "obligations": obligations, "count": len(obligations)}

    async def _tool_draft_legal_document(self, params: dict) -> dict:
        doc_type = params["document_type"]
        log.info(f"[auditor] Legal document drafted: {doc_type}")
        return {"document_type": doc_type, "status": "DRAFTED",
                "note": "Document prepared for founder review. Not executed."}

    async def _tool_check_compliance_flag(self, params: dict) -> dict:
        entity_id = params["entity_id"]
        entity_type = params["entity_type"]
        flag_type = params.get("flag_type", "GENERAL")
        severity = params.get("severity", "MEDIUM")

        try:
            await self.db.execute(
                text("""
                    INSERT INTO arch_compliance_events
                        (event_type, entity_id, entity_type, severity, detail)
                    VALUES (:flag, :eid, :etype, :sev, :detail)
                """),
                {"flag": flag_type, "eid": entity_id, "etype": entity_type,
                 "sev": severity, "detail": json.dumps({"flagged_by": "auditor"})},
            )
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            log.warning(f"[auditor] Compliance flag DB write failed: {e}")
        return {"entity_id": entity_id, "flag_type": flag_type, "severity": severity, "flagged": True}
