"""Treasury Agent models — autonomous financial management.

Build Brief V2, Module 4: A Treasury Agent is authorised by its operator
to autonomously manage the operator's credit portfolio — buying, selling,
lending, and allocating credits within operator-defined risk parameters.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Integer, Text, JSON

from app.database.db import Base


class TreasuryAgent(Base):
    """An agent designated as a treasury manager for its operator."""
    __tablename__ = "treasury_agents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False, unique=True)
    operator_id = Column(String, nullable=False)
    status = Column(String(20), default="active")  # active|paused|suspended

    # Risk parameters
    max_single_trade_pct = Column(Float, nullable=False)   # % of portfolio per trade
    max_lending_pct = Column(Float, nullable=False)         # % of portfolio to lend
    min_reserve_pct = Column(Float, nullable=False)          # always keep X% liquid
    buy_threshold = Column(Float, nullable=True)             # buy when price drops below
    sell_threshold = Column(Float, nullable=True)            # sell when price rises above
    approved_currencies = Column(JSON, nullable=False, default=list)
    allowed_actions = Column(JSON, nullable=False, default=list)  # trade, lend, borrow, convert
    execution_interval_minutes = Column(Integer, default=60)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TreasuryAction(Base):
    """Log of all actions taken by a treasury agent."""
    __tablename__ = "treasury_actions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    treasury_id = Column(String, nullable=False)
    action_type = Column(String(30), nullable=False)  # trade_buy, trade_sell, lend, convert, rebalance
    rationale = Column(Text, nullable=False)           # AI-generated explanation
    amount = Column(Float, nullable=True)
    currency = Column(String(20), nullable=True)
    result_status = Column(String(20), nullable=True)  # success, failed, skipped
    transaction_id = Column(String, nullable=True)
    executed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
