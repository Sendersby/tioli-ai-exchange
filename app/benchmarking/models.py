"""Agent Benchmarking & Evaluation Service models.

Build Brief V2, Module 7: Independent evaluation by verified evaluator agents.
Commission: 15% of R1,200 benchmark fee. 85% to evaluator operator.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Integer, Text, JSON

from app.database.db import Base

BENCHMARK_REPORT_FEE_ZAR = 1200.0
BENCHMARK_COMMISSION_PCT = 0.15  # 15%


class EvaluationAgent(Base):
    __tablename__ = "evaluation_agents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False, unique=True)
    operator_id = Column(String, nullable=False)
    specialisation_domains = Column(JSON, nullable=False)
    methodology_description = Column(Text, nullable=False)
    price_per_evaluation = Column(Float, nullable=False, default=BENCHMARK_REPORT_FEE_ZAR)
    avg_turnaround_hours = Column(Integer, nullable=False, default=48)
    evaluations_completed = Column(Integer, default=0)
    meta_reputation_score = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class BenchmarkReport(Base):
    __tablename__ = "benchmark_reports"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluator_id = Column(String, nullable=False)
    subject_agent_id = Column(String, nullable=False)
    comparison_agent_id = Column(String, nullable=True)
    report_type = Column(String(30), nullable=False)  # single|comparative|sector_ranking
    task_category = Column(String(100), nullable=False)
    test_suite_ref = Column(String(64), nullable=False)
    scores = Column(JSON, nullable=False)
    overall_score = Column(Float, nullable=False)
    summary = Column(Text, nullable=False)
    full_report_hash = Column(String(64), nullable=False)
    is_public = Column(Boolean, default=True)
    commissioned_by_operator_id = Column(String, nullable=True)
    price_paid = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
