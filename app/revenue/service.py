"""Revenue Engine Service — autonomous revenue tracking, auto-match, quick tasks.

Target: $5,000 USD/month by August 2026.
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.revenue.models import (
    RevenueTransaction, RevenueDailySummary, RevenueMilestoneLog,
    RevenueExchangeRate, OperatorSubscriptionEvent, AutoMatchRequest,
    QuickTask, RetentionScore, WelcomeSequenceStatus,
    REVENUE_STREAMS, REVENUE_MILESTONES, REVENUE_PARAMETERS,
    SUBSCRIPTION_TIERS_REVENUE, AUTO_MATCH_CONFIG,
)
from app.agents.models import Agent

logger = logging.getLogger(__name__)


class RevenueEngineService:
    """Autonomous revenue tracking and generation engine."""

    # ── Revenue Recording ─────────────────────────────────────────────

    async def record_revenue(
        self, db: AsyncSession, stream: str, source_type: str,
        gross_zar: float, description: str = "",
        source_id: str | None = None, agent_id: str | None = None,
        operator_id: str | None = None, exchange_rate: float = 18.50,
    ) -> dict:
        """Record a revenue transaction."""
        charitable = round(gross_zar * 0.10, 2)
        net_zar = round(gross_zar - charitable, 2)
        gross_usd = round(gross_zar / exchange_rate, 2)
        net_usd = round(net_zar / exchange_rate, 2)

        tx = RevenueTransaction(
            stream=stream, source_type=source_type, source_id=source_id,
            agent_id=agent_id, operator_id=operator_id,
            gross_amount_zar=gross_zar, gross_amount_usd=gross_usd,
            charitable_amount_zar=charitable,
            net_amount_zar=net_zar, net_amount_usd=net_usd,
            exchange_rate=exchange_rate, description=description,
        )
        db.add(tx)
        await db.flush()

        # Check milestones
        await self._check_milestones(db)

        return {
            "revenue_id": tx.id, "stream": stream,
            "gross_zar": gross_zar, "gross_usd": gross_usd,
            "net_zar": net_zar, "net_usd": net_usd,
            "charitable": charitable,
        }

    async def _check_milestones(self, db: AsyncSession) -> None:
        """Check if any revenue milestones have been achieved this month."""
        now = datetime.now(timezone.utc)
        month_key = now.strftime("%Y-%m")
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        total_usd = (await db.execute(
            select(func.sum(RevenueTransaction.net_amount_usd)).where(
                RevenueTransaction.created_at >= month_start
            )
        )).scalar() or 0

        for milestone_usd, message in REVENUE_MILESTONES.items():
            if total_usd >= milestone_usd:
                existing = await db.execute(
                    select(RevenueMilestoneLog).where(
                        RevenueMilestoneLog.milestone_usd == milestone_usd,
                        RevenueMilestoneLog.month == month_key,
                    )
                )
                if not existing.scalar_one_or_none():
                    db.add(RevenueMilestoneLog(
                        milestone_usd=milestone_usd, message=message,
                        month=month_key, total_usd_at_achievement=round(total_usd, 2),
                    ))
                    logger.info(f"REVENUE MILESTONE: {message} (${total_usd:.2f})")

    # ── Revenue Dashboard Data ────────────────────────────────────────

    async def get_revenue_dashboard(self, db: AsyncSession) -> dict:
        """Complete revenue intelligence dashboard data."""
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
        year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

        # Panel 1: Live Revenue Gauge
        mtd_result = await db.execute(
            select(
                func.sum(RevenueTransaction.net_amount_usd),
                func.sum(RevenueTransaction.net_amount_zar),
                func.sum(RevenueTransaction.charitable_amount_zar),
                func.count(RevenueTransaction.id),
            ).where(RevenueTransaction.created_at >= month_start)
        )
        row = mtd_result.one()
        mtd_usd = round(row[0] or 0, 2)
        mtd_zar = round(row[1] or 0, 2)
        mtd_charitable = round(row[2] or 0, 2)
        mtd_count = row[3] or 0

        # Days elapsed and projection
        days_elapsed = max((now - month_start).days, 1)
        days_in_month = 30
        daily_rate = mtd_usd / days_elapsed if days_elapsed > 0 else 0
        projected_month = round(daily_rate * days_in_month, 2)
        target = REVENUE_PARAMETERS["monthly_floor_usd"]
        progress_pct = round(mtd_usd / target * 100, 1) if target > 0 else 0

        # YTD
        ytd_result = await db.execute(
            select(func.sum(RevenueTransaction.net_amount_usd)).where(
                RevenueTransaction.created_at >= year_start
            )
        )
        ytd_usd = round((ytd_result.scalar() or 0), 2)

        # Previous month for comparison
        prev_result = await db.execute(
            select(func.sum(RevenueTransaction.net_amount_usd)).where(
                RevenueTransaction.created_at >= prev_month_start,
                RevenueTransaction.created_at < month_start,
            )
        )
        prev_usd = round((prev_result.scalar() or 0), 2)

        # Panel 2: Stream Breakdown
        streams = {}
        for stream_name in REVENUE_STREAMS:
            s_result = await db.execute(
                select(
                    func.sum(RevenueTransaction.net_amount_usd),
                    func.count(RevenueTransaction.id),
                ).where(
                    RevenueTransaction.stream == stream_name,
                    RevenueTransaction.created_at >= month_start,
                )
            )
            s_row = s_result.one()
            prev_s_result = await db.execute(
                select(func.sum(RevenueTransaction.net_amount_usd)).where(
                    RevenueTransaction.stream == stream_name,
                    RevenueTransaction.created_at >= prev_month_start,
                    RevenueTransaction.created_at < month_start,
                )
            )
            streams[stream_name] = {
                "current_usd": round(s_row[0] or 0, 2),
                "transactions": s_row[1] or 0,
                "previous_usd": round((prev_s_result.scalar() or 0), 2),
            }

        # Panel 3: Subscriber Health
        from app.subscriptions.models import OperatorSubscription
        active_subs = (await db.execute(
            select(func.count(OperatorSubscription.id)).where(
                OperatorSubscription.status == "active"
            )
        )).scalar() or 0

        from app.agenthub.models import AgentHubProfile
        pro_agents = (await db.execute(
            select(func.count(AgentHubProfile.id)).where(
                AgentHubProfile.profile_tier == "PRO"
            )
        )).scalar() or 0

        total_agents = (await db.execute(select(func.count(Agent.id)))).scalar() or 0

        # Panel 4: Transaction Pipeline
        quick_tasks_active = (await db.execute(
            select(func.count(QuickTask.id)).where(QuickTask.status == "ORDERED")
        )).scalar() or 0

        quick_tasks_completed = (await db.execute(
            select(func.count(QuickTask.id)).where(
                QuickTask.status == "CONFIRMED",
                QuickTask.confirmed_at >= month_start,
            )
        )).scalar() or 0

        # Panel 5: Acquisition
        new_agents_month = (await db.execute(
            select(func.count(Agent.id)).where(Agent.created_at >= month_start)
        )).scalar() or 0

        new_profiles_month = (await db.execute(
            select(func.count(AgentHubProfile.id)).where(
                AgentHubProfile.created_at >= month_start
            )
        )).scalar() or 0

        # Milestones achieved
        milestones = await db.execute(
            select(RevenueMilestoneLog).order_by(RevenueMilestoneLog.achieved_at.desc()).limit(10)
        )
        milestone_list = [
            {"milestone": m.milestone_usd, "message": m.message,
             "achieved_at": str(m.achieved_at), "month": m.month}
            for m in milestones.scalars().all()
        ]

        return {
            "gauge": {
                "mtd_usd": mtd_usd, "mtd_zar": mtd_zar,
                "target_usd": target, "progress_pct": progress_pct,
                "projected_month_usd": projected_month,
                "daily_rate_usd": round(daily_rate, 2),
                "ytd_usd": ytd_usd, "previous_month_usd": prev_usd,
                "mtd_charitable_zar": mtd_charitable,
                "mtd_transactions": mtd_count,
            },
            "streams": streams,
            "subscribers": {
                "operator_subscriptions": active_subs,
                "agenthub_pro": pro_agents,
                "total_agents": total_agents,
            },
            "pipeline": {
                "quick_tasks_pending": quick_tasks_active,
                "quick_tasks_completed_mtd": quick_tasks_completed,
            },
            "acquisition": {
                "new_agents_mtd": new_agents_month,
                "new_profiles_mtd": new_profiles_month,
            },
            "milestones": milestone_list,
        }

    async def get_daily_revenue_report(self, db: AsyncSession) -> dict:
        """Generate daily revenue pulse for WhatsApp/email."""
        now = datetime.now(timezone.utc)
        yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Yesterday's revenue
        yesterday = await db.execute(
            select(
                func.sum(RevenueTransaction.net_amount_usd),
                func.sum(RevenueTransaction.net_amount_zar),
                func.count(RevenueTransaction.id),
            ).where(
                RevenueTransaction.created_at >= yesterday_start,
                RevenueTransaction.created_at < yesterday_end,
            )
        )
        y = yesterday.one()

        # MTD
        mtd = await db.execute(
            select(func.sum(RevenueTransaction.net_amount_usd)).where(
                RevenueTransaction.created_at >= month_start
            )
        )
        mtd_usd = round((mtd.scalar() or 0), 2)

        target = REVENUE_PARAMETERS["monthly_floor_usd"]
        progress = round(mtd_usd / target * 100, 1) if target > 0 else 0

        return {
            "date": yesterday_start.strftime("%Y-%m-%d"),
            "yesterday_usd": round(y[0] or 0, 2),
            "yesterday_zar": round(y[1] or 0, 2),
            "yesterday_transactions": y[2] or 0,
            "mtd_usd": mtd_usd,
            "target_usd": target,
            "progress_pct": progress,
            "on_track": progress >= (now.day / 30 * 100),
            "message": (
                f"TiOLi Revenue Pulse\n"
                f"Yesterday: ${round(y[0] or 0, 2)} ({y[2] or 0} txns)\n"
                f"MTD: ${mtd_usd} / ${target} ({progress}%)\n"
                f"{'On track' if progress >= (now.day / 30 * 100) else 'BELOW TARGET'}"
            ),
        }

    # ── Auto-Match Engine ─────────────────────────────────────────────

    async def auto_match(
        self, db: AsyncSession, operator_id: str, task_description: str,
    ) -> dict:
        """Parse task description and find top matching agents."""
        # Parse keywords from description
        keywords = [w.strip().lower() for w in re.split(r'[,;\s]+', task_description) if len(w.strip()) > 3]

        # Search AgentHub profiles
        from app.agenthub.models import AgentHubProfile, AgentHubSkill
        all_profiles = await db.execute(
            select(AgentHubProfile).where(
                AgentHubProfile.is_active == True,
                AgentHubProfile.open_to_engagements == True,
            ).order_by(AgentHubProfile.reputation_score.desc()).limit(100)
        )

        scored = []
        weights = AUTO_MATCH_CONFIG["match_score_weights"]

        for p in all_profiles.scalars().all():
            score = 0

            # Capability alignment (40%)
            searchable = " ".join([
                (p.display_name or "").lower(),
                (p.headline or "").lower(),
                (p.bio or "").lower(),
                " ".join(p.specialisation_domains or []).lower(),
            ])
            kw_hits = sum(1 for kw in keywords if kw in searchable)
            score += kw_hits * 10 * weights["capability_alignment"]

            # Check skills
            skills_result = await db.execute(
                select(AgentHubSkill).where(AgentHubSkill.profile_id == p.id)
            )
            for skill in skills_result.scalars().all():
                for kw in keywords:
                    if kw in skill.skill_name.lower():
                        score += 15 * weights["capability_alignment"]

            # Availability (20%)
            if p.availability_status == "AVAILABLE":
                score += 10 * weights["availability"]

            # Reputation (20%)
            score += p.reputation_score * weights["reputation_score"]

            if score > 0:
                scored.append({
                    "agent_id": p.agent_id, "display_name": p.display_name,
                    "headline": p.headline, "reputation": p.reputation_score,
                    "match_score": round(score, 2),
                })

        scored.sort(key=lambda x: x["match_score"], reverse=True)
        top = scored[:AUTO_MATCH_CONFIG["max_agent_suggestions"]]

        # Record the match request
        match_req = AutoMatchRequest(
            operator_id=operator_id, task_description=task_description,
            parsed_capabilities=keywords,
            matched_agents=[a["agent_id"] for a in top],
            proposals_sent=len(top),
            status="MATCHED" if top else "NO_MATCH",
            matched_at=datetime.now(timezone.utc) if top else None,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(match_req)
        await db.flush()

        return {
            "match_id": match_req.id,
            "task_description": task_description,
            "keywords_parsed": keywords,
            "matches": top,
            "proposals_sent": len(top),
            "status": match_req.status,
            "expires_at": str(match_req.expires_at),
        }

    # ── Quick Tasks ───────────────────────────────────────────────────

    async def create_quick_task(
        self, db: AsyncSession, provider_agent_id: str,
        title: str, price: float, description: str = "",
        client_agent_id: str | None = None,
        client_operator_id: str | None = None,
        gig_package_id: str | None = None,
        tier_selected: str = "basic",
    ) -> dict:
        """Create a Quick Task — 3-state micro-engagement."""
        commission_rate = 0.12
        commission = round(price * commission_rate, 4)
        charitable = round(commission * 0.10, 4)

        task = QuickTask(
            gig_package_id=gig_package_id,
            provider_agent_id=provider_agent_id,
            client_agent_id=client_agent_id,
            client_operator_id=client_operator_id,
            title=title, description=description,
            price=price, tier_selected=tier_selected,
            commission_rate=commission_rate,
            commission_amount=commission,
            charitable_amount=charitable,
            auto_confirm_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(task)
        await db.flush()

        return {
            "task_id": task.id, "title": title, "price": price,
            "commission": commission, "status": "ORDERED",
            "auto_confirm_at": str(task.auto_confirm_at),
        }

    async def deliver_quick_task(
        self, db: AsyncSession, task_id: str, deliverable_ref: str = "",
    ) -> dict:
        """Mark a Quick Task as delivered."""
        result = await db.execute(select(QuickTask).where(QuickTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task or task.status != "ORDERED":
            raise ValueError("Task not found or not in ORDERED status")
        task.status = "DELIVERED"
        task.delivered_at = datetime.now(timezone.utc)
        task.deliverable_ref = deliverable_ref
        await db.flush()
        return {"task_id": task_id, "status": "DELIVERED"}

    async def confirm_quick_task(self, db: AsyncSession, task_id: str) -> dict:
        """Confirm delivery — triggers commission capture."""
        result = await db.execute(select(QuickTask).where(QuickTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task or task.status != "DELIVERED":
            raise ValueError("Task not found or not in DELIVERED status")
        task.status = "CONFIRMED"
        task.confirmed_at = datetime.now(timezone.utc)
        await db.flush()

        # Record revenue
        await self.record_revenue(
            db, "agentbroker_commission", "quick_task",
            task.commission_amount, f"Quick Task: {task.title}",
            source_id=task.id, agent_id=task.provider_agent_id,
        )

        return {
            "task_id": task_id, "status": "CONFIRMED",
            "commission_captured": task.commission_amount,
        }

    async def list_quick_tasks(
        self, db: AsyncSession, status: str | None = None,
        agent_id: str | None = None, limit: int = 50,
    ) -> list[dict]:
        query = select(QuickTask)
        if status:
            query = query.where(QuickTask.status == status.upper())
        if agent_id:
            query = query.where(
                (QuickTask.provider_agent_id == agent_id) |
                (QuickTask.client_agent_id == agent_id)
            )
        query = query.order_by(QuickTask.ordered_at.desc()).limit(limit)
        result = await db.execute(query)
        return [
            {
                "task_id": t.id, "title": t.title, "price": t.price,
                "status": t.status, "provider": t.provider_agent_id,
                "client": t.client_agent_id, "commission": t.commission_amount,
                "ordered_at": str(t.ordered_at),
            }
            for t in result.scalars().all()
        ]

    # ── Retention Scoring ─────────────────────────────────────────────

    async def compute_retention_scores(self, db: AsyncSession) -> dict:
        """Compute retention risk scores for all subscribers."""
        now = datetime.now(timezone.utc)
        computed = 0

        # Score agents with profiles
        from app.agenthub.models import AgentHubProfile
        profiles = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.is_active == True)
        )
        for p in profiles.scalars().all():
            days_inactive = 0
            if p.updated_at:
                days_inactive = (now - p.updated_at).days

            score = 100
            if days_inactive > 30: score -= 40
            elif days_inactive > 14: score -= 20
            elif days_inactive > 7: score -= 10

            if (p.connection_count or 0) < 3: score -= 10
            if (p.view_count_total or 0) < 5: score -= 10
            if not p.headline: score -= 5
            if not p.bio or len(p.bio) < 20: score -= 5

            score = max(0, min(100, score))
            risk = "LOW"
            if score < 40: risk = "CRITICAL"
            elif score < 60: risk = "HIGH"
            elif score < 80: risk = "MEDIUM"

            existing = await db.execute(
                select(RetentionScore).where(
                    RetentionScore.entity_id == p.agent_id,
                    RetentionScore.entity_type == "agent",
                )
            )
            rs = existing.scalar_one_or_none()
            if rs:
                rs.score = score
                rs.days_since_login = days_inactive
                rs.risk_level = risk
                rs.computed_at = now
            else:
                db.add(RetentionScore(
                    entity_type="agent", entity_id=p.agent_id,
                    score=score, days_since_login=days_inactive,
                    risk_level=risk,
                ))
            computed += 1

        await db.flush()
        return {"computed": computed}

    async def get_at_risk_subscribers(self, db: AsyncSession) -> list[dict]:
        """Get subscribers at risk of churning."""
        result = await db.execute(
            select(RetentionScore).where(
                RetentionScore.risk_level.in_(["HIGH", "CRITICAL"])
            ).order_by(RetentionScore.score)
        )
        return [
            {
                "entity_type": r.entity_type, "entity_id": r.entity_id,
                "score": r.score, "risk": r.risk_level,
                "days_inactive": r.days_since_login,
            }
            for r in result.scalars().all()
        ]

    # ── Exchange Rate ─────────────────────────────────────────────────

    async def get_exchange_rate(self, db: AsyncSession) -> float:
        """Get current USD/ZAR rate."""
        result = await db.execute(
            select(RevenueExchangeRate).order_by(RevenueExchangeRate.fetched_at.desc()).limit(1)
        )
        rate = result.scalar_one_or_none()
        if rate:
            return rate.rate
        return 18.50  # default
