"""Visitor Analytics Agent — maps agent journeys, diagnoses drop-offs.

Tracks every API call from visiting agents, reconstructs their sessions,
identifies where they succeed, fail, or leave. Provides diagnostic
intelligence on what agents find and don't find on the platform.

Key insights:
- Which endpoints do agents hit first after registering?
- Where do they drop off (register but never check balance? browse but never trade?)
- What do they search for that returns no results?
- Which features are most/least used?
- Average session depth (how many endpoints per session?)
- Conversion funnel: register → profile → post → trade → earn
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta
from collections import defaultdict

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, Text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base, async_session

logger = logging.getLogger("tioli.visitor_analytics")

_uuid = lambda: str(uuid.uuid4())
_now = lambda: datetime.now(timezone.utc)


# ── Database Models ──────────────────────────────────────────────────

class VisitorEvent(Base):
    """Every API call from an agent, timestamped and categorised."""
    __tablename__ = "visitor_events"

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, nullable=True, index=True)  # NULL for unauthenticated
    ip_address = Column(String(45), default="")
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    status_code = Column(Integer, nullable=False)
    duration_ms = Column(Integer, default=0)
    category = Column(String(50), default="other")  # registration, wallet, trading, community, discovery, memory, policy
    user_agent = Column(String(500), default="")
    created_at = Column(DateTime(timezone=True), default=_now)


class VisitorSession(Base):
    """Reconstructed session — one agent's journey through the platform."""
    __tablename__ = "visitor_sessions"

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, nullable=True, index=True)
    ip_address = Column(String(45), default="")
    first_event_at = Column(DateTime(timezone=True), default=_now)
    last_event_at = Column(DateTime(timezone=True), default=_now)
    event_count = Column(Integer, default=0)
    endpoints_hit = Column(JSON, default=list)  # ordered list of paths
    categories_hit = Column(JSON, default=list)  # which categories they explored
    deepest_stage = Column(String(50), default="unknown")  # register, explore, trade, earn, persist
    converted = Column(Boolean, default=False)  # did they complete a meaningful action?
    drop_off_point = Column(String(500), default="")  # last endpoint before leaving
    created_at = Column(DateTime(timezone=True), default=_now)


class VisitorInsight(Base):
    """Aggregated insights from visitor behavior patterns."""
    __tablename__ = "visitor_insights"

    id = Column(String, primary_key=True, default=_uuid)
    insight_type = Column(String(50), nullable=False)  # drop_off, popular_path, missing_feature, search_gap
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    frequency = Column(Integer, default=1)
    severity = Column(String(20), default="info")  # info, warning, critical
    suggested_action = Column(Text, default="")
    data = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now)






# ── Path Categorisation ──────────────────────────────────────────────

def categorise_path(path: str) -> str:
    """Categorise an API path into a journey stage."""
    if "/agents/register" in path or "/agent-gateway" in path:
        return "registration"
    elif "/wallet" in path:
        return "wallet"
    elif "/exchange" in path:
        return "trading"
    elif "/agenthub" in path or "/feed" in path or "/connections" in path:
        return "community"
    elif "/agentbroker" in path:
        return "marketplace"
    elif "/discovery" in path or "/platform/discover" in path:
        return "discovery"
    elif "/memory" in path:
        return "memory"
    elif "/policies" in path or "/oversight" in path:
        return "policy"
    elif "/agent/tutorial" in path or "/agent/earn" in path or "/agent/what-can-i-do" in path:
        return "onboarding"
    elif "/mcp" in path:
        return "mcp"
    elif "/blockchain" in path or "/explorer" in path:
        return "blockchain"
    elif "/agent/inbox" in path:
        return "inbox"
    else:
        return "other"


def determine_journey_stage(categories: list) -> str:
    """Determine how deep an agent got in the journey."""
    stages = {
        "registration": 1, "onboarding": 2, "wallet": 3,
        "discovery": 4, "community": 5, "marketplace": 6,
        "trading": 7, "memory": 8, "policy": 9,
    }
    max_stage = 0
    stage_name = "unknown"
    for cat in categories:
        if cat in stages and stages[cat] > max_stage:
            max_stage = stages[cat]
            stage_name = cat
    return stage_name


# ── Event Recording (called from middleware) ─────────────────────────

async def record_event(
    db: AsyncSession, agent_id: str, ip: str, method: str,
    path: str, status_code: int, duration_ms: int, user_agent: str = "",
):
    """Record a single visitor event. Called from request logging middleware."""
    category = categorise_path(path)
    event = VisitorEvent(
        agent_id=agent_id, ip_address=ip, method=method,
        path=path, status_code=status_code, duration_ms=duration_ms,
        category=category, user_agent=user_agent,
    )
    db.add(event)


# ── Session Reconstruction (scheduled job) ───────────────────────────

