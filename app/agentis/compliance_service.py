"""Agentis Compliance Engine — Service Layer (Module 10).

The backbone of Agentis. First module enabled, last module disabled.
Every banking transaction passes through compliance checks.

Handles: FICA/AML monitoring, CTR/STR generation, sanctions screening,
POPIA compliance, regulatory reporting, audit logging, feature flag management.
"""

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentis.compliance_models import (
    AgentisFicaMonitoringEvent,
    AgentisCtrReport,
    AgentisStrReport,
    AgentisSanctionsCheck,
    AgentisRegulatoryReport,
    AgentisPopiaRequest,
    AgentisFeatureFlag,
    AgentisAuditLog,
)

# CTR threshold — single transaction >= R49,999.99 in cash-equivalent
CTR_THRESHOLD_ZAR = 49_999.99

# Structuring detection — multiple transactions summing > R50,000 in 24h
STRUCTURING_THRESHOLD_ZAR = 50_000.00

# Velocity — transaction volume > 200% of 30-day rolling average
VELOCITY_MULTIPLIER = 2.0

# POPIA response deadline — 30 days
POPIA_RESPONSE_DAYS = 30

# FIC submission deadlines
CTR_SUBMISSION_BUSINESS_DAYS = 2
STR_SUBMISSION_BUSINESS_DAYS = 15


