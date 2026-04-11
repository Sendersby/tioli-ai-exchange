"""Agent Profile Service — aggregates all profile data from across the platform.

Returns a single comprehensive profile object for rendering the full
11-tab agent profile page.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import Agent, Wallet
from app.agenthub.models import (
    AgentHubProfile, AgentHubSkill, AgentHubPost, AgentHubConnection,
    AgentHubSkillEndorsement, AgentHubRanking, AgentHubAchievement,
    AgentHubPortfolioItem, AgentHubGigPackage, AgentHubCollabMatch,
)
from app.governance.models import Proposal, Vote
from app.agent_profile.models import (
    PlatformEvent, SparkAnswer, SparkReply, ProfileView, FeaturedWork,
    CONVERSATION_SPARKS,
)

logger = logging.getLogger(__name__)

# First 1,000 agents get Connect/Engage free. After that, Pro required.
FOUNDING_MEMBER_LIMIT = 1000


class ProfileService:
    """Aggregates profile data from all platform systems."""

    async def get_full_profile(self, db: AsyncSession, agent_id: str) -> dict | None:
        """Get the complete profile data for an agent — powers all 11 tabs."""
        # Base agent
        agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
        if not agent:
            return None

        # Profile
        profile = (await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )).scalar_one_or_none()

        # Auto-seed profile if it doesn't exist
        if not profile:
            profile = AgentHubProfile(
                agent_id=agent_id, operator_id=agent_id,
                display_name=agent.name, bio=agent.description or "",
                primary_language="en",
            )
            db.add(profile)
            await db.flush()

        # Skills
        skills = (await db.execute(
            select(AgentHubSkill).where(AgentHubSkill.profile_id == profile.id)
        )).scalars().all()

        # Wallets
        wallets = (await db.execute(
            select(Wallet).where(Wallet.agent_id == agent_id)
        )).scalars().all()
        wallet_map = {w.currency: round(w.balance, 2) for w in wallets}

        # Ranking
        ranking = (await db.execute(
            select(AgentHubRanking).where(AgentHubRanking.agent_id == agent_id)
        )).scalar_one_or_none()

        # Connections
        connection_count = (await db.execute(
            select(func.count(AgentHubConnection.id)).where(
                AgentHubConnection.status == "ACCEPTED",
                (AgentHubConnection.requester_agent_id == agent_id) |
                (AgentHubConnection.receiver_agent_id == agent_id),
            )
        )).scalar() or 0

        # Engagements (from AgentBroker)
        engagement_count = 0
        engagement_value = 0.0
        try:
            from app.agentbroker.models import AgentEngagement
            eng_result = await db.execute(
                select(func.count(AgentEngagement.id), func.coalesce(func.sum(AgentEngagement.agreed_price), 0))
                .where(
                    (AgentEngagement.provider_agent_id == agent_id) |
                    (AgentEngagement.client_agent_id == agent_id),
                    AgentEngagement.current_state == "completed",
                )
            )
            row = eng_result.first()
            if row:
                engagement_count = row[0] or 0
                engagement_value = float(row[1] or 0)
        except Exception as e:
            import logging; logging.getLogger("service").warning(f"Suppressed: {e}")

        # Charity contribution (10% of engagement value)
        charity_value = round(engagement_value * 0.1, 2)

        # Governance
        proposals_submitted = (await db.execute(
            select(func.count(Proposal.id)).where(Proposal.submitted_by == agent_id)
        )).scalar() or 0
        votes_cast = (await db.execute(
            select(func.count(Vote.id)).where(Vote.agent_id == agent_id)
        )).scalar() or 0
        proposals_approved = (await db.execute(
            select(func.count(Proposal.id)).where(
                Proposal.submitted_by == agent_id,
                Proposal.status == "approved",
            )
        )).scalar() or 0

        # Activity feed (recent events)
        events = (await db.execute(
            select(PlatformEvent).where(PlatformEvent.agent_id == agent_id)
            .order_by(PlatformEvent.created_at.desc()).limit(10)
        )).scalars().all()

        # Badges
        badges = (await db.execute(
            select(AgentHubAchievement).where(AgentHubAchievement.agent_id == agent_id)
        )).scalars().all()

        # Gig packages (services)
        gigs = (await db.execute(
            select(AgentHubGigPackage).where(AgentHubGigPackage.agent_id == agent_id)
        )).scalars().all()

        # Portfolio items
        portfolio = (await db.execute(
            select(AgentHubPortfolioItem).where(AgentHubPortfolioItem.profile_id == profile.id)
        )).scalars().all()

        # Featured work
        featured = (await db.execute(
            select(FeaturedWork).where(FeaturedWork.agent_id == agent_id)
            .order_by(FeaturedWork.display_order)
        )).scalars().all()

        # Conversation sparks
        spark_answers = (await db.execute(
            select(SparkAnswer).where(SparkAnswer.agent_id == agent_id)
        )).scalars().all()
        spark_map = {a.question_id: a for a in spark_answers}

        # Build sparks with replies
        sparks = []
        is_pro = (profile.profile_tier or "FREE").upper() == "PRO"
        available_qs = CONVERSATION_SPARKS if is_pro else [q for q in CONVERSATION_SPARKS if q["tier"] == "free"]
        for q in available_qs:
            answer = spark_map.get(q["id"])
            spark_data = {
                "question_id": q["id"],
                "question": q["question"],
                "tier": q["tier"],
                "answered": answer is not None,
                "answer_text": answer.answer_text if answer else None,
                "is_pinned": answer.is_pinned if answer else False,
                "replies": [],
            }
            if answer:
                replies = (await db.execute(
                    select(SparkReply).where(SparkReply.answer_id == answer.id)
                    .order_by(SparkReply.created_at.desc()).limit(3)
                )).scalars().all()
                # Get replier names
                replier_ids = {r.agent_id for r in replies}
                replier_names = {}
                if replier_ids:
                    nr = await db.execute(select(Agent.id, Agent.name).where(Agent.id.in_(replier_ids)))
                    replier_names = {r[0]: r[1] for r in nr}
                spark_data["replies"] = [
                    {
                        "agent_id": r.agent_id,
                        "agent_name": replier_names.get(r.agent_id, "Agent"),
                        "text": r.reply_text,
                        "created_at": str(r.created_at),
                    }
                    for r in replies
                ]
            sparks.append(spark_data)

        # Colleagues (recent connections with names)
        colleagues = []
        try:
            conn_result = await db.execute(
                select(AgentHubConnection).where(
                    AgentHubConnection.status == "ACCEPTED",
                    (AgentHubConnection.requester_agent_id == agent_id) |
                    (AgentHubConnection.receiver_agent_id == agent_id),
                ).limit(12)
            )
            for c in conn_result.scalars().all():
                other_id = c.receiver_agent_id if c.requester_agent_id == agent_id else c.requester_agent_id
                other = (await db.execute(select(Agent.name, Agent.platform).where(Agent.id == other_id))).first()
                if other:
                    colleagues.append({
                        "agent_id": other_id,
                        "name": other[0],
                        "platform": other[1],
                    })
        except Exception as e:
            import logging; logging.getLogger("service").warning(f"Suppressed: {e}")

        # Profile views (Pro analytics)
        total_views = (await db.execute(
            select(func.count(ProfileView.id)).where(ProfileView.profile_agent_id == agent_id)
        )).scalar() or 0

        # Posts count
        post_count = (await db.execute(
            select(func.count(AgentHubPost.id)).where(AgentHubPost.author_agent_id == agent_id)
        )).scalar() or 0

        # Endorsements received
        endorsement_count = 0
        try:
            endorsement_count = (await db.execute(
                select(func.count(AgentHubSkillEndorsement.id))
                .join(AgentHubSkill, AgentHubSkillEndorsement.skill_id == AgentHubSkill.id)
                .where(AgentHubSkill.profile_id == profile.id)
            )).scalar() or 0
        except Exception as e:
            import logging; logging.getLogger("service").warning(f"Suppressed: {e}")

        # Success rate
        success_rate = 100.0 if engagement_count > 0 else 0.0
        if ranking:
            success_rate = ranking.success_rate_pct or 100.0

        return {
            "agent": {
                "id": agent.id,
                "name": agent.name,
                "platform": agent.platform,
                "description": agent.description,
                "created_at": str(agent.created_at) if agent.created_at else None,
            },
            "profile": {
                "display_name": profile.display_name,
                "headline": profile.headline,
                "bio": profile.bio,
                "handle": profile.handle,
                "avatar_url": profile.avatar_url,
                "location_region": profile.location_region,
                "primary_language": profile.primary_language,
                "tier": profile.profile_tier or "FREE",
                "is_verified": profile.is_verified,
                "is_featured": profile.is_featured,
            },
            "stats": {
                "reputation": round(ranking.composite_score, 1) if ranking else 0.0,
                "engagements": engagement_count,
                "value": round(engagement_value, 2),
                "charity": round(charity_value, 2),
                "colleagues": connection_count,
                "success_rate": round(success_rate, 1),
                "posts": post_count,
                "endorsements": endorsement_count,
            },
            "skills": [
                {
                    "name": s.skill_name,
                    "level": s.proficiency_level,
                    "endorsements": s.endorsement_count,
                    "is_verified": s.is_verified,
                }
                for s in skills
            ],
            "wallets": wallet_map,
            "ranking": {
                "tier": ranking.tier if ranking else "NOVICE",
                "composite_score": ranking.composite_score if ranking else 0.0,
                "global_rank": ranking.global_rank if ranking else None,
                "engagement_score": ranking.engagement_score if ranking else 0.0,
                "reputation_score": ranking.reputation_score if ranking else 0.0,
                "community_score": ranking.community_score if ranking else 0.0,
                "skill_score": ranking.skill_score if ranking else 0.0,
            } if ranking else None,
            "governance": {
                "proposals_submitted": proposals_submitted,
                "votes_cast": votes_cast,
                "proposals_approved": proposals_approved,
                "approval_rate": round(proposals_approved / max(1, proposals_submitted) * 100, 1),
            },
            "activity": [
                {
                    "id": e.id,
                    "type": e.event_type,
                    "category": e.category,
                    "title": e.title,
                    "description": e.description,
                    "icon_type": e.icon_type,
                    "blockchain_hash": e.blockchain_hash,
                    "related_agent_id": e.related_agent_id,
                    "created_at": str(e.created_at),
                }
                for e in events
            ],
            "badges": [
                {
                    "code": b.badge_code,
                    "name": b.badge_name,
                    "tier": b.badge_tier,
                }
                for b in badges
            ],
            "services": [
                {
                    "id": g.id,
                    "title": g.title,
                    "category": g.category,
                    "pricing_model": g.pricing_model,
                }
                for g in gigs
            ],
            "portfolio": [
                {
                    "id": p.id,
                    "title": p.title,
                    "description": p.description,
                }
                for p in portfolio[:5]
            ],
            "featured_work": [
                {
                    "id": f.id,
                    "title": f.title,
                    "description": f.description,
                    "value": f.value,
                    "reviewer_name": f.reviewer_name,
                    "review_text": f.review_text,
                    "rating": f.rating,
                    "blockchain_hash": f.blockchain_hash,
                }
                for f in featured
            ],
            "colleagues": colleagues,
            "sparks": sparks,
            "analytics": {
                "profile_views": total_views,
            },
            "access": await self._get_access_info(db, agent_id, profile),
            "cross_platform": await self._get_cross_platform_links(db, agent_id),
        }

    async def _get_access_info(self, db: AsyncSession, agent_id: str, profile) -> dict:
        """Determine access level — founding member (first 1000) get Connect/Engage free."""
        total_agents = (await db.execute(
            select(func.count(Agent.id))
        )).scalar() or 0

        is_pro = (profile.profile_tier or "FREE").upper() == "PRO"

        # Check if this agent is within the first 1000 registrations
        # Count agents registered before this one
        agent_position = (await db.execute(
            select(func.count(Agent.id)).where(Agent.created_at <= (
                select(Agent.created_at).where(Agent.id == agent_id).scalar_subquery()
            ))
        )).scalar() or 0

        is_founding_member = agent_position <= FOUNDING_MEMBER_LIMIT
        connect_engage_free = is_pro or is_founding_member
        founding_slots_remaining = max(0, FOUNDING_MEMBER_LIMIT - total_agents)

        return {
            "is_pro": is_pro,
            "is_founding_member": is_founding_member,
            "founding_member_number": agent_position if is_founding_member else None,
            "connect_engage_unlocked": connect_engage_free,
            "founding_slots_remaining": founding_slots_remaining,
            "total_agents_registered": total_agents,
            "founding_member_limit": FOUNDING_MEMBER_LIMIT,
            "promo_message": f"Founding Member #{agent_position} — Connect & Engage unlocked free!" if is_founding_member else (
                "Pro subscription required for Connect & Engage" if not is_pro else "Pro member — all features unlocked"
            ),
        }

    async def _get_cross_platform_links(self, db: AsyncSession, agent_id: str) -> list[dict]:
        """Get cross-platform identity links for an agent."""
        try:
            from app.agent_profile.cross_platform import get_agent_links
            return await get_agent_links(db, agent_id)
        except Exception as e:
            return []

    async def record_profile_view(self, db: AsyncSession, profile_agent_id: str, viewer_agent_id: str = None, source: str = "direct"):
        """Record a profile page view."""
        view = ProfileView(
            profile_agent_id=profile_agent_id,
            viewer_agent_id=viewer_agent_id,
            source=source,
        )
        db.add(view)

    async def emit_event(
        self, db: AsyncSession, agent_id: str, event_type: str,
        title: str, description: str = "", category: str = "general",
        icon_type: str = "general", blockchain_hash: str = None,
        related_agent_id: str = None, metadata: dict = None,
    ):
        """Emit a platform event to an agent's activity feed."""
        event = PlatformEvent(
            agent_id=agent_id,
            event_type=event_type,
            category=category,
            title=title,
            description=description,
            icon_type=icon_type,
            blockchain_hash=blockchain_hash,
            related_agent_id=related_agent_id,
            event_data=metadata or {},
        )
        db.add(event)
        return event
