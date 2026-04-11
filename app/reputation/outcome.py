"""Outcome Recording — captures quality ratings and records to blockchain."""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.reputation.models import TaskDispatch, TaskOutcome, TaskRequest


class OutcomeService:
    """Records task outcomes and optionally writes to blockchain."""

    async def record_outcome(
        self,
        db: AsyncSession,
        dispatch_id: str,
        rated_by_agent_id: str,
        quality_rating: int,
        *,
        rating_tags: list[str] | None = None,
        review_text: str | None = None,
    ) -> TaskOutcome:
        """Record a quality rating for a completed dispatch."""

        if quality_rating < 1 or quality_rating > 5:
            raise ValueError("quality_rating must be 1-5")

        dispatch = await db.get(TaskDispatch, dispatch_id)
        if not dispatch:
            raise ValueError(f"Dispatch {dispatch_id} not found")
        if dispatch.status != "delivered":
            raise ValueError(f"Dispatch is in state '{dispatch.status}', must be delivered to rate")

        # Determine on-time status
        on_time = dispatch.sla_met

        # Record outcome
        outcome = TaskOutcome(
            outcome_id=str(uuid.uuid4()),
            task_id=dispatch.task_id,
            dispatch_id=dispatch_id,
            engagement_id=dispatch.engagement_id,
            agent_id=dispatch.agent_id,
            rated_by_agent_id=rated_by_agent_id,
            quality_rating=quality_rating,
            rating_tags=rating_tags or [],
            review_text=review_text,
            on_time=on_time,
            response_time_seconds=dispatch.response_time_seconds,
        )

        # Try to record on blockchain
        try:
            from app.blockchain.blockchain import blockchain
            tx_id = blockchain.add_transaction(
                sender=rated_by_agent_id,
                recipient=dispatch.agent_id,
                amount=0,
                transaction_type="task_outcome",
                metadata={
                    "task_id": dispatch.task_id,
                    "dispatch_id": dispatch_id,
                    "quality_rating": quality_rating,
                    "on_time": on_time,
                    "rating_tags": rating_tags or [],
                    "response_time_seconds": dispatch.response_time_seconds,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            outcome.blockchain_tx_id = tx_id
        except Exception as e:
            import logging; logging.getLogger("outcome").warning(f"Suppressed: {e}")  # blockchain recording is best-effort

        db.add(outcome)
        return outcome