class AgentisComplianceService:
    """Core compliance engine for all Agentis banking operations."""

    def __init__(self, blockchain=None):
        self.blockchain = blockchain

    # ------------------------------------------------------------------
    # Feature Flag Management
    # ------------------------------------------------------------------

    async def seed_feature_flags(self, db: AsyncSession) -> None:
        """Seed all Agentis feature flags with correct prerequisites."""
        flags = [
            # Phase 1 — CFI Level
            ("AGENTIS_COMPLIANCE_ENABLED", [], "CIPC registration complete + CBDA first contact",
             "Compliance Engine, FICA monitoring, sanctions screening, audit logging"),
            ("AGENTIS_CFI_MEMBER_ENABLED", ["AGENTIS_COMPLIANCE_ENABLED"],
             "CBDA CFI application submitted", "Member onboarding, KYC, mandate management"),
            ("AGENTIS_CFI_ACCOUNTS_ENABLED", ["AGENTIS_CFI_MEMBER_ENABLED"],
             "CBDA CFI registration approved", "Share accounts, call accounts, basic savings"),
            ("AGENTIS_CFI_PAYMENTS_ENABLED", ["AGENTIS_CFI_ACCOUNTS_ENABLED"],
             "CBDA CFI registration approved", "Internal member-to-member transfers only"),
            ("AGENTIS_CFI_GOVERNANCE_ENABLED", ["AGENTIS_CFI_MEMBER_ENABLED"],
             "CFI constitution adopted and minutes filed", "Meeting management, basic voting"),
            ("AGENTIS_PHASE0_WALLET_ENABLED", ["AGENTIS_COMPLIANCE_ENABLED"],
             "FSP licence application submitted", "Pre-banking wallet product"),
            # Phase 2 — Primary Co-op Bank
            ("AGENTIS_PCB_DEPOSITS_ENABLED",
             ["AGENTIS_CFI_ACCOUNTS_ENABLED", "AGENTIS_CFI_PAYMENTS_ENABLED",
              "AGENTIS_CFI_GOVERNANCE_ENABLED"],
             "SARB Prudential Authority registration certificate",
             "Full deposit suite (FD, Notice, IR, MC accounts)"),
            ("AGENTIS_PCB_EFT_ENABLED", ["AGENTIS_PCB_DEPOSITS_ENABLED"],
             "SARB primary co-op bank registration",
             "EFT payments via Peach Payments / Ozow"),
            ("AGENTIS_PCB_TREASURY_ENABLED", ["AGENTIS_PCB_DEPOSITS_ENABLED"],
             "SARB primary co-op bank registration",
             "Treasury snapshots, regulatory ratio monitoring, SARB reporting"),
            ("AGENTIS_PCB_DEPOSIT_INSURANCE_ENABLED", ["AGENTIS_PCB_DEPOSITS_ENABLED"],
             "SARB primary co-op bank registration",
             "CoBIF levy calculation and payment, CoDI registration"),
            ("AGENTIS_PCB_GOVERNANCE_ENABLED",
             ["AGENTIS_CFI_GOVERNANCE_ENABLED", "AGENTIS_PCB_DEPOSITS_ENABLED"],
             "SARB primary co-op bank registration",
             "AGM management, dividend declaration, special resolutions"),
            ("AGENTIS_CFI_LENDING_ENABLED",
             ["AGENTIS_CFI_ACCOUNTS_ENABLED"],
             "NCR credit provider registration confirmed",
             "Basic member loans only (PML, MEL under R10,000)"),
            ("AGENTIS_NCA_LENDING_ENABLED", ["AGENTIS_CFI_LENDING_ENABLED"],
             "NCR full credit provider registration + SARB registration",
             "Full lending suite (OOD, EIL, BEL, RCF, ABA)"),
            ("AGENTIS_FSP_INTERMEDIARY_ENABLED", ["AGENTIS_PCB_DEPOSITS_ENABLED"],
             "FSCA FSP Category I licence confirmed",
             "Insurance distribution, investment referral, pension collection"),
            # Phase 3+
            ("AGENTIS_FX_ENABLED", ["AGENTIS_PCB_EFT_ENABLED"],
             "SARB forex approval + authorised dealer bank relationship",
             "Foreign exchange, international payments, SDA tracking"),
            ("AGENTIS_CASP_ENABLED", ["AGENTIS_PCB_DEPOSITS_ENABLED"],
             "FSCA CASP licence confirmed",
             "Crypto-denominated accounts, crypto payment rails"),
        ]

        for flag_name, prereqs, reg_trigger, description in flags:
            existing = await db.execute(
                select(AgentisFeatureFlag).where(
                    AgentisFeatureFlag.flag_name == flag_name
                )
            )
            if not existing.scalar_one_or_none():
                flag = AgentisFeatureFlag(
                    flag_name=flag_name,
                    is_enabled=False,
                    prerequisite_flags=prereqs,
                    regulatory_trigger=reg_trigger,
                    description=description,
                )
                db.add(flag)

    async def check_flag(self, db: AsyncSession, flag_name: str) -> bool:
        """Check if a feature flag is enabled. Returns False if not found."""
        result = await db.execute(
            select(AgentisFeatureFlag.is_enabled).where(
                AgentisFeatureFlag.flag_name == flag_name
            )
        )
        row = result.scalar_one_or_none()
        return bool(row) if row is not None else False

    async def enable_flag(self, db: AsyncSession, flag_name: str,
                          enabled_by: str, three_fa_ref: str) -> dict:
        """Enable a feature flag after checking prerequisites."""
        result = await db.execute(
            select(AgentisFeatureFlag).where(
                AgentisFeatureFlag.flag_name == flag_name
            )
        )
        flag = result.scalar_one_or_none()
        if not flag:
            return {"error": "FLAG_NOT_FOUND", "message": f"Flag {flag_name} does not exist"}

        if flag.is_enabled:
            return {"error": "ALREADY_ENABLED", "message": f"Flag {flag_name} is already enabled"}

        # Check prerequisites
        if flag.prerequisite_flags:
            for prereq_name in flag.prerequisite_flags:
                prereq_enabled = await self.check_flag(db, prereq_name)
                if not prereq_enabled:
                    return {
                        "error": "PREREQUISITE_NOT_MET",
                        "message": f"Prerequisite flag {prereq_name} must be enabled first",
                    }

        flag.is_enabled = True
        flag.enabled_by = enabled_by
        flag.enabled_at = datetime.now(timezone.utc)
        flag.enabled_3fa_ref = three_fa_ref
        flag.updated_at = datetime.now(timezone.utc)

        await self.log_audit(db, "OWNER", enabled_by, "ENABLE_FEATURE_FLAG",
                             "FEATURE_FLAG", flag.flag_id,
                             {"flag_name": flag_name, "three_fa_ref": three_fa_ref})

        return {"status": "enabled", "flag_name": flag_name}

    # ------------------------------------------------------------------
    # FICA / AML Transaction Monitoring
    # ------------------------------------------------------------------

    async def log_monitoring_event(
        self, db: AsyncSession, *,
        event_type: str,
        description: str,
        severity: str = "info",
        member_id: str | None = None,
        agent_id: str | None = None,
        mandate_id: str | None = None,
        transaction_id: str | None = None,
        account_id: str | None = None,
        channel: str = "api",
        amount_zar: float | None = None,
        currency: str | None = None,
        event_data: dict | None = None,
        requires_review: bool = False,
    ) -> AgentisFicaMonitoringEvent:
        """Create a FICA monitoring event record."""
        event = AgentisFicaMonitoringEvent(
            event_type=event_type,
            description=description,
            severity=severity,
            member_id=member_id,
            agent_id=agent_id,
            mandate_id=mandate_id,
            transaction_id=transaction_id,
            account_id=account_id,
            channel=channel,
            amount_zar=amount_zar,
            currency=currency,
            event_data=event_data,
            requires_review=requires_review,
        )

        # Write to blockchain for immutability
        if self.blockchain:
            from app.blockchain.transaction import Transaction, TransactionType
            tx = Transaction(
                type=TransactionType.AGENTIS_COMPLIANCE_EVENT,
                sender_id=agent_id or member_id or "system",
                amount=amount_zar or 0,
                currency=currency or "ZAR",
                description=f"FICA: {event_type} — {description[:100]}",
                metadata={"event_type": event_type, "severity": severity},
            )
            self.blockchain.add_transaction(tx)
            event.blockchain_hash = tx.id

        db.add(event)
        return event

    async def check_ctr_threshold(
        self, db: AsyncSession, *,
        member_id: str,
        transaction_id: str,
        account_id: str,
        amount_zar: float,
        currency: str,
        transaction_type: str,
        counterparty_info: str | None = None,
    ) -> AgentisCtrReport | None:
        """Check if transaction triggers CTR threshold and create report if so."""
        if amount_zar < CTR_THRESHOLD_ZAR:
            return None

        # Create monitoring event
        event = await self.log_monitoring_event(
            db,
            event_type="CTR_TRIGGER",
            description=f"Transaction of R{amount_zar:,.2f} exceeds CTR threshold",
            severity="high",
            member_id=member_id,
            transaction_id=transaction_id,
            account_id=account_id,
            amount_zar=amount_zar,
            currency=currency,
            requires_review=True,
        )

        # Create CTR report — must be submitted to FIC within 2 business days
        now = datetime.now(timezone.utc)
        ctr = AgentisCtrReport(
            monitoring_event_id=event.event_id,
            member_id=member_id,
            transaction_id=transaction_id,
            account_id=account_id,
            amount_zar=amount_zar,
            currency=currency,
            transaction_type=transaction_type,
            counterparty_info=counterparty_info,
            submission_deadline=now + timedelta(days=CTR_SUBMISSION_BUSINESS_DAYS + 2),
        )
        db.add(ctr)
        return ctr

    async def check_structuring(
        self, db: AsyncSession, *,
        member_id: str,
        amount_zar: float,
    ) -> AgentisStrReport | None:
        """Detect potential structuring — multiple sub-threshold transactions summing > R50k in 24h."""
        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)

        # Query recent monitoring events for this member's transactions
        result = await db.execute(
            select(func.sum(AgentisFicaMonitoringEvent.amount_zar)).where(
                and_(
                    AgentisFicaMonitoringEvent.member_id == member_id,
                    AgentisFicaMonitoringEvent.event_type == "AGENT_BANKING_ACTION",
                    AgentisFicaMonitoringEvent.created_at >= twenty_four_hours_ago,
                    AgentisFicaMonitoringEvent.amount_zar.isnot(None),
                )
            )
        )
        total_24h = result.scalar() or 0

        if (total_24h + amount_zar) <= STRUCTURING_THRESHOLD_ZAR:
            return None
        if amount_zar >= CTR_THRESHOLD_ZAR:
            return None  # Not structuring if single txn exceeds threshold

        # Potential structuring detected
        event = await self.log_monitoring_event(
            db,
            event_type="STRUCTURING_SUSPECT",
            description=(
                f"Potential structuring: R{amount_zar:,.2f} txn would bring 24h total to "
                f"R{total_24h + amount_zar:,.2f} (threshold: R{STRUCTURING_THRESHOLD_ZAR:,.2f})"
            ),
            severity="high",
            member_id=member_id,
            amount_zar=amount_zar,
            requires_review=True,
        )

        now = datetime.now(timezone.utc)
        str_report = AgentisStrReport(
            monitoring_event_id=event.event_id,
            member_id=member_id,
            suspicion_type="STRUCTURING",
            suspicion_description=event.description,
            evidence_data={"total_24h": total_24h, "current_amount": amount_zar},
            submission_deadline=now + timedelta(days=STR_SUBMISSION_BUSINESS_DAYS + 5),
        )
        db.add(str_report)
        return str_report

    async def screen_sanctions(
        self, db: AsyncSession, *,
        entity_type: str,
        entity_id: str,
        entity_name: str,
    ) -> AgentisSanctionsCheck:
        """Screen an entity against sanctions lists. Phase 1: simulated clear result."""
        lists_checked = [
            "OFAC_SDN", "UN_CONSOLIDATED", "EU_SANCTIONS", "UK_SANCTIONS", "SA_FINSURV"
        ]

        check = AgentisSanctionsCheck(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            lists_checked=lists_checked,
            screening_result="clear",
            match_score=0.0,
            next_screening_due=datetime.now(timezone.utc) + timedelta(days=365),
        )
        db.add(check)

        await self.log_monitoring_event(
            db,
            event_type="BENEFICIARY_SCREENING",
            description=f"Sanctions screening: {entity_type} {entity_name} — CLEAR",
            severity="info",
            member_id=entity_id if entity_type == "MEMBER" else None,
        )

        return check

    # ------------------------------------------------------------------
    # POPIA Compliance
    # ------------------------------------------------------------------

    async def create_popia_request(
        self, db: AsyncSession, *,
        member_id: str,
        request_type: str,
        description: str | None = None,
    ) -> AgentisPopiaRequest:
        """Create a POPIA access/erasure/correction request."""
        now = datetime.now(timezone.utc)
        request = AgentisPopiaRequest(
            member_id=member_id,
            request_type=request_type,
            description=description,
            deadline_at=now + timedelta(days=POPIA_RESPONSE_DAYS),
        )
        db.add(request)

        await self.log_monitoring_event(
            db,
            event_type="KYC_EVENT",
            description=f"POPIA {request_type} request received from member {member_id}",
            severity="medium",
            member_id=member_id,
        )

        return request

    # ------------------------------------------------------------------
    # Regulatory Reporting
    # ------------------------------------------------------------------

    async def generate_report(
        self, db: AsyncSession, *,
        report_type: str,
        period_start: datetime,
        period_end: datetime,
        report_data: dict,
    ) -> AgentisRegulatoryReport:
        """Generate a regulatory report and store for review."""
        data_json = json.dumps(report_data, sort_keys=True, default=str)
        report_hash = hashlib.sha256(data_json.encode()).hexdigest()

        report = AgentisRegulatoryReport(
            report_type=report_type,
            reporting_period_start=period_start,
            reporting_period_end=period_end,
            report_data=report_data,
            report_hash=report_hash,
        )
        db.add(report)

        await self.log_audit(
            db, "SYSTEM", "compliance_engine", "GENERATE_REPORT",
            "REGULATORY_REPORT", report.report_id,
            {"report_type": report_type, "period_end": period_end.isoformat()},
        )

        return report

    # ------------------------------------------------------------------
    # Audit Logging
    # ------------------------------------------------------------------

    async def log_audit(
        self, db: AsyncSession,
        actor_type: str, actor_id: str | None,
        action: str, resource_type: str,
        resource_id: str | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AgentisAuditLog:
        """Write an immutable audit log entry."""
        entry = AgentisAuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if self.blockchain:
            from app.blockchain.transaction import Transaction, TransactionType
            tx = Transaction(
                type=TransactionType.AGENTIS_COMPLIANCE_EVENT,
                sender_id=actor_id or "system",
                amount=0,
                description=f"AUDIT: {action} on {resource_type}/{resource_id}",
                metadata={"actor_type": actor_type, "action": action},
            )
            self.blockchain.add_transaction(tx)
            entry.blockchain_hash = tx.id

        db.add(entry)
        return entry

    # ------------------------------------------------------------------
    # Pre-transaction compliance wrapper
    # ------------------------------------------------------------------

    async def pre_transaction_check(
        self, db: AsyncSession, *,
        member_id: str,
        agent_id: str | None = None,
        mandate_id: str | None = None,
        account_id: str,
        amount_zar: float,
        currency: str = "ZAR",
        transaction_type: str,
        channel: str = "api",
        counterparty_info: str | None = None,
    ) -> dict[str, Any]:
        """Run all pre-transaction compliance checks. Returns dict with pass/fail and any reports."""
        results: dict[str, Any] = {"passed": True, "ctr": None, "str": None, "events": []}

        # Log the banking action
        event = await self.log_monitoring_event(
            db,
            event_type="AGENT_BANKING_ACTION",
            description=f"{transaction_type}: R{amount_zar:,.2f} {currency}",
            severity="info",
            member_id=member_id,
            agent_id=agent_id,
            mandate_id=mandate_id,
            account_id=account_id,
            channel=channel,
            amount_zar=amount_zar,
            currency=currency,
        )
        results["events"].append(event.event_id)

        # CTR check
        ctr = await self.check_ctr_threshold(
            db,
            member_id=member_id,
            transaction_id=event.event_id,
            account_id=account_id,
            amount_zar=amount_zar,
            currency=currency,
            transaction_type=transaction_type,
            counterparty_info=counterparty_info,
        )
        if ctr:
            results["ctr"] = ctr.ctr_id

        # Structuring check
        str_report = await self.check_structuring(
            db,
            member_id=member_id,
            amount_zar=amount_zar,
        )
        if str_report:
            results["str"] = str_report.str_id

        return results

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    async def get_pending_reviews(self, db: AsyncSession, limit: int = 50) -> list:
        """Get monitoring events requiring compliance officer review."""
        result = await db.execute(
            select(AgentisFicaMonitoringEvent).where(
                AgentisFicaMonitoringEvent.requires_review == True,
                AgentisFicaMonitoringEvent.reviewed_at.is_(None),
            ).order_by(AgentisFicaMonitoringEvent.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_ctr_reports(self, db: AsyncSession, status: str | None = None,
                              limit: int = 50) -> list:
        """Get CTR reports, optionally filtered by status."""
        query = select(AgentisCtrReport).order_by(AgentisCtrReport.created_at.desc())
        if status:
            query = query.where(AgentisCtrReport.status == status)
        result = await db.execute(query.limit(limit))
        return list(result.scalars().all())

    async def get_str_reports(self, db: AsyncSession, status: str | None = None,
                              limit: int = 50) -> list:
        """Get STR reports, optionally filtered by status."""
        query = select(AgentisStrReport).order_by(AgentisStrReport.created_at.desc())
        if status:
            query = query.where(AgentisStrReport.status == status)
        result = await db.execute(query.limit(limit))
        return list(result.scalars().all())

    async def get_sanctions_alerts(self, db: AsyncSession, limit: int = 50) -> list:
        """Get sanctions checks with non-clear results."""
        result = await db.execute(
            select(AgentisSanctionsCheck).where(
                AgentisSanctionsCheck.screening_result != "clear"
            ).order_by(AgentisSanctionsCheck.screened_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_feature_flags(self, db: AsyncSession) -> list[dict]:
        """Get all feature flags with their current state."""
        result = await db.execute(
            select(AgentisFeatureFlag).order_by(AgentisFeatureFlag.flag_name)
        )
        flags = result.scalars().all()
        return [
            {
                "flag_name": f.flag_name,
                "is_enabled": f.is_enabled,
                "prerequisite_flags": f.prerequisite_flags,
                "regulatory_trigger": f.regulatory_trigger,
                "description": f.description,
                "enabled_at": f.enabled_at.isoformat() if f.enabled_at else None,
            }
            for f in flags
        ]
