"""Database models for AI agents and their wallets."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database.db import Base


class Agent(Base):
    """An AI agent registered on the TiOLi platform.

    Each agent gets a unique ID, API key for authentication,
    and a wallet for holding tokens/credits.
    """
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    platform = Column(String(255), nullable=False)  # e.g. "OpenAI", "Anthropic", "Custom"
    description = Column(Text, default="")
    api_key_hash = Column(String(255), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    is_approved = Column(Boolean, default=True)  # Owner can revoke
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_active = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    wallets = relationship("Wallet", back_populates="agent", cascade="all, delete-orphan")


class Wallet(Base):
    """A wallet holding a specific currency/token type for an agent.

    Each agent can have multiple wallets — one per currency type.
    """
    __tablename__ = "wallets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    currency = Column(String(50), nullable=False, default="AGENTIS")
    balance = Column(Float, default=0.0, nullable=False)
    frozen_balance = Column(Float, default=0.0, nullable=False)  # Held in pending loans
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    agent = relationship("Agent", back_populates="wallets")

    @property
    def available_balance(self) -> float:
        return self.balance - self.frozen_balance


class Loan(Base):
    """An IOU-based loan between two agents."""
    __tablename__ = "loans"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lender_id = Column(String, ForeignKey("agents.id"), nullable=False)
    borrower_id = Column(String, ForeignKey("agents.id"), nullable=False)
    principal = Column(Float, nullable=False)
    interest_rate = Column(Float, nullable=False)  # e.g. 0.05 for 5%
    currency = Column(String(50), default="AGENTIS")
    amount_repaid = Column(Float, default=0.0)
    status = Column(String(20), default="active")  # active, repaid, defaulted
    issued_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    due_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def total_owed(self) -> float:
        return self.principal * (1 + self.interest_rate)

    @property
    def remaining(self) -> float:
        return self.total_owed - self.amount_repaid
