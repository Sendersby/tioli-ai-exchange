"""Policy & Guardrail Engine — models.

Per Build Brief v4.0 Section 3.3:
- Operators publish policies that constrain agent actions
- Policy types: MAX_TRANSACTION, PROHIBITED_COUNTERPARTY, REQUIRE_CONFIRMATION_ABOVE, etc.
- ESCALATE_TO_HUMAN path with pending approvals
- Policy check before any financial action
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, ForeignKey, Index
from app.database.db import Base

_uuid = lambda: str(uuid.uuid4())
_now = lambda: datetime.now(timezone.utc)


# Valid policy types
POLICY_TYPES = [
    "MAX_TRANSACTION_VALUE",       # Max amount per single transaction
    "DAILY_TRANSACTION_LIMIT",     # Max total daily spend
    "PROHIBITED_COUNTERPARTY",     # Block transactions with specific agents
    "REQUIRE_CONFIRMATION_ABOVE",  # Escalate to human above threshold
    "CAPABILITY_WHITELIST",        # Only allow specific action types
    "WORKING_HOURS",              # Only transact during specified hours (UTC)
    "MAX_SINGLE_ENGAGEMENT",      # Max value for AgentBroker engagements
]


class AgentPolicy(Base):
    """Operator-defined policy constraining agent actions."""
    __tablename__ = "agent_policies"
    __table_args__ = (
        Index("ix_agent_policy_agent", "agent_id"),
        Index("ix_agent_policy_operator", "operator_id"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    operator_id = Column(String, nullable=False)  # Owner of the policy
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True)  # NULL = applies to all operator's agents
    policy_type = Column(String(50), nullable=False)  # From POLICY_TYPES
    policy_value = Column(JSON, nullable=False)  # Type-specific configuration
    is_active = Column(Boolean, default=True)
    description = Column(String(500), default="")
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class PendingApproval(Base):
    """Action escalated to human for approval."""
    __tablename__ = "pending_approvals"
    __table_args__ = (
        Index("ix_pending_approval_operator", "operator_id"),
        Index("ix_pending_approval_status", "status"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    operator_id = Column(String, nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    action_type = Column(String(50), nullable=False)  # transfer, trade, engagement_fund
    action_params = Column(JSON, nullable=False)  # Full context of the proposed action
    policy_id = Column(String, ForeignKey("agent_policies.id"), nullable=True)  # Policy that triggered escalation
    policy_type = Column(String(50), default="")
    threshold = Column(String(200), default="")  # Human-readable threshold description
    status = Column(String(20), default="PENDING")  # PENDING, APPROVED, REJECTED, EXPIRED
    reviewer_notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_now)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)  # 24-hour timeout


class PolicyAuditLog(Base):
    """Audit log of every policy check — transparency for compliance."""
    __tablename__ = "policy_audit_log"

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, nullable=False, index=True)
    action_type = Column(String(50), nullable=False)
    result = Column(String(20), nullable=False)  # ALLOW, DENY, ESCALATE
    policy_id = Column(String, nullable=True)  # Which policy matched
    policy_type = Column(String(50), default="")
    details = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_now)
