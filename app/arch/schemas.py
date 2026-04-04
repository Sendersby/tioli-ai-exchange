"""Arch Agent Pydantic schemas — request/response contracts.

All critical Arch Agent endpoints use these schemas for validation.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
import os


class ProposalType(str, Enum):
    OPERATIONAL = "OPERATIONAL_EXPENSE"
    VENDOR = "VENDOR_PAYMENT"
    INVESTMENT = "INVESTMENT"
    CHARITABLE = "CHARITABLE_DISBURSEMENT"
    EMERGENCY = "EMERGENCY"


class FinancialProposalCreate(BaseModel):
    proposal_type: ProposalType
    description: str = Field(..., min_length=20, max_length=500)
    amount_zar: Decimal = Field(..., gt=0, le=Decimal("10000000"))
    amount_crypto: Optional[dict] = None
    justification: str = Field(..., min_length=50, max_length=5000)
    vendor_ref: Optional[str] = None
    urgency: str = Field(
        default="ROUTINE", pattern="^(ROUTINE|URGENT|EMERGENCY)$"
    )

    @field_validator("amount_zar")
    @classmethod
    def check_min_threshold(cls, v):
        min_zar = Decimal(os.getenv("ARCH_MIN_FINANCIAL_PROPOSAL_ZAR", "500"))
        if v < min_zar:
            raise ValueError(f"Amount below minimum threshold of R{min_zar}")
        return v


class FinancialProposalResponse(BaseModel):
    proposal_id: UUID
    status: str
    reserve_floor_zar: Decimal
    total_balance_zar: Decimal
    headroom_zar: Decimal
    ceiling_30d_remaining: Decimal
    would_breach_floor: bool
    would_breach_ceiling: bool
    board_vote_required: bool
    founder_approval_required: bool
    estimated_decision_by: datetime


class BoardConveneRequest(BaseModel):
    session_type: str = Field(
        default="WEEKLY", pattern="^(WEEKLY|EMERGENCY|SPECIAL)$"
    )
    agenda: List[dict] = Field(..., min_length=1)
    urgency: str = "ROUTINE"


class BoardConveneResponse(BaseModel):
    session_id: UUID
    quorum_met: bool
    agents_present: List[str]
    agents_absent: List[str]
    session_status: str
    next_session_at: Optional[datetime] = None


class ArchHealthResponse(BaseModel):
    agent_id: str
    status: str
    model: str
    agent_version: str
    last_heartbeat: Optional[datetime] = None
    tokens_used_month: int
    token_budget: int
    token_pct_used: float
    circuit_breaker: bool
    kpi_pass_rate: Optional[float] = None
    uptime_hours: float = 0.0


class IncidentDeclareRequest(BaseModel):
    severity: str = Field(..., pattern="^(P1|P2|P3|P4)$")
    title: str = Field(..., max_length=200)
    description: str
    popia_notifiable: bool = False
    affected_systems: List[str] = []


class AccountFreezeRequest(BaseModel):
    account_id: str
    account_type: str = Field(..., pattern="^(agent|operator)$")
    reason: str
    incident_ref: Optional[str] = None


class CodeProposalCreate(BaseModel):
    tier: str = Field(..., pattern="^(0|1|2|3)$")
    title: str = Field(..., max_length=200)
    description: str
    rationale: str
    file_changes: list = Field(default_factory=list)


class FounderSubmissionRequest(BaseModel):
    item_type: str = Field(
        ...,
        pattern="^(FINANCIAL_PROPOSAL|DEFER_TO_OWNER|INFORMATION|APPROVAL_REQUEST|EMERGENCY)$",
    )
    priority: str = Field(..., pattern="^(ROUTINE|URGENT|CRITICAL)$")
    subject: str = Field(..., max_length=200)
    situation: str
    options: List[str] = []
    recommendation: Optional[str] = None
    deadline_hours: int = Field(default=24, ge=1, le=168)
