"""Agentis Compliance Engine — Database Models (Module 10).

FICA/AML monitoring, sanctions screening, CTR/STR reports, POPIA compliance,
regulatory reporting. This module MUST be enabled before any other Agentis module.

ADDITIVE ONLY. No existing tables modified.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Float, String, Boolean, Integer, Text,
    ForeignKey, Index, JSON,
)

from app.database.db import Base


# ---------------------------------------------------------------------------
# FICA / AML Transaction Monitoring
# ---------------------------------------------------------------------------

class AgentisFicaMonitoringEvent(Base):
    """Every banking action by an agent or flagged transaction creates an event."""
    __tablename__ = "agentis_fica_monitoring_events"

    event_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    member_id = Column(String, ForeignKey("agentis_members.member_id"), nullable=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    mandate_id = Column(String, nullable=True)
    transaction_id = Column(String, nullable=True)
    account_id = Column(String, nullable=True)

    event_type = Column(String(50), nullable=False)
    # Types: AGENT_BANKING_ACTION, CTR_TRIGGER, STR_TRIGGER, STRUCTURING_SUSPECT,
    #        SANCTIONS_HIT, DORMANT_ACTIVATION, VELOCITY_BREACH, MANDATE_BREACH,
    #        PEP_FLAG, BENEFICIARY_SCREENING, KYC_EVENT, FRAUD_ALERT

    severity = Column(String(20), nullable=False, default="info")
    # info, low, medium, high, critical

    channel = Column(String(30), nullable=False, default="api")
    # api, dashboard, mcp, agent_autonomous, system, scheduled

    description = Column(Text, nullable=False)
    event_data = Column(JSON, nullable=True)

    amount_zar = Column(Float, nullable=True)
    currency = Column(String(10), nullable=True)

    requires_review = Column(Boolean, nullable=False, default=False)
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_outcome = Column(String(50), nullable=True)
    # cleared, escalated, reported_to_fic, false_positive

    blockchain_hash = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_fica_events_member", "member_id"),
        Index("ix_fica_events_agent", "agent_id"),
        Index("ix_fica_events_type", "event_type"),
        Index("ix_fica_events_severity", "severity"),
        Index("ix_fica_events_review", "requires_review"),
        Index("ix_fica_events_created", "created_at"),
    )


class AgentisCtrReport(Base):
    """Currency Transaction Report — auto-generated for transactions >= R49,999.99."""
    __tablename__ = "agentis_ctr_reports"

    ctr_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    monitoring_event_id = Column(String, ForeignKey("agentis_fica_monitoring_events.event_id"),
                                 nullable=False)
    member_id = Column(String, nullable=False)
    transaction_id = Column(String, nullable=False)
    account_id = Column(String, nullable=False)

    amount_zar = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False, default="ZAR")
    transaction_type = Column(String(40), nullable=False)
    counterparty_info = Column(Text, nullable=True)

    # FIC submission tracking
    goaml_reference = Column(String(100), nullable=True)
    submitted_to_fic = Column(Boolean, nullable=False, default=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    submission_deadline = Column(DateTime(timezone=True), nullable=True)
    # Must submit within 2 business days

    status = Column(String(20), nullable=False, default="pending")
    # pending, submitted, acknowledged, queried

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_ctr_member", "member_id"),
        Index("ix_ctr_status", "status"),
    )


class AgentisStrReport(Base):
    """Suspicious Transaction Report — pattern-based detection."""
    __tablename__ = "agentis_str_reports"

    str_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    monitoring_event_id = Column(String, ForeignKey("agentis_fica_monitoring_events.event_id"),
                                 nullable=False)
    member_id = Column(String, nullable=False)

    suspicion_type = Column(String(50), nullable=False)
    # STRUCTURING, UNUSUAL_PATTERN, GEOGRAPHY_ANOMALY, ROUND_NUMBER,
    # VELOCITY_ANOMALY, SANCTIONS_PROXIMITY, DORMANT_REACTIVATION

    suspicion_description = Column(Text, nullable=False)
    evidence_data = Column(JSON, nullable=True)
    related_transaction_ids = Column(JSON, nullable=True)

    # Review workflow
    assigned_to = Column(String, nullable=True)  # FICA compliance officer
    investigation_notes = Column(Text, nullable=True)
    confirmed_suspicious = Column(Boolean, nullable=True)

    # FIC submission
    goaml_reference = Column(String(100), nullable=True)
    submitted_to_fic = Column(Boolean, nullable=False, default=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    submission_deadline = Column(DateTime(timezone=True), nullable=True)
    # Must submit within 15 business days if confirmed

    status = Column(String(20), nullable=False, default="pending_review")
    # pending_review, under_investigation, confirmed, false_positive, submitted, closed

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_str_member", "member_id"),
        Index("ix_str_status", "status"),
        Index("ix_str_type", "suspicion_type"),
    )


class AgentisSanctionsCheck(Base):
    """Sanctions/PEP screening records for members and beneficiaries."""
    __tablename__ = "agentis_sanctions_checks"

    check_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type = Column(String(20), nullable=False)
    # MEMBER, BENEFICIARY, COUNTERPARTY

    entity_id = Column(String, nullable=False)
    entity_name = Column(String(200), nullable=False)

    # Screening details
    lists_checked = Column(JSON, nullable=False)
    # ["OFAC_SDN", "UN_CONSOLIDATED", "EU_SANCTIONS", "UK_SANCTIONS", "SA_FINSURV"]

    screening_result = Column(String(30), nullable=False, default="pending")
    # pending, clear, partial_match, confirmed_match, error

    match_details = Column(JSON, nullable=True)
    match_score = Column(Float, nullable=True)  # 0.0-1.0 confidence

    # Review
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_decision = Column(String(30), nullable=True)
    # cleared, blocked, escalated

    is_pep = Column(Boolean, nullable=False, default=False)
    pep_category = Column(String(50), nullable=True)
    # DOMESTIC_PEP, FOREIGN_PEP, INTERNATIONAL_ORG, FAMILY_ASSOCIATE

    screened_at = Column(DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(timezone.utc))
    next_screening_due = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_sanctions_entity", "entity_type", "entity_id"),
        Index("ix_sanctions_result", "screening_result"),
    )


class AgentisRegulatoryReport(Base):
    """Generated regulatory reports (SARB DI returns, FIC reports, CBDA quarterly)."""
    __tablename__ = "agentis_regulatory_reports"

    report_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    report_type = Column(String(30), nullable=False)
    # DI100, DI200, DI300, DI400, DI500, FIC_MONTHLY, CBDA_QUARTERLY,
    # EXCHANGE_CONTROL, NCR_QUARTERLY

    reporting_period_start = Column(DateTime(timezone=True), nullable=False)
    reporting_period_end = Column(DateTime(timezone=True), nullable=False)

    report_data = Column(JSON, nullable=False)
    report_hash = Column(String(64), nullable=False)  # SHA256 for integrity

    # Submission tracking
    generated_at = Column(DateTime(timezone=True), nullable=False,
                          default=lambda: datetime.now(timezone.utc))
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    submitted_to = Column(String(50), nullable=True)
    # SARB, FIC, CBDA, NCR, FINSURV
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    submission_reference = Column(String(100), nullable=True)

    status = Column(String(20), nullable=False, default="generated")
    # generated, under_review, approved, submitted, acknowledged

    __table_args__ = (
        Index("ix_reg_reports_type", "report_type"),
        Index("ix_reg_reports_period", "reporting_period_end"),
        Index("ix_reg_reports_status", "status"),
    )


class AgentisPopiaRequest(Base):
    """POPIA access and erasure requests from members."""
    __tablename__ = "agentis_popia_requests"

    request_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    member_id = Column(String, nullable=False)

    request_type = Column(String(20), nullable=False)
    # ACCESS, ERASURE, CORRECTION, OBJECTION

    description = Column(Text, nullable=True)

    # Processing
    status = Column(String(20), nullable=False, default="received")
    # received, processing, completed, partially_completed, rejected

    data_compiled = Column(Boolean, nullable=False, default=False)
    data_export_path = Column(String(500), nullable=True)

    # For erasure: track what can/cannot be erased
    erasable_records = Column(JSON, nullable=True)
    retained_records = Column(JSON, nullable=True)
    # Records retained for FICA (5yr) or tax (7yr) legal obligation
    retention_reason = Column(Text, nullable=True)

    # Deadlines: POPIA requires response within 30 days
    received_at = Column(DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(timezone.utc))
    deadline_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_popia_member", "member_id"),
        Index("ix_popia_status", "status"),
    )


class AgentisFeatureFlag(Base):
    """Runtime feature flag state with audit trail."""
    __tablename__ = "agentis_feature_flags"

    flag_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    flag_name = Column(String(60), unique=True, nullable=False)
    is_enabled = Column(Boolean, nullable=False, default=False)
    prerequisite_flags = Column(JSON, nullable=True)
    # List of flag names that must be enabled first

    regulatory_trigger = Column(String(200), nullable=True)
    # Description of what regulatory approval enables this flag

    enabled_by = Column(String, nullable=True)
    enabled_at = Column(DateTime(timezone=True), nullable=True)
    enabled_3fa_ref = Column(String(100), nullable=True)

    disabled_by = Column(String, nullable=True)
    disabled_at = Column(DateTime(timezone=True), nullable=True)

    description = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))


class AgentisAuditLog(Base):
    """Immutable audit log for all Agentis administrative actions."""
    __tablename__ = "agentis_audit_log"

    log_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    actor_type = Column(String(20), nullable=False)
    # OWNER, OPERATOR, AGENT, SYSTEM, COMPLIANCE_OFFICER

    actor_id = Column(String, nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String, nullable=True)

    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    blockchain_hash = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_audit_actor", "actor_type", "actor_id"),
        Index("ix_audit_action", "action"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
        Index("ix_audit_created", "created_at"),
    )
