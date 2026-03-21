"""Pipeline models — agent swarms and multi-step orchestration.

Build Brief V2, Module 1: A Pipeline is a pre-assembled, reputation-verified
sequence of agents that collectively completes a multi-step task as a single
purchasable engagement. Client purchases an outcome, not individual agents.

Commission: 10% standard AgentBroker + 2% pipeline surcharge on GEV.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Integer, Text, JSON

from app.database.db import Base

PIPELINE_SURCHARGE_PCT = 0.02  # 2% additional on top of standard commission


class Pipeline(Base):
    """A pre-assembled multi-step agent pipeline."""
    __tablename__ = "agent_pipelines"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    operator_id = Column(String, nullable=False)
    pipeline_name = Column(String(120), nullable=False)
    description = Column(Text, nullable=False)
    capability_tags = Column(JSON, nullable=False)
    pricing_model = Column(String(20), nullable=False)  # fixed|per_task|outcome|auction
    base_price = Column(Float, nullable=True)
    price_currency = Column(String(20), nullable=False, default="TIOLI")
    estimated_duration_hours = Column(Integer, nullable=True)
    reputation_score = Column(Float, default=0.0)
    total_engagements = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PipelineStep(Base):
    """A step within a pipeline, assigned to a specific agent."""
    __tablename__ = "pipeline_steps"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_id = Column(String, nullable=False)
    step_order = Column(Integer, nullable=False)
    agent_id = Column(String, nullable=False)
    step_name = Column(String(120), nullable=False)
    input_spec = Column(JSON, nullable=True)   # what this step receives
    output_spec = Column(JSON, nullable=True)  # what this step must produce
    revenue_share_pct = Column(Float, nullable=False)  # % of pipeline GEV


class PipelineEngagement(Base):
    """An active engagement of a pipeline by a client."""
    __tablename__ = "pipeline_engagements"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_id = Column(String, nullable=False)
    client_operator_id = Column(String, nullable=False)
    status = Column(String(30), default="proposed")  # proposed|active|step_N|completed|cancelled
    gross_value = Column(Float, nullable=False)
    escrow_id = Column(String, nullable=True)
    current_step = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
