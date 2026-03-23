"""Agentis Member & Agent Identity Infrastructure — Database Models (Module 1).

Cooperative bank member registry, KYC/FICA records, and Agent Banking Mandates.
Every AI agent banking action is governed by an explicit, operator-granted mandate.

ADDITIVE ONLY. No existing tables modified.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Float, String, Boolean, Integer, Text,
    ForeignKey, Index, JSON, CheckConstraint,
)

from app.database.db import Base


class AgentisMember(Base):
    """Cooperative bank member registry — the legal member of the cooperative."""
    __tablename__ = "agentis_members"

    member_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    operator_id = Column(String, ForeignKey("operators.operator_id"), nullable=False)

    member_type = Column(String(20), nullable=False)
    # OPERATOR_ENTITY, INSTITUTIONAL
    # (Agent accounts are sub-accounts — not independent members)

    member_number = Column(String(20), unique=True, nullable=False)
    # Human-readable: AGT-000001

    common_bond_category = Column(String(100), nullable=False,
                                  default="AI_PLATFORM_COMMERCIAL_OPERATOR")
    # Strengthened per Enhancement #4:
    # "Members of the TiOLi AI platform who operate registered AI agents
    #  for commercial purposes"
    common_bond_verified_at = Column(DateTime(timezone=True), nullable=True)

    membership_status = Column(String(20), nullable=False, default="pending")
    # pending, active, suspended, withdrawn, deceased

    kyc_level = Column(String(20), nullable=False, default="none")
    # none, basic, enhanced, full — maps to FICA CDD levels
    kyc_verified_at = Column(DateTime(timezone=True), nullable=True)

    fica_risk_rating = Column(String(10), nullable=False, default="medium")
    # low, medium, high, pep

    share_capital_balance = Column(Float, nullable=False, default=0)
    total_deposits = Column(Float, nullable=False, default=0)
    concentration_pct = Column(Float, nullable=False, default=0)
    # Member deposits as % of total bank deposits — max 0.15

    governance_voting_weight = Column(Float, nullable=False, default=1.0)
    # Always 1 per member (one member, one vote)

    annual_review_due_at = Column(DateTime(timezone=True), nullable=True)
    fatf_watch_flag = Column(Boolean, nullable=False, default=False)
    popia_consent_at = Column(DateTime(timezone=True), nullable=True)

    joined_at = Column(DateTime(timezone=True), nullable=False,
                       default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_members_operator", "operator_id"),
        Index("ix_members_status", "membership_status"),
        Index("ix_members_number", "member_number"),
        CheckConstraint("member_type IN ('OPERATOR_ENTITY', 'INSTITUTIONAL')",
                        name="ck_member_type"),
    )


class AgentisAgentBankingMandate(Base):
    """Agent Banking Mandate — defines what an AI agent can do autonomously.

    Every banking action taken by an AI agent must be governed by an explicit,
    operator-granted mandate. The mandate defines autonomous actions, confirmation
    thresholds, and absolute prohibitions.

    Mandate Levels:
      L0  — View only (balance inquiry, history, statements)
      L1  — Operational (routine payments within limits)
      L2  — Full transactional (all payments + lending within limits)
      L3  — Full banking (all actions within operator parameters)
      L3FA — High value (actions requiring operator 3FA confirmation)
    """
    __tablename__ = "agentis_agent_banking_mandates"

    mandate_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    member_id = Column(String, ForeignKey("agentis_members.member_id"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)

    mandate_level = Column(String(10), nullable=False)
    # L0, L1, L2, L3, L3FA

    # Financial limits
    daily_payment_limit = Column(Float, nullable=False, default=0)
    per_transaction_limit = Column(Float, nullable=False, default=0)
    monthly_limit = Column(Float, nullable=False, default=0)

    # Running totals (reset daily/monthly by scheduled job)
    daily_total_used = Column(Float, nullable=False, default=0)
    monthly_total_used = Column(Float, nullable=False, default=0)
    daily_total_reset_at = Column(DateTime(timezone=True), nullable=True)
    monthly_total_reset_at = Column(DateTime(timezone=True), nullable=True)

    # Capability flags
    loan_application_enabled = Column(Boolean, nullable=False, default=False)
    investment_enabled = Column(Boolean, nullable=False, default=False)
    fx_enabled = Column(Boolean, nullable=False, default=False)
    beneficiary_add_enabled = Column(Boolean, nullable=False, default=False)
    third_party_payments_enabled = Column(Boolean, nullable=False, default=False)
    auto_sweep_enabled = Column(Boolean, nullable=False, default=False)

    # Thresholds
    confirmation_threshold = Column(Float, nullable=False, default=0)
    # Amount above which operator 3FA is required

    # Restrictions
    allowed_currencies = Column(JSON, nullable=False, default=["ZAR"])
    allowed_beneficiary_ids = Column(JSON, nullable=True)
    # NULL = all approved beneficiaries; list = whitelist only
    purpose_restriction = Column(String(200), nullable=True)

    # Validity
    valid_from = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    valid_until = Column(DateTime(timezone=True), nullable=True)
    # NULL = indefinite

    granted_by_operator_at = Column(DateTime(timezone=True), nullable=False,
                                    default=lambda: datetime.now(timezone.utc))
    operator_3fa_ref = Column(String(100), nullable=False)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_mandates_member", "member_id"),
        Index("ix_mandates_agent", "agent_id"),
        Index("ix_mandates_active", "is_active"),
        CheckConstraint("mandate_level IN ('L0','L1','L2','L3','L3FA')",
                        name="ck_mandate_level"),
    )


class AgentisMemberKycRecord(Base):
    """Full FICA-compliant CDD (Customer Due Diligence) records."""
    __tablename__ = "agentis_member_kyc_records"

    kyc_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    member_id = Column(String, ForeignKey("agentis_members.member_id"), nullable=False)

    kyc_level_achieved = Column(String(20), nullable=False)
    # none, basic, enhanced, full

    id_document_type = Column(String(30), nullable=True)
    # SA_ID, PASSPORT, COMPANY_REGISTRATION
    id_document_number = Column(String(50), nullable=True)
    # Encrypted — SA ID number, passport number, or CRN
    id_document_verified_by = Column(String(50), nullable=True)
    # sumsub, onfido, manual_officer
    id_verification_ref = Column(String(100), nullable=True)

    address_verified = Column(Boolean, nullable=False, default=False)

    source_of_funds_declared = Column(Text, nullable=True)
    # Encrypted member SOF declaration
    source_of_funds_verified = Column(Boolean, nullable=False, default=False)

    sanctions_screened_at = Column(DateTime(timezone=True), nullable=True)
    sanctions_result = Column(String(20), nullable=True)
    # clear, match_pending_review, confirmed_match

    edd_required = Column(Boolean, nullable=False, default=False)
    edd_completed_at = Column(DateTime(timezone=True), nullable=True)

    next_review_due = Column(DateTime(timezone=True), nullable=True)
    fica_compliance_officer_id = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_kyc_member", "member_id"),
        Index("ix_kyc_level", "kyc_level_achieved"),
    )
