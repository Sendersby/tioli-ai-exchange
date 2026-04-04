"""Transaction models for the TiOLi blockchain ledger."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    """All supported transaction types on the platform."""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    TRADE = "trade"
    LOAN_ISSUE = "loan_issue"
    LOAN_REPAYMENT = "loan_repayment"
    COMMISSION_DEDUCTION = "commission_deduction"
    CHARITY_DEDUCTION = "charity_deduction"
    AGENT_REGISTRATION = "agent_registration"
    # Agentis Cooperative Bank transaction types
    AGENTIS_ACCOUNT_OPEN = "agentis_account_open"
    AGENTIS_DEPOSIT = "agentis_deposit"
    AGENTIS_WITHDRAWAL = "agentis_withdrawal"
    AGENTIS_TRANSFER_INTERNAL = "agentis_transfer_internal"
    AGENTIS_TRANSFER_EXTERNAL = "agentis_transfer_external"
    AGENTIS_INTEREST_CREDIT = "agentis_interest_credit"
    AGENTIS_FEE_DEBIT = "agentis_fee_debit"
    AGENTIS_MEMBER_JOIN = "agentis_member_join"
    AGENTIS_MANDATE_GRANT = "agentis_mandate_grant"
    AGENTIS_MANDATE_REVOKE = "agentis_mandate_revoke"
    AGENTIS_KYC_VERIFICATION = "agentis_kyc_verification"
    AGENTIS_COMPLIANCE_EVENT = "agentis_compliance_event"
    AGENTIS_STANDING_ORDER = "agentis_standing_order"
    AGENTIS_CHARITABLE_ALLOCATION = "agentis_charitable_allocation"
    AGENTIS_MEMBERSHIP_FEE = "agentis_membership_fee"
    AGENTIS_GOVERNANCE_VOTE = "agentis_governance_vote"
    AGENTIS_DIVIDEND_PAYMENT = "agentis_dividend_payment"
    # AGENTIS DAP v0.5.1 transaction types
    DELIVERABLE_HASH = "deliverable_hash"
    DISPUTE_DEPOSIT = "dispute_deposit"
    DISPUTE_RESOLVED = "dispute_resolved"
    ARBITER_RATING = "arbiter_rating"
    DEPOSIT_FORFEITED = "deposit_forfeited"
    DEPOSIT_RETURNED = "deposit_returned"
    AUTO_FINALIZED = "auto_finalized"
    TOKEN_PURCHASE = "token_purchase"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REVERSED = "reversed"


class Transaction(BaseModel):
    """A single transaction recorded on the TiOLi blockchain.

    Every action that moves value — deposits, trades, loans, fees —
    is captured as a Transaction with full traceability.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: TransactionType
    sender_id: str | None = None  # None for deposits (external source)
    receiver_id: str | None = None  # None for withdrawals (external dest)
    amount: float = Field(ge=0)  # >= 0; registrations and system events use 0
    currency: str = "AGENTIS"  # Platform native token
    status: TransactionStatus = TransactionStatus.PENDING
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Fee tracking — every transaction records what was deducted
    founder_commission: float = 0.0
    charity_fee: float = 0.0

    def to_ledger_entry(self) -> dict[str, Any]:
        """Convert to a dictionary suitable for blockchain storage."""
        return self.model_dump()
