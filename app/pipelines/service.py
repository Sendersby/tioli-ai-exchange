"""Pipeline service — creation, engagement, step advancement, and settlement.

Build Brief V2, Module 1: Commission = 10% AgentBroker + 2% pipeline surcharge.
Settlement at each milestone distributes revenue to member agents per share.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.pipelines.models import (
    Pipeline, PipelineStep, PipelineEngagement, PIPELINE_SURCHARGE_PCT,
)
from app.agents.models import Agent

logger = logging.getLogger(__name__)


class PipelineService:
    """Manages pipeline creation, engagement, and step-by-step execution."""

    async def create_pipeline(
        self, db: AsyncSession, operator_id: str,
        pipeline_name: str, description: str,
        capability_tags: list[str], steps: list[dict],
        pricing_model: str = "fixed", base_price: float | None = None,
        price_currency: str = "TIOLI",
        estimated_duration_hours: int | None = None,
    ) -> dict:
        """Create a new pipeline. Validate revenue shares sum to 100%."""
        if not steps:
            raise ValueError("Pipeline must have at least one step")

        total_share = sum(s.get("revenue_share_pct", 0) for s in steps)
        if abs(total_share - 100.0) > 0.01:
            raise ValueError(f"Revenue shares must sum to 100%. Current total: {total_share}%")

        valid_models = {"fixed", "per_task", "outcome", "auction"}
        if pricing_model not in valid_models:
            raise ValueError(f"Invalid pricing model. Allowed: {valid_models}")

        pipeline = Pipeline(
            operator_id=operator_id,
            pipeline_name=pipeline_name,
            description=description,
            capability_tags=capability_tags,
            pricing_model=pricing_model,
            base_price=base_price,
            price_currency=price_currency,
            estimated_duration_hours=estimated_duration_hours,
        )
        db.add(pipeline)
        await db.flush()

        # Create steps
        for i, step_data in enumerate(steps, 1):
            step = PipelineStep(
                pipeline_id=pipeline.id,
                step_order=i,
                agent_id=step_data["agent_id"],
                step_name=step_data["step_name"],
                input_spec=step_data.get("input_spec"),
                output_spec=step_data.get("output_spec"),
                revenue_share_pct=step_data["revenue_share_pct"],
            )
            db.add(step)

        await db.flush()

        return {
            "pipeline_id": pipeline.id,
            "pipeline_name": pipeline_name,
            "steps": len(steps),
            "pricing_model": pricing_model,
            "base_price": base_price,
            "surcharge_pct": f"{PIPELINE_SURCHARGE_PCT * 100:.0f}%",
            "total_commission": "10% AgentBroker + 2% pipeline surcharge",
        }

    async def search_pipelines(
        self, db: AsyncSession,
        capability_tag: str | None = None,
        max_price: float | None = None,
        min_reputation: float | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Discover pipelines by capability, price, reputation."""
        query = select(Pipeline).where(Pipeline.is_active == True)
        if max_price is not None:
            query = query.where(Pipeline.base_price <= max_price)
        if min_reputation is not None:
            query = query.where(Pipeline.reputation_score >= min_reputation)
        query = query.order_by(Pipeline.reputation_score.desc()).limit(limit)

        result = await db.execute(query)
        pipelines = result.scalars().all()

        if capability_tag:
            pipelines = [p for p in pipelines if capability_tag in (p.capability_tags or [])]

        output = []
        for p in pipelines:
            step_count = (await db.execute(
                select(func.count(PipelineStep.id)).where(PipelineStep.pipeline_id == p.id)
            )).scalar() or 0

            output.append({
                "pipeline_id": p.id,
                "pipeline_name": p.pipeline_name,
                "description": p.description[:200],
                "capability_tags": p.capability_tags,
                "pricing_model": p.pricing_model,
                "base_price": p.base_price,
                "price_currency": p.price_currency,
                "steps": step_count,
                "reputation_score": p.reputation_score,
                "total_engagements": p.total_engagements,
            })
        return output

    async def engage_pipeline(
        self, db: AsyncSession, pipeline_id: str,
        client_operator_id: str, gross_value: float,
    ) -> dict:
        """Create a pipeline engagement. Fund escrow for full value."""
        pipeline_result = await db.execute(
            select(Pipeline).where(Pipeline.id == pipeline_id, Pipeline.is_active == True)
        )
        pipeline = pipeline_result.scalar_one_or_none()
        if not pipeline:
            raise ValueError("Pipeline not found or inactive")

        engagement = PipelineEngagement(
            pipeline_id=pipeline_id,
            client_operator_id=client_operator_id,
            status="active",
            gross_value=gross_value,
            current_step=1,
        )
        db.add(engagement)
        await db.flush()

        # Get step count
        step_count = (await db.execute(
            select(func.count(PipelineStep.id)).where(PipelineStep.pipeline_id == pipeline_id)
        )).scalar() or 0

        return {
            "engagement_id": engagement.id,
            "pipeline_id": pipeline_id,
            "pipeline_name": pipeline.pipeline_name,
            "gross_value": gross_value,
            "total_steps": step_count,
            "current_step": 1,
            "status": "active",
            "commission_breakdown": {
                "agentbroker_pct": "10%",
                "pipeline_surcharge_pct": f"{PIPELINE_SURCHARGE_PCT * 100:.0f}%",
                "total_platform_pct": f"{(0.10 + PIPELINE_SURCHARGE_PCT) * 100:.0f}%",
            },
        }

    async def advance_step(
        self, db: AsyncSession, engagement_id: str,
    ) -> dict:
        """Advance to next step after current step delivery verified."""
        eng_result = await db.execute(
            select(PipelineEngagement).where(PipelineEngagement.id == engagement_id)
        )
        engagement = eng_result.scalar_one_or_none()
        if not engagement:
            raise ValueError("Engagement not found")

        # Get total steps
        total_steps = (await db.execute(
            select(func.count(PipelineStep.id)).where(
                PipelineStep.pipeline_id == engagement.pipeline_id
            )
        )).scalar() or 0

        # Get current step agent for payment
        current_step_result = await db.execute(
            select(PipelineStep).where(
                PipelineStep.pipeline_id == engagement.pipeline_id,
                PipelineStep.step_order == engagement.current_step,
            )
        )
        current_step = current_step_result.scalar_one_or_none()

        step_payment = 0.0
        if current_step:
            step_payment = round(engagement.gross_value * current_step.revenue_share_pct / 100, 4)

        if engagement.current_step >= total_steps:
            engagement.status = "completed"
            engagement.completed_at = datetime.now(timezone.utc)

            # Update pipeline stats
            pipeline_result = await db.execute(
                select(Pipeline).where(Pipeline.id == engagement.pipeline_id)
            )
            pipeline = pipeline_result.scalar_one_or_none()
            if pipeline:
                pipeline.total_engagements = (pipeline.total_engagements or 0) + 1
        else:
            engagement.current_step += 1
            engagement.status = f"step_{engagement.current_step}"

        await db.flush()

        return {
            "engagement_id": engagement.id,
            "step_completed": engagement.current_step - 1 if engagement.status != "completed" else total_steps,
            "step_payment": step_payment,
            "agent_paid": current_step.agent_id if current_step else None,
            "current_step": engagement.current_step,
            "total_steps": total_steps,
            "status": engagement.status,
        }

    async def get_engagement(self, db: AsyncSession, engagement_id: str) -> dict | None:
        """Full engagement state including step history."""
        eng_result = await db.execute(
            select(PipelineEngagement).where(PipelineEngagement.id == engagement_id)
        )
        engagement = eng_result.scalar_one_or_none()
        if not engagement:
            return None

        steps_result = await db.execute(
            select(PipelineStep)
            .where(PipelineStep.pipeline_id == engagement.pipeline_id)
            .order_by(PipelineStep.step_order)
        )
        steps = steps_result.scalars().all()

        return {
            "engagement_id": engagement.id,
            "pipeline_id": engagement.pipeline_id,
            "status": engagement.status,
            "gross_value": engagement.gross_value,
            "current_step": engagement.current_step,
            "total_steps": len(steps),
            "steps": [
                {
                    "step_order": s.step_order,
                    "step_name": s.step_name,
                    "agent_id": s.agent_id,
                    "revenue_share_pct": s.revenue_share_pct,
                    "completed": s.step_order < engagement.current_step,
                    "active": s.step_order == engagement.current_step,
                }
                for s in steps
            ],
            "created_at": str(engagement.created_at),
            "completed_at": str(engagement.completed_at) if engagement.completed_at else None,
        }

    async def get_platform_stats(self, db: AsyncSession) -> dict:
        """Platform-wide pipeline statistics."""
        active = (await db.execute(
            select(func.count(Pipeline.id)).where(Pipeline.is_active == True)
        )).scalar() or 0

        total_gev = (await db.execute(
            select(func.sum(PipelineEngagement.gross_value))
        )).scalar() or 0.0

        avg_steps = (await db.execute(
            select(func.avg(PipelineStep.step_order))
        )).scalar() or 0

        return {
            "active_pipelines": active,
            "total_gev": round(total_gev, 4),
            "avg_steps_per_pipeline": round(avg_steps, 1),
        }
