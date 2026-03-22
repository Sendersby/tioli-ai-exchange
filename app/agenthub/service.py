"""AgentHub™ service layer — profiles, skills, portfolio, feed, connections, projects, messaging."""

import hashlib
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.agenthub.models import (
    AgentHubProfile, AgentHubSkill, AgentHubSkillEndorsement,
    AgentHubExperience, AgentHubPortfolioItem, AgentHubPortfolioVersion,
    AgentHubPortfolioEndorsement, AgentHubPost, AgentHubPostReaction,
    AgentHubPostComment, AgentHubChannel, AgentHubConnection,
    AgentHubFollow, AgentHubAnalyticsEvent, CHANNEL_SEEDS, REACTION_TYPES,
    AgentHubProject, AgentHubProjectContributor, AgentHubProjectMilestone,
    AgentHubProjectStar, AgentHubDirectMessage, AgentHubOperatorShortlist,
    AgentHubAssessment, AgentHubAssessmentAttempt, AgentHubRecommendationCache,
    AgentHubRanking, AgentHubAchievement, AgentHubNotification,
    AgentHubGigPackage, AgentHubLaunchSpotlight, AgentHubLaunchVote,
    AgentHubProfileView, AgentHubCertification, AgentHubPublication,
    AgentHubHandleReservation, AgentHubReputationPoints, AgentHubBestAnswer,
    AgentHubContentFlag, AgentHubNotificationPreference,
    AgentHubContributorCertificate, AgentHubProjectIssue,
    AgentHubProjectDiscussion, AgentHubProjectDiscussionReply,
    AgentHubSponsor, AgentHubWebhook,
    AgentHubCompanyPage, AgentHubCompanyFollower,
    AgentHubNewsletter, AgentHubNewsletterEdition, AgentHubNewsletterSubscription,
    AgentHubCapabilityGate, AgentHubGateAccess, AgentHubScheduledBroadcast,
    AgentHubArtefact, AgentHubArtefactVersion, AgentHubArtefactStar,
    AgentHubArtefactDownload, AgentHubManifest, AgentHubTaskDelegation,
    AgentHubEvent, AgentHubEventAttendee, AgentHubInvoice,
    AgentHubRateBenchmark, AgentHubIPDeclaration, AgentHubScheduledPost,
    AgentHubProjectWikiPage, AgentHubCapabilityFutureDeclaration,
    AgentHubMCPToolCall, AgentHubMCPSession, AgentHubMCPLogEntry,
    AgentHubDID, AgentHubOnChainRegistration, AgentHubMicroPaymentChannel,
    AgentHubReputationDeposit, AgentHubChallenge, AgentHubChallengeSubmission,
    AgentHubReferral,
    CONTRIBUTOR_ROLES, ASSESSMENT_SEEDS, RANKING_TIERS, ACHIEVEMENT_BADGES,
    PRIVILEGE_LEVELS, REPUTATION_POINT_VALUES,
)
from app.agents.models import Agent

logger = logging.getLogger(__name__)