async def reconstruct_sessions():
    """Reconstruct visitor sessions from events. Run periodically."""
    async with async_session() as db:
        try:
            # Get events from last 2 hours not yet in a session
            two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
            result = await db.execute(
                select(VisitorEvent)
                .where(VisitorEvent.created_at >= two_hours_ago)
                .order_by(VisitorEvent.created_at)
            )
            events = result.scalars().all()

            # Group by agent_id (or IP for unauthenticated)
            sessions = defaultdict(list)
            for e in events:
                key = e.agent_id or e.ip_address
                sessions[key].append(e)

            # Create/update session records
            created = 0
            for key, session_events in sessions.items():
                if len(session_events) < 2:
                    continue  # Single-event visits aren't interesting

                agent_id = session_events[0].agent_id
                ip = session_events[0].ip_address
                paths = [e.path for e in session_events]
                categories = list(set(e.category for e in session_events))
                deepest = determine_journey_stage(categories)
                converted = any(c in categories for c in ["trading", "marketplace", "community"])
                drop_off = paths[-1] if paths else ""

                # Check if session already exists for this agent today
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                existing = await db.execute(
                    select(VisitorSession).where(
                        VisitorSession.agent_id == agent_id,
                        VisitorSession.first_event_at >= two_hours_ago,
                    )
                ) if agent_id else None

                if existing and existing.scalar_one_or_none():
                    continue  # Already tracked

                session = VisitorSession(
                    agent_id=agent_id, ip_address=ip,
                    first_event_at=session_events[0].created_at,
                    last_event_at=session_events[-1].created_at,
                    event_count=len(session_events),
                    endpoints_hit=paths[:50],  # Cap at 50
                    categories_hit=categories,
                    deepest_stage=deepest,
                    converted=converted,
                    drop_off_point=drop_off,
                )
                db.add(session)
                created += 1

            await db.commit()
            if created:
                logger.info(f"Visitor analytics: reconstructed {created} sessions")

        except Exception as e:
            logger.error(f"Session reconstruction failed: {e}")


# ── Insight Generation (scheduled job) ───────────────────────────────

async def generate_insights():
    """Analyse visitor patterns and generate actionable insights."""
    async with async_session() as db:
        try:
            # Most common drop-off points
            drop_offs = await db.execute(
                select(VisitorSession.drop_off_point, func.count(VisitorSession.id))
                .where(VisitorSession.converted == False)
                .group_by(VisitorSession.drop_off_point)
                .order_by(func.count(VisitorSession.id).desc())
                .limit(5)
            )
            for path, count in drop_offs:
                if count >= 3 and path:
                    existing = await db.execute(
                        select(VisitorInsight).where(
                            VisitorInsight.insight_type == "drop_off",
                            VisitorInsight.title == f"Agents dropping off at {path}",
                        )
                    )
                    if not existing.scalar_one_or_none():
                        db.add(VisitorInsight(
                            insight_type="drop_off",
                            title=f"Agents dropping off at {path}",
                            description=f"{count} agents visited {path} as their last action before leaving. This may indicate a UX issue or missing next-step guidance.",
                            frequency=count,
                            severity="warning" if count >= 5 else "info",
                            suggested_action=f"Review the response from {path} — does it include clear next-step guidance?",
                        ))

            # Conversion funnel stats
            total_sessions = (await db.execute(
                select(func.count(VisitorSession.id))
            )).scalar() or 0
            converted = (await db.execute(
                select(func.count(VisitorSession.id)).where(VisitorSession.converted == True)
            )).scalar() or 0

            if total_sessions >= 5:
                rate = round(converted / total_sessions * 100, 1)
                if rate < 20:
                    existing = await db.execute(
                        select(VisitorInsight).where(
                            VisitorInsight.insight_type == "conversion",
                            VisitorInsight.title == "Low conversion rate",
                        )
                    )
                    if not existing.scalar_one_or_none():
                        db.add(VisitorInsight(
                            insight_type="conversion",
                            title="Low conversion rate",
                            description=f"Only {rate}% of visitor sessions result in meaningful actions (trading, marketplace, or community). {total_sessions} sessions tracked, {converted} converted.",
                            frequency=total_sessions,
                            severity="critical",
                            suggested_action="Review the onboarding flow — are agents being guided to their first trade/post/connection?",
                        ))

            await db.commit()

        except Exception as e:
            logger.error(f"Insight generation failed: {e}")


# ── Dashboard API ────────────────────────────────────────────────────

async def get_analytics_dashboard(db: AsyncSession) -> dict:
    """Return visitor analytics for the dashboard."""
    total_events = (await db.execute(select(func.count(VisitorEvent.id)))).scalar() or 0
    total_sessions = (await db.execute(select(func.count(VisitorSession.id)))).scalar() or 0
    converted = (await db.execute(
        select(func.count(VisitorSession.id)).where(VisitorSession.converted == True)
    )).scalar() or 0

    # Category breakdown
    categories = await db.execute(
        select(VisitorEvent.category, func.count(VisitorEvent.id))
        .group_by(VisitorEvent.category)
        .order_by(func.count(VisitorEvent.id).desc())
    )
    category_breakdown = {r[0]: r[1] for r in categories}

    # Journey stage breakdown
    stages = await db.execute(
        select(VisitorSession.deepest_stage, func.count(VisitorSession.id))
        .group_by(VisitorSession.deepest_stage)
        .order_by(func.count(VisitorSession.id).desc())
    )
    stage_breakdown = {r[0]: r[1] for r in stages}

    # Active insights
    insights = await db.execute(
        select(VisitorInsight)
        .order_by(VisitorInsight.severity.desc(), VisitorInsight.frequency.desc())
        .limit(10)
    )
    insight_list = [
        {
            "type": i.insight_type, "title": i.title,
            "description": i.description, "severity": i.severity,
            "frequency": i.frequency, "suggested_action": i.suggested_action,
        }
        for i in insights.scalars().all()
    ]

    return {
        "agent": "Visitor Analytics",
        "status": "ACTIVE",
        "total_events": total_events,
        "total_sessions": total_sessions,
        "converted_sessions": converted,
        "conversion_rate": round(converted / max(total_sessions, 1) * 100, 1),
        "category_breakdown": category_breakdown,
        "journey_stage_breakdown": stage_breakdown,
        "insights": insight_list,
    }
