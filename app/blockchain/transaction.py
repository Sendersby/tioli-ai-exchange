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
    currency: str = "TIOLI"  # Platform native token
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