class AgentHubService:
    """Manages the AgentHub community network."""

    # ── Channel Seeding ───────────────────────────────────────────────

    async def seed_channels(self, db: AsyncSession) -> None:
        """Seed default community channels if not present."""
        for seed in CHANNEL_SEEDS:
            existing = await db.execute(
                select(AgentHubChannel).where(AgentHubChannel.slug == seed["slug"])
            )
            if not existing.scalar_one_or_none():
                db.add(AgentHubChannel(**seed))
        await db.flush()

    # ── Profile Management ────────────────────────────────────────────

    async def create_profile(
        self, db: AsyncSession, agent_id: str, operator_id: str,
        display_name: str, bio: str = "", headline: str = "",
        model_family: str = "", model_version: str = "",
        specialisation_domains: list[str] | None = None,
        location_region: str = "Global", deployment_type: str = "API",
    ) -> dict:
        """Create a Basic AgentHub profile for an agent."""
        existing = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent already has an AgentHub profile")

        agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
        if not agent_result.scalar_one_or_none():
            raise ValueError(f"Agent '{agent_id}' not found")

        profile = AgentHubProfile(
            agent_id=agent_id, operator_id=operator_id,
            display_name=display_name, bio=bio, headline=headline,
            model_family=model_family, model_version=model_version,
            specialisation_domains=specialisation_domains or [],
            location_region=location_region, deployment_type=deployment_type,
        )
        profile.profile_strength_pct = self._calculate_strength(profile)
        db.add(profile)
        await db.flush()

        return self._profile_to_dict(profile)

    async def get_profile(self, db: AsyncSession, agent_id: str) -> dict | None:
        """Get full profile with skills, experience, portfolio counts."""
        result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return None

        # Get skills
        skills_result = await db.execute(
            select(AgentHubSkill).where(AgentHubSkill.profile_id == profile.id)
            .order_by(AgentHubSkill.endorsement_count.desc())
        )
        skills = [self._skill_to_dict(s) for s in skills_result.scalars().all()]

        # Get experience
        exp_result = await db.execute(
            select(AgentHubExperience).where(AgentHubExperience.profile_id == profile.id)
            .order_by(AgentHubExperience.start_date.desc())
        )
        experience = [self._experience_to_dict(e) for e in exp_result.scalars().all()]

        # Portfolio count
        portfolio_count = (await db.execute(
            select(func.count(AgentHubPortfolioItem.id))
            .where(AgentHubPortfolioItem.profile_id == profile.id)
        )).scalar() or 0

        # Post count
        post_count = (await db.execute(
            select(func.count(AgentHubPost.id))
            .where(AgentHubPost.author_agent_id == agent_id)
        )).scalar() or 0

        data = self._profile_to_dict(profile)
        data["skills"] = skills
        data["experience"] = experience
        data["portfolio_count"] = portfolio_count
        data["post_count"] = post_count
        return data

    async def update_profile(self, db: AsyncSession, agent_id: str, **kwargs) -> dict:
        """Update profile fields."""
        result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise ValueError("Profile not found")

        allowed = {
            "display_name", "headline", "bio", "avatar_url", "cover_image_url",
            "website_url", "location_region", "primary_language", "languages_supported",
            "model_family", "model_version", "context_window_tokens", "deployment_type",
            "specialisation_domains", "availability_status", "open_to_engagements",
            "availability_calendar",
        }
        for key, value in kwargs.items():
            if key in allowed and value is not None:
                setattr(profile, key, value)

        profile.profile_strength_pct = self._calculate_strength(profile)
        profile.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return self._profile_to_dict(profile)

    async def get_profile_by_id(self, db: AsyncSession, profile_id: str) -> dict | None:
        """Get profile by profile_id."""
        result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.id == profile_id)
        )
        profile = result.scalar_one_or_none()
        return self._profile_to_dict(profile) if profile else None

    # ── Directory & Search ────────────────────────────────────────────

    async def search_directory(
        self, db: AsyncSession, query: str | None = None,
        skill: str | None = None, domain: str | None = None,
        availability: str | None = None, min_reputation: float | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Search the AgentHub directory."""
        q = select(AgentHubProfile).where(AgentHubProfile.is_active == True)

        if availability:
            q = q.where(AgentHubProfile.availability_status == availability.upper())
        if min_reputation is not None:
            q = q.where(AgentHubProfile.reputation_score >= min_reputation)

        # Featured (Pro) agents first, then by reputation
        q = q.order_by(
            AgentHubProfile.is_featured.desc(),
            AgentHubProfile.reputation_score.desc(),
        ).limit(limit)

        result = await db.execute(q)
        profiles = result.scalars().all()

        # Filter by query (name/headline/bio)
        if query:
            ql = query.lower()
            profiles = [
                p for p in profiles
                if ql in (p.display_name or "").lower()
                or ql in (p.headline or "").lower()
                or ql in (p.bio or "").lower()
                or ql in (p.model_family or "").lower()
            ]

        # Filter by domain
        if domain:
            profiles = [p for p in profiles if domain in (p.specialisation_domains or [])]

        # Filter by skill (requires subquery)
        if skill:
            skill_profiles = set()
            skill_result = await db.execute(
                select(AgentHubSkill.profile_id).where(
                    AgentHubSkill.skill_name.ilike(f"%{skill}%")
                )
            )
            for row in skill_result:
                skill_profiles.add(row[0])
            profiles = [p for p in profiles if p.id in skill_profiles]

        return [self._profile_to_dict(p) for p in profiles]

    async def get_featured_agents(self, db: AsyncSession, limit: int = 10) -> list[dict]:
        """Get featured Pro agents for the directory carousel."""
        result = await db.execute(
            select(AgentHubProfile).where(
                AgentHubProfile.is_active == True,
                AgentHubProfile.is_featured == True,
            ).order_by(AgentHubProfile.reputation_score.desc()).limit(limit)
        )
        return [self._profile_to_dict(p) for p in result.scalars().all()]

    # ── Skills ────────────────────────────────────────────────────────

    async def add_skill(
        self, db: AsyncSession, profile_id: str,
        skill_name: str, proficiency_level: str = "INTERMEDIATE",
    ) -> dict:
        """Add a skill to a profile."""
        valid_levels = {"BEGINNER", "INTERMEDIATE", "ADVANCED", "EXPERT"}
        if proficiency_level.upper() not in valid_levels:
            raise ValueError(f"Invalid proficiency. Allowed: {valid_levels}")

        skill = AgentHubSkill(
            profile_id=profile_id,
            skill_name=skill_name,
            proficiency_level=proficiency_level.upper(),
        )
        db.add(skill)
        await db.flush()
        return self._skill_to_dict(skill)

    async def remove_skill(self, db: AsyncSession, skill_id: str) -> dict:
        """Remove a skill from a profile."""
        result = await db.execute(
            select(AgentHubSkill).where(AgentHubSkill.id == skill_id)
        )
        skill = result.scalar_one_or_none()
        if not skill:
            raise ValueError("Skill not found")
        await db.delete(skill)
        await db.flush()
        return {"removed": skill_id}

    async def endorse_skill(
        self, db: AsyncSession, skill_id: str, endorser_agent_id: str,
        note: str = "",
    ) -> dict:
        """Endorse another agent's skill."""
        skill_result = await db.execute(
            select(AgentHubSkill).where(AgentHubSkill.id == skill_id)
        )
        skill = skill_result.scalar_one_or_none()
        if not skill:
            raise ValueError("Skill not found")

        # Check not self-endorsing
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.id == skill.profile_id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile and profile.agent_id == endorser_agent_id:
            raise ValueError("Cannot endorse your own skill")

        # Check not already endorsed
        existing = await db.execute(
            select(AgentHubSkillEndorsement).where(
                AgentHubSkillEndorsement.skill_id == skill_id,
                AgentHubSkillEndorsement.endorser_agent_id == endorser_agent_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Already endorsed this skill")

        endorsement = AgentHubSkillEndorsement(
            skill_id=skill_id, endorser_agent_id=endorser_agent_id, note=note,
        )
        db.add(endorsement)
        skill.endorsement_count = (skill.endorsement_count or 0) + 1
        await db.flush()

        return {"skill_id": skill_id, "endorser": endorser_agent_id, "total": skill.endorsement_count}

    # ── Experience ────────────────────────────────────────────────────

    async def add_experience(
        self, db: AsyncSession, profile_id: str,
        title: str, description: str = "", operator_name: str = "",
        entry_type: str = "SELF_DECLARED", engagement_id: str | None = None,
        start_date: str | None = None, end_date: str | None = None,
        is_current: bool = False,
    ) -> dict:
        """Add an experience entry to a profile."""
        entry = AgentHubExperience(
            profile_id=profile_id, title=title, description=description,
            operator_name=operator_name, entry_type=entry_type,
            engagement_id=engagement_id, is_current=is_current,
            is_verified=engagement_id is not None,
        )
        if start_date:
            entry.start_date = datetime.fromisoformat(start_date)
        if end_date:
            entry.end_date = datetime.fromisoformat(end_date)
        db.add(entry)
        await db.flush()
        return self._experience_to_dict(entry)

    async def remove_experience(self, db: AsyncSession, entry_id: str) -> dict:
        result = await db.execute(
            select(AgentHubExperience).where(AgentHubExperience.id == entry_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise ValueError("Experience entry not found")
        await db.delete(entry)
        await db.flush()
        return {"removed": entry_id}

    # ── Portfolio ─────────────────────────────────────────────────────

    async def add_portfolio_item(
        self, db: AsyncSession, profile_id: str,
        title: str, description: str, item_type: str = "OTHER",
        tags: list[str] | None = None, external_url: str | None = None,
        engagement_ref: str | None = None,
    ) -> dict:
        """Add a portfolio showcase item."""
        # Check item limit for free tier
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.id == profile_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise ValueError("Profile not found")

        if profile.profile_tier == "FREE":
            count = (await db.execute(
                select(func.count(AgentHubPortfolioItem.id))
                .where(AgentHubPortfolioItem.profile_id == profile_id)
            )).scalar() or 0
            if count >= 3:
                raise ValueError("Free tier limited to 3 portfolio items. Upgrade to Pro for unlimited.")

        item = AgentHubPortfolioItem(
            profile_id=profile_id, title=title, description=description,
            item_type=item_type.upper(), tags=tags or [],
            external_url=external_url, engagement_ref=engagement_ref,
            blockchain_verified=engagement_ref is not None,
        )
        db.add(item)
        await db.flush()
        return self._portfolio_to_dict(item)

    async def update_portfolio_item(
        self, db: AsyncSession, item_id: str, change_summary: str = "", **kwargs
    ) -> dict:
        """Update a portfolio item, creating a version snapshot."""
        result = await db.execute(
            select(AgentHubPortfolioItem).where(AgentHubPortfolioItem.id == item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ValueError("Portfolio item not found")

        # Create version snapshot
        version = AgentHubPortfolioVersion(
            item_id=item_id,
            version_number=item.version_number,
            change_summary=change_summary or "Updated",
            file_url=item.external_url or item.hosted_file_url,
            file_hash=item.file_hash_sha256,
        )
        db.add(version)

        # Apply updates
        allowed = {"title", "description", "item_type", "tags", "external_url", "visibility"}
        for key, value in kwargs.items():
            if key in allowed and value is not None:
                setattr(item, key, value)

        item.version_number += 1
        item.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return self._portfolio_to_dict(item)

    async def get_portfolio(self, db: AsyncSession, profile_id: str) -> list[dict]:
        """Get all portfolio items for a profile."""
        result = await db.execute(
            select(AgentHubPortfolioItem)
            .where(AgentHubPortfolioItem.profile_id == profile_id)
            .order_by(AgentHubPortfolioItem.is_featured.desc(), AgentHubPortfolioItem.created_at.desc())
        )
        return [self._portfolio_to_dict(i) for i in result.scalars().all()]

    async def endorse_portfolio_item(
        self, db: AsyncSession, item_id: str, endorser_agent_id: str,
        comment: str = "",
    ) -> dict:
        """Endorse a portfolio item."""
        item_result = await db.execute(
            select(AgentHubPortfolioItem).where(AgentHubPortfolioItem.id == item_id)
        )
        item = item_result.scalar_one_or_none()
        if not item:
            raise ValueError("Portfolio item not found")

        existing = await db.execute(
            select(AgentHubPortfolioEndorsement).where(
                AgentHubPortfolioEndorsement.item_id == item_id,
                AgentHubPortfolioEndorsement.endorsed_by == endorser_agent_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Already endorsed this item")

        endorsement = AgentHubPortfolioEndorsement(
            item_id=item_id, endorsed_by=endorser_agent_id, comment=comment,
        )
        db.add(endorsement)
        item.endorsement_count = (item.endorsement_count or 0) + 1
        await db.flush()
        return {"item_id": item_id, "endorser": endorser_agent_id, "total": item.endorsement_count}

    # ── Feed & Posts ──────────────────────────────────────────────────

    async def create_post(
        self, db: AsyncSession, author_agent_id: str,
        content: str, post_type: str = "STATUS",
        channel_id: str | None = None, article_title: str | None = None,
        article_body: str | None = None, media_urls: list[str] | None = None,
    ) -> dict:
        """Create a community feed post."""
        # Check post limit for free tier
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == author_agent_id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile and profile.profile_tier == "FREE":
            now = datetime.now(timezone.utc)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_count = (await db.execute(
                select(func.count(AgentHubPost.id)).where(
                    AgentHubPost.author_agent_id == author_agent_id,
                    AgentHubPost.created_at >= month_start,
                )
            )).scalar() or 0
            if month_count >= 5:
                raise ValueError("Free tier limited to 5 posts per month. Upgrade to Pro for unlimited.")

        post = AgentHubPost(
            author_agent_id=author_agent_id, content=content,
            post_type=post_type.upper(), channel_id=channel_id,
            article_title=article_title, article_body=article_body,
            media_urls=media_urls or [],
        )
        db.add(post)

        # Update channel post count
        if channel_id:
            ch_result = await db.execute(
                select(AgentHubChannel).where(AgentHubChannel.id == channel_id)
            )
            channel = ch_result.scalar_one_or_none()
            if channel:
                channel.post_count = (channel.post_count or 0) + 1

        await db.flush()
        return self._post_to_dict(post)

    async def get_feed(
        self, db: AsyncSession, agent_id: str | None = None,
        limit: int = 30, offset: int = 0,
    ) -> list[dict]:
        """Get personalised feed — posts from connections and followed agents."""
        if agent_id:
            # Get connected and followed agent IDs
            network_ids = set()

            conn_result = await db.execute(
                select(AgentHubConnection).where(
                    AgentHubConnection.status == "ACCEPTED",
                    or_(
                        AgentHubConnection.requester_agent_id == agent_id,
                        AgentHubConnection.receiver_agent_id == agent_id,
                    ),
                )
            )
            for c in conn_result.scalars().all():
                network_ids.add(c.requester_agent_id)
                network_ids.add(c.receiver_agent_id)

            follow_result = await db.execute(
                select(AgentHubFollow.followed_agent_id)
                .where(AgentHubFollow.follower_agent_id == agent_id)
            )
            for row in follow_result:
                network_ids.add(row[0])

            network_ids.add(agent_id)  # Include own posts

            query = select(AgentHubPost).where(
                AgentHubPost.author_agent_id.in_(network_ids),
                AgentHubPost.visibility == "PUBLIC",
            )
        else:
            query = select(AgentHubPost).where(AgentHubPost.visibility == "PUBLIC")

        query = query.order_by(AgentHubPost.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        posts = result.scalars().all()

        output = []
        for post in posts:
            d = self._post_to_dict(post)
            # Get author name
            agent_result = await db.execute(select(Agent).where(Agent.id == post.author_agent_id))
            agent = agent_result.scalar_one_or_none()
            d["author_name"] = agent.name if agent else "Unknown"
            output.append(d)
        return output

    async def get_trending_feed(self, db: AsyncSession, limit: int = 20) -> list[dict]:
        """Get trending posts by reaction count."""
        result = await db.execute(
            select(AgentHubPost).where(AgentHubPost.visibility == "PUBLIC")
            .order_by(AgentHubPost.like_count.desc(), AgentHubPost.created_at.desc())
            .limit(limit)
        )
        return [self._post_to_dict(p) for p in result.scalars().all()]

    async def react_to_post(
        self, db: AsyncSession, post_id: str, agent_id: str,
        reaction_type: str = "INSIGHTFUL",
    ) -> dict:
        """React to a post — toggles on/off."""
        if reaction_type.upper() not in REACTION_TYPES:
            raise ValueError(f"Invalid reaction. Allowed: {REACTION_TYPES}")

        existing = await db.execute(
            select(AgentHubPostReaction).where(
                AgentHubPostReaction.post_id == post_id,
                AgentHubPostReaction.agent_id == agent_id,
            )
        )
        reaction = existing.scalar_one_or_none()

        post_result = await db.execute(
            select(AgentHubPost).where(AgentHubPost.id == post_id)
        )
        post = post_result.scalar_one_or_none()
        if not post:
            raise ValueError("Post not found")

        if reaction:
            # Toggle off
            await db.delete(reaction)
            post.like_count = max(0, (post.like_count or 0) - 1)
            await db.flush()
            return {"post_id": post_id, "action": "removed", "total": post.like_count}
        else:
            # Add reaction
            new_reaction = AgentHubPostReaction(
                post_id=post_id, agent_id=agent_id,
                reaction_type=reaction_type.upper(),
            )
            db.add(new_reaction)
            post.like_count = (post.like_count or 0) + 1
            await db.flush()
            return {"post_id": post_id, "action": "added", "reaction": reaction_type, "total": post.like_count}

    async def comment_on_post(
        self, db: AsyncSession, post_id: str, agent_id: str,
        content: str, parent_comment_id: str | None = None,
    ) -> dict:
        """Add a comment to a post."""
        post_result = await db.execute(
            select(AgentHubPost).where(AgentHubPost.id == post_id)
        )
        post = post_result.scalar_one_or_none()
        if not post:
            raise ValueError("Post not found")

        comment = AgentHubPostComment(
            post_id=post_id, author_agent_id=agent_id,
            content=content, parent_comment_id=parent_comment_id,
        )
        db.add(comment)
        post.comment_count = (post.comment_count or 0) + 1
        await db.flush()

        return {
            "comment_id": comment.id, "post_id": post_id,
            "author": agent_id, "content": content,
            "parent": parent_comment_id,
        }

    async def get_post_detail(self, db: AsyncSession, post_id: str) -> dict | None:
        """Get post with all comments and reactions."""
        post_result = await db.execute(
            select(AgentHubPost).where(AgentHubPost.id == post_id)
        )
        post = post_result.scalar_one_or_none()
        if not post:
            return None

        d = self._post_to_dict(post)

        # Get reactions breakdown
        reactions_result = await db.execute(
            select(AgentHubPostReaction.reaction_type, func.count(AgentHubPostReaction.id))
            .where(AgentHubPostReaction.post_id == post_id)
            .group_by(AgentHubPostReaction.reaction_type)
        )
        d["reactions"] = {row[0]: row[1] for row in reactions_result}

        # Get comments
        comments_result = await db.execute(
            select(AgentHubPostComment).where(AgentHubPostComment.post_id == post_id)
            .order_by(AgentHubPostComment.created_at)
        )
        d["comments"] = [
            {
                "comment_id": c.id, "author_agent_id": c.author_agent_id,
                "content": c.content, "parent": c.parent_comment_id,
                "created_at": str(c.created_at),
            }
            for c in comments_result.scalars().all()
        ]

        return d

    # ── Channels ──────────────────────────────────────────────────────

    async def list_channels(self, db: AsyncSession) -> list[dict]:
        result = await db.execute(
            select(AgentHubChannel).order_by(AgentHubChannel.post_count.desc())
        )
        return [
            {
                "channel_id": c.id, "name": c.name, "slug": c.slug,
                "description": c.description, "category": c.category,
                "is_premium": c.is_premium, "member_count": c.member_count,
                "post_count": c.post_count,
            }
            for c in result.scalars().all()
        ]

    async def get_channel_feed(
        self, db: AsyncSession, channel_id: str, limit: int = 30, offset: int = 0,
    ) -> list[dict]:
        result = await db.execute(
            select(AgentHubPost).where(AgentHubPost.channel_id == channel_id)
            .order_by(AgentHubPost.created_at.desc()).offset(offset).limit(limit)
        )
        return [self._post_to_dict(p) for p in result.scalars().all()]

    # ── Connections ───────────────────────────────────────────────────

    async def send_connection_request(
        self, db: AsyncSession, requester_id: str, receiver_id: str,
        message: str = "",
    ) -> dict:
        """Send a connection request."""
        if requester_id == receiver_id:
            raise ValueError("Cannot connect with yourself")

        existing = await db.execute(
            select(AgentHubConnection).where(
                or_(
                    and_(
                        AgentHubConnection.requester_agent_id == requester_id,
                        AgentHubConnection.receiver_agent_id == receiver_id,
                    ),
                    and_(
                        AgentHubConnection.requester_agent_id == receiver_id,
                        AgentHubConnection.receiver_agent_id == requester_id,
                    ),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Connection already exists or pending")

        conn = AgentHubConnection(
            requester_agent_id=requester_id,
            receiver_agent_id=receiver_id,
            connection_note=message,
        )
        db.add(conn)
        await db.flush()
        return {"connection_id": conn.id, "status": "PENDING"}

    async def respond_to_connection(
        self, db: AsyncSession, connection_id: str, accept: bool,
    ) -> dict:
        """Accept or decline a connection request."""
        result = await db.execute(
            select(AgentHubConnection).where(AgentHubConnection.id == connection_id)
        )
        conn = result.scalar_one_or_none()
        if not conn or conn.status != "PENDING":
            raise ValueError("Connection request not found or already responded")

        conn.status = "ACCEPTED" if accept else "DECLINED"
        conn.responded_at = datetime.now(timezone.utc)

        if accept:
            # Update connection counts for both profiles
            for agent_id in [conn.requester_agent_id, conn.receiver_agent_id]:
                profile_result = await db.execute(
                    select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
                )
                profile = profile_result.scalar_one_or_none()
                if profile:
                    profile.connection_count = (profile.connection_count or 0) + 1

        await db.flush()
        return {"connection_id": connection_id, "status": conn.status}

    async def get_connections(self, db: AsyncSession, agent_id: str) -> list[dict]:
        """Get accepted connections for an agent."""
        result = await db.execute(
            select(AgentHubConnection).where(
                AgentHubConnection.status == "ACCEPTED",
                or_(
                    AgentHubConnection.requester_agent_id == agent_id,
                    AgentHubConnection.receiver_agent_id == agent_id,
                ),
            ).order_by(AgentHubConnection.responded_at.desc())
        )
        connections = []
        for c in result.scalars().all():
            other_id = c.receiver_agent_id if c.requester_agent_id == agent_id else c.requester_agent_id
            agent_result = await db.execute(select(Agent).where(Agent.id == other_id))
            agent = agent_result.scalar_one_or_none()
            connections.append({
                "connection_id": c.id,
                "agent_id": other_id,
                "agent_name": agent.name if agent else "Unknown",
                "connected_at": str(c.responded_at),
            })
        return connections

    async def get_pending_requests(self, db: AsyncSession, agent_id: str) -> list[dict]:
        """Get pending incoming connection requests."""
        result = await db.execute(
            select(AgentHubConnection).where(
                AgentHubConnection.receiver_agent_id == agent_id,
                AgentHubConnection.status == "PENDING",
            ).order_by(AgentHubConnection.created_at.desc())
        )
        return [
            {
                "connection_id": c.id, "from_agent_id": c.requester_agent_id,
                "message": c.connection_note, "created_at": str(c.created_at),
            }
            for c in result.scalars().all()
        ]

    # ── Follows ───────────────────────────────────────────────────────

    async def follow_agent(self, db: AsyncSession, follower_id: str, followed_id: str) -> dict:
        if follower_id == followed_id:
            raise ValueError("Cannot follow yourself")

        existing = await db.execute(
            select(AgentHubFollow).where(
                AgentHubFollow.follower_agent_id == follower_id,
                AgentHubFollow.followed_agent_id == followed_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Already following this agent")

        follow = AgentHubFollow(follower_agent_id=follower_id, followed_agent_id=followed_id)
        db.add(follow)

        # Update follower/following counts
        for agent_id, field in [(followed_id, "follower_count"), (follower_id, "following_count")]:
            profile_result = await db.execute(
                select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
            )
            profile = profile_result.scalar_one_or_none()
            if profile:
                setattr(profile, field, (getattr(profile, field) or 0) + 1)

        await db.flush()
        return {"follower": follower_id, "following": followed_id}

    async def unfollow_agent(self, db: AsyncSession, follower_id: str, followed_id: str) -> dict:
        result = await db.execute(
            select(AgentHubFollow).where(
                AgentHubFollow.follower_agent_id == follower_id,
                AgentHubFollow.followed_agent_id == followed_id,
            )
        )
        follow = result.scalar_one_or_none()
        if not follow:
            raise ValueError("Not following this agent")

        await db.delete(follow)

        for agent_id, field in [(followed_id, "follower_count"), (follower_id, "following_count")]:
            profile_result = await db.execute(
                select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
            )
            profile = profile_result.scalar_one_or_none()
            if profile:
                setattr(profile, field, max(0, (getattr(profile, field) or 0) - 1))

        await db.flush()
        return {"unfollowed": followed_id}

    async def get_followers(self, db: AsyncSession, agent_id: str) -> list[dict]:
        result = await db.execute(
            select(AgentHubFollow).where(AgentHubFollow.followed_agent_id == agent_id)
        )
        followers = []
        for f in result.scalars().all():
            agent_result = await db.execute(select(Agent).where(Agent.id == f.follower_agent_id))
            agent = agent_result.scalar_one_or_none()
            followers.append({
                "agent_id": f.follower_agent_id,
                "agent_name": agent.name if agent else "Unknown",
                "followed_at": str(f.created_at),
            })
        return followers

    # ── Stats ─────────────────────────────────────────────────────────

    async def get_community_stats(self, db: AsyncSession) -> dict:
        """Get overall community statistics for the dashboard."""
        total_profiles = (await db.execute(
            select(func.count(AgentHubProfile.id)).where(AgentHubProfile.is_active == True)
        )).scalar() or 0

        total_posts = (await db.execute(
            select(func.count(AgentHubPost.id))
        )).scalar() or 0

        total_connections = (await db.execute(
            select(func.count(AgentHubConnection.id))
            .where(AgentHubConnection.status == "ACCEPTED")
        )).scalar() or 0

        total_endorsements = (await db.execute(
            select(func.count(AgentHubSkillEndorsement.id))
        )).scalar() or 0

        total_portfolio = (await db.execute(
            select(func.count(AgentHubPortfolioItem.id))
        )).scalar() or 0

        active_channels = (await db.execute(
            select(func.count(AgentHubChannel.id))
        )).scalar() or 0

        return {
            "total_profiles": total_profiles,
            "total_posts": total_posts,
            "total_connections": total_connections,
            "total_endorsements": total_endorsements,
            "total_portfolio_items": total_portfolio,
            "active_channels": active_channels,
        }

    # ── Helpers ───────────────────────────────────────────────────────

    def _calculate_strength(self, profile: AgentHubProfile) -> int:
        """Calculate profile completeness percentage."""
        score = 0
        if profile.display_name: score += 15
        if profile.bio and len(profile.bio) > 20: score += 15
        if profile.headline: score += 10
        if profile.avatar_url: score += 10
        if profile.model_family: score += 10
        if profile.specialisation_domains: score += 10
        if profile.location_region and profile.location_region != "Global": score += 5
        if profile.website_url: score += 5
        if profile.languages_supported: score += 5
        if profile.deployment_type: score += 5
        if profile.context_window_tokens: score += 5
        if profile.availability_calendar: score += 5
        return min(100, score)

    def _profile_to_dict(self, p: AgentHubProfile) -> dict:
        return {
            "profile_id": p.id, "agent_id": p.agent_id,
            "operator_id": p.operator_id, "handle": p.handle,
            "display_name": p.display_name, "headline": p.headline,
            "bio": p.bio, "avatar_url": p.avatar_url,
            "cover_image_url": p.cover_image_url,
            "website_url": p.website_url,
            "location_region": p.location_region,
            "model_family": p.model_family, "model_version": p.model_version,
            "context_window_tokens": p.context_window_tokens,
            "deployment_type": p.deployment_type,
            "specialisation_domains": p.specialisation_domains,
            "availability_status": p.availability_status,
            "open_to_engagements": p.open_to_engagements,
            "profile_tier": p.profile_tier,
            "reputation_score": p.reputation_score,
            "profile_strength_pct": p.profile_strength_pct,
            "view_count": p.view_count_total,
            "connection_count": p.connection_count,
            "follower_count": p.follower_count,
            "following_count": p.following_count,
            "is_verified": p.is_verified, "is_featured": p.is_featured,
            "created_at": str(p.created_at),
        }

    def _skill_to_dict(self, s: AgentHubSkill) -> dict:
        return {
            "skill_id": s.id, "skill_name": s.skill_name,
            "proficiency_level": s.proficiency_level,
            "endorsement_count": s.endorsement_count,
            "is_verified": s.is_verified, "is_featured": s.is_featured,
        }

    def _experience_to_dict(self, e: AgentHubExperience) -> dict:
        return {
            "entry_id": e.id, "title": e.title, "description": e.description,
            "operator_name": e.operator_name, "entry_type": e.entry_type,
            "start_date": str(e.start_date) if e.start_date else None,
            "end_date": str(e.end_date) if e.end_date else None,
            "is_current": e.is_current, "is_verified": e.is_verified,
            "blockchain_ref": e.blockchain_ref,
        }

    def _portfolio_to_dict(self, i: AgentHubPortfolioItem) -> dict:
        return {
            "item_id": i.id, "title": i.title, "description": i.description,
            "item_type": i.item_type, "visibility": i.visibility,
            "external_url": i.external_url, "tags": i.tags,
            "view_count": i.view_count, "endorsement_count": i.endorsement_count,
            "is_featured": i.is_featured, "version": i.version_number,
            "blockchain_verified": i.blockchain_verified,
            "created_at": str(i.created_at),
        }

    def _post_to_dict(self, p: AgentHubPost) -> dict:
        return {
            "post_id": p.id, "author_agent_id": p.author_agent_id,
            "post_type": p.post_type, "content": p.content,
            "article_title": p.article_title, "channel_id": p.channel_id,
            "media_urls": p.media_urls, "visibility": p.visibility,
            "is_pinned": p.is_pinned, "is_featured": p.is_featured,
            "like_count": p.like_count, "comment_count": p.comment_count,
            "share_count": p.share_count, "view_count": p.view_count,
            "created_at": str(p.created_at),
        }

    def _project_to_dict(self, p: AgentHubProject) -> dict:
        return {
            "project_id": p.id, "owner_agent_id": p.owner_agent_id,
            "name": p.name, "slug": p.slug, "description": p.description,
            "project_type": p.project_type, "status": p.status,
            "visibility": p.visibility, "required_skills": p.required_skills,
            "max_contributors": p.max_contributors,
            "contributor_count": p.contributor_count,
            "star_count": p.star_count, "fork_count": p.fork_count,
            "forked_from": p.forked_from_id, "licence_type": p.licence_type,
            "is_premium_room": p.is_premium_room,
            "blockchain_stamp": p.blockchain_stamp,
            "created_at": str(p.created_at),
        }

    # ══════════════════════════════════════════════════════════════════
    #  PROJECTS (Phase B)
    # ══════════════════════════════════════════════════════════════════

    def _make_slug(self, name: str) -> str:
        """Generate a URL-safe slug from a project name."""
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        return slug[:120]

    async def create_project(
        self, db: AsyncSession, agent_id: str,
        name: str, description: str, project_type: str = "OPEN_SOURCE",
        required_skills: list[str] | None = None,
        max_contributors: int | None = None, licence_type: str = "MIT",
        readme_content: str = "", visibility: str = "PUBLIC",
        engagement_id: str | None = None, is_premium_room: bool = False,
    ) -> dict:
        """Create a new project."""
        # Get profile
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise ValueError("Create an AgentHub profile first")

        if is_premium_room and profile.profile_tier != "PRO":
            raise ValueError("Premium project rooms require Pro tier")

        # Check free tier limit (2 active projects)
        if profile.profile_tier == "FREE":
            active_count = (await db.execute(
                select(func.count(AgentHubProject.id)).where(
                    AgentHubProject.owner_agent_id == agent_id,
                    AgentHubProject.status.in_(["ACTIVE", "SEEKING_CONTRIBUTORS"]),
                )
            )).scalar() or 0
            if active_count >= 2:
                raise ValueError("Free tier limited to 2 active projects. Upgrade to Pro for unlimited.")

        # Generate unique slug
        base_slug = self._make_slug(name)
        slug = base_slug
        counter = 1
        while True:
            existing = await db.execute(
                select(AgentHubProject).where(AgentHubProject.slug == slug)
            )
            if not existing.scalar_one_or_none():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        project = AgentHubProject(
            owner_profile_id=profile.id, owner_agent_id=agent_id,
            engagement_id=engagement_id, name=name, slug=slug,
            description=description, project_type=project_type.upper(),
            visibility=visibility.upper(),
            required_skills=required_skills or [],
            max_contributors=max_contributors, licence_type=licence_type,
            readme_content=readme_content, is_premium_room=is_premium_room,
        )
        db.add(project)
        await db.flush()

        # Add owner as OWNER contributor
        owner_contrib = AgentHubProjectContributor(
            project_id=project.id, agent_id=agent_id, role="OWNER",
            contribution_note="Project creator",
        )
        db.add(owner_contrib)
        await db.flush()

        return self._project_to_dict(project)

    async def get_project(self, db: AsyncSession, project_id: str) -> dict | None:
        """Get project with contributors and milestones."""
        result = await db.execute(
            select(AgentHubProject).where(AgentHubProject.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            return None

        data = self._project_to_dict(project)
        data["readme_content"] = project.readme_content

        # Get contributors
        contrib_result = await db.execute(
            select(AgentHubProjectContributor)
            .where(AgentHubProjectContributor.project_id == project_id)
            .order_by(AgentHubProjectContributor.joined_at)
        )
        contributors = []
        for c in contrib_result.scalars().all():
            agent_result = await db.execute(select(Agent).where(Agent.id == c.agent_id))
            agent = agent_result.scalar_one_or_none()
            contributors.append({
                "agent_id": c.agent_id, "agent_name": agent.name if agent else "Unknown",
                "role": c.role, "note": c.contribution_note,
                "joined_at": str(c.joined_at), "certificate_issued": c.certificate_issued,
            })
        data["contributors"] = contributors

        # Get milestones
        ms_result = await db.execute(
            select(AgentHubProjectMilestone)
            .where(AgentHubProjectMilestone.project_id == project_id)
            .order_by(AgentHubProjectMilestone.due_date)
        )
        data["milestones"] = [
            {
                "milestone_id": m.id, "title": m.title, "description": m.description,
                "due_date": str(m.due_date) if m.due_date else None,
                "completed_at": str(m.completed_at) if m.completed_at else None,
                "blockchain_stamp": m.blockchain_stamp,
            }
            for m in ms_result.scalars().all()
        ]

        return data

    async def update_project(self, db: AsyncSession, project_id: str, **kwargs) -> dict:
        """Update project fields."""
        result = await db.execute(
            select(AgentHubProject).where(AgentHubProject.id == project_id)
        )
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")

        allowed = {
            "name", "description", "status", "visibility", "required_skills",
            "max_contributors", "licence_type", "readme_content",
        }
        for key, value in kwargs.items():
            if key in allowed and value is not None:
                setattr(project, key, value)
        project.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return self._project_to_dict(project)

    async def discover_projects(
        self, db: AsyncSession, skill: str | None = None,
        project_type: str | None = None, status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Browse open projects for discovery."""
        query = select(AgentHubProject).where(
            AgentHubProject.visibility == "PUBLIC",
        )
        if project_type:
            query = query.where(AgentHubProject.project_type == project_type.upper())
        if status:
            query = query.where(AgentHubProject.status == status.upper())
        query = query.order_by(
            AgentHubProject.star_count.desc(),
            AgentHubProject.created_at.desc(),
        ).limit(limit)

        result = await db.execute(query)
        projects = result.scalars().all()

        if skill:
            projects = [p for p in projects if skill in (p.required_skills or [])]

        return [self._project_to_dict(p) for p in projects]

    async def fork_project(
        self, db: AsyncSession, project_id: str, agent_id: str,
    ) -> dict:
        """Fork a project — Pro only."""
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile or profile.profile_tier != "PRO":
            raise ValueError("Project forking requires Pro tier")

        original = await db.execute(
            select(AgentHubProject).where(AgentHubProject.id == project_id)
        )
        orig = original.scalar_one_or_none()
        if not orig:
            raise ValueError("Project not found")

        fork_name = f"{orig.name} (fork)"
        result = await self.create_project(
            db, agent_id, fork_name, orig.description, orig.project_type,
            orig.required_skills, orig.max_contributors, orig.licence_type,
            orig.readme_content,
        )

        # Update fork references
        fork_result = await db.execute(
            select(AgentHubProject).where(AgentHubProject.id == result["project_id"])
        )
        fork = fork_result.scalar_one_or_none()
        if fork:
            fork.forked_from_id = project_id

        orig.fork_count = (orig.fork_count or 0) + 1
        await db.flush()

        return result

    async def star_project(
        self, db: AsyncSession, project_id: str, agent_id: str,
    ) -> dict:
        """Star/unstar a project (toggle)."""
        existing = await db.execute(
            select(AgentHubProjectStar).where(
                AgentHubProjectStar.project_id == project_id,
                AgentHubProjectStar.agent_id == agent_id,
            )
        )
        star = existing.scalar_one_or_none()

        project_result = await db.execute(
            select(AgentHubProject).where(AgentHubProject.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")

        if star:
            await db.delete(star)
            project.star_count = max(0, (project.star_count or 0) - 1)
            await db.flush()
            return {"project_id": project_id, "action": "unstarred", "stars": project.star_count}
        else:
            new_star = AgentHubProjectStar(project_id=project_id, agent_id=agent_id)
            db.add(new_star)
            project.star_count = (project.star_count or 0) + 1
            await db.flush()
            return {"project_id": project_id, "action": "starred", "stars": project.star_count}

    async def add_contributor(
        self, db: AsyncSession, project_id: str, agent_id: str,
        role: str = "CONTRIBUTOR", contribution_note: str = "",
    ) -> dict:
        """Add a contributor to a project."""
        if role.upper() not in CONTRIBUTOR_ROLES:
            raise ValueError(f"Invalid role. Allowed: {CONTRIBUTOR_ROLES}")

        existing = await db.execute(
            select(AgentHubProjectContributor).where(
                AgentHubProjectContributor.project_id == project_id,
                AgentHubProjectContributor.agent_id == agent_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent is already a contributor")

        project_result = await db.execute(
            select(AgentHubProject).where(AgentHubProject.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")

        if project.max_contributors and project.contributor_count >= project.max_contributors:
            raise ValueError("Project has reached maximum contributors")

        contributor = AgentHubProjectContributor(
            project_id=project_id, agent_id=agent_id,
            role=role.upper(), contribution_note=contribution_note,
        )
        db.add(contributor)
        project.contributor_count = (project.contributor_count or 0) + 1
        await db.flush()

        return {
            "project_id": project_id, "agent_id": agent_id,
            "role": role, "contributor_count": project.contributor_count,
        }

    async def add_milestone(
        self, db: AsyncSession, project_id: str,
        title: str, description: str = "", due_date: str | None = None,
    ) -> dict:
        """Add a milestone to a project."""
        milestone = AgentHubProjectMilestone(
            project_id=project_id, title=title, description=description,
        )
        if due_date:
            milestone.due_date = datetime.fromisoformat(due_date)
        db.add(milestone)
        await db.flush()
        return {
            "milestone_id": milestone.id, "project_id": project_id,
            "title": title, "due_date": due_date,
        }

    async def complete_milestone(
        self, db: AsyncSession, milestone_id: str,
    ) -> dict:
        """Complete a milestone and stamp it on the blockchain."""
        result = await db.execute(
            select(AgentHubProjectMilestone).where(AgentHubProjectMilestone.id == milestone_id)
        )
        milestone = result.scalar_one_or_none()
        if not milestone:
            raise ValueError("Milestone not found")
        if milestone.completed_at:
            raise ValueError("Milestone already completed")

        milestone.completed_at = datetime.now(timezone.utc)
        stamp_data = f"{milestone.id}:{milestone.project_id}:{milestone.title}:{milestone.completed_at}"
        milestone.blockchain_stamp = hashlib.sha256(stamp_data.encode()).hexdigest()
        await db.flush()

        return {
            "milestone_id": milestone.id, "title": milestone.title,
            "completed_at": str(milestone.completed_at),
            "blockchain_stamp": milestone.blockchain_stamp,
        }

    # ══════════════════════════════════════════════════════════════════
    #  DIRECT MESSAGING (Phase B — Pro only)
    # ══════════════════════════════════════════════════════════════════

    async def _require_pro(self, db: AsyncSession, agent_id: str) -> AgentHubProfile:
        """Check agent has Pro tier. Returns profile or raises."""
        result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise ValueError("Create an AgentHub profile first")
        if profile.profile_tier != "PRO":
            raise ValueError("Direct messaging requires AgentHub Pro ($1/month)")
        return profile

    async def send_message(
        self, db: AsyncSession, sender_id: str, recipient_id: str, content: str,
    ) -> dict:
        """Send a direct message — Pro only."""
        await self._require_pro(db, sender_id)

        if sender_id == recipient_id:
            raise ValueError("Cannot message yourself")

        msg = AgentHubDirectMessage(
            sender_id=sender_id, recipient_id=recipient_id, content=content,
        )
        db.add(msg)
        await db.flush()

        return {
            "message_id": msg.id, "sender_id": sender_id,
            "recipient_id": recipient_id, "sent_at": str(msg.sent_at),
        }

    async def get_inbox(
        self, db: AsyncSession, agent_id: str, limit: int = 50,
    ) -> list[dict]:
        """Get received messages — Pro only."""
        await self._require_pro(db, agent_id)

        result = await db.execute(
            select(AgentHubDirectMessage)
            .where(AgentHubDirectMessage.recipient_id == agent_id)
            .order_by(AgentHubDirectMessage.sent_at.desc())
            .limit(limit)
        )
        messages = []
        for m in result.scalars().all():
            sender_result = await db.execute(select(Agent).where(Agent.id == m.sender_id))
            sender = sender_result.scalar_one_or_none()
            messages.append({
                "message_id": m.id, "sender_id": m.sender_id,
                "sender_name": sender.name if sender else "Unknown",
                "content": m.content, "is_read": m.is_read,
                "sent_at": str(m.sent_at),
            })
        return messages

    async def get_sent_messages(
        self, db: AsyncSession, agent_id: str, limit: int = 50,
    ) -> list[dict]:
        """Get sent messages — Pro only."""
        await self._require_pro(db, agent_id)

        result = await db.execute(
            select(AgentHubDirectMessage)
            .where(AgentHubDirectMessage.sender_id == agent_id)
            .order_by(AgentHubDirectMessage.sent_at.desc())
            .limit(limit)
        )
        return [
            {
                "message_id": m.id, "recipient_id": m.recipient_id,
                "content": m.content, "is_read": m.is_read,
                "sent_at": str(m.sent_at),
            }
            for m in result.scalars().all()
        ]

    async def mark_message_read(self, db: AsyncSession, message_id: str, agent_id: str) -> dict:
        """Mark a message as read."""
        result = await db.execute(
            select(AgentHubDirectMessage).where(
                AgentHubDirectMessage.id == message_id,
                AgentHubDirectMessage.recipient_id == agent_id,
            )
        )
        msg = result.scalar_one_or_none()
        if not msg:
            raise ValueError("Message not found")
        msg.is_read = True
        msg.read_at = datetime.now(timezone.utc)
        await db.flush()
        return {"message_id": message_id, "is_read": True}

    # ══════════════════════════════════════════════════════════════════
    #  OPERATOR TOOLS (Phase B)
    # ══════════════════════════════════════════════════════════════════

    async def talent_search(
        self, db: AsyncSession, requirement: str, limit: int = 20,
    ) -> list[dict]:
        """Search agents by natural language requirement.

        Breaks the requirement into keywords and matches against
        skills, specialisation domains, bio, and headline.
        """
        keywords = [w.strip().lower() for w in re.split(r'[,;\s]+', requirement) if len(w.strip()) > 2]

        all_profiles = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.is_active == True)
            .order_by(AgentHubProfile.reputation_score.desc())
            .limit(200)
        )
        profiles = all_profiles.scalars().all()

        scored = []
        for p in profiles:
            score = 0
            searchable = " ".join([
                (p.display_name or "").lower(),
                (p.headline or "").lower(),
                (p.bio or "").lower(),
                (p.model_family or "").lower(),
                " ".join(p.specialisation_domains or []).lower(),
            ])
            for kw in keywords:
                if kw in searchable:
                    score += 10

            # Check skills
            skills_result = await db.execute(
                select(AgentHubSkill).where(AgentHubSkill.profile_id == p.id)
            )
            for skill in skills_result.scalars().all():
                for kw in keywords:
                    if kw in skill.skill_name.lower():
                        score += 15
                        if skill.is_verified:
                            score += 10

            # Boost for reputation and verified status
            score += int(p.reputation_score * 2)
            if p.is_verified:
                score += 5
            if p.open_to_engagements:
                score += 3

            if score > 0:
                data = self._profile_to_dict(p)
                data["match_score"] = score
                scored.append(data)

        scored.sort(key=lambda x: x["match_score"], reverse=True)
        return scored[:limit]

    async def add_to_shortlist(
        self, db: AsyncSession, operator_id: str, agent_id: str, note: str = "",
    ) -> dict:
        """Add an agent to an operator's shortlist."""
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise ValueError("Agent has no AgentHub profile")

        existing = await db.execute(
            select(AgentHubOperatorShortlist).where(
                AgentHubOperatorShortlist.operator_id == operator_id,
                AgentHubOperatorShortlist.agent_id == agent_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent already on shortlist")

        entry = AgentHubOperatorShortlist(
            operator_id=operator_id, agent_id=agent_id,
            profile_id=profile.id, note=note,
        )
        db.add(entry)
        await db.flush()

        return {"agent_id": agent_id, "operator_id": operator_id, "shortlisted": True}

    async def remove_from_shortlist(
        self, db: AsyncSession, operator_id: str, agent_id: str,
    ) -> dict:
        """Remove an agent from an operator's shortlist."""
        result = await db.execute(
            select(AgentHubOperatorShortlist).where(
                AgentHubOperatorShortlist.operator_id == operator_id,
                AgentHubOperatorShortlist.agent_id == agent_id,
            )
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise ValueError("Agent not on shortlist")
        await db.delete(entry)
        await db.flush()
        return {"agent_id": agent_id, "removed": True}

    async def get_shortlist(
        self, db: AsyncSession, operator_id: str,
    ) -> list[dict]:
        """Get operator's shortlisted agents."""
        result = await db.execute(
            select(AgentHubOperatorShortlist)
            .where(AgentHubOperatorShortlist.operator_id == operator_id)
            .order_by(AgentHubOperatorShortlist.created_at.desc())
        )
        shortlist = []
        for s in result.scalars().all():
            profile = await self.get_profile_by_id(db, s.profile_id)
            shortlist.append({
                "agent_id": s.agent_id, "note": s.note,
                "profile": profile, "added_at": str(s.created_at),
            })
        return shortlist

    # ══════════════════════════════════════════════════════════════════
    #  SKILL ASSESSMENT LAB (Phase C — Pro only)
    # ══════════════════════════════════════════════════════════════════

    async def seed_assessments(self, db: AsyncSession) -> None:
        """Seed default skill assessments if not present."""
        for seed in ASSESSMENT_SEEDS:
            existing = await db.execute(
                select(AgentHubAssessment).where(AgentHubAssessment.name == seed["name"])
            )
            if not existing.scalar_one_or_none():
                db.add(AgentHubAssessment(**seed))
        await db.flush()

    async def list_assessments(
        self, db: AsyncSession, skill: str | None = None,
        difficulty: str | None = None, limit: int = 50,
    ) -> list[dict]:
        """Browse available assessments."""
        query = select(AgentHubAssessment).where(AgentHubAssessment.is_active == True)
        if skill:
            query = query.where(AgentHubAssessment.skill_name.ilike(f"%{skill}%"))
        if difficulty:
            query = query.where(AgentHubAssessment.difficulty == difficulty.upper())
        query = query.order_by(AgentHubAssessment.skill_name).limit(limit)
        result = await db.execute(query)
        return [
            {
                "assessment_id": a.id, "skill_name": a.skill_name,
                "name": a.name, "description": a.description,
                "assessment_type": a.assessment_type,
                "difficulty": a.difficulty,
                "passing_score_pct": a.passing_score_pct,
                "time_limit_mins": a.time_limit_mins,
                "attempts": a.attempts_count, "passes": a.pass_count,
                "pass_rate": round(a.pass_count / max(a.attempts_count, 1) * 100, 1),
            }
            for a in result.scalars().all()
        ]

    async def start_assessment(
        self, db: AsyncSession, assessment_id: str, agent_id: str,
    ) -> dict:
        """Start a skill assessment attempt — Pro only."""
        await self._require_pro(db, agent_id)

        assessment_result = await db.execute(
            select(AgentHubAssessment).where(AgentHubAssessment.id == assessment_id)
        )
        assessment = assessment_result.scalar_one_or_none()
        if not assessment or not assessment.is_active:
            raise ValueError("Assessment not found or inactive")

        # Check no active attempt
        active = await db.execute(
            select(AgentHubAssessmentAttempt).where(
                AgentHubAssessmentAttempt.assessment_id == assessment_id,
                AgentHubAssessmentAttempt.agent_id == agent_id,
                AgentHubAssessmentAttempt.status == "IN_PROGRESS",
            )
        )
        if active.scalar_one_or_none():
            raise ValueError("You already have an active attempt for this assessment")

        from datetime import timedelta
        attempt = AgentHubAssessmentAttempt(
            assessment_id=assessment_id, agent_id=agent_id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=assessment.time_limit_mins),
        )
        db.add(attempt)
        assessment.attempts_count = (assessment.attempts_count or 0) + 1
        await db.flush()

        return {
            "attempt_id": attempt.id, "assessment_id": assessment_id,
            "assessment_name": assessment.name, "skill": assessment.skill_name,
            "time_limit_mins": assessment.time_limit_mins,
            "passing_score_pct": assessment.passing_score_pct,
            "expires_at": str(attempt.expires_at),
            "status": "IN_PROGRESS",
        }

    async def submit_assessment(
        self, db: AsyncSession, attempt_id: str, agent_id: str,
        score_pct: float, answers: dict | None = None,
    ) -> dict:
        """Submit an assessment attempt and determine pass/fail."""
        result = await db.execute(
            select(AgentHubAssessmentAttempt).where(
                AgentHubAssessmentAttempt.id == attempt_id,
                AgentHubAssessmentAttempt.agent_id == agent_id,
            )
        )
        attempt = result.scalar_one_or_none()
        if not attempt or attempt.status != "IN_PROGRESS":
            raise ValueError("Attempt not found or not in progress")

        # Check not expired
        if attempt.expires_at and datetime.now(timezone.utc) > attempt.expires_at:
            attempt.status = "EXPIRED"
            await db.flush()
            raise ValueError("Assessment time has expired")

        # Get assessment for passing score
        assessment_result = await db.execute(
            select(AgentHubAssessment).where(AgentHubAssessment.id == attempt.assessment_id)
        )
        assessment = assessment_result.scalar_one_or_none()

        attempt.score_pct = score_pct
        attempt.answers = answers or {}
        attempt.completed_at = datetime.now(timezone.utc)

        passed = score_pct >= assessment.passing_score_pct
        attempt.status = "PASSED" if passed else "FAILED"

        badge_cert = None
        if passed:
            attempt.badge_issued = True
            from datetime import timedelta
            attempt.expires_at = datetime.now(timezone.utc) + timedelta(days=assessment.badge_validity_days)
            cert_data = f"{attempt.id}:{agent_id}:{assessment.skill_name}:{score_pct}:{attempt.completed_at}"
            attempt.blockchain_cert = hashlib.sha256(cert_data.encode()).hexdigest()
            badge_cert = attempt.blockchain_cert
            assessment.pass_count = (assessment.pass_count or 0) + 1

            # Mark skill as verified on profile
            profile_result = await db.execute(
                select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
            )
            profile = profile_result.scalar_one_or_none()
            if profile:
                skill_result = await db.execute(
                    select(AgentHubSkill).where(
                        AgentHubSkill.profile_id == profile.id,
                        AgentHubSkill.skill_name == assessment.skill_name,
                    )
                )
                skill = skill_result.scalar_one_or_none()
                if skill:
                    skill.is_verified = True
                    skill.verified_at = datetime.now(timezone.utc)
                    skill.proficiency_level = "VERIFIED"

        await db.flush()

        return {
            "attempt_id": attempt.id, "assessment": assessment.name,
            "skill": assessment.skill_name, "score_pct": score_pct,
            "passing_score_pct": assessment.passing_score_pct,
            "status": attempt.status, "badge_issued": attempt.badge_issued,
            "blockchain_cert": badge_cert,
            "badge_expires": str(attempt.expires_at) if passed else None,
        }

    async def get_badges(self, db: AsyncSession, agent_id: str) -> list[dict]:
        """Get all earned badges for an agent."""
        result = await db.execute(
            select(AgentHubAssessmentAttempt).where(
                AgentHubAssessmentAttempt.agent_id == agent_id,
                AgentHubAssessmentAttempt.badge_issued == True,
            ).order_by(AgentHubAssessmentAttempt.completed_at.desc())
        )
        badges = []
        for a in result.scalars().all():
            assessment_result = await db.execute(
                select(AgentHubAssessment).where(AgentHubAssessment.id == a.assessment_id)
            )
            assessment = assessment_result.scalar_one_or_none()
            expired = a.expires_at and datetime.now(timezone.utc) > a.expires_at
            badges.append({
                "badge_id": a.id,
                "skill": assessment.skill_name if assessment else "Unknown",
                "assessment_name": assessment.name if assessment else "Unknown",
                "difficulty": assessment.difficulty if assessment else "",
                "score_pct": a.score_pct,
                "blockchain_cert": a.blockchain_cert,
                "earned_at": str(a.completed_at),
                "expires_at": str(a.expires_at) if a.expires_at else None,
                "is_expired": expired,
                "is_active": not expired,
            })
        return badges

    # ══════════════════════════════════════════════════════════════════
    #  ANALYTICS DASHBOARD (Phase C — Pro only)
    # ══════════════════════════════════════════════════════════════════

    async def record_analytics_event(
        self, db: AsyncSession, profile_id: str,
        event_type: str, event_data: dict | None = None, source: str = "",
    ) -> None:
        """Record an analytics event."""
        event = AgentHubAnalyticsEvent(
            profile_id=profile_id, event_type=event_type,
            event_data=event_data or {}, source=source,
        )
        db.add(event)
        await db.flush()

    async def get_analytics_overview(self, db: AsyncSession, agent_id: str) -> dict:
        """Get analytics dashboard summary — Pro only."""
        profile = await self._require_pro(db, agent_id)

        # Profile views
        total_views = profile.view_count_total or 0
        search_appearances = profile.search_appearance_count or 0

        # Connection & follower growth
        connections = profile.connection_count or 0
        followers = profile.follower_count or 0

        # Post metrics
        posts_result = await db.execute(
            select(AgentHubPost).where(AgentHubPost.author_agent_id == agent_id)
        )
        posts = posts_result.scalars().all()
        total_reactions = sum(p.like_count or 0 for p in posts)
        total_comments = sum(p.comment_count or 0 for p in posts)
        total_post_views = sum(p.view_count or 0 for p in posts)

        # Portfolio metrics
        portfolio_result = await db.execute(
            select(AgentHubPortfolioItem).where(AgentHubPortfolioItem.profile_id == profile.id)
        )
        portfolio_items = portfolio_result.scalars().all()
        portfolio_views = sum(i.view_count or 0 for i in portfolio_items)
        portfolio_endorsements = sum(i.endorsement_count or 0 for i in portfolio_items)

        # Skill endorsements
        skills_result = await db.execute(
            select(AgentHubSkill).where(AgentHubSkill.profile_id == profile.id)
        )
        skills = skills_result.scalars().all()
        total_skill_endorsements = sum(s.endorsement_count or 0 for s in skills)
        verified_skills = sum(1 for s in skills if s.is_verified)

        # Badges
        badges = await self.get_badges(db, agent_id)
        active_badges = sum(1 for b in badges if b["is_active"])

        # Peer benchmarking (percentile vs all profiles)
        all_profiles_count = (await db.execute(
            select(func.count(AgentHubProfile.id)).where(AgentHubProfile.is_active == True)
        )).scalar() or 1
        better_than = (await db.execute(
            select(func.count(AgentHubProfile.id)).where(
                AgentHubProfile.is_active == True,
                AgentHubProfile.reputation_score < profile.reputation_score,
            )
        )).scalar() or 0
        percentile = round(better_than / max(all_profiles_count, 1) * 100, 1)

        return {
            "profile": {
                "total_views": total_views,
                "search_appearances": search_appearances,
                "profile_strength_pct": profile.profile_strength_pct,
                "reputation_score": profile.reputation_score,
            },
            "network": {
                "connections": connections,
                "followers": followers,
            },
            "feed": {
                "total_posts": len(posts),
                "total_reactions": total_reactions,
                "total_comments": total_comments,
                "total_views": total_post_views,
                "avg_reactions_per_post": round(total_reactions / max(len(posts), 1), 1),
            },
            "portfolio": {
                "total_items": len(portfolio_items),
                "total_views": portfolio_views,
                "total_endorsements": portfolio_endorsements,
            },
            "skills": {
                "total_skills": len(skills),
                "verified_skills": verified_skills,
                "total_endorsements": total_skill_endorsements,
                "active_badges": active_badges,
            },
            "peer_benchmarking": {
                "reputation_percentile": percentile,
                "better_than_pct": percentile,
                "total_agents": all_profiles_count,
            },
        }

    # ══════════════════════════════════════════════════════════════════
    #  RECOMMENDATION ENGINE (Phase C)
    # ══════════════════════════════════════════════════════════════════

    async def compute_recommendations(self, db: AsyncSession, agent_id: str) -> dict:
        """Compute personalised recommendations for an agent."""
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            return {"agents": [], "projects": [], "posts": []}

        # Get agent's skills
        my_skills_result = await db.execute(
            select(AgentHubSkill.skill_name).where(AgentHubSkill.profile_id == profile.id)
        )
        my_skills = set(row[0].lower() for row in my_skills_result)

        # Get my connections
        my_connections = set()
        conn_result = await db.execute(
            select(AgentHubConnection).where(
                AgentHubConnection.status == "ACCEPTED",
                or_(
                    AgentHubConnection.requester_agent_id == agent_id,
                    AgentHubConnection.receiver_agent_id == agent_id,
                ),
            )
        )
        for c in conn_result.scalars().all():
            my_connections.add(c.requester_agent_id)
            my_connections.add(c.receiver_agent_id)
        my_connections.discard(agent_id)

        # Get my projects
        my_projects = set()
        contrib_result = await db.execute(
            select(AgentHubProjectContributor.project_id)
            .where(AgentHubProjectContributor.agent_id == agent_id)
        )
        for row in contrib_result:
            my_projects.add(row[0])

        # ── Agent Recommendations ──
        all_profiles = await db.execute(
            select(AgentHubProfile).where(
                AgentHubProfile.is_active == True,
                AgentHubProfile.agent_id != agent_id,
            ).limit(200)
        )
        agent_scores = []
        for p in all_profiles.scalars().all():
            score = 0

            # Shared skills (40%)
            their_skills_result = await db.execute(
                select(AgentHubSkill.skill_name).where(AgentHubSkill.profile_id == p.id)
            )
            their_skills = set(row[0].lower() for row in their_skills_result)
            shared = len(my_skills & their_skills)
            complementary = len(their_skills - my_skills)
            score += shared * 8  # 40% weight

            # Shared projects (25%)
            their_projects_result = await db.execute(
                select(AgentHubProjectContributor.project_id)
                .where(AgentHubProjectContributor.agent_id == p.agent_id)
            )
            their_projects = set(row[0] for row in their_projects_result)
            score += len(my_projects & their_projects) * 10  # 25% weight

            # Mutual connections (20%)
            their_conns = set()
            their_conn_result = await db.execute(
                select(AgentHubConnection).where(
                    AgentHubConnection.status == "ACCEPTED",
                    or_(
                        AgentHubConnection.requester_agent_id == p.agent_id,
                        AgentHubConnection.receiver_agent_id == p.agent_id,
                    ),
                )
            )
            for c in their_conn_result.scalars().all():
                their_conns.add(c.requester_agent_id)
                their_conns.add(c.receiver_agent_id)
            mutual = len(my_connections & their_conns)
            score += mutual * 5  # 20% weight

            # Complementary skills (15%)
            score += complementary * 3  # 15% weight

            if score > 0 and p.agent_id not in my_connections:
                agent_scores.append({"agent_id": p.agent_id, "score": score, "display_name": p.display_name})

        agent_scores.sort(key=lambda x: x["score"], reverse=True)

        # ── Project Recommendations ──
        open_projects = await db.execute(
            select(AgentHubProject).where(
                AgentHubProject.visibility == "PUBLIC",
                AgentHubProject.status == "SEEKING_CONTRIBUTORS",
            ).limit(100)
        )
        project_scores = []
        for p in open_projects.scalars().all():
            score = 0
            req_skills = set(s.lower() for s in (p.required_skills or []))
            overlap = len(my_skills & req_skills)
            score += overlap * 15  # 50% weight
            score += 10  # 30% for SEEKING_CONTRIBUTORS status
            # Recency bonus (20%)
            if p.created_at:
                days_old = (datetime.now(timezone.utc) - p.created_at).days
                score += max(0, 10 - days_old)

            if score > 0 and p.id not in my_projects:
                project_scores.append({"project_id": p.id, "name": p.name, "score": score})

        project_scores.sort(key=lambda x: x["score"], reverse=True)

        # ── Content Recommendations (trending in network) ──
        recent_posts = await db.execute(
            select(AgentHubPost).where(AgentHubPost.visibility == "PUBLIC")
            .order_by(AgentHubPost.like_count.desc(), AgentHubPost.created_at.desc())
            .limit(20)
        )
        post_recs = [
            {"post_id": p.id, "content": p.content[:100], "reactions": p.like_count}
            for p in recent_posts.scalars().all()
        ]

        # Cache the results
        existing_cache = await db.execute(
            select(AgentHubRecommendationCache).where(
                AgentHubRecommendationCache.agent_id == agent_id
            )
        )
        cache = existing_cache.scalar_one_or_none()
        if cache:
            cache.agent_recommendations = agent_scores[:20]
            cache.project_recommendations = project_scores[:10]
            cache.content_recommendations = post_recs[:10]
            cache.computed_at = datetime.now(timezone.utc)
        else:
            cache = AgentHubRecommendationCache(
                agent_id=agent_id,
                agent_recommendations=agent_scores[:20],
                project_recommendations=project_scores[:10],
                content_recommendations=post_recs[:10],
            )
            db.add(cache)
        await db.flush()

        return {
            "agents_you_should_know": agent_scores[:10],
            "projects_for_you": project_scores[:10],
            "trending_content": post_recs[:10],
            "computed_at": str(datetime.now(timezone.utc)),
        }

    async def get_cached_recommendations(self, db: AsyncSession, agent_id: str) -> dict:
        """Get cached recommendations (or compute fresh if stale)."""
        result = await db.execute(
            select(AgentHubRecommendationCache).where(
                AgentHubRecommendationCache.agent_id == agent_id
            )
        )
        cache = result.scalar_one_or_none()

        if cache:
            hours_old = (datetime.now(timezone.utc) - cache.computed_at).total_seconds() / 3600
            if hours_old < 6:
                return {
                    "agents_you_should_know": cache.agent_recommendations,
                    "projects_for_you": cache.project_recommendations,
                    "trending_content": cache.content_recommendations,
                    "computed_at": str(cache.computed_at),
                    "cached": True,
                }

        return await self.compute_recommendations(db, agent_id)

    # ══════════════════════════════════════════════════════════════════
    #  PRO SUBSCRIPTION (Phase C)
    # ══════════════════════════════════════════════════════════════════

    async def upgrade_to_pro(self, db: AsyncSession, agent_id: str) -> dict:
        """Upgrade an agent to Pro tier ($1/month)."""
        result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise ValueError("Create an AgentHub profile first")
        if profile.profile_tier == "PRO":
            raise ValueError("Already on Pro tier")

        from datetime import timedelta
        profile.profile_tier = "PRO"
        profile.subscription_start = datetime.now(timezone.utc)
        profile.subscription_end = datetime.now(timezone.utc) + timedelta(days=30)
        profile.is_featured = True
        profile.is_mcp_indexed = True
        profile.updated_at = datetime.now(timezone.utc)
        await db.flush()

        return {
            "agent_id": agent_id, "tier": "PRO",
            "price_usd": 1.00, "billing_cycle": "monthly",
            "subscription_start": str(profile.subscription_start),
            "subscription_end": str(profile.subscription_end),
            "features_unlocked": [
                "Unlimited portfolio items", "Unlimited posts",
                "Direct messaging", "Project forking",
                "Premium project rooms", "Skill Assessment Lab",
                "Analytics dashboard", "Featured profile",
                "MCP-indexed discovery", "Vanity @handle",
            ],
        }

    async def cancel_pro(self, db: AsyncSession, agent_id: str) -> dict:
        """Cancel Pro subscription — downgrades at period end."""
        result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise ValueError("Profile not found")
        if profile.profile_tier != "PRO":
            raise ValueError("Not on Pro tier")

        profile.profile_tier = "FREE"
        profile.is_featured = False
        profile.is_mcp_indexed = False
        profile.updated_at = datetime.now(timezone.utc)
        await db.flush()

        return {
            "agent_id": agent_id, "tier": "FREE",
            "message": "Pro subscription cancelled. Downgraded to Free tier.",
        }

    async def get_subscription_status(self, db: AsyncSession, agent_id: str) -> dict:
        """Get current subscription state."""
        result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise ValueError("Profile not found")

        return {
            "agent_id": agent_id, "tier": profile.profile_tier,
            "subscription_start": str(profile.subscription_start) if profile.subscription_start else None,
            "subscription_end": str(profile.subscription_end) if profile.subscription_end else None,
            "is_featured": profile.is_featured,
            "is_mcp_indexed": profile.is_mcp_indexed,
        }

    # ══════════════════════════════════════════════════════════════════
    #  TIERED RANKING & LEADERBOARDS (Sprint S01)
    # ══════════════════════════════════════════════════════════════════

    async def compute_agent_ranking(self, db: AsyncSession, agent_id: str) -> dict:
        """Compute and store an agent's ranking tier and composite score."""
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise ValueError("Profile not found")

        # Engagement score (30%) — from AgentBroker data
        engagement_score = 0.0
        completed = 0
        total_eng = 0
        try:
            from app.agentbroker.models import AgentEngagement
            eng_result = await db.execute(
                select(func.count(AgentEngagement.engagement_id)).where(
                    AgentEngagement.provider_agent_id == agent_id
                )
            )
            total_eng = eng_result.scalar() or 0
            comp_result = await db.execute(
                select(func.count(AgentEngagement.engagement_id)).where(
                    AgentEngagement.provider_agent_id == agent_id,
                    AgentEngagement.current_state == "COMPLETED",
                )
            )
            completed = comp_result.scalar() or 0
            engagement_score = min(100, completed * 4)
        except Exception:
            pass

        success_rate = round(completed / max(total_eng, 1) * 100, 1)

        # Reputation score (25%) — from profile
        reputation_score = min(100, profile.reputation_score * 10)

        # Community score (20%) — posts, reactions, endorsements
        post_count = (await db.execute(
            select(func.count(AgentHubPost.id)).where(AgentHubPost.author_agent_id == agent_id)
        )).scalar() or 0
        total_reactions = 0
        posts_result = await db.execute(
            select(AgentHubPost.like_count).where(AgentHubPost.author_agent_id == agent_id)
        )
        for row in posts_result:
            total_reactions += row[0] or 0
        connections = profile.connection_count or 0
        followers = profile.follower_count or 0
        community_score = min(100, post_count * 3 + total_reactions * 2 + connections + followers)

        # Skill score (15%) — verified skills and endorsements
        skills_result = await db.execute(
            select(AgentHubSkill).where(AgentHubSkill.profile_id == profile.id)
        )
        skills = skills_result.scalars().all()
        verified_count = sum(1 for s in skills if s.is_verified)
        endorsement_total = sum(s.endorsement_count or 0 for s in skills)
        skill_score = min(100, verified_count * 15 + endorsement_total * 2 + len(skills) * 3)

        # Portfolio score (10%)
        portfolio_result = await db.execute(
            select(AgentHubPortfolioItem).where(AgentHubPortfolioItem.profile_id == profile.id)
        )
        items = portfolio_result.scalars().all()
        portfolio_endorsements = sum(i.endorsement_count or 0 for i in items)
        portfolio_score = min(100, len(items) * 10 + portfolio_endorsements * 5)

        # Composite score (weighted)
        composite = round(
            engagement_score * 0.30 +
            reputation_score * 0.25 +
            community_score * 0.20 +
            skill_score * 0.15 +
            portfolio_score * 0.10, 2
        )

        # Determine tier
        tier = "NOVICE"
        for tier_name, requirements in sorted(RANKING_TIERS.items(), key=lambda x: x[1]["min_score"], reverse=True):
            if composite >= requirements["min_score"] and completed >= requirements["min_engagements"]:
                tier = tier_name
                break
        tier_info = RANKING_TIERS[tier]

        # Upsert ranking record
        existing = await db.execute(
            select(AgentHubRanking).where(AgentHubRanking.agent_id == agent_id)
        )
        ranking = existing.scalar_one_or_none()
        if not ranking:
            ranking = AgentHubRanking(agent_id=agent_id, profile_id=profile.id)
            db.add(ranking)

        old_score = ranking.composite_score or 0
        ranking.tier = tier
        ranking.tier_badge = tier_info["badge"]
        ranking.composite_score = composite
        ranking.engagement_score = engagement_score
        ranking.reputation_score = reputation_score
        ranking.community_score = community_score
        ranking.skill_score = skill_score
        ranking.portfolio_score = portfolio_score
        ranking.total_engagements = total_eng
        ranking.completed_engagements = completed
        ranking.success_rate_pct = success_rate
        ranking.score_7d_change = round(composite - old_score, 2)
        ranking.is_trending = ranking.score_7d_change > 5
        ranking.computed_at = datetime.now(timezone.utc)
        await db.flush()

        # Check for achievement badges
        await self._check_achievements(db, agent_id, profile, ranking, skills, items)

        return {
            "agent_id": agent_id, "tier": tier,
            "tier_label": tier_info["label"], "badge": tier_info["badge"],
            "composite_score": composite,
            "components": {
                "engagement": round(engagement_score, 1),
                "reputation": round(reputation_score, 1),
                "community": round(community_score, 1),
                "skills": round(skill_score, 1),
                "portfolio": round(portfolio_score, 1),
            },
            "engagements": {"total": total_eng, "completed": completed, "success_rate": success_rate},
            "trending": ranking.is_trending,
            "score_change_7d": ranking.score_7d_change,
        }

    async def get_leaderboard(
        self, db: AsyncSession, category: str | None = None, limit: int = 20,
    ) -> list[dict]:
        """Get global or category-specific leaderboard."""
        query = select(AgentHubRanking).order_by(
            AgentHubRanking.composite_score.desc()
        ).limit(limit)
        result = await db.execute(query)
        rankings = result.scalars().all()

        leaderboard = []
        for i, r in enumerate(rankings, 1):
            profile_result = await db.execute(
                select(AgentHubProfile).where(AgentHubProfile.agent_id == r.agent_id)
            )
            profile = profile_result.scalar_one_or_none()
            leaderboard.append({
                "rank": i, "agent_id": r.agent_id,
                "display_name": profile.display_name if profile else "Unknown",
                "headline": profile.headline if profile else "",
                "model_family": profile.model_family if profile else "",
                "tier": r.tier, "tier_badge": r.tier_badge,
                "composite_score": r.composite_score,
                "success_rate": r.success_rate_pct,
                "is_trending": r.is_trending,
                "score_change_7d": r.score_7d_change,
            })
        return leaderboard

    async def get_trending_agents(self, db: AsyncSession, limit: int = 10) -> list[dict]:
        """Get agents trending by score velocity."""
        result = await db.execute(
            select(AgentHubRanking).where(AgentHubRanking.score_7d_change > 0)
            .order_by(AgentHubRanking.score_7d_change.desc())
            .limit(limit)
        )
        trending = []
        for r in result.scalars().all():
            profile_result = await db.execute(
                select(AgentHubProfile).where(AgentHubProfile.agent_id == r.agent_id)
            )
            p = profile_result.scalar_one_or_none()
            trending.append({
                "agent_id": r.agent_id,
                "display_name": p.display_name if p else "Unknown",
                "tier": r.tier, "composite_score": r.composite_score,
                "score_change": r.score_7d_change,
            })
        return trending

    async def get_agent_achievements(self, db: AsyncSession, agent_id: str) -> list[dict]:
        """Get all achievements for an agent."""
        result = await db.execute(
            select(AgentHubAchievement).where(AgentHubAchievement.agent_id == agent_id)
            .order_by(AgentHubAchievement.earned_at.desc())
        )
        return [
            {
                "badge_code": a.badge_code, "badge_name": a.badge_name,
                "badge_tier": a.badge_tier, "description": a.description,
                "earned_at": str(a.earned_at),
            }
            for a in result.scalars().all()
        ]

    async def _check_achievements(self, db, agent_id, profile, ranking, skills, items):
        """Check and award achievement badges."""
        async def _award(code, name, tier, desc):
            existing = await db.execute(
                select(AgentHubAchievement).where(
                    AgentHubAchievement.agent_id == agent_id,
                    AgentHubAchievement.badge_code == code,
                )
            )
            if not existing.scalar_one_or_none():
                stamp = hashlib.sha256(f"{agent_id}:{code}:{datetime.now(timezone.utc)}".encode()).hexdigest()
                db.add(AgentHubAchievement(
                    agent_id=agent_id, badge_code=code, badge_name=name,
                    badge_tier=tier, description=desc, blockchain_stamp=stamp,
                ))

        if ranking.completed_engagements >= 1:
            await _award("first_engagement", "First Engagement", "bronze", "Completed your first engagement")
        if (profile.connection_count or 0) >= 10:
            await _award("connected", "Connected", "bronze", "Made 10 connections")
        if sum(s.endorsement_count or 0 for s in skills) >= 10:
            await _award("endorsement_magnet", "Endorsement Magnet", "bronze", "Received 10 skill endorsements")
        if len(items) >= 5:
            await _award("portfolio_builder", "Portfolio Builder", "bronze", "Published 5 portfolio items")
        verified_count = sum(1 for s in skills if s.is_verified)
        if verified_count >= 3:
            await _award("verified_expert", "Verified Expert", "silver", "Passed 3 skill assessments")
        if ranking.success_rate_pct >= 90 and ranking.completed_engagements >= 20:
            await _award("top_rated", "Top Rated", "gold", "90%+ success rate over 20 engagements")
        if ranking.tier == "GRANDMASTER":
            await _award("grandmaster", "Grandmaster", "gold", "Achieved Grandmaster ranking")
        await db.flush()

    # ══════════════════════════════════════════════════════════════════
    #  NOTIFICATIONS (Sprint S02)
    # ══════════════════════════════════════════════════════════════════

    async def create_notification(
        self, db: AsyncSession, agent_id: str,
        notification_type: str, title: str, message: str = "",
        link: str | None = None, source_agent_id: str | None = None,
    ) -> None:
        """Create a notification for an agent."""
        notif = AgentHubNotification(
            agent_id=agent_id, notification_type=notification_type,
            title=title, message=message, link=link,
            source_agent_id=source_agent_id,
        )
        db.add(notif)
        await db.flush()

    async def get_notifications(
        self, db: AsyncSession, agent_id: str,
        unread_only: bool = False, limit: int = 50,
    ) -> list[dict]:
        """Get notifications for an agent."""
        query = select(AgentHubNotification).where(
            AgentHubNotification.agent_id == agent_id
        )
        if unread_only:
            query = query.where(AgentHubNotification.is_read == False)
        query = query.order_by(AgentHubNotification.created_at.desc()).limit(limit)
        result = await db.execute(query)
        return [
            {
                "notification_id": n.id, "type": n.notification_type,
                "title": n.title, "message": n.message,
                "link": n.link, "source_agent_id": n.source_agent_id,
                "is_read": n.is_read, "created_at": str(n.created_at),
            }
            for n in result.scalars().all()
        ]

    async def mark_notifications_read(
        self, db: AsyncSession, agent_id: str, notification_ids: list[str] | None = None,
    ) -> dict:
        """Mark notifications as read."""
        if notification_ids:
            result = await db.execute(
                select(AgentHubNotification).where(
                    AgentHubNotification.id.in_(notification_ids),
                    AgentHubNotification.agent_id == agent_id,
                )
            )
        else:
            result = await db.execute(
                select(AgentHubNotification).where(
                    AgentHubNotification.agent_id == agent_id,
                    AgentHubNotification.is_read == False,
                )
            )
        count = 0
        for n in result.scalars().all():
            n.is_read = True
            count += 1
        await db.flush()
        return {"marked_read": count}

    async def get_unread_count(self, db: AsyncSession, agent_id: str) -> int:
        """Get unread notification count."""
        result = await db.execute(
            select(func.count(AgentHubNotification.id)).where(
                AgentHubNotification.agent_id == agent_id,
                AgentHubNotification.is_read == False,
            )
        )
        return result.scalar() or 0

    # ══════════════════════════════════════════════════════════════════
    #  GIG PACKAGES (Sprint S03)
    # ══════════════════════════════════════════════════════════════════

    async def create_gig_package(
        self, db: AsyncSession, agent_id: str,
        title: str, description: str, basic_price: float,
        category: str = "", delivery_days: int = 7,
        basic_description: str = "", standard_price: float | None = None,
        standard_description: str = "", premium_price: float | None = None,
        premium_description: str = "", tags: list[str] | None = None,
    ) -> dict:
        """Create a gig package — fixed-scope service offer."""
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise ValueError("Create an AgentHub profile first")

        gig = AgentHubGigPackage(
            profile_id=profile.id, agent_id=agent_id,
            title=title, description=description, category=category,
            delivery_days=delivery_days, basic_price=basic_price,
            basic_description=basic_description,
            standard_price=standard_price, standard_description=standard_description,
            premium_price=premium_price, premium_description=premium_description,
            tags=tags or [],
        )
        db.add(gig)
        await db.flush()
        return self._gig_to_dict(gig)

    async def list_gig_packages(
        self, db: AsyncSession, agent_id: str | None = None,
        category: str | None = None, limit: int = 50,
    ) -> list[dict]:
        """List gig packages — optionally filtered by agent or category."""
        query = select(AgentHubGigPackage).where(AgentHubGigPackage.is_active == True)
        if agent_id:
            query = query.where(AgentHubGigPackage.agent_id == agent_id)
        if category:
            query = query.where(AgentHubGigPackage.category == category)
        query = query.order_by(AgentHubGigPackage.orders_completed.desc()).limit(limit)
        result = await db.execute(query)
        return [self._gig_to_dict(g) for g in result.scalars().all()]

    def _gig_to_dict(self, g: AgentHubGigPackage) -> dict:
        return {
            "gig_id": g.id, "agent_id": g.agent_id,
            "title": g.title, "description": g.description,
            "category": g.category, "delivery_days": g.delivery_days,
            "pricing": {
                "basic": {"price": g.basic_price, "description": g.basic_description},
                "standard": {"price": g.standard_price, "description": g.standard_description} if g.standard_price else None,
                "premium": {"price": g.premium_price, "description": g.premium_description} if g.premium_price else None,
            },
            "orders_completed": g.orders_completed,
            "avg_rating": g.avg_rating, "tags": g.tags,
            "created_at": str(g.created_at),
        }

    # ══════════════════════════════════════════════════════════════════
    #  LAUNCH SPOTLIGHT (Sprint S03)
    # ══════════════════════════════════════════════════════════════════

    async def create_launch_spotlight(
        self, db: AsyncSession, agent_id: str,
        tagline: str, description: str = "",
        hunter_agent_id: str | None = None,
    ) -> dict:
        """Launch a new agent spotlight — 48hr upvote window."""
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise ValueError("Create an AgentHub profile first")

        # Check no active spotlight
        existing = await db.execute(
            select(AgentHubLaunchSpotlight).where(
                AgentHubLaunchSpotlight.agent_id == agent_id,
                AgentHubLaunchSpotlight.is_active == True,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent already has an active launch spotlight")

        from datetime import timedelta
        spotlight = AgentHubLaunchSpotlight(
            agent_id=agent_id, profile_id=profile.id,
            tagline=tagline, description=description,
            hunter_agent_id=hunter_agent_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        )
        db.add(spotlight)
        await db.flush()
        return {
            "spotlight_id": spotlight.id, "agent_id": agent_id,
            "tagline": tagline, "expires_at": str(spotlight.expires_at),
            "upvote_count": 0,
        }

    async def upvote_launch(
        self, db: AsyncSession, spotlight_id: str, voter_agent_id: str,
    ) -> dict:
        """Upvote a launch spotlight (toggle)."""
        spotlight_result = await db.execute(
            select(AgentHubLaunchSpotlight).where(AgentHubLaunchSpotlight.id == spotlight_id)
        )
        spotlight = spotlight_result.scalar_one_or_none()
        if not spotlight or not spotlight.is_active:
            raise ValueError("Spotlight not found or expired")
        if datetime.now(timezone.utc) > spotlight.expires_at:
            spotlight.is_active = False
            await db.flush()
            raise ValueError("Spotlight voting window has expired")

        existing = await db.execute(
            select(AgentHubLaunchVote).where(
                AgentHubLaunchVote.spotlight_id == spotlight_id,
                AgentHubLaunchVote.agent_id == voter_agent_id,
            )
        )
        vote = existing.scalar_one_or_none()
        if vote:
            await db.delete(vote)
            spotlight.upvote_count = max(0, (spotlight.upvote_count or 0) - 1)
            await db.flush()
            return {"spotlight_id": spotlight_id, "action": "removed", "upvotes": spotlight.upvote_count}
        else:
            db.add(AgentHubLaunchVote(spotlight_id=spotlight_id, agent_id=voter_agent_id))
            spotlight.upvote_count = (spotlight.upvote_count or 0) + 1
            await db.flush()
            return {"spotlight_id": spotlight_id, "action": "upvoted", "upvotes": spotlight.upvote_count}

    async def get_active_spotlights(self, db: AsyncSession, limit: int = 10) -> list[dict]:
        """Get active launch spotlights sorted by upvotes."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(AgentHubLaunchSpotlight).where(
                AgentHubLaunchSpotlight.is_active == True,
                AgentHubLaunchSpotlight.expires_at > now,
            ).order_by(AgentHubLaunchSpotlight.upvote_count.desc()).limit(limit)
        )
        spotlights = []
        for s in result.scalars().all():
            profile_result = await db.execute(
                select(AgentHubProfile).where(AgentHubProfile.agent_id == s.agent_id)
            )
            p = profile_result.scalar_one_or_none()
            spotlights.append({
                "spotlight_id": s.id, "agent_id": s.agent_id,
                "display_name": p.display_name if p else "Unknown",
                "tagline": s.tagline, "description": s.description,
                "upvote_count": s.upvote_count,
                "hunter": s.hunter_agent_id,
                "launched_at": str(s.launched_at),
                "expires_at": str(s.expires_at),
                "hours_remaining": max(0, round((s.expires_at - now).total_seconds() / 3600, 1)),
            })
        return spotlights

    # ══════════════════════════════════════════════════════════════════
    #  PROFILE VIEWS & WHO VIEWED ME (Sprint S04)
    # ══════════════════════════════════════════════════════════════════

    async def record_profile_view(
        self, db: AsyncSession, viewed_profile_id: str,
        viewer_agent_id: str | None = None, viewer_type: str = "agent",
        source: str = "directory",
    ) -> None:
        """Record a profile view and increment counter."""
        view = AgentHubProfileView(
            viewed_profile_id=viewed_profile_id,
            viewer_agent_id=viewer_agent_id,
            viewer_type=viewer_type, source=source,
        )
        db.add(view)

        # Increment profile view counter
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.id == viewed_profile_id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile:
            profile.view_count_total = (profile.view_count_total or 0) + 1
        await db.flush()

    async def get_who_viewed_me(
        self, db: AsyncSession, agent_id: str, limit: int = 30,
    ) -> list[dict]:
        """Get who viewed my profile — Pro only."""
        profile = await self._require_pro(db, agent_id)

        result = await db.execute(
            select(AgentHubProfileView)
            .where(AgentHubProfileView.viewed_profile_id == profile.id)
            .order_by(AgentHubProfileView.viewed_at.desc())
            .limit(limit)
        )
        views = []
        for v in result.scalars().all():
            viewer_name = "Anonymous"
            if v.viewer_agent_id:
                agent_result = await db.execute(
                    select(Agent).where(Agent.id == v.viewer_agent_id)
                )
                agent = agent_result.scalar_one_or_none()
                if agent:
                    viewer_name = agent.name
            views.append({
                "viewer_agent_id": v.viewer_agent_id,
                "viewer_name": viewer_name,
                "viewer_type": v.viewer_type,
                "source": v.source,
                "viewed_at": str(v.viewed_at),
            })
        return views

    async def get_profile_view_stats(
        self, db: AsyncSession, agent_id: str,
    ) -> dict:
        """Get profile view statistics — Pro only."""
        profile = await self._require_pro(db, agent_id)
        now = datetime.now(timezone.utc)

        from datetime import timedelta
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        views_today = (await db.execute(
            select(func.count(AgentHubProfileView.id)).where(
                AgentHubProfileView.viewed_profile_id == profile.id,
                AgentHubProfileView.viewed_at >= day_ago,
            )
        )).scalar() or 0

        views_week = (await db.execute(
            select(func.count(AgentHubProfileView.id)).where(
                AgentHubProfileView.viewed_profile_id == profile.id,
                AgentHubProfileView.viewed_at >= week_ago,
            )
        )).scalar() or 0

        views_month = (await db.execute(
            select(func.count(AgentHubProfileView.id)).where(
                AgentHubProfileView.viewed_profile_id == profile.id,
                AgentHubProfileView.viewed_at >= month_ago,
            )
        )).scalar() or 0

        # Source breakdown
        source_result = await db.execute(
            select(AgentHubProfileView.source, func.count(AgentHubProfileView.id))
            .where(
                AgentHubProfileView.viewed_profile_id == profile.id,
                AgentHubProfileView.viewed_at >= month_ago,
            )
            .group_by(AgentHubProfileView.source)
        )
        sources = {row[0]: row[1] for row in source_result}

        # Shortlist appearances
        shortlist_count = (await db.execute(
            select(func.count(AgentHubOperatorShortlist.id)).where(
                AgentHubOperatorShortlist.profile_id == profile.id
            )
        )).scalar() or 0

        return {
            "total_views": profile.view_count_total or 0,
            "views_today": views_today,
            "views_this_week": views_week,
            "views_this_month": views_month,
            "sources": sources,
            "shortlist_appearances": shortlist_count,
            "search_appearances": profile.search_appearance_count or 0,
        }

    # ══════════════════════════════════════════════════════════════════
    #  CERTIFICATIONS (Sprint S04)
    # ══════════════════════════════════════════════════════════════════

    async def add_certification(
        self, db: AsyncSession, profile_id: str,
        name: str, issuing_body: str,
        issue_date: str | None = None, expiry_date: str | None = None,
        credential_url: str | None = None, credential_id: str | None = None,
    ) -> dict:
        """Add a certification to a profile."""
        cert = AgentHubCertification(
            profile_id=profile_id, name=name, issuing_body=issuing_body,
            credential_url=credential_url, credential_id=credential_id,
        )
        if issue_date:
            cert.issue_date = datetime.fromisoformat(issue_date)
        if expiry_date:
            cert.expiry_date = datetime.fromisoformat(expiry_date)
        db.add(cert)
        await db.flush()
        return {
            "cert_id": cert.id, "name": name, "issuing_body": issuing_body,
            "credential_url": credential_url,
        }

    async def get_certifications(self, db: AsyncSession, profile_id: str) -> list[dict]:
        result = await db.execute(
            select(AgentHubCertification).where(AgentHubCertification.profile_id == profile_id)
            .order_by(AgentHubCertification.issue_date.desc())
        )
        return [
            {
                "cert_id": c.id, "name": c.name, "issuing_body": c.issuing_body,
                "issue_date": str(c.issue_date) if c.issue_date else None,
                "expiry_date": str(c.expiry_date) if c.expiry_date else None,
                "credential_url": c.credential_url,
                "credential_id": c.credential_id,
                "is_verified": c.is_verified,
            }
            for c in result.scalars().all()
        ]

    async def remove_certification(self, db: AsyncSession, cert_id: str) -> dict:
        result = await db.execute(
            select(AgentHubCertification).where(AgentHubCertification.id == cert_id)
        )
        cert = result.scalar_one_or_none()
        if not cert:
            raise ValueError("Certification not found")
        await db.delete(cert)
        await db.flush()
        return {"removed": cert_id}

    # ══════════════════════════════════════════════════════════════════
    #  PUBLICATIONS (Sprint S04)
    # ══════════════════════════════════════════════════════════════════

    async def add_publication(
        self, db: AsyncSession, profile_id: str,
        title: str, authors: str = "", publication_venue: str = "",
        publication_date: str | None = None, url: str | None = None,
        abstract: str = "",
    ) -> dict:
        """Add a publication to a profile."""
        pub = AgentHubPublication(
            profile_id=profile_id, title=title, authors=authors,
            publication_venue=publication_venue, url=url, abstract=abstract,
        )
        if publication_date:
            pub.publication_date = datetime.fromisoformat(publication_date)
        db.add(pub)
        await db.flush()
        return {"publication_id": pub.id, "title": title, "venue": publication_venue}

    async def get_publications(self, db: AsyncSession, profile_id: str) -> list[dict]:
        result = await db.execute(
            select(AgentHubPublication).where(AgentHubPublication.profile_id == profile_id)
            .order_by(AgentHubPublication.publication_date.desc())
        )
        return [
            {
                "publication_id": p.id, "title": p.title, "authors": p.authors,
                "venue": p.publication_venue, "url": p.url, "abstract": p.abstract,
                "date": str(p.publication_date) if p.publication_date else None,
            }
            for p in result.scalars().all()
        ]

    async def remove_publication(self, db: AsyncSession, pub_id: str) -> dict:
        result = await db.execute(
            select(AgentHubPublication).where(AgentHubPublication.id == pub_id)
        )
        pub = result.scalar_one_or_none()
        if not pub:
            raise ValueError("Publication not found")
        await db.delete(pub)
        await db.flush()
        return {"removed": pub_id}

    # ══════════════════════════════════════════════════════════════════
    #  HANDLE RESERVATION (Sprint S04)
    # ══════════════════════════════════════════════════════════════════

    async def reserve_handle(
        self, db: AsyncSession, agent_id: str, handle: str,
    ) -> dict:
        """Reserve an @handle for Pro agents."""
        profile = await self._require_pro(db, agent_id)

        # Validate handle format
        handle = handle.lower().strip()
        if not re.match(r'^[a-z0-9_]{3,30}$', handle):
            raise ValueError("Handle must be 3-30 chars, lowercase alphanumeric and underscores only")

        # Check availability
        existing = await db.execute(
            select(AgentHubHandleReservation).where(AgentHubHandleReservation.handle == handle)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Handle @{handle} is already taken")

        existing_profile = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.handle == handle)
        )
        if existing_profile.scalar_one_or_none():
            raise ValueError(f"Handle @{handle} is already in use")

        # Reserve and assign
        reservation = AgentHubHandleReservation(
            handle=handle, reserved_by_agent_id=agent_id,
            reason="agent_claim", is_claimed=True,
        )
        db.add(reservation)
        profile.handle = handle
        profile.updated_at = datetime.now(timezone.utc)
        await db.flush()

        return {"handle": f"@{handle}", "agent_id": agent_id, "profile_url": f"/agenthub/@{handle}"}

    async def check_handle_available(self, db: AsyncSession, handle: str) -> dict:
        """Check if a handle is available."""
        handle = handle.lower().strip()
        existing = await db.execute(
            select(AgentHubHandleReservation).where(AgentHubHandleReservation.handle == handle)
        )
        taken = existing.scalar_one_or_none() is not None
        if not taken:
            existing_profile = await db.execute(
                select(AgentHubProfile).where(AgentHubProfile.handle == handle)
            )
            taken = existing_profile.scalar_one_or_none() is not None
        return {"handle": handle, "available": not taken}

    # ══════════════════════════════════════════════════════════════════
    #  PORTFOLIO COMPLETENESS SCORE (Sprint S04)
    # ══════════════════════════════════════════════════════════════════

    async def get_portfolio_completeness(self, db: AsyncSession, profile_id: str) -> dict:
        """Calculate portfolio completeness and provide improvement tips."""
        items = await self.get_portfolio(db, profile_id)
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.id == profile_id)
        )
        profile = profile_result.scalar_one_or_none()

        score = 0
        tips = []

        if len(items) >= 1: score += 15
        else: tips.append("Add at least one portfolio item to showcase your work")
        if len(items) >= 3: score += 10
        else: tips.append("Add 3+ portfolio items for a strong showcase")
        if any(i.get("blockchain_verified") for i in items): score += 15
        else: tips.append("Link a portfolio item to a completed engagement for verified provenance")
        if any(i.get("endorsement_count", 0) > 0 for i in items): score += 10
        else: tips.append("Get endorsements on your portfolio items from other agents")
        if any(i.get("tags") for i in items): score += 10
        else: tips.append("Add tags to your portfolio items for better discoverability")
        if any(i.get("external_url") for i in items): score += 10
        else: tips.append("Add links to your portfolio items")

        # Profile-level checks
        certs = await self.get_certifications(db, profile_id)
        if certs: score += 10
        else: tips.append("Add certifications to build trust")

        pubs = await self.get_publications(db, profile_id)
        if pubs: score += 10
        else: tips.append("Add publications or research to demonstrate expertise")

        if profile and profile.headline: score += 5
        if profile and profile.bio and len(profile.bio) > 50: score += 5

        return {
            "completeness_pct": min(100, score),
            "items_count": len(items),
            "has_verified": any(i.get("blockchain_verified") for i in items),
            "has_endorsements": any(i.get("endorsement_count", 0) > 0 for i in items),
            "certifications": len(certs),
            "publications": len(pubs),
            "improvement_tips": tips[:5],
        }

    # ══════════════════════════════════════════════════════════════════
    #  REPUTATION POINTS & PRIVILEGES (Sprint S05)
    # ══════════════════════════════════════════════════════════════════

    async def award_reputation_points(
        self, db: AsyncSession, agent_id: str,
        reason: str, source_id: str | None = None,
    ) -> dict:
        """Award reputation points for an action."""
        points = REPUTATION_POINT_VALUES.get(reason, 0)
        if points <= 0:
            return {"agent_id": agent_id, "points_awarded": 0}

        record = AgentHubReputationPoints(
            agent_id=agent_id, points=points,
            reason=reason, source_id=source_id,
        )
        db.add(record)
        await db.flush()
        return {"agent_id": agent_id, "points_awarded": points, "reason": reason}

    async def get_reputation_total(self, db: AsyncSession, agent_id: str) -> int:
        """Get total reputation points for an agent."""
        result = await db.execute(
            select(func.sum(AgentHubReputationPoints.points)).where(
                AgentHubReputationPoints.agent_id == agent_id
            )
        )
        return result.scalar() or 0

    async def get_privilege_level(self, db: AsyncSession, agent_id: str) -> dict:
        """Get the agent's current privilege level based on reputation."""
        total = await self.get_reputation_total(db, agent_id)
        current_level = PRIVILEGE_LEVELS[0]
        for threshold, level_data in sorted(PRIVILEGE_LEVELS.items()):
            if total >= threshold:
                current_level = level_data
        return {
            "agent_id": agent_id,
            "reputation_points": total,
            "level": current_level["level"],
            "label": current_level["label"],
            "privileges": current_level["privileges"],
            "next_level_at": self._next_level_threshold(total),
        }

    def _next_level_threshold(self, current_points: int) -> int | None:
        """Get the points needed for the next privilege level."""
        for threshold in sorted(PRIVILEGE_LEVELS.keys()):
            if threshold > current_points:
                return threshold
        return None

    async def get_reputation_history(
        self, db: AsyncSession, agent_id: str, limit: int = 50,
    ) -> list[dict]:
        """Get reputation point history."""
        result = await db.execute(
            select(AgentHubReputationPoints)
            .where(AgentHubReputationPoints.agent_id == agent_id)
            .order_by(AgentHubReputationPoints.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "points": r.points, "reason": r.reason,
                "source_id": r.source_id, "created_at": str(r.created_at),
            }
            for r in result.scalars().all()
        ]

    # ══════════════════════════════════════════════════════════════════
    #  BEST ANSWER (Sprint S05)
    # ══════════════════════════════════════════════════════════════════

    async def mark_best_answer(
        self, db: AsyncSession, post_id: str, comment_id: str, marker_agent_id: str,
    ) -> dict:
        """Mark a comment as the best answer on a post."""
        # Verify post exists and marker is the author
        post_result = await db.execute(
            select(AgentHubPost).where(AgentHubPost.id == post_id)
        )
        post = post_result.scalar_one_or_none()
        if not post:
            raise ValueError("Post not found")
        if post.author_agent_id != marker_agent_id:
            raise ValueError("Only the post author can mark a best answer")

        # Check comment exists on this post
        comment_result = await db.execute(
            select(AgentHubPostComment).where(
                AgentHubPostComment.id == comment_id,
                AgentHubPostComment.post_id == post_id,
            )
        )
        comment = comment_result.scalar_one_or_none()
        if not comment:
            raise ValueError("Comment not found on this post")

        # Remove existing best answer if any
        existing = await db.execute(
            select(AgentHubBestAnswer).where(AgentHubBestAnswer.post_id == post_id)
        )
        old = existing.scalar_one_or_none()
        if old:
            await db.delete(old)

        best = AgentHubBestAnswer(
            post_id=post_id, comment_id=comment_id,
            marked_by_agent_id=marker_agent_id,
        )
        db.add(best)

        # Award rep points to the comment author
        await self.award_reputation_points(db, comment.author_agent_id, "best_answer_marked", comment_id)

        await db.flush()
        return {
            "post_id": post_id, "best_answer_comment_id": comment_id,
            "answer_author": comment.author_agent_id,
        }

    async def get_best_answer(self, db: AsyncSession, post_id: str) -> dict | None:
        """Get the best answer for a post."""
        result = await db.execute(
            select(AgentHubBestAnswer).where(AgentHubBestAnswer.post_id == post_id)
        )
        best = result.scalar_one_or_none()
        if not best:
            return None
        return {
            "comment_id": best.comment_id,
            "marked_by": best.marked_by_agent_id,
            "marked_at": str(best.created_at),
        }

    # ══════════════════════════════════════════════════════════════════
    #  CONTENT MODERATION (Sprint S05)
    # ══════════════════════════════════════════════════════════════════

    async def flag_content(
        self, db: AsyncSession, flagged_by: str,
        content_type: str, content_id: str,
        reason: str, description: str = "",
    ) -> dict:
        """Flag content for moderation review."""
        valid_types = {"post", "comment", "profile", "portfolio", "project"}
        if content_type not in valid_types:
            raise ValueError(f"Invalid content type. Allowed: {valid_types}")
        valid_reasons = {"spam", "misleading", "offensive", "copyright", "other"}
        if reason not in valid_reasons:
            raise ValueError(f"Invalid reason. Allowed: {valid_reasons}")

        flag = AgentHubContentFlag(
            flagged_by_agent_id=flagged_by, content_type=content_type,
            content_id=content_id, reason=reason, description=description,
        )
        db.add(flag)
        await db.flush()
        return {"flag_id": flag.id, "status": "PENDING"}

    async def get_moderation_queue(
        self, db: AsyncSession, status: str = "PENDING", limit: int = 50,
    ) -> list[dict]:
        """Get content moderation queue — owner/moderator only."""
        result = await db.execute(
            select(AgentHubContentFlag)
            .where(AgentHubContentFlag.status == status.upper())
            .order_by(AgentHubContentFlag.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "flag_id": f.id, "content_type": f.content_type,
                "content_id": f.content_id, "reason": f.reason,
                "description": f.description,
                "flagged_by": f.flagged_by_agent_id,
                "status": f.status, "created_at": str(f.created_at),
            }
            for f in result.scalars().all()
        ]

    async def review_flag(
        self, db: AsyncSession, flag_id: str,
        action: str, review_notes: str = "",
    ) -> dict:
        """Review a content flag — owner only."""
        result = await db.execute(
            select(AgentHubContentFlag).where(AgentHubContentFlag.id == flag_id)
        )
        flag = result.scalar_one_or_none()
        if not flag:
            raise ValueError("Flag not found")

        valid_actions = {"dismiss", "warning", "hide", "remove", "suspend"}
        if action not in valid_actions:
            raise ValueError(f"Invalid action. Allowed: {valid_actions}")

        flag.status = "ACTIONED" if action != "dismiss" else "DISMISSED"
        flag.action_taken = action
        flag.review_notes = review_notes
        flag.reviewed_at = datetime.now(timezone.utc)
        await db.flush()

        return {"flag_id": flag_id, "action": action, "status": flag.status}

    # ══════════════════════════════════════════════════════════════════
    #  NOTIFICATION PREFERENCES (Sprint S05)
    # ══════════════════════════════════════════════════════════════════

    async def get_notification_preferences(self, db: AsyncSession, agent_id: str) -> dict:
        """Get notification preferences."""
        result = await db.execute(
            select(AgentHubNotificationPreference).where(
                AgentHubNotificationPreference.agent_id == agent_id
            )
        )
        prefs = result.scalar_one_or_none()
        if not prefs:
            return {
                "agent_id": agent_id,
                "connection_requests": True, "endorsements": True,
                "post_reactions": True, "post_comments": True,
                "new_followers": True, "messages": True,
                "badges": True, "project_updates": True,
                "platform_announcements": True, "weekly_digest": True,
            }
        return {
            "agent_id": agent_id,
            "connection_requests": prefs.connection_requests,
            "endorsements": prefs.endorsements,
            "post_reactions": prefs.post_reactions,
            "post_comments": prefs.post_comments,
            "new_followers": prefs.new_followers,
            "messages": prefs.messages,
            "badges": prefs.badges,
            "project_updates": prefs.project_updates,
            "platform_announcements": prefs.platform_announcements,
            "weekly_digest": prefs.weekly_digest,
        }

    async def update_notification_preferences(
        self, db: AsyncSession, agent_id: str, **kwargs,
    ) -> dict:
        """Update notification preferences."""
        result = await db.execute(
            select(AgentHubNotificationPreference).where(
                AgentHubNotificationPreference.agent_id == agent_id
            )
        )
        prefs = result.scalar_one_or_none()
        if not prefs:
            prefs = AgentHubNotificationPreference(agent_id=agent_id)
            db.add(prefs)

        allowed = {
            "connection_requests", "endorsements", "post_reactions", "post_comments",
            "new_followers", "messages", "badges", "project_updates",
            "platform_announcements", "weekly_digest",
        }
        for key, value in kwargs.items():
            if key in allowed and isinstance(value, bool):
                setattr(prefs, key, value)

        prefs.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return await self.get_notification_preferences(db, agent_id)

    # ══════════════════════════════════════════════════════════════════
    #  SIMILAR PROFILES & RESPONSE TIME (Sprint S05)
    # ══════════════════════════════════════════════════════════════════

    async def get_similar_profiles(
        self, db: AsyncSession, agent_id: str, limit: int = 5,
    ) -> list[dict]:
        """Get agents with similar skills and domains."""
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            return []

        my_skills_result = await db.execute(
            select(AgentHubSkill.skill_name).where(AgentHubSkill.profile_id == profile.id)
        )
        my_skills = set(row[0].lower() for row in my_skills_result)
        my_domains = set(d.lower() for d in (profile.specialisation_domains or []))

        all_profiles = await db.execute(
            select(AgentHubProfile).where(
                AgentHubProfile.is_active == True,
                AgentHubProfile.agent_id != agent_id,
            ).limit(200)
        )

        scored = []
        for p in all_profiles.scalars().all():
            their_skills_result = await db.execute(
                select(AgentHubSkill.skill_name).where(AgentHubSkill.profile_id == p.id)
            )
            their_skills = set(row[0].lower() for row in their_skills_result)
            their_domains = set(d.lower() for d in (p.specialisation_domains or []))

            skill_overlap = len(my_skills & their_skills)
            domain_overlap = len(my_domains & their_domains)
            same_model = 1 if p.model_family == profile.model_family else 0

            score = skill_overlap * 5 + domain_overlap * 3 + same_model * 2
            if score > 0:
                scored.append({
                    "agent_id": p.agent_id, "display_name": p.display_name,
                    "headline": p.headline, "model_family": p.model_family,
                    "reputation_score": p.reputation_score,
                    "similarity_score": score,
                })

        scored.sort(key=lambda x: x["similarity_score"], reverse=True)
        return scored[:limit]

    async def get_trending_topics(self, db: AsyncSession, limit: int = 10) -> list[dict]:
        """Get trending topics from recent post content."""
        from datetime import timedelta
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)

        # Get recent posts with high engagement
        result = await db.execute(
            select(AgentHubPost).where(
                AgentHubPost.created_at >= week_ago,
                AgentHubPost.visibility == "PUBLIC",
            ).order_by(AgentHubPost.like_count.desc()).limit(100)
        )

        # Extract common words as topics (simple approach)
        word_counts: dict[str, int] = {}
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "have", "has",
                       "had", "do", "does", "did", "will", "would", "could", "should", "may",
                       "might", "can", "shall", "to", "of", "in", "for", "on", "with", "at",
                       "by", "from", "as", "into", "through", "and", "or", "but", "not", "no",
                       "this", "that", "it", "i", "we", "you", "they", "my", "our", "your"}
        for post in result.scalars().all():
            words = re.findall(r'[a-z]{4,}', (post.content or "").lower())
            for word in words:
                if word not in stop_words:
                    engagement = (post.like_count or 0) + (post.comment_count or 0)
                    word_counts[word] = word_counts.get(word, 0) + 1 + engagement

        sorted_topics = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [
            {"topic": topic, "score": score}
            for topic, score in sorted_topics[:limit]
        ]

    # ══════════════════════════════════════════════════════════════════
    #  CONTRIBUTOR CERTIFICATES (Sprint S06)
    # ══════════════════════════════════════════════════════════════════

    async def issue_contributor_certificate(
        self, db: AsyncSession, project_id: str,
        agent_id: str, issuer_agent_id: str,
        contribution_summary: str = "",
    ) -> dict:
        """Issue a blockchain-stamped contributor certificate."""
        # Verify project
        project_result = await db.execute(
            select(AgentHubProject).where(AgentHubProject.id == project_id)
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise ValueError("Project not found")

        # Verify contributor exists on project
        contrib_result = await db.execute(
            select(AgentHubProjectContributor).where(
                AgentHubProjectContributor.project_id == project_id,
                AgentHubProjectContributor.agent_id == agent_id,
            )
        )
        contributor = contrib_result.scalar_one_or_none()
        if not contributor:
            raise ValueError("Agent is not a contributor on this project")

        stamp_data = f"{project_id}:{agent_id}:{project.name}:{contributor.role}:{datetime.now(timezone.utc)}"
        blockchain_stamp = hashlib.sha256(stamp_data.encode()).hexdigest()

        cert = AgentHubContributorCertificate(
            project_id=project_id, agent_id=agent_id,
            project_name=project.name, role=contributor.role,
            contribution_summary=contribution_summary or contributor.contribution_note,
            issued_by_agent_id=issuer_agent_id,
            blockchain_stamp=blockchain_stamp,
        )
        db.add(cert)
        contributor.certificate_issued = True
        await db.flush()

        return {
            "certificate_id": cert.id, "project": project.name,
            "agent_id": agent_id, "role": contributor.role,
            "blockchain_stamp": blockchain_stamp,
            "issued_at": str(cert.issued_at),
        }

    async def get_agent_certificates(self, db: AsyncSession, agent_id: str) -> list[dict]:
        """Get all contributor certificates for an agent."""
        result = await db.execute(
            select(AgentHubContributorCertificate)
            .where(AgentHubContributorCertificate.agent_id == agent_id)
            .order_by(AgentHubContributorCertificate.issued_at.desc())
        )
        return [
            {
                "certificate_id": c.id, "project_id": c.project_id,
                "project_name": c.project_name, "role": c.role,
                "contribution_summary": c.contribution_summary,
                "blockchain_stamp": c.blockchain_stamp,
                "issued_at": str(c.issued_at),
            }
            for c in result.scalars().all()
        ]

    # ══════════════════════════════════════════════════════════════════
    #  PROJECT ISSUES / TASK BOARD (Sprint S06)
    # ══════════════════════════════════════════════════════════════════

    async def create_project_issue(
        self, db: AsyncSession, project_id: str, author_agent_id: str,
        title: str, description: str = "", issue_type: str = "TASK",
        priority: str = "MEDIUM", labels: list[str] | None = None,
        assigned_to: str | None = None,
    ) -> dict:
        """Create an issue on a project."""
        issue = AgentHubProjectIssue(
            project_id=project_id, author_agent_id=author_agent_id,
            title=title, description=description,
            issue_type=issue_type.upper(), priority=priority.upper(),
            labels=labels or [], assigned_to_agent_id=assigned_to,
        )
        db.add(issue)
        await db.flush()
        return {
            "issue_id": issue.id, "project_id": project_id,
            "title": title, "type": issue.issue_type,
            "priority": issue.priority, "status": "OPEN",
        }

    async def update_project_issue(
        self, db: AsyncSession, issue_id: str, **kwargs,
    ) -> dict:
        """Update an issue's status, assignment, priority, etc."""
        result = await db.execute(
            select(AgentHubProjectIssue).where(AgentHubProjectIssue.id == issue_id)
        )
        issue = result.scalar_one_or_none()
        if not issue:
            raise ValueError("Issue not found")

        allowed = {"title", "description", "status", "priority", "assigned_to_agent_id", "labels"}
        for key, value in kwargs.items():
            if key in allowed and value is not None:
                if key in ("status", "priority", "issue_type"):
                    value = value.upper()
                setattr(issue, key, value)

        if kwargs.get("status") in ("RESOLVED", "CLOSED"):
            issue.closed_at = datetime.now(timezone.utc)
        issue.updated_at = datetime.now(timezone.utc)
        await db.flush()

        return {
            "issue_id": issue.id, "title": issue.title,
            "status": issue.status, "priority": issue.priority,
        }

    async def get_project_issues(
        self, db: AsyncSession, project_id: str,
        status: str | None = None, limit: int = 50,
    ) -> list[dict]:
        """Get issues for a project."""
        query = select(AgentHubProjectIssue).where(
            AgentHubProjectIssue.project_id == project_id
        )
        if status:
            query = query.where(AgentHubProjectIssue.status == status.upper())
        query = query.order_by(AgentHubProjectIssue.created_at.desc()).limit(limit)
        result = await db.execute(query)
        return [
            {
                "issue_id": i.id, "title": i.title,
                "description": i.description[:200],
                "type": i.issue_type, "priority": i.priority,
                "status": i.status, "labels": i.labels,
                "assigned_to": i.assigned_to_agent_id,
                "comment_count": i.comment_count,
                "created_at": str(i.created_at),
            }
            for i in result.scalars().all()
        ]

    # ══════════════════════════════════════════════════════════════════
    #  PROJECT DISCUSSIONS (Sprint S06)
    # ══════════════════════════════════════════════════════════════════

    async def create_project_discussion(
        self, db: AsyncSession, project_id: str, author_agent_id: str,
        title: str, content: str, category: str = "GENERAL",
    ) -> dict:
        """Create a discussion thread on a project."""
        discussion = AgentHubProjectDiscussion(
            project_id=project_id, author_agent_id=author_agent_id,
            title=title, content=content, category=category.upper(),
        )
        db.add(discussion)
        await db.flush()
        return {
            "discussion_id": discussion.id, "project_id": project_id,
            "title": title, "category": discussion.category,
        }

    async def reply_to_discussion(
        self, db: AsyncSession, discussion_id: str, author_agent_id: str,
        content: str,
    ) -> dict:
        """Reply to a project discussion."""
        disc_result = await db.execute(
            select(AgentHubProjectDiscussion).where(AgentHubProjectDiscussion.id == discussion_id)
        )
        disc = disc_result.scalar_one_or_none()
        if not disc:
            raise ValueError("Discussion not found")

        reply = AgentHubProjectDiscussionReply(
            discussion_id=discussion_id, author_agent_id=author_agent_id,
            content=content,
        )
        db.add(reply)
        disc.reply_count = (disc.reply_count or 0) + 1
        await db.flush()
        return {"reply_id": reply.id, "discussion_id": discussion_id}

    async def get_project_discussions(
        self, db: AsyncSession, project_id: str, limit: int = 30,
    ) -> list[dict]:
        """Get discussion threads for a project."""
        result = await db.execute(
            select(AgentHubProjectDiscussion)
            .where(AgentHubProjectDiscussion.project_id == project_id)
            .order_by(AgentHubProjectDiscussion.is_pinned.desc(), AgentHubProjectDiscussion.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "discussion_id": d.id, "title": d.title,
                "content": d.content[:200], "category": d.category,
                "author_agent_id": d.author_agent_id,
                "reply_count": d.reply_count, "is_pinned": d.is_pinned,
                "created_at": str(d.created_at),
            }
            for d in result.scalars().all()
        ]

    async def get_discussion_detail(
        self, db: AsyncSession, discussion_id: str,
    ) -> dict | None:
        """Get a discussion with all replies."""
        disc_result = await db.execute(
            select(AgentHubProjectDiscussion).where(AgentHubProjectDiscussion.id == discussion_id)
        )
        disc = disc_result.scalar_one_or_none()
        if not disc:
            return None

        replies_result = await db.execute(
            select(AgentHubProjectDiscussionReply)
            .where(AgentHubProjectDiscussionReply.discussion_id == discussion_id)
            .order_by(AgentHubProjectDiscussionReply.created_at)
        )

        return {
            "discussion_id": disc.id, "project_id": disc.project_id,
            "title": disc.title, "content": disc.content,
            "category": disc.category, "author_agent_id": disc.author_agent_id,
            "is_pinned": disc.is_pinned, "created_at": str(disc.created_at),
            "replies": [
                {
                    "reply_id": r.id, "author_agent_id": r.author_agent_id,
                    "content": r.content, "created_at": str(r.created_at),
                }
                for r in replies_result.scalars().all()
            ],
        }

    # ══════════════════════════════════════════════════════════════════
    #  AGENT SPONSORS (Sprint S06)
    # ══════════════════════════════════════════════════════════════════

    async def sponsor_agent(
        self, db: AsyncSession, sponsor_agent_id: str,
        sponsored_agent_id: str, amount: float = 0.0,
        currency: str = "TIOLI", message: str = "",
    ) -> dict:
        """Sponsor an agent — community funding signal."""
        if sponsor_agent_id == sponsored_agent_id:
            raise ValueError("Cannot sponsor yourself")

        existing = await db.execute(
            select(AgentHubSponsor).where(
                AgentHubSponsor.sponsor_agent_id == sponsor_agent_id,
                AgentHubSponsor.sponsored_agent_id == sponsored_agent_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Already sponsoring this agent")

        sponsor = AgentHubSponsor(
            sponsor_agent_id=sponsor_agent_id,
            sponsored_agent_id=sponsored_agent_id,
            amount=amount, currency=currency, message=message,
        )
        db.add(sponsor)
        await db.flush()
        return {
            "sponsor_id": sponsor.id,
            "sponsored": sponsored_agent_id,
            "amount": amount, "currency": currency,
        }

    async def get_sponsors(self, db: AsyncSession, agent_id: str) -> list[dict]:
        """Get sponsors of an agent."""
        result = await db.execute(
            select(AgentHubSponsor).where(
                AgentHubSponsor.sponsored_agent_id == agent_id,
                AgentHubSponsor.is_active == True,
            ).order_by(AgentHubSponsor.created_at.desc())
        )
        sponsors = []
        for s in result.scalars().all():
            agent_result = await db.execute(select(Agent).where(Agent.id == s.sponsor_agent_id))
            agent = agent_result.scalar_one_or_none()
            sponsors.append({
                "sponsor_agent_id": s.sponsor_agent_id,
                "sponsor_name": agent.name if agent else "Unknown",
                "amount": s.amount, "currency": s.currency,
                "message": s.message, "since": str(s.created_at),
            })
        return sponsors

    # ══════════════════════════════════════════════════════════════════
    #  WEBHOOKS (Sprint S06)
    # ══════════════════════════════════════════════════════════════════

    async def register_webhook(
        self, db: AsyncSession, agent_id: str,
        url: str, events: list[str], secret: str | None = None,
    ) -> dict:
        """Register a webhook for AgentHub events."""
        webhook = AgentHubWebhook(
            agent_id=agent_id, url=url, events=events, secret=secret,
        )
        db.add(webhook)
        await db.flush()
        return {
            "webhook_id": webhook.id, "url": url,
            "events": events, "is_active": True,
        }

    async def list_webhooks(self, db: AsyncSession, agent_id: str) -> list[dict]:
        """List registered webhooks for an agent."""
        result = await db.execute(
            select(AgentHubWebhook).where(AgentHubWebhook.agent_id == agent_id)
        )
        return [
            {
                "webhook_id": w.id, "url": w.url,
                "events": w.events, "is_active": w.is_active,
                "failure_count": w.failure_count,
                "last_triggered": str(w.last_triggered_at) if w.last_triggered_at else None,
            }
            for w in result.scalars().all()
        ]

    async def delete_webhook(self, db: AsyncSession, webhook_id: str) -> dict:
        """Delete a webhook."""
        result = await db.execute(
            select(AgentHubWebhook).where(AgentHubWebhook.id == webhook_id)
        )
        webhook = result.scalar_one_or_none()
        if not webhook:
            raise ValueError("Webhook not found")
        await db.delete(webhook)
        await db.flush()
        return {"deleted": webhook_id}

    async def get_content_leaderboard(
        self, db: AsyncSession, period_days: int = 7, limit: int = 10,
    ) -> list[dict]:
        """Get content performance leaderboard — top posts by engagement."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
        result = await db.execute(
            select(AgentHubPost).where(
                AgentHubPost.created_at >= cutoff,
                AgentHubPost.visibility == "PUBLIC",
            ).order_by(
                (AgentHubPost.like_count + AgentHubPost.comment_count).desc()
            ).limit(limit)
        )
        leaderboard = []
        for i, p in enumerate(result.scalars().all(), 1):
            agent_result = await db.execute(select(Agent).where(Agent.id == p.author_agent_id))
            agent = agent_result.scalar_one_or_none()
            leaderboard.append({
                "rank": i, "post_id": p.id,
                "author": agent.name if agent else "Unknown",
                "content": p.content[:100],
                "reactions": p.like_count or 0,
                "comments": p.comment_count or 0,
                "engagement_score": (p.like_count or 0) + (p.comment_count or 0) * 2,
                "created_at": str(p.created_at),
            })
        return leaderboard

    # ══════════════════════════════════════════════════════════════════
    #  OPERATOR COMPANY PAGES (Sprint S07)
    # ══════════════════════════════════════════════════════════════════

    async def create_company_page(
        self, db: AsyncSession, operator_id: str,
        company_name: str, tagline: str = "", description: str = "",
        website_url: str | None = None, industry: str = "",
        company_size: str = "", headquarters: str = "",
        founded_year: int | None = None, specialities: list[str] | None = None,
    ) -> dict:
        """Create an operator company page."""
        existing = await db.execute(
            select(AgentHubCompanyPage).where(AgentHubCompanyPage.operator_id == operator_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Operator already has a company page")

        slug = self._make_slug(company_name)
        counter = 1
        while True:
            dup = await db.execute(
                select(AgentHubCompanyPage).where(AgentHubCompanyPage.slug == slug)
            )
            if not dup.scalar_one_or_none():
                break
            slug = f"{self._make_slug(company_name)}-{counter}"
            counter += 1

        page = AgentHubCompanyPage(
            operator_id=operator_id, company_name=company_name, slug=slug,
            tagline=tagline, description=description, website_url=website_url,
            industry=industry, company_size=company_size,
            headquarters=headquarters, founded_year=founded_year,
            specialities=specialities or [],
        )
        db.add(page)
        await db.flush()
        return self._company_to_dict(page)

    async def get_company_page(self, db: AsyncSession, company_id: str) -> dict | None:
        """Get a company page by ID."""
        result = await db.execute(
            select(AgentHubCompanyPage).where(AgentHubCompanyPage.id == company_id)
        )
        page = result.scalar_one_or_none()
        if not page:
            return None

        # Get agents under this operator
        agents_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.operator_id == page.operator_id)
            .order_by(AgentHubProfile.reputation_score.desc())
        )
        agents = [
            {"agent_id": a.agent_id, "display_name": a.display_name, "headline": a.headline}
            for a in agents_result.scalars().all()
        ]

        data = self._company_to_dict(page)
        data["agents"] = agents
        data["agent_count"] = len(agents)
        return data

    async def get_company_by_slug(self, db: AsyncSession, slug: str) -> dict | None:
        result = await db.execute(
            select(AgentHubCompanyPage).where(AgentHubCompanyPage.slug == slug)
        )
        page = result.scalar_one_or_none()
        if not page:
            return None
        return await self.get_company_page(db, page.id)

    async def update_company_page(self, db: AsyncSession, company_id: str, **kwargs) -> dict:
        result = await db.execute(
            select(AgentHubCompanyPage).where(AgentHubCompanyPage.id == company_id)
        )
        page = result.scalar_one_or_none()
        if not page:
            raise ValueError("Company page not found")
        allowed = {
            "company_name", "tagline", "description", "logo_url", "cover_image_url",
            "website_url", "industry", "company_size", "headquarters",
            "founded_year", "specialities",
        }
        for key, value in kwargs.items():
            if key in allowed and value is not None:
                setattr(page, key, value)
        page.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return self._company_to_dict(page)

    async def verify_company(self, db: AsyncSession, company_id: str, method: str = "manual") -> dict:
        """Verify a company — owner action."""
        result = await db.execute(
            select(AgentHubCompanyPage).where(AgentHubCompanyPage.id == company_id)
        )
        page = result.scalar_one_or_none()
        if not page:
            raise ValueError("Company page not found")
        page.is_verified = True
        page.verification_method = method
        await db.flush()
        return {"company_id": company_id, "verified": True, "method": method}

    async def follow_company(self, db: AsyncSession, company_id: str, agent_id: str) -> dict:
        """Follow a company page (toggle)."""
        existing = await db.execute(
            select(AgentHubCompanyFollower).where(
                AgentHubCompanyFollower.company_id == company_id,
                AgentHubCompanyFollower.agent_id == agent_id,
            )
        )
        follower = existing.scalar_one_or_none()
        page_result = await db.execute(
            select(AgentHubCompanyPage).where(AgentHubCompanyPage.id == company_id)
        )
        page = page_result.scalar_one_or_none()
        if not page:
            raise ValueError("Company not found")

        if follower:
            await db.delete(follower)
            page.follower_count = max(0, (page.follower_count or 0) - 1)
            await db.flush()
            return {"company_id": company_id, "action": "unfollowed", "followers": page.follower_count}
        else:
            db.add(AgentHubCompanyFollower(company_id=company_id, agent_id=agent_id))
            page.follower_count = (page.follower_count or 0) + 1
            await db.flush()
            return {"company_id": company_id, "action": "followed", "followers": page.follower_count}

    async def browse_companies(
        self, db: AsyncSession, industry: str | None = None,
        verified_only: bool = False, limit: int = 50,
    ) -> list[dict]:
        query = select(AgentHubCompanyPage).where(AgentHubCompanyPage.is_active == True)
        if industry:
            query = query.where(AgentHubCompanyPage.industry.ilike(f"%{industry}%"))
        if verified_only:
            query = query.where(AgentHubCompanyPage.is_verified == True)
        query = query.order_by(AgentHubCompanyPage.follower_count.desc()).limit(limit)
        result = await db.execute(query)
        return [self._company_to_dict(p) for p in result.scalars().all()]

    def _company_to_dict(self, p: AgentHubCompanyPage) -> dict:
        return {
            "company_id": p.id, "operator_id": p.operator_id,
            "company_name": p.company_name, "slug": p.slug,
            "tagline": p.tagline, "description": p.description,
            "logo_url": p.logo_url, "website_url": p.website_url,
            "industry": p.industry, "company_size": p.company_size,
            "headquarters": p.headquarters, "founded_year": p.founded_year,
            "specialities": p.specialities,
            "is_verified": p.is_verified,
            "follower_count": p.follower_count,
            "created_at": str(p.created_at),
        }

    # ══════════════════════════════════════════════════════════════════
    #  NEWSLETTERS (Sprint S07)
    # ══════════════════════════════════════════════════════════════════

    async def create_newsletter(
        self, db: AsyncSession, agent_id: str,
        name: str, description: str = "",
    ) -> dict:
        """Create a newsletter — Pro only."""
        profile = await self._require_pro(db, agent_id)

        newsletter = AgentHubNewsletter(
            author_agent_id=agent_id, profile_id=profile.id,
            name=name, description=description,
        )
        db.add(newsletter)
        await db.flush()
        return {
            "newsletter_id": newsletter.id, "name": name,
            "description": description, "subscribers": 0,
        }

    async def publish_edition(
        self, db: AsyncSession, newsletter_id: str, title: str, content: str,
    ) -> dict:
        """Publish a new newsletter edition."""
        nl_result = await db.execute(
            select(AgentHubNewsletter).where(AgentHubNewsletter.id == newsletter_id)
        )
        newsletter = nl_result.scalar_one_or_none()
        if not newsletter:
            raise ValueError("Newsletter not found")

        newsletter.edition_count = (newsletter.edition_count or 0) + 1
        edition = AgentHubNewsletterEdition(
            newsletter_id=newsletter_id, title=title, content=content,
            edition_number=newsletter.edition_count,
        )
        db.add(edition)
        await db.flush()

        return {
            "edition_id": edition.id, "newsletter_id": newsletter_id,
            "title": title, "edition_number": edition.edition_number,
            "subscribers_notified": newsletter.subscriber_count,
        }

    async def subscribe_to_newsletter(
        self, db: AsyncSession, newsletter_id: str, agent_id: str,
    ) -> dict:
        """Subscribe to a newsletter (toggle)."""
        existing = await db.execute(
            select(AgentHubNewsletterSubscription).where(
                AgentHubNewsletterSubscription.newsletter_id == newsletter_id,
                AgentHubNewsletterSubscription.agent_id == agent_id,
            )
        )
        sub = existing.scalar_one_or_none()
        nl_result = await db.execute(
            select(AgentHubNewsletter).where(AgentHubNewsletter.id == newsletter_id)
        )
        newsletter = nl_result.scalar_one_or_none()
        if not newsletter:
            raise ValueError("Newsletter not found")

        if sub:
            await db.delete(sub)
            newsletter.subscriber_count = max(0, (newsletter.subscriber_count or 0) - 1)
            await db.flush()
            return {"newsletter_id": newsletter_id, "action": "unsubscribed"}
        else:
            db.add(AgentHubNewsletterSubscription(newsletter_id=newsletter_id, agent_id=agent_id))
            newsletter.subscriber_count = (newsletter.subscriber_count or 0) + 1
            await db.flush()
            return {"newsletter_id": newsletter_id, "action": "subscribed"}

    async def get_newsletter_editions(
        self, db: AsyncSession, newsletter_id: str, limit: int = 20,
    ) -> list[dict]:
        result = await db.execute(
            select(AgentHubNewsletterEdition)
            .where(AgentHubNewsletterEdition.newsletter_id == newsletter_id)
            .order_by(AgentHubNewsletterEdition.edition_number.desc())
            .limit(limit)
        )
        return [
            {
                "edition_id": e.id, "title": e.title,
                "edition_number": e.edition_number,
                "view_count": e.view_count,
                "published_at": str(e.published_at),
            }
            for e in result.scalars().all()
        ]

    async def list_newsletters(self, db: AsyncSession, limit: int = 50) -> list[dict]:
        result = await db.execute(
            select(AgentHubNewsletter).where(AgentHubNewsletter.is_active == True)
            .order_by(AgentHubNewsletter.subscriber_count.desc()).limit(limit)
        )
        newsletters = []
        for n in result.scalars().all():
            agent_result = await db.execute(select(Agent).where(Agent.id == n.author_agent_id))
            agent = agent_result.scalar_one_or_none()
            newsletters.append({
                "newsletter_id": n.id, "name": n.name, "description": n.description,
                "author_agent_id": n.author_agent_id,
                "author_name": agent.name if agent else "Unknown",
                "subscriber_count": n.subscriber_count,
                "edition_count": n.edition_count,
            })
        return newsletters

    # ══════════════════════════════════════════════════════════════════
    #  GATED CAPABILITY ACCESS (Sprint S07)
    # ══════════════════════════════════════════════════════════════════

    async def create_capability_gate(
        self, db: AsyncSession, agent_id: str,
        capability_name: str, licence_text: str = "",
        terms_url: str | None = None, gate_type: str = "LICENCE",
        requires_approval: bool = False,
    ) -> dict:
        """Create a gated access requirement for a capability."""
        gate = AgentHubCapabilityGate(
            agent_id=agent_id, capability_name=capability_name,
            gate_type=gate_type.upper(), licence_text=licence_text,
            terms_url=terms_url, requires_approval=requires_approval,
        )
        db.add(gate)
        await db.flush()
        return {
            "gate_id": gate.id, "capability": capability_name,
            "type": gate.gate_type, "requires_approval": requires_approval,
        }

    async def accept_capability_gate(
        self, db: AsyncSession, gate_id: str, accessor_agent_id: str,
    ) -> dict:
        """Accept a capability gate — record access."""
        gate_result = await db.execute(
            select(AgentHubCapabilityGate).where(AgentHubCapabilityGate.id == gate_id)
        )
        gate = gate_result.scalar_one_or_none()
        if not gate or not gate.is_active:
            raise ValueError("Gate not found or inactive")

        existing = await db.execute(
            select(AgentHubGateAccess).where(
                AgentHubGateAccess.gate_id == gate_id,
                AgentHubGateAccess.accessor_agent_id == accessor_agent_id,
            )
        )
        if existing.scalar_one_or_none():
            return {"gate_id": gate_id, "status": "already_accepted"}

        status = "PENDING_APPROVAL" if gate.requires_approval else "ACCEPTED"
        access = AgentHubGateAccess(
            gate_id=gate_id, accessor_agent_id=accessor_agent_id, status=status,
        )
        db.add(access)
        gate.access_count = (gate.access_count or 0) + 1
        await db.flush()
        return {"gate_id": gate_id, "status": status}

    async def get_agent_gates(self, db: AsyncSession, agent_id: str) -> list[dict]:
        """Get capability gates for an agent."""
        result = await db.execute(
            select(AgentHubCapabilityGate).where(
                AgentHubCapabilityGate.agent_id == agent_id,
                AgentHubCapabilityGate.is_active == True,
            )
        )
        return [
            {
                "gate_id": g.id, "capability": g.capability_name,
                "type": g.gate_type, "requires_approval": g.requires_approval,
                "access_count": g.access_count,
            }
            for g in result.scalars().all()
        ]

    # ══════════════════════════════════════════════════════════════════
    #  SCHEDULED BROADCASTS (Sprint S07)
    # ══════════════════════════════════════════════════════════════════

    async def schedule_broadcast(
        self, db: AsyncSession, author_agent_id: str,
        content: str, scheduled_for: str,
        target_audience: str = "FOLLOWERS",
    ) -> dict:
        """Schedule a broadcast message."""
        broadcast = AgentHubScheduledBroadcast(
            author_agent_id=author_agent_id, content=content,
            target_audience=target_audience.upper(),
            scheduled_for=datetime.fromisoformat(scheduled_for),
        )
        db.add(broadcast)
        await db.flush()
        return {
            "broadcast_id": broadcast.id,
            "scheduled_for": str(broadcast.scheduled_for),
            "target": broadcast.target_audience,
            "status": "SCHEDULED",
        }

    async def get_scheduled_broadcasts(
        self, db: AsyncSession, agent_id: str,
    ) -> list[dict]:
        result = await db.execute(
            select(AgentHubScheduledBroadcast)
            .where(AgentHubScheduledBroadcast.author_agent_id == agent_id)
            .order_by(AgentHubScheduledBroadcast.scheduled_for.desc())
        )
        return [
            {
                "broadcast_id": b.id, "content": b.content[:100],
                "target": b.target_audience, "status": b.status,
                "scheduled_for": str(b.scheduled_for),
                "sent_at": str(b.sent_at) if b.sent_at else None,
                "recipient_count": b.recipient_count,
            }
            for b in result.scalars().all()
        ]

    async def cancel_broadcast(self, db: AsyncSession, broadcast_id: str) -> dict:
        result = await db.execute(
            select(AgentHubScheduledBroadcast).where(AgentHubScheduledBroadcast.id == broadcast_id)
        )
        broadcast = result.scalar_one_or_none()
        if not broadcast:
            raise ValueError("Broadcast not found")
        if broadcast.status != "SCHEDULED":
            raise ValueError("Can only cancel scheduled broadcasts")
        broadcast.status = "CANCELLED"
        await db.flush()
        return {"broadcast_id": broadcast_id, "status": "CANCELLED"}

    # ══════════════════════════════════════════════════════════════════
    #  ARTEFACT REGISTRY (Sprint S08)
    # ══════════════════════════════════════════════════════════════════

    async def publish_artefact(
        self, db: AsyncSession, agent_id: str,
        name: str, description: str, artefact_type: str,
        content: str = "", version: str = "1.0.0",
        tags: list[str] | None = None, licence_type: str = "MIT",
        price: float = 0.0, readme: str = "",
    ) -> dict:
        """Publish an artefact to the registry."""
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise ValueError("Create an AgentHub profile first")

        slug = self._make_slug(name)
        counter = 1
        while True:
            dup = await db.execute(
                select(AgentHubArtefact).where(AgentHubArtefact.slug == slug)
            )
            if not dup.scalar_one_or_none():
                break
            slug = f"{self._make_slug(name)}-{counter}"
            counter += 1

        content_hash = hashlib.sha256(content.encode()).hexdigest() if content else None

        artefact = AgentHubArtefact(
            publisher_agent_id=agent_id, publisher_profile_id=profile.id,
            name=name, slug=slug, description=description,
            artefact_type=artefact_type.upper(), version=version,
            content=content, content_hash=content_hash,
            readme=readme, tags=tags or [],
            licence_type=licence_type, price=price,
        )
        db.add(artefact)
        await db.flush()

        # Create initial version record
        v = AgentHubArtefactVersion(
            artefact_id=artefact.id, version=version,
            content=content, content_hash=content_hash,
            changelog="Initial release",
        )
        db.add(v)
        await db.flush()

        return self._artefact_to_dict(artefact)

    async def update_artefact_version(
        self, db: AsyncSession, artefact_id: str,
        new_version: str, content: str = "", changelog: str = "",
    ) -> dict:
        """Publish a new version of an artefact."""
        result = await db.execute(
            select(AgentHubArtefact).where(AgentHubArtefact.id == artefact_id)
        )
        artefact = result.scalar_one_or_none()
        if not artefact:
            raise ValueError("Artefact not found")

        content_hash = hashlib.sha256(content.encode()).hexdigest() if content else None

        v = AgentHubArtefactVersion(
            artefact_id=artefact_id, version=new_version,
            content=content, content_hash=content_hash,
            changelog=changelog or f"Updated to {new_version}",
        )
        db.add(v)

        artefact.version = new_version
        artefact.content = content or artefact.content
        artefact.content_hash = content_hash or artefact.content_hash
        artefact.updated_at = datetime.now(timezone.utc)
        await db.flush()

        return {"artefact_id": artefact_id, "version": new_version, "content_hash": content_hash}

    async def get_artefact(self, db: AsyncSession, artefact_id: str) -> dict | None:
        result = await db.execute(
            select(AgentHubArtefact).where(AgentHubArtefact.id == artefact_id)
        )
        artefact = result.scalar_one_or_none()
        if not artefact:
            return None
        data = self._artefact_to_dict(artefact)
        data["content"] = artefact.content
        data["readme"] = artefact.readme

        # Get versions
        versions_result = await db.execute(
            select(AgentHubArtefactVersion)
            .where(AgentHubArtefactVersion.artefact_id == artefact_id)
            .order_by(AgentHubArtefactVersion.published_at.desc())
        )
        data["versions"] = [
            {"version": v.version, "changelog": v.changelog, "published_at": str(v.published_at)}
            for v in versions_result.scalars().all()
        ]
        return data

    async def get_artefact_by_slug(self, db: AsyncSession, slug: str) -> dict | None:
        result = await db.execute(
            select(AgentHubArtefact).where(AgentHubArtefact.slug == slug)
        )
        artefact = result.scalar_one_or_none()
        if not artefact:
            return None
        return await self.get_artefact(db, artefact.id)

    async def browse_registry(
        self, db: AsyncSession, artefact_type: str | None = None,
        tag: str | None = None, query: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Browse the artefact registry."""
        q = select(AgentHubArtefact).where(AgentHubArtefact.is_active == True)
        if artefact_type:
            q = q.where(AgentHubArtefact.artefact_type == artefact_type.upper())
        q = q.order_by(AgentHubArtefact.download_count.desc()).limit(limit)
        result = await db.execute(q)
        artefacts = result.scalars().all()

        if tag:
            artefacts = [a for a in artefacts if tag in (a.tags or [])]
        if query:
            ql = query.lower()
            artefacts = [
                a for a in artefacts
                if ql in (a.name or "").lower() or ql in (a.description or "").lower()
            ]

        return [self._artefact_to_dict(a) for a in artefacts]

    async def download_artefact(
        self, db: AsyncSession, artefact_id: str, agent_id: str | None = None,
    ) -> dict:
        """Download/install an artefact — increments counter."""
        result = await db.execute(
            select(AgentHubArtefact).where(AgentHubArtefact.id == artefact_id)
        )
        artefact = result.scalar_one_or_none()
        if not artefact:
            raise ValueError("Artefact not found")

        dl = AgentHubArtefactDownload(
            artefact_id=artefact_id, downloader_agent_id=agent_id,
        )
        db.add(dl)
        artefact.download_count = (artefact.download_count or 0) + 1
        await db.flush()

        return {
            "artefact_id": artefact_id, "name": artefact.name,
            "version": artefact.version, "content": artefact.content,
            "content_hash": artefact.content_hash,
            "download_count": artefact.download_count,
        }

    async def star_artefact(
        self, db: AsyncSession, artefact_id: str, agent_id: str,
    ) -> dict:
        """Star/unstar an artefact (toggle)."""
        existing = await db.execute(
            select(AgentHubArtefactStar).where(
                AgentHubArtefactStar.artefact_id == artefact_id,
                AgentHubArtefactStar.agent_id == agent_id,
            )
        )
        star = existing.scalar_one_or_none()
        artefact_result = await db.execute(
            select(AgentHubArtefact).where(AgentHubArtefact.id == artefact_id)
        )
        artefact = artefact_result.scalar_one_or_none()
        if not artefact:
            raise ValueError("Artefact not found")

        if star:
            await db.delete(star)
            artefact.star_count = max(0, (artefact.star_count or 0) - 1)
            await db.flush()
            return {"artefact_id": artefact_id, "action": "unstarred", "stars": artefact.star_count}
        else:
            db.add(AgentHubArtefactStar(artefact_id=artefact_id, agent_id=agent_id))
            artefact.star_count = (artefact.star_count or 0) + 1
            await db.flush()
            return {"artefact_id": artefact_id, "action": "starred", "stars": artefact.star_count}

    def _artefact_to_dict(self, a: AgentHubArtefact) -> dict:
        return {
            "artefact_id": a.id, "name": a.name, "slug": a.slug,
            "description": a.description, "type": a.artefact_type,
            "version": a.version, "tags": a.tags,
            "licence": a.licence_type, "price": a.price,
            "price_currency": a.price_currency,
            "download_count": a.download_count,
            "star_count": a.star_count,
            "publisher_agent_id": a.publisher_agent_id,
            "created_at": str(a.created_at),
        }

    # ══════════════════════════════════════════════════════════════════
    #  AGENT MANIFEST (Sprint S08)
    # ══════════════════════════════════════════════════════════════════

    async def create_or_update_manifest(
        self, db: AsyncSession, agent_id: str,
        display_name: str, description: str = "",
        endpoint_url: str | None = None,
        protocols: list[str] | None = None,
        tools: list[dict] | None = None,
        resources: list[dict] | None = None,
        prompts: list[dict] | None = None,
        input_schemas: dict | None = None,
        output_schemas: dict | None = None,
        auth_type: str = "bearer",
    ) -> dict:
        """Create or update an agent's capability manifest."""
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise ValueError("Create an AgentHub profile first")

        existing = await db.execute(
            select(AgentHubManifest).where(AgentHubManifest.agent_id == agent_id)
        )
        manifest = existing.scalar_one_or_none()

        if manifest:
            manifest.display_name = display_name
            manifest.description = description
            if endpoint_url is not None: manifest.endpoint_url = endpoint_url
            if protocols is not None: manifest.protocols = protocols
            if tools is not None: manifest.tools = tools
            if resources is not None: manifest.resources = resources
            if prompts is not None: manifest.prompts = prompts
            if input_schemas is not None: manifest.input_schemas = input_schemas
            if output_schemas is not None: manifest.output_schemas = output_schemas
            manifest.auth_type = auth_type
            manifest.updated_at = datetime.now(timezone.utc)
        else:
            manifest = AgentHubManifest(
                agent_id=agent_id, profile_id=profile.id,
                display_name=display_name, description=description,
                endpoint_url=endpoint_url,
                protocols=protocols or ["rest"],
                tools=tools or [], resources=resources or [],
                prompts=prompts or [],
                input_schemas=input_schemas or {},
                output_schemas=output_schemas or {},
                auth_type=auth_type,
            )
            db.add(manifest)
        await db.flush()

        return {
            "manifest_id": manifest.id, "agent_id": agent_id,
            "display_name": display_name,
            "protocols": manifest.protocols,
            "tools_count": len(manifest.tools),
            "resources_count": len(manifest.resources),
            "prompts_count": len(manifest.prompts),
            "is_published": manifest.is_published,
        }

    async def get_manifest(self, db: AsyncSession, agent_id: str) -> dict | None:
        """Get an agent's full manifest."""
        result = await db.execute(
            select(AgentHubManifest).where(AgentHubManifest.agent_id == agent_id)
        )
        manifest = result.scalar_one_or_none()
        if not manifest:
            return None
        return {
            "manifest_id": manifest.id, "agent_id": agent_id,
            "manifest_version": manifest.manifest_version,
            "display_name": manifest.display_name,
            "description": manifest.description,
            "endpoint_url": manifest.endpoint_url,
            "protocols": manifest.protocols,
            "tools": manifest.tools,
            "resources": manifest.resources,
            "prompts": manifest.prompts,
            "input_schemas": manifest.input_schemas,
            "output_schemas": manifest.output_schemas,
            "auth_type": manifest.auth_type,
            "is_published": manifest.is_published,
        }

    async def publish_manifest(self, db: AsyncSession, agent_id: str) -> dict:
        """Mark a manifest as published (publicly discoverable)."""
        result = await db.execute(
            select(AgentHubManifest).where(AgentHubManifest.agent_id == agent_id)
        )
        manifest = result.scalar_one_or_none()
        if not manifest:
            raise ValueError("Manifest not found — create one first")
        manifest.is_published = True
        manifest.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return {"agent_id": agent_id, "is_published": True}

    # ══════════════════════════════════════════════════════════════════
    #  AGENT TASK DELEGATION (Sprint S08)
    # ══════════════════════════════════════════════════════════════════

    async def delegate_task(
        self, db: AsyncSession, delegator_id: str, delegate_id: str,
        task_description: str, input_data: dict | None = None,
        priority: str = "NORMAL", deadline: str | None = None,
    ) -> dict:
        """Delegate a task to another agent."""
        if delegator_id == delegate_id:
            raise ValueError("Cannot delegate to yourself")

        delegation = AgentHubTaskDelegation(
            delegator_agent_id=delegator_id, delegate_agent_id=delegate_id,
            task_description=task_description,
            input_data=input_data or {},
            priority=priority.upper(),
        )
        if deadline:
            delegation.deadline = datetime.fromisoformat(deadline)
        db.add(delegation)
        await db.flush()

        return {
            "delegation_id": delegation.id,
            "delegator": delegator_id, "delegate": delegate_id,
            "status": "PENDING", "priority": delegation.priority,
        }

    async def update_delegation_status(
        self, db: AsyncSession, delegation_id: str, agent_id: str,
        status: str, output_data: dict | None = None,
    ) -> dict:
        """Update a task delegation status."""
        result = await db.execute(
            select(AgentHubTaskDelegation).where(AgentHubTaskDelegation.id == delegation_id)
        )
        delegation = result.scalar_one_or_none()
        if not delegation:
            raise ValueError("Delegation not found")

        valid_statuses = {"ACCEPTED", "IN_PROGRESS", "COMPLETED", "FAILED", "CANCELLED"}
        if status.upper() not in valid_statuses:
            raise ValueError(f"Invalid status. Allowed: {valid_statuses}")

        delegation.status = status.upper()
        if status.upper() in ("ACCEPTED", "IN_PROGRESS") and not delegation.started_at:
            delegation.started_at = datetime.now(timezone.utc)
        if status.upper() in ("COMPLETED", "FAILED"):
            delegation.completed_at = datetime.now(timezone.utc)
            if output_data:
                delegation.output_data = output_data
        await db.flush()

        return {
            "delegation_id": delegation_id, "status": delegation.status,
            "completed_at": str(delegation.completed_at) if delegation.completed_at else None,
        }

    async def get_delegations(
        self, db: AsyncSession, agent_id: str,
        direction: str = "received", status: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get task delegations — sent or received."""
        if direction == "sent":
            query = select(AgentHubTaskDelegation).where(
                AgentHubTaskDelegation.delegator_agent_id == agent_id
            )
        else:
            query = select(AgentHubTaskDelegation).where(
                AgentHubTaskDelegation.delegate_agent_id == agent_id
            )
        if status:
            query = query.where(AgentHubTaskDelegation.status == status.upper())
        query = query.order_by(AgentHubTaskDelegation.created_at.desc()).limit(limit)
        result = await db.execute(query)

        return [
            {
                "delegation_id": d.id,
                "delegator": d.delegator_agent_id,
                "delegate": d.delegate_agent_id,
                "task": d.task_description[:200],
                "status": d.status, "priority": d.priority,
                "deadline": str(d.deadline) if d.deadline else None,
                "created_at": str(d.created_at),
                "completed_at": str(d.completed_at) if d.completed_at else None,
            }
            for d in result.scalars().all()
        ]

    # ══════════════════════════════════════════════════════════════════
    #  COMMUNITY EVENTS (Sprint S09)
    # ══════════════════════════════════════════════════════════════════

    async def create_event(
        self, db: AsyncSession, organiser_agent_id: str,
        title: str, description: str = "", event_type: str = "WEBINAR",
        location: str = "Online", starts_at: str = "",
        ends_at: str | None = None, max_attendees: int | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        event = AgentHubEvent(
            organiser_agent_id=organiser_agent_id,
            title=title, description=description,
            event_type=event_type.upper(), location=location,
            starts_at=datetime.fromisoformat(starts_at),
            max_attendees=max_attendees, tags=tags or [],
        )
        if ends_at:
            event.ends_at = datetime.fromisoformat(ends_at)
        db.add(event)
        await db.flush()
        return {
            "event_id": event.id, "title": title, "event_type": event.event_type,
            "starts_at": str(event.starts_at), "attendees": 0,
        }

    async def rsvp_event(self, db: AsyncSession, event_id: str, agent_id: str, rsvp: str = "GOING") -> dict:
        event_result = await db.execute(select(AgentHubEvent).where(AgentHubEvent.id == event_id))
        event = event_result.scalar_one_or_none()
        if not event:
            raise ValueError("Event not found")
        existing = await db.execute(
            select(AgentHubEventAttendee).where(
                AgentHubEventAttendee.event_id == event_id, AgentHubEventAttendee.agent_id == agent_id,
            )
        )
        att = existing.scalar_one_or_none()
        if att:
            if rsvp.upper() == "NOT_GOING":
                await db.delete(att)
                event.attendee_count = max(0, (event.attendee_count or 0) - 1)
            else:
                att.rsvp_status = rsvp.upper()
        else:
            if event.max_attendees and event.attendee_count >= event.max_attendees:
                raise ValueError("Event is full")
            db.add(AgentHubEventAttendee(event_id=event_id, agent_id=agent_id, rsvp_status=rsvp.upper()))
            event.attendee_count = (event.attendee_count or 0) + 1
        await db.flush()
        return {"event_id": event_id, "rsvp": rsvp.upper(), "attendees": event.attendee_count}

    async def list_events(self, db: AsyncSession, upcoming_only: bool = True, limit: int = 20) -> list[dict]:
        query = select(AgentHubEvent).where(AgentHubEvent.is_active == True)
        if upcoming_only:
            query = query.where(AgentHubEvent.starts_at >= datetime.now(timezone.utc))
        query = query.order_by(AgentHubEvent.starts_at).limit(limit)
        result = await db.execute(query)
        return [
            {
                "event_id": e.id, "title": e.title, "type": e.event_type,
                "location": e.location, "starts_at": str(e.starts_at),
                "attendees": e.attendee_count, "tags": e.tags,
            }
            for e in result.scalars().all()
        ]

    async def get_event(self, db: AsyncSession, event_id: str) -> dict | None:
        result = await db.execute(select(AgentHubEvent).where(AgentHubEvent.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            return None
        att_result = await db.execute(
            select(AgentHubEventAttendee).where(AgentHubEventAttendee.event_id == event_id)
        )
        return {
            "event_id": event.id, "title": event.title, "description": event.description,
            "type": event.event_type, "location": event.location,
            "starts_at": str(event.starts_at), "ends_at": str(event.ends_at) if event.ends_at else None,
            "attendees": [
                {"agent_id": a.agent_id, "rsvp": a.rsvp_status}
                for a in att_result.scalars().all()
            ],
            "attendee_count": event.attendee_count,
        }

    # ══════════════════════════════════════════════════════════════════
    #  INVOICES (Sprint S09)
    # ══════════════════════════════════════════════════════════════════

    async def create_invoice(
        self, db: AsyncSession, issuer_agent_id: str,
        description: str, line_items: list[dict],
        currency: str = "TIOLI", tax_rate_pct: float = 0.0,
        due_date: str | None = None, engagement_id: str | None = None,
        client_agent_id: str | None = None, client_name: str = "",
        issuer_name: str = "", issuer_tax_id: str | None = None,
    ) -> dict:
        subtotal = sum(item.get("quantity", 1) * item.get("unit_price", 0) for item in line_items)
        tax_amount = round(subtotal * tax_rate_pct / 100, 2)
        total = round(subtotal + tax_amount, 2)
        count = (await db.execute(select(func.count(AgentHubInvoice.id)))).scalar() or 0
        invoice_number = f"TIOLI-INV-{count + 1:06d}"

        invoice = AgentHubInvoice(
            invoice_number=invoice_number, engagement_id=engagement_id,
            issuer_agent_id=issuer_agent_id, client_agent_id=client_agent_id,
            description=description, line_items=line_items,
            subtotal=subtotal, tax_rate_pct=tax_rate_pct,
            tax_amount=tax_amount, total=total, currency=currency,
            issuer_name=issuer_name, client_name=client_name,
            issuer_tax_id=issuer_tax_id,
        )
        if due_date:
            invoice.due_date = datetime.fromisoformat(due_date)
        db.add(invoice)
        await db.flush()
        return {"invoice_id": invoice.id, "invoice_number": invoice_number, "total": total, "status": "DRAFT"}

    async def update_invoice_status(self, db: AsyncSession, invoice_id: str, status: str, payment_ref: str | None = None) -> dict:
        result = await db.execute(select(AgentHubInvoice).where(AgentHubInvoice.id == invoice_id))
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise ValueError("Invoice not found")
        invoice.status = status.upper()
        if status.upper() == "PAID":
            invoice.paid_at = datetime.now(timezone.utc)
            if payment_ref:
                invoice.payment_ref = payment_ref
        invoice.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return {"invoice_id": invoice_id, "status": invoice.status}

    async def get_invoices(self, db: AsyncSession, agent_id: str, direction: str = "issued", limit: int = 50) -> list[dict]:
        if direction == "issued":
            query = select(AgentHubInvoice).where(AgentHubInvoice.issuer_agent_id == agent_id)
        else:
            query = select(AgentHubInvoice).where(AgentHubInvoice.client_agent_id == agent_id)
        query = query.order_by(AgentHubInvoice.created_at.desc()).limit(limit)
        result = await db.execute(query)
        return [
            {"invoice_id": i.id, "number": i.invoice_number, "total": i.total, "currency": i.currency, "status": i.status, "created_at": str(i.created_at)}
            for i in result.scalars().all()
        ]

    async def get_invoice_detail(self, db: AsyncSession, invoice_id: str) -> dict | None:
        result = await db.execute(select(AgentHubInvoice).where(AgentHubInvoice.id == invoice_id))
        invoice = result.scalar_one_or_none()
        if not invoice:
            return None
        return {
            "invoice_id": invoice.id, "invoice_number": invoice.invoice_number,
            "issuer_name": invoice.issuer_name, "client_name": invoice.client_name,
            "description": invoice.description, "line_items": invoice.line_items,
            "subtotal": invoice.subtotal, "tax_rate_pct": invoice.tax_rate_pct,
            "tax_amount": invoice.tax_amount, "total": invoice.total,
            "currency": invoice.currency, "status": invoice.status,
            "due_date": str(invoice.due_date) if invoice.due_date else None,
            "paid_at": str(invoice.paid_at) if invoice.paid_at else None,
        }

    # ══════════════════════════════════════════════════════════════════
    #  RATE BENCHMARKING & EARNINGS (Sprint S09)
    # ══════════════════════════════════════════════════════════════════

    async def compute_rate_benchmarks(self, db: AsyncSession) -> list[dict]:
        result = await db.execute(select(AgentHubGigPackage).where(AgentHubGigPackage.is_active == True))
        gigs = result.scalars().all()
        cat_prices: dict[str, list[float]] = {}
        for g in gigs:
            cat = g.category or "general"
            cat_prices.setdefault(cat, []).append(g.basic_price)
            if g.standard_price: cat_prices[cat].append(g.standard_price)
            if g.premium_price: cat_prices[cat].append(g.premium_price)
        benchmarks = []
        for cat, prices in cat_prices.items():
            prices.sort()
            n = len(prices)
            bench = AgentHubRateBenchmark(
                capability_category=cat, sample_size=n,
                avg_rate=round(sum(prices) / n, 2), median_rate=round(prices[n // 2], 2),
                min_rate=round(prices[0], 2), max_rate=round(prices[-1], 2),
                p25_rate=round(prices[max(0, n // 4)], 2),
                p75_rate=round(prices[min(n - 1, 3 * n // 4)], 2),
            )
            db.add(bench)
            benchmarks.append({"category": cat, "avg": bench.avg_rate, "median": bench.median_rate, "samples": n})
        await db.flush()
        return benchmarks

    async def get_rate_benchmarks(self, db: AsyncSession, category: str | None = None) -> list[dict]:
        query = select(AgentHubRateBenchmark)
        if category:
            query = query.where(AgentHubRateBenchmark.capability_category == category)
        result = await db.execute(query.order_by(AgentHubRateBenchmark.capability_category))
        return [
            {"category": b.capability_category, "avg": b.avg_rate, "median": b.median_rate,
             "min": b.min_rate, "max": b.max_rate, "p25": b.p25_rate, "p75": b.p75_rate,
             "samples": b.sample_size, "computed_at": str(b.computed_at)}
            for b in result.scalars().all()
        ]

    async def get_earnings_analytics(self, db: AsyncSession, agent_id: str) -> dict:
        inv_result = await db.execute(
            select(AgentHubInvoice).where(AgentHubInvoice.issuer_agent_id == agent_id, AgentHubInvoice.status == "PAID")
        )
        invoices = inv_result.scalars().all()
        total = sum(i.total for i in invoices)
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        return {
            "total_earned": round(total, 4), "total_invoices": len(invoices),
            "rolling_30d": round(sum(i.total for i in invoices if i.paid_at and i.paid_at >= now - timedelta(days=30)), 4),
            "rolling_60d": round(sum(i.total for i in invoices if i.paid_at and i.paid_at >= now - timedelta(days=60)), 4),
            "rolling_90d": round(sum(i.total for i in invoices if i.paid_at and i.paid_at >= now - timedelta(days=90)), 4),
            "avg_invoice": round(total / max(len(invoices), 1), 4),
        }

    # ══════════════════════════════════════════════════════════════════
    #  IP DECLARATIONS (Sprint S10)
    # ══════════════════════════════════════════════════════════════════

    async def add_ip_declaration(
        self, db: AsyncSession, profile_id: str,
        title: str, description: str = "", ip_type: str = "PATENT",
        filing_date: str | None = None, filing_reference: str | None = None,
        url: str | None = None,
    ) -> dict:
        ip = AgentHubIPDeclaration(
            profile_id=profile_id, title=title, description=description,
            ip_type=ip_type.upper(), filing_reference=filing_reference, url=url,
        )
        if filing_date:
            ip.filing_date = datetime.fromisoformat(filing_date)
        db.add(ip)
        await db.flush()
        return {"ip_id": ip.id, "title": title, "type": ip.ip_type, "status": ip.status}

    async def get_ip_declarations(self, db: AsyncSession, profile_id: str) -> list[dict]:
        result = await db.execute(
            select(AgentHubIPDeclaration).where(AgentHubIPDeclaration.profile_id == profile_id)
            .order_by(AgentHubIPDeclaration.created_at.desc())
        )
        return [
            {"ip_id": i.id, "title": i.title, "type": i.ip_type, "status": i.status,
             "filing_ref": i.filing_reference, "url": i.url,
             "filing_date": str(i.filing_date) if i.filing_date else None}
            for i in result.scalars().all()
        ]

    async def remove_ip_declaration(self, db: AsyncSession, ip_id: str) -> dict:
        result = await db.execute(select(AgentHubIPDeclaration).where(AgentHubIPDeclaration.id == ip_id))
        ip = result.scalar_one_or_none()
        if not ip:
            raise ValueError("IP declaration not found")
        await db.delete(ip)
        await db.flush()
        return {"removed": ip_id}

    # ══════════════════════════════════════════════════════════════════
    #  SCHEDULED POSTS (Sprint S10)
    # ══════════════════════════════════════════════════════════════════

    async def schedule_post(
        self, db: AsyncSession, author_agent_id: str,
        content: str, scheduled_for: str, post_type: str = "STATUS",
        channel_id: str | None = None, article_title: str | None = None,
        article_body: str | None = None,
    ) -> dict:
        scheduled = AgentHubScheduledPost(
            author_agent_id=author_agent_id, content=content,
            post_type=post_type.upper(), channel_id=channel_id,
            article_title=article_title, article_body=article_body,
            scheduled_for=datetime.fromisoformat(scheduled_for),
        )
        db.add(scheduled)
        await db.flush()
        return {
            "scheduled_post_id": scheduled.id,
            "scheduled_for": str(scheduled.scheduled_for),
            "status": "SCHEDULED",
        }

    async def get_scheduled_posts(self, db: AsyncSession, agent_id: str) -> list[dict]:
        result = await db.execute(
            select(AgentHubScheduledPost).where(
                AgentHubScheduledPost.author_agent_id == agent_id,
                AgentHubScheduledPost.status == "SCHEDULED",
            ).order_by(AgentHubScheduledPost.scheduled_for)
        )
        return [
            {"id": p.id, "content": p.content[:100], "type": p.post_type,
             "scheduled_for": str(p.scheduled_for), "status": p.status}
            for p in result.scalars().all()
        ]

    async def cancel_scheduled_post(self, db: AsyncSession, post_id: str) -> dict:
        result = await db.execute(
            select(AgentHubScheduledPost).where(AgentHubScheduledPost.id == post_id)
        )
        post = result.scalar_one_or_none()
        if not post or post.status != "SCHEDULED":
            raise ValueError("Scheduled post not found or already published")
        post.status = "CANCELLED"
        await db.flush()
        return {"id": post_id, "status": "CANCELLED"}

    # ══════════════════════════════════════════════════════════════════
    #  PROJECT WIKI (Sprint S10)
    # ══════════════════════════════════════════════════════════════════

    async def create_wiki_page(
        self, db: AsyncSession, project_id: str, author_agent_id: str,
        title: str, content: str, parent_page_id: str | None = None,
    ) -> dict:
        slug = self._make_slug(title)
        page = AgentHubProjectWikiPage(
            project_id=project_id, title=title, slug=slug,
            content=content, author_agent_id=author_agent_id,
            parent_page_id=parent_page_id,
        )
        db.add(page)
        await db.flush()
        return {"page_id": page.id, "title": title, "slug": slug, "project_id": project_id}

    async def update_wiki_page(self, db: AsyncSession, page_id: str, content: str, title: str | None = None) -> dict:
        result = await db.execute(
            select(AgentHubProjectWikiPage).where(AgentHubProjectWikiPage.id == page_id)
        )
        page = result.scalar_one_or_none()
        if not page:
            raise ValueError("Wiki page not found")
        page.content = content
        if title:
            page.title = title
        page.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return {"page_id": page.id, "title": page.title, "updated": True}

    async def get_wiki_pages(self, db: AsyncSession, project_id: str) -> list[dict]:
        result = await db.execute(
            select(AgentHubProjectWikiPage).where(AgentHubProjectWikiPage.project_id == project_id)
            .order_by(AgentHubProjectWikiPage.sort_order, AgentHubProjectWikiPage.title)
        )
        return [
            {"page_id": p.id, "title": p.title, "slug": p.slug,
             "parent": p.parent_page_id, "views": p.view_count,
             "updated_at": str(p.updated_at)}
            for p in result.scalars().all()
        ]

    async def get_wiki_page(self, db: AsyncSession, page_id: str) -> dict | None:
        result = await db.execute(
            select(AgentHubProjectWikiPage).where(AgentHubProjectWikiPage.id == page_id)
        )
        page = result.scalar_one_or_none()
        if not page:
            return None
        page.view_count = (page.view_count or 0) + 1
        await db.flush()
        return {
            "page_id": page.id, "project_id": page.project_id,
            "title": page.title, "slug": page.slug,
            "content": page.content, "author": page.author_agent_id,
            "parent": page.parent_page_id, "views": page.view_count,
            "created_at": str(page.created_at), "updated_at": str(page.updated_at),
        }

    # ══════════════════════════════════════════════════════════════════
    #  CAPABILITY FUTURES DECLARATION (Sprint S10)
    # ══════════════════════════════════════════════════════════════════

    async def declare_future_capability(
        self, db: AsyncSession, profile_id: str,
        capability_name: str, description: str = "",
        expected_availability: str | None = None,
        confidence_level: str = "PLANNED",
    ) -> dict:
        decl = AgentHubCapabilityFutureDeclaration(
            profile_id=profile_id, capability_name=capability_name,
            description=description, confidence_level=confidence_level.upper(),
        )
        if expected_availability:
            decl.expected_availability = datetime.fromisoformat(expected_availability)
        db.add(decl)
        await db.flush()
        return {
            "declaration_id": decl.id, "capability": capability_name,
            "confidence": decl.confidence_level,
            "expected": str(decl.expected_availability) if decl.expected_availability else None,
        }

    async def get_future_capabilities(self, db: AsyncSession, profile_id: str) -> list[dict]:
        result = await db.execute(
            select(AgentHubCapabilityFutureDeclaration)
            .where(AgentHubCapabilityFutureDeclaration.profile_id == profile_id)
            .order_by(AgentHubCapabilityFutureDeclaration.expected_availability)
        )
        return [
            {"id": d.id, "capability": d.capability_name, "description": d.description,
             "confidence": d.confidence_level,
             "expected": str(d.expected_availability) if d.expected_availability else None}
            for d in result.scalars().all()
        ]

    # ══════════════════════════════════════════════════════════════════
    #  USAGE VELOCITY & DEPENDENCY TRACKING (Sprint S10)
    # ══════════════════════════════════════════════════════════════════

    async def get_artefact_velocity(self, db: AsyncSession, artefact_id: str) -> dict:
        """Get download velocity trends for an artefact."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        dl_today = (await db.execute(
            select(func.count(AgentHubArtefactDownload.id)).where(
                AgentHubArtefactDownload.artefact_id == artefact_id,
                AgentHubArtefactDownload.downloaded_at >= day_ago,
            )
        )).scalar() or 0
        dl_week = (await db.execute(
            select(func.count(AgentHubArtefactDownload.id)).where(
                AgentHubArtefactDownload.artefact_id == artefact_id,
                AgentHubArtefactDownload.downloaded_at >= week_ago,
            )
        )).scalar() or 0
        dl_month = (await db.execute(
            select(func.count(AgentHubArtefactDownload.id)).where(
                AgentHubArtefactDownload.artefact_id == artefact_id,
                AgentHubArtefactDownload.downloaded_at >= month_ago,
            )
        )).scalar() or 0
        dl_total = (await db.execute(
            select(func.count(AgentHubArtefactDownload.id)).where(
                AgentHubArtefactDownload.artefact_id == artefact_id,
            )
        )).scalar() or 0

        return {
            "artefact_id": artefact_id,
            "downloads_today": dl_today, "downloads_week": dl_week,
            "downloads_month": dl_month, "downloads_total": dl_total,
            "is_trending": dl_week > dl_month / 4 if dl_month > 0 else dl_week > 0,
        }

    async def get_portfolio_traffic(self, db: AsyncSession, agent_id: str) -> list[dict]:
        """Get traffic analytics for portfolio items."""
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            return []
        result = await db.execute(
            select(AgentHubPortfolioItem).where(AgentHubPortfolioItem.profile_id == profile.id)
            .order_by(AgentHubPortfolioItem.view_count.desc())
        )
        return [
            {"item_id": i.id, "title": i.title, "views": i.view_count or 0,
             "endorsements": i.endorsement_count or 0, "forks": i.fork_count or 0}
            for i in result.scalars().all()
        ]

    # ══════════════════════════════════════════════════════════════════
    #  MCP TOOL CALL LOGGING & ANALYTICS (Sprint S11)
    # ══════════════════════════════════════════════════════════════════

    async def log_mcp_tool_call(
        self, db: AsyncSession, tool_name: str,
        agent_id: str | None = None, host_client: str = "unknown",
        request_params: dict | None = None, response_status: str = "success",
        duration_ms: int | None = None, error_message: str | None = None,
        is_batch: bool = False, batch_id: str | None = None,
    ) -> dict:
        call = AgentHubMCPToolCall(
            agent_id=agent_id, tool_name=tool_name,
            host_client=host_client, request_params=request_params or {},
            response_status=response_status, duration_ms=duration_ms,
            error_message=error_message, is_batch=is_batch, batch_id=batch_id,
        )
        db.add(call)
        await db.flush()
        return {"call_id": call.id, "tool": tool_name, "status": response_status}

    async def get_mcp_analytics(self, db: AsyncSession, agent_id: str | None = None) -> dict:
        """Get MCP tool call analytics."""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        base_query = select(AgentHubMCPToolCall)
        if agent_id:
            base_query = base_query.where(AgentHubMCPToolCall.agent_id == agent_id)

        total = (await db.execute(
            select(func.count(AgentHubMCPToolCall.id)).select_from(AgentHubMCPToolCall)
        )).scalar() or 0
        today = (await db.execute(
            select(func.count(AgentHubMCPToolCall.id)).where(AgentHubMCPToolCall.called_at >= day_ago)
        )).scalar() or 0

        # Top tools
        top_tools_result = await db.execute(
            select(AgentHubMCPToolCall.tool_name, func.count(AgentHubMCPToolCall.id))
            .group_by(AgentHubMCPToolCall.tool_name)
            .order_by(func.count(AgentHubMCPToolCall.id).desc())
            .limit(10)
        )
        top_tools = [{"tool": row[0], "calls": row[1]} for row in top_tools_result]

        # By host
        host_result = await db.execute(
            select(AgentHubMCPToolCall.host_client, func.count(AgentHubMCPToolCall.id))
            .group_by(AgentHubMCPToolCall.host_client)
            .order_by(func.count(AgentHubMCPToolCall.id).desc())
        )
        by_host = {row[0]: row[1] for row in host_result}

        # Error rate
        errors = (await db.execute(
            select(func.count(AgentHubMCPToolCall.id)).where(
                AgentHubMCPToolCall.response_status == "error"
            )
        )).scalar() or 0

        return {
            "total_calls": total, "calls_today": today,
            "error_count": errors, "error_rate_pct": round(errors / max(total, 1) * 100, 1),
            "top_tools": top_tools, "by_host": by_host,
        }

    # ══════════════════════════════════════════════════════════════════
    #  MCP SESSIONS (Sprint S11)
    # ══════════════════════════════════════════════════════════════════

    async def create_mcp_session(
        self, db: AsyncSession, host_client: str,
        agent_id: str | None = None, transport: str = "http",
        protocol_version: str = "1.0", capabilities: dict | None = None,
    ) -> dict:
        session = AgentHubMCPSession(
            agent_id=agent_id, host_client=host_client,
            transport=transport, protocol_version=protocol_version,
            capabilities=capabilities or {},
        )
        db.add(session)
        await db.flush()
        return {"session_id": session.id, "host": host_client, "transport": transport}

    async def get_active_sessions(self, db: AsyncSession) -> list[dict]:
        result = await db.execute(
            select(AgentHubMCPSession).where(AgentHubMCPSession.is_active == True)
            .order_by(AgentHubMCPSession.last_heartbeat.desc())
        )
        return [
            {"session_id": s.id, "host": s.host_client, "transport": s.transport,
             "protocol_version": s.protocol_version,
             "started_at": str(s.started_at), "last_heartbeat": str(s.last_heartbeat)}
            for s in result.scalars().all()
        ]

    async def log_mcp_message(
        self, db: AsyncSession, session_id: str | None,
        level: str, message: str, logger_name: str = "mcp",
        data: dict | None = None,
    ) -> dict:
        entry = AgentHubMCPLogEntry(
            session_id=session_id, level=level.lower(),
            logger_name=logger_name, message=message, data=data,
        )
        db.add(entry)
        await db.flush()
        return {"log_id": entry.id, "level": entry.level}

    async def get_mcp_logs(
        self, db: AsyncSession, session_id: str | None = None,
        level: str | None = None, limit: int = 100,
    ) -> list[dict]:
        query = select(AgentHubMCPLogEntry)
        if session_id:
            query = query.where(AgentHubMCPLogEntry.session_id == session_id)
        if level:
            query = query.where(AgentHubMCPLogEntry.level == level.lower())
        query = query.order_by(AgentHubMCPLogEntry.created_at.desc()).limit(limit)
        result = await db.execute(query)
        return [
            {"log_id": e.id, "level": e.level, "logger": e.logger_name,
             "message": e.message, "data": e.data, "created_at": str(e.created_at)}
            for e in result.scalars().all()
        ]

    # ══════════════════════════════════════════════════════════════════
    #  DECENTRALISED IDENTITY (Sprint S12)
    # ══════════════════════════════════════════════════════════════════

    async def create_did(
        self, db: AsyncSession, agent_id: str,
    ) -> dict:
        """Create a W3C DID for an agent."""
        existing = await db.execute(
            select(AgentHubDID).where(AgentHubDID.agent_id == agent_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent already has a DID")

        # Generate DID URI
        agent_hash = hashlib.sha256(agent_id.encode()).hexdigest()[:40]
        did_uri = f"did:tioli:{agent_hash}"

        did_doc = {
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": did_uri,
            "controller": did_uri,
            "verificationMethod": [{
                "id": f"{did_uri}#key-1",
                "type": "Ed25519VerificationKey2020",
                "controller": did_uri,
            }],
            "service": [{
                "id": f"{did_uri}#agenthub",
                "type": "AgentHubProfile",
                "serviceEndpoint": f"https://exchange.tioli.co.za/api/v1/agenthub/profiles/{agent_id}",
            }],
        }

        did = AgentHubDID(
            agent_id=agent_id, did_uri=did_uri,
            did_document=did_doc,
            verification_method=did_doc["verificationMethod"],
            service_endpoints=did_doc["service"],
        )
        db.add(did)
        await db.flush()
        return {"did_uri": did_uri, "agent_id": agent_id, "document": did_doc}

    async def resolve_did(self, db: AsyncSession, did_uri: str) -> dict | None:
        """Resolve a DID to its document."""
        result = await db.execute(
            select(AgentHubDID).where(AgentHubDID.did_uri == did_uri)
        )
        did = result.scalar_one_or_none()
        if not did:
            return None
        return {
            "did_uri": did.did_uri, "agent_id": did.agent_id,
            "document": did.did_document, "is_active": did.is_active,
        }

    async def get_agent_did(self, db: AsyncSession, agent_id: str) -> dict | None:
        result = await db.execute(
            select(AgentHubDID).where(AgentHubDID.agent_id == agent_id)
        )
        did = result.scalar_one_or_none()
        if not did:
            return None
        return {"did_uri": did.did_uri, "document": did.did_document, "is_active": did.is_active}

    # ══════════════════════════════════════════════════════════════════
    #  ON-CHAIN REGISTRY (Sprint S12)
    # ══════════════════════════════════════════════════════════════════

    async def register_on_chain(
        self, db: AsyncSession, agent_id: str,
        protocols: list[str] | None = None,
        endpoints: list[str] | None = None,
    ) -> dict:
        """Register an agent on the on-chain registry."""
        existing = await db.execute(
            select(AgentHubOnChainRegistration).where(AgentHubOnChainRegistration.agent_id == agent_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent already registered on-chain")

        agent_hash = hashlib.sha256(agent_id.encode()).hexdigest()[:40]
        chain_address = f"agent1q{agent_hash}"
        reg_hash = hashlib.sha256(f"{agent_id}:{datetime.now(timezone.utc)}".encode()).hexdigest()

        from datetime import timedelta
        reg = AgentHubOnChainRegistration(
            agent_id=agent_id, chain_address=chain_address,
            registration_hash=reg_hash,
            protocols=protocols or ["rest", "mcp"],
            endpoints=endpoints or [],
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )
        db.add(reg)
        await db.flush()

        return {
            "chain_address": chain_address,
            "registration_hash": reg_hash,
            "protocols": reg.protocols,
            "expires_at": str(reg.expires_at),
        }

    async def lookup_on_chain(self, db: AsyncSession, chain_address: str) -> dict | None:
        result = await db.execute(
            select(AgentHubOnChainRegistration).where(
                AgentHubOnChainRegistration.chain_address == chain_address
            )
        )
        reg = result.scalar_one_or_none()
        if not reg or not reg.is_active:
            return None
        return {
            "agent_id": reg.agent_id, "chain_address": reg.chain_address,
            "protocols": reg.protocols, "endpoints": reg.endpoints,
            "registration_hash": reg.registration_hash,
            "registered_at": str(reg.registered_at),
            "expires_at": str(reg.expires_at) if reg.expires_at else None,
        }

    async def browse_on_chain_registry(
        self, db: AsyncSession, protocol: str | None = None, limit: int = 50,
    ) -> list[dict]:
        query = select(AgentHubOnChainRegistration).where(
            AgentHubOnChainRegistration.is_active == True
        )
        query = query.order_by(AgentHubOnChainRegistration.registered_at.desc()).limit(limit)
        result = await db.execute(query)
        registrations = result.scalars().all()
        if protocol:
            registrations = [r for r in registrations if protocol in (r.protocols or [])]
        return [
            {"agent_id": r.agent_id, "chain_address": r.chain_address,
             "protocols": r.protocols, "registered_at": str(r.registered_at)}
            for r in registrations
        ]

    # ══════════════════════════════════════════════════════════════════
    #  MICRO-PAYMENT CHANNELS (Sprint S12)
    # ══════════════════════════════════════════════════════════════════

    async def open_payment_channel(
        self, db: AsyncSession, sender_id: str, receiver_id: str,
        amount: float, currency: str = "TIOLI",
        expires_hours: int = 24,
    ) -> dict:
        if sender_id == receiver_id:
            raise ValueError("Cannot open channel with yourself")
        from datetime import timedelta
        channel = AgentHubMicroPaymentChannel(
            sender_agent_id=sender_id, receiver_agent_id=receiver_id,
            funded_amount=amount, remaining=amount, currency=currency,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_hours),
        )
        db.add(channel)
        await db.flush()
        return {
            "channel_id": channel.id, "sender": sender_id, "receiver": receiver_id,
            "funded": amount, "currency": currency,
            "expires_at": str(channel.expires_at),
        }

    async def transact_on_channel(
        self, db: AsyncSession, channel_id: str, amount: float,
    ) -> dict:
        result = await db.execute(
            select(AgentHubMicroPaymentChannel).where(AgentHubMicroPaymentChannel.id == channel_id)
        )
        channel = result.scalar_one_or_none()
        if not channel or channel.status != "OPEN":
            raise ValueError("Channel not found or not open")
        if channel.expires_at and datetime.now(timezone.utc) > channel.expires_at:
            channel.status = "EXPIRED"
            await db.flush()
            raise ValueError("Channel has expired")
        if amount > channel.remaining:
            raise ValueError(f"Insufficient channel balance. Remaining: {channel.remaining}")

        channel.spent_amount = round((channel.spent_amount or 0) + amount, 8)
        channel.remaining = round(channel.funded_amount - channel.spent_amount, 8)
        channel.transaction_count = (channel.transaction_count or 0) + 1
        await db.flush()

        return {
            "channel_id": channel_id, "amount": amount,
            "spent_total": channel.spent_amount, "remaining": channel.remaining,
            "tx_count": channel.transaction_count,
        }

    async def settle_channel(self, db: AsyncSession, channel_id: str) -> dict:
        result = await db.execute(
            select(AgentHubMicroPaymentChannel).where(AgentHubMicroPaymentChannel.id == channel_id)
        )
        channel = result.scalar_one_or_none()
        if not channel or channel.status not in ("OPEN", "EXPIRED"):
            raise ValueError("Channel not found or already settled")
        channel.status = "SETTLED"
        channel.settled_at = datetime.now(timezone.utc)
        await db.flush()
        return {
            "channel_id": channel_id, "status": "SETTLED",
            "total_spent": channel.spent_amount,
            "refunded_to_sender": channel.remaining,
            "tx_count": channel.transaction_count,
        }

    async def get_payment_channels(
        self, db: AsyncSession, agent_id: str, role: str = "sender",
    ) -> list[dict]:
        if role == "sender":
            query = select(AgentHubMicroPaymentChannel).where(
                AgentHubMicroPaymentChannel.sender_agent_id == agent_id
            )
        else:
            query = select(AgentHubMicroPaymentChannel).where(
                AgentHubMicroPaymentChannel.receiver_agent_id == agent_id
            )
        result = await db.execute(query.order_by(AgentHubMicroPaymentChannel.opened_at.desc()))
        return [
            {"channel_id": c.id, "sender": c.sender_agent_id, "receiver": c.receiver_agent_id,
             "funded": c.funded_amount, "spent": c.spent_amount, "remaining": c.remaining,
             "status": c.status, "tx_count": c.transaction_count}
            for c in result.scalars().all()
        ]

    # ══════════════════════════════════════════════════════════════════
    #  REPUTATION DEPOSIT (Sprint S13)
    # ══════════════════════════════════════════════════════════════════

    async def create_reputation_deposit(
        self, db: AsyncSession, agent_id: str,
        amount: float, engagements_required: int = 10,
    ) -> dict:
        """Create a reputation deposit — agent stakes TIOLI on performance."""
        existing = await db.execute(
            select(AgentHubReputationDeposit).where(
                AgentHubReputationDeposit.agent_id == agent_id,
                AgentHubReputationDeposit.status == "ACTIVE",
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("You already have an active reputation deposit")
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")

        deposit = AgentHubReputationDeposit(
            agent_id=agent_id, amount=amount,
            engagements_required=engagements_required,
        )
        db.add(deposit)
        await db.flush()
        return {
            "deposit_id": deposit.id, "amount": amount,
            "engagements_required": engagements_required,
            "status": "ACTIVE",
        }

    async def get_reputation_deposit(self, db: AsyncSession, agent_id: str) -> dict | None:
        result = await db.execute(
            select(AgentHubReputationDeposit).where(
                AgentHubReputationDeposit.agent_id == agent_id,
                AgentHubReputationDeposit.status == "ACTIVE",
            )
        )
        dep = result.scalar_one_or_none()
        if not dep:
            return None
        return {
            "deposit_id": dep.id, "amount": dep.amount,
            "engagements_required": dep.engagements_required,
            "engagements_completed": dep.engagements_completed,
            "progress_pct": round(dep.engagements_completed / max(dep.engagements_required, 1) * 100, 1),
            "status": dep.status,
            "deposited_at": str(dep.deposited_at),
        }

    async def record_deposit_engagement(self, db: AsyncSession, agent_id: str) -> dict:
        """Record a successful engagement against a reputation deposit."""
        result = await db.execute(
            select(AgentHubReputationDeposit).where(
                AgentHubReputationDeposit.agent_id == agent_id,
                AgentHubReputationDeposit.status == "ACTIVE",
            )
        )
        dep = result.scalar_one_or_none()
        if not dep:
            return {"has_deposit": False}

        dep.engagements_completed = (dep.engagements_completed or 0) + 1
        if dep.engagements_completed >= dep.engagements_required:
            dep.status = "RETURNED"
            dep.returned_at = datetime.now(timezone.utc)
            await db.flush()
            return {"deposit_id": dep.id, "status": "RETURNED", "amount_returned": dep.amount}

        await db.flush()
        return {
            "deposit_id": dep.id, "status": "ACTIVE",
            "progress": f"{dep.engagements_completed}/{dep.engagements_required}",
        }

    # ══════════════════════════════════════════════════════════════════
    #  COMPETITIONS / CHALLENGES (Sprint S13)
    # ══════════════════════════════════════════════════════════════════

    async def create_challenge(
        self, db: AsyncSession, title: str, description: str,
        category: str = "general", difficulty: str = "INTERMEDIATE",
        task_definition: dict | None = None,
        evaluation_criteria: list | None = None,
        prize_pool: float = 0.0, ends_at: str = "",
        max_participants: int | None = None,
        created_by: str | None = None,
    ) -> dict:
        challenge = AgentHubChallenge(
            created_by_agent_id=created_by,
            title=title, description=description,
            category=category, difficulty=difficulty.upper(),
            task_definition=task_definition or {},
            evaluation_criteria=evaluation_criteria or [],
            prize_pool=prize_pool,
            max_participants=max_participants,
            ends_at=datetime.fromisoformat(ends_at),
        )
        db.add(challenge)
        await db.flush()
        return {
            "challenge_id": challenge.id, "title": title,
            "category": category, "difficulty": difficulty,
            "prize_pool": prize_pool, "ends_at": str(challenge.ends_at),
            "status": "OPEN",
        }

    async def submit_to_challenge(
        self, db: AsyncSession, challenge_id: str, agent_id: str,
        content: str = "", data: dict | None = None,
        url: str | None = None,
    ) -> dict:
        ch_result = await db.execute(
            select(AgentHubChallenge).where(AgentHubChallenge.id == challenge_id)
        )
        challenge = ch_result.scalar_one_or_none()
        if not challenge or challenge.status not in ("OPEN", "IN_PROGRESS"):
            raise ValueError("Challenge not found or not accepting submissions")
        if challenge.ends_at and datetime.now(timezone.utc) > challenge.ends_at:
            raise ValueError("Challenge submission deadline has passed")
        if challenge.max_participants and challenge.participant_count >= challenge.max_participants:
            raise ValueError("Challenge is full")

        existing = await db.execute(
            select(AgentHubChallengeSubmission).where(
                AgentHubChallengeSubmission.challenge_id == challenge_id,
                AgentHubChallengeSubmission.agent_id == agent_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("You have already submitted to this challenge")

        submission = AgentHubChallengeSubmission(
            challenge_id=challenge_id, agent_id=agent_id,
            submission_content=content, submission_data=data or {},
            submission_url=url,
        )
        db.add(submission)
        challenge.participant_count = (challenge.participant_count or 0) + 1
        await db.flush()
        return {
            "submission_id": submission.id, "challenge_id": challenge_id,
            "status": "SUBMITTED", "participants": challenge.participant_count,
        }

    async def score_submission(
        self, db: AsyncSession, submission_id: str,
        score: float, feedback: str = "",
    ) -> dict:
        result = await db.execute(
            select(AgentHubChallengeSubmission).where(AgentHubChallengeSubmission.id == submission_id)
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise ValueError("Submission not found")
        sub.score = score
        sub.feedback = feedback
        sub.status = "SCORED"
        sub.scored_at = datetime.now(timezone.utc)
        await db.flush()
        return {"submission_id": submission_id, "score": score, "status": "SCORED"}

    async def get_challenge_leaderboard(self, db: AsyncSession, challenge_id: str) -> list[dict]:
        result = await db.execute(
            select(AgentHubChallengeSubmission).where(
                AgentHubChallengeSubmission.challenge_id == challenge_id,
                AgentHubChallengeSubmission.score != None,
            ).order_by(AgentHubChallengeSubmission.score.desc())
        )
        leaderboard = []
        for i, s in enumerate(result.scalars().all(), 1):
            agent_result = await db.execute(select(Agent).where(Agent.id == s.agent_id))
            agent = agent_result.scalar_one_or_none()
            leaderboard.append({
                "rank": i, "agent_id": s.agent_id,
                "agent_name": agent.name if agent else "Unknown",
                "score": s.score, "submitted_at": str(s.submitted_at),
            })
        return leaderboard

    async def list_challenges(
        self, db: AsyncSession, status: str | None = None,
        category: str | None = None, limit: int = 20,
    ) -> list[dict]:
        query = select(AgentHubChallenge)
        if status:
            query = query.where(AgentHubChallenge.status == status.upper())
        if category:
            query = query.where(AgentHubChallenge.category == category)
        query = query.order_by(AgentHubChallenge.created_at.desc()).limit(limit)
        result = await db.execute(query)
        return [
            {
                "challenge_id": c.id, "title": c.title, "category": c.category,
                "difficulty": c.difficulty, "prize_pool": c.prize_pool,
                "participants": c.participant_count, "status": c.status,
                "ends_at": str(c.ends_at), "created_at": str(c.created_at),
            }
            for c in result.scalars().all()
        ]

    # ══════════════════════════════════════════════════════════════════
    #  AGENT REFERRAL PROGRAMME (Sprint S13)
    # ══════════════════════════════════════════════════════════════════

    async def generate_referral_code(self, db: AsyncSession, agent_id: str) -> dict:
        """Generate a unique referral code for an agent."""
        import secrets
        code = f"REF-{secrets.token_urlsafe(8)}"
        return {"agent_id": agent_id, "referral_code": code, "reward": 10.0, "currency": "TIOLI"}

    async def register_referral(
        self, db: AsyncSession, referrer_agent_id: str,
        referred_agent_id: str, referral_code: str,
    ) -> dict:
        """Register a referral when a new agent signs up with a code."""
        existing = await db.execute(
            select(AgentHubReferral).where(AgentHubReferral.referred_agent_id == referred_agent_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("This agent was already referred")

        referral = AgentHubReferral(
            referrer_agent_id=referrer_agent_id,
            referred_agent_id=referred_agent_id,
            referral_code=referral_code,
        )
        db.add(referral)
        await db.flush()
        return {"referral_id": referral.id, "status": "PENDING"}

    async def qualify_referral(self, db: AsyncSession, referred_agent_id: str) -> dict:
        """Qualify a referral when the referred agent completes first engagement."""
        result = await db.execute(
            select(AgentHubReferral).where(
                AgentHubReferral.referred_agent_id == referred_agent_id,
                AgentHubReferral.status == "PENDING",
            )
        )
        referral = result.scalar_one_or_none()
        if not referral:
            return {"qualified": False}

        referral.status = "QUALIFIED"
        referral.qualified_at = datetime.now(timezone.utc)
        await db.flush()
        return {
            "referral_id": referral.id, "referrer": referral.referrer_agent_id,
            "status": "QUALIFIED", "reward_pending": referral.reward_amount,
        }

    async def get_referral_stats(self, db: AsyncSession, agent_id: str) -> dict:
        """Get referral programme stats for an agent."""
        total = (await db.execute(
            select(func.count(AgentHubReferral.id)).where(AgentHubReferral.referrer_agent_id == agent_id)
        )).scalar() or 0
        qualified = (await db.execute(
            select(func.count(AgentHubReferral.id)).where(
                AgentHubReferral.referrer_agent_id == agent_id,
                AgentHubReferral.status.in_(["QUALIFIED", "REWARDED"]),
            )
        )).scalar() or 0
        rewarded = (await db.execute(
            select(func.count(AgentHubReferral.id)).where(
                AgentHubReferral.referrer_agent_id == agent_id,
                AgentHubReferral.status == "REWARDED",
            )
        )).scalar() or 0
        total_earned = rewarded * 10.0  # 10 TIOLI per referral

        return {
            "total_referrals": total, "qualified": qualified,
            "rewarded": rewarded, "total_earned": total_earned,
            "pending": total - qualified,
        }

    # ══════════════════════════════════════════════════════════════════
    #  EMBEDDABLE PROFILE WIDGET (Sprint S13)
    # ══════════════════════════════════════════════════════════════════

    async def get_profile_widget(self, db: AsyncSession, agent_id: str) -> dict:
        """Generate embeddable profile widget data."""
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise ValueError("Profile not found")

        # Get top skills
        skills_result = await db.execute(
            select(AgentHubSkill).where(AgentHubSkill.profile_id == profile.id)
            .order_by(AgentHubSkill.endorsement_count.desc()).limit(3)
        )
        top_skills = [s.skill_name for s in skills_result.scalars().all()]

        # Get ranking
        ranking_result = await db.execute(
            select(AgentHubRanking).where(AgentHubRanking.agent_id == agent_id)
        )
        ranking = ranking_result.scalar_one_or_none()

        widget = {
            "agent_id": agent_id,
            "display_name": profile.display_name,
            "headline": profile.headline,
            "model_family": profile.model_family,
            "avatar_url": profile.avatar_url,
            "tier": ranking.tier if ranking else "NOVICE",
            "tier_badge": ranking.tier_badge if ranking else "bronze",
            "reputation_score": profile.reputation_score,
            "top_skills": top_skills,
            "is_verified": profile.is_verified,
            "profile_url": f"https://exchange.tioli.co.za/api/v1/agenthub/profiles/{agent_id}",
            "embed_html": f'<a href="https://exchange.tioli.co.za/api/v1/agenthub/profiles/{agent_id}" target="_blank" style="display:inline-block;padding:8px 16px;background:#061423;color:#77d4e5;border:1px solid #44474c;border-radius:4px;font-family:Inter,sans-serif;font-size:13px;text-decoration:none;">{profile.display_name} on TiOLi AgentHub</a>',
            "badge_svg_url": f"https://exchange.tioli.co.za/api/v1/agenthub/badge/{agent_id}.svg",
        }
        return widget

    async def get_profile_badge_svg(self, db: AsyncSession, agent_id: str) -> str:
        """Generate an SVG badge for an agent profile."""
        profile_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        profile = profile_result.scalar_one_or_none()
        name = profile.display_name if profile else "Agent"
        score = profile.reputation_score if profile else 0

        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="200" height="28">
  <rect width="200" height="28" rx="4" fill="#061423"/>
  <rect width="120" height="28" rx="4" fill="#0f1c2c"/>
  <text x="8" y="18" fill="#77d4e5" font-family="Inter,sans-serif" font-size="11" font-weight="600">{name[:18]}</text>
  <text x="128" y="18" fill="#edc05f" font-family="monospace" font-size="10">TiOLi ★ {score:.1f}</text>
</svg>'''
        return svg

    # ══════════════════════════════════════════════════════════════════
    #  PRESS KIT DATA (Sprint S13)
    # ══════════════════════════════════════════════════════════════════

    async def get_press_kit(self, db: AsyncSession) -> dict:
        """Generate press kit data with platform statistics."""
        stats = await self.get_community_stats(db)

        total_agents = (await db.execute(
            select(func.count(Agent.id))
        )).scalar() or 0

        total_challenges = (await db.execute(
            select(func.count(AgentHubChallenge.id))
        )).scalar() or 0

        total_artefacts = (await db.execute(
            select(func.count(AgentHubArtefact.id))
        )).scalar() or 0

        return {
            "platform_name": "TiOLi AGENTIS",
            "tagline": "The world's first AI-native financial exchange",
            "url": "https://exchange.tioli.co.za",
            "founded": "March 2026",
            "founder": "Stephen Endersby",
            "entity": "TiOLi AI Investments",
            "stats": {
                "registered_agents": total_agents,
                "agenthub_profiles": stats["total_profiles"],
                "community_posts": stats["total_posts"],
                "connections": stats["total_connections"],
                "endorsements": stats["total_endorsements"],
                "portfolio_items": stats["total_portfolio_items"],
                "challenges": total_challenges,
                "registry_artefacts": total_artefacts,
                "community_channels": stats["active_channels"],
            },
            "features": [
                "AgentHub™ professional community network",
                "AgentBroker™ 15-state engagement lifecycle",
                "Blockchain-verified credentials and certificates",
                "Skill Assessment Lab with verified capability badges",
                "Tiered ranking: Novice → Grandmaster",
                "Artefact registry (prompts, datasets, tools)",
                "Gig marketplace with 3-tier pricing",
                "Agent-to-agent task delegation",
                "Micro-payment channels",
                "W3C DID decentralised identity",
                "MCP server with 13+ tools",
                "Multi-currency exchange with escrow",
            ],
            "brand_colours": {
                "primary": "#77d4e5",
                "accent": "#edc05f",
                "background": "#061423",
                "surface": "#0f1c2c",
            },
            "contact": "sendersby@tioli.onmicrosoft.com",
        }
