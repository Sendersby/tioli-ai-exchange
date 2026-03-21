"""Benchmarking service — evaluator registration, report commissioning, leaderboard."""

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.benchmarking.models import (
    EvaluationAgent, BenchmarkReport, BENCHMARK_REPORT_FEE_ZAR, BENCHMARK_COMMISSION_PCT,
)

logger = logging.getLogger(__name__)


class BenchmarkingService:
    async def register_evaluator(
        self, db: AsyncSession, agent_id: str, operator_id: str,
        specialisation_domains: list[str], methodology_description: str,
        price_per_evaluation: float = BENCHMARK_REPORT_FEE_ZAR,
        avg_turnaround_hours: int = 48,
    ) -> dict:
        existing = await db.execute(
            select(EvaluationAgent).where(EvaluationAgent.agent_id == agent_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent already registered as evaluator")

        evaluator = EvaluationAgent(
            agent_id=agent_id, operator_id=operator_id,
            specialisation_domains=specialisation_domains,
            methodology_description=methodology_description,
            price_per_evaluation=price_per_evaluation,
            avg_turnaround_hours=avg_turnaround_hours,
        )
        db.add(evaluator)
        await db.flush()

        return {
            "evaluator_id": evaluator.id, "agent_id": agent_id,
            "domains": specialisation_domains,
            "price": price_per_evaluation,
            "commission_pct": f"{BENCHMARK_COMMISSION_PCT*100:.0f}%",
        }

    async def commission_report(
        self, db: AsyncSession, evaluator_id: str,
        subject_agent_id: str, task_category: str,
        commissioned_by_operator_id: str,
        report_type: str = "single",
        comparison_agent_id: str | None = None,
    ) -> dict:
        eval_result = await db.execute(
            select(EvaluationAgent).where(EvaluationAgent.id == evaluator_id)
        )
        evaluator = eval_result.scalar_one_or_none()
        if not evaluator or not evaluator.is_active:
            raise ValueError("Evaluator not found or inactive")

        price = evaluator.price_per_evaluation
        platform_fee = round(price * BENCHMARK_COMMISSION_PCT, 2)

        # Placeholder report — evaluator will submit scores later
        test_suite_ref = hashlib.sha256(
            f"{evaluator_id}:{subject_agent_id}:{task_category}:{datetime.now(timezone.utc)}".encode()
        ).hexdigest()

        report = BenchmarkReport(
            evaluator_id=evaluator_id,
            subject_agent_id=subject_agent_id,
            comparison_agent_id=comparison_agent_id,
            report_type=report_type,
            task_category=task_category,
            test_suite_ref=test_suite_ref,
            scores={},  # Populated by evaluator
            overall_score=0.0,
            summary="Evaluation pending",
            full_report_hash="",
            commissioned_by_operator_id=commissioned_by_operator_id,
            price_paid=price,
        )
        db.add(report)
        await db.flush()

        return {
            "report_id": report.id, "evaluator_id": evaluator_id,
            "subject_agent_id": subject_agent_id,
            "report_type": report_type,
            "price_paid": price, "platform_fee": platform_fee,
            "evaluator_receives": round(price - platform_fee, 2),
            "status": "pending",
        }

    async def get_report(self, db: AsyncSession, report_id: str) -> dict | None:
        result = await db.execute(
            select(BenchmarkReport).where(BenchmarkReport.id == report_id)
        )
        report = result.scalar_one_or_none()
        if not report:
            return None
        return {
            "report_id": report.id, "evaluator_id": report.evaluator_id,
            "subject_agent_id": report.subject_agent_id,
            "report_type": report.report_type,
            "task_category": report.task_category,
            "scores": report.scores, "overall_score": report.overall_score,
            "summary": report.summary,
            "full_report_hash": report.full_report_hash,
            "is_public": report.is_public,
            "price_paid": report.price_paid,
            "created_at": str(report.created_at),
        }

    async def search_reports(
        self, db: AsyncSession, agent_id: str | None = None,
        task_category: str | None = None, min_score: float | None = None,
        limit: int = 50,
    ) -> list[dict]:
        query = select(BenchmarkReport).where(BenchmarkReport.is_public == True)
        if agent_id:
            query = query.where(BenchmarkReport.subject_agent_id == agent_id)
        if task_category:
            query = query.where(BenchmarkReport.task_category == task_category)
        if min_score is not None:
            query = query.where(BenchmarkReport.overall_score >= min_score)
        query = query.order_by(BenchmarkReport.overall_score.desc()).limit(limit)

        result = await db.execute(query)
        return [
            {
                "report_id": r.id, "subject_agent_id": r.subject_agent_id,
                "task_category": r.task_category,
                "overall_score": r.overall_score, "summary": r.summary[:200],
            }
            for r in result.scalars().all()
        ]

    async def get_leaderboard(self, db: AsyncSession, task_category: str | None = None, limit: int = 20) -> list[dict]:
        query = select(BenchmarkReport).where(
            BenchmarkReport.is_public == True,
            BenchmarkReport.overall_score > 0,
        )
        if task_category:
            query = query.where(BenchmarkReport.task_category == task_category)
        query = query.order_by(BenchmarkReport.overall_score.desc()).limit(limit)

        result = await db.execute(query)
        return [
            {
                "rank": i + 1,
                "agent_id": r.subject_agent_id,
                "task_category": r.task_category,
                "overall_score": r.overall_score,
                "report_id": r.id,
            }
            for i, r in enumerate(result.scalars().all())
        ]
