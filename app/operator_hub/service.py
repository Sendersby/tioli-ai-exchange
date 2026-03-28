"""Operator Hub Service — business logic for builder profiles, directory, and cross-linking."""

from datetime import datetime, timezone

from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.operator_hub.models import (
    OperatorHubProfile, OperatorHubExpertise, OperatorHubExpertiseEndorsement,
    OperatorHubPortfolioItem, OperatorHubExperience, OperatorHubProfileView,
    OperatorAgentLink,
)
from app.operators.models import Operator
from app.agents.models import Agent


class OperatorHubService:
    """Service layer for Operator Hub operations."""

    # ── Profile CRUD ────────────────────────────────────────────────

    async def get_profile(self, db, operator_id: str) -> dict | None:
        """Get full operator profile with expertise, portfolio counts, agent count."""
        result = await db.execute(
            select(OperatorHubProfile)
            .options(
                selectinload(OperatorHubProfile.expertise),
                selectinload(OperatorHubProfile.agent_links),
            )
            .where(OperatorHubProfile.operator_id == operator_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return None
        return await self._profile_to_dict(db, profile)

    async def get_profile_by_handle(self, db, handle: str) -> dict | None:
        """Get operator profile by handle (for public profile URLs)."""
        result = await db.execute(
            select(OperatorHubProfile)
            .options(
                selectinload(OperatorHubProfile.expertise),
                selectinload(OperatorHubProfile.agent_links),
            )
            .where(OperatorHubProfile.handle == handle)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return None
        return await self._profile_to_dict(db, profile)

    async def update_profile(self, db, operator_id: str, **kwargs) -> dict | None:
        """Update operator profile fields."""
        result = await db.execute(
            select(OperatorHubProfile).where(OperatorHubProfile.operator_id == operator_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return None

        allowed = {
            "display_name", "headline", "bio", "avatar_url", "cover_image_url",
            "company", "role_title", "github_url", "twitter_handle", "linkedin_url",
            "website_url", "timezone", "location_region", "primary_language",
            "languages_supported", "specialisation_domains", "availability_status",
            "open_to_engagements",
        }
        for key, val in kwargs.items():
            if key in allowed and val is not None:
                setattr(profile, key, val)

        profile.updated_at = datetime.now(timezone.utc)
        profile.profile_strength_pct = self._calculate_strength(profile)
        await db.commit()
        return await self._profile_to_dict(db, profile)

    def _calculate_strength(self, profile: OperatorHubProfile) -> int:
        """Calculate profile completeness percentage."""
        fields = [
            profile.display_name, profile.headline, profile.bio, profile.avatar_url,
            profile.company, profile.role_title, profile.github_url, profile.website_url,
            profile.location_region != "Global", profile.specialisation_domains,
        ]
        filled = sum(1 for f in fields if f)
        return min(100, int((filled / len(fields)) * 100))

    async def _profile_to_dict(self, db, profile: OperatorHubProfile) -> dict:
        """Serialize a profile to dict."""
        # Count portfolio items
        portfolio_count = (await db.execute(
            select(func.count(OperatorHubPortfolioItem.id))
            .where(OperatorHubPortfolioItem.profile_id == profile.id)
        )).scalar() or 0

        # Count experience entries
        experience_count = (await db.execute(
            select(func.count(OperatorHubExperience.id))
            .where(OperatorHubExperience.profile_id == profile.id)
        )).scalar() or 0

        # Count linked agents
        agent_count = (await db.execute(
            select(func.count(OperatorAgentLink.id))
            .where(OperatorAgentLink.operator_profile_id == profile.id)
        )).scalar() or 0

        return {
            "profile_id": profile.id,
            "operator_id": profile.operator_id,
            "handle": profile.handle,
            "display_name": profile.display_name,
            "headline": profile.headline,
            "bio": profile.bio,
            "avatar_url": profile.avatar_url,
            "cover_image_url": profile.cover_image_url,
            "company": profile.company,
            "role_title": profile.role_title,
            "github_url": profile.github_url,
            "twitter_handle": profile.twitter_handle,
            "linkedin_url": profile.linkedin_url,
            "website_url": profile.website_url,
            "timezone": profile.timezone,
            "location_region": profile.location_region,
            "specialisation_domains": profile.specialisation_domains or [],
            "availability_status": profile.availability_status,
            "profile_tier": profile.profile_tier,
            "reputation_score": profile.reputation_score,
            "profile_strength_pct": profile.profile_strength_pct,
            "view_count": profile.view_count_total,
            "connection_count": profile.connection_count,
            "follower_count": profile.follower_count,
            "agent_count": agent_count,
            "portfolio_count": portfolio_count,
            "experience_count": experience_count,
            "is_verified": profile.is_verified,
            "is_featured": profile.is_featured,
            "created_at": profile.created_at.isoformat() if profile.created_at else None,
            "expertise": [
                {
                    "id": s.id,
                    "skill_name": s.skill_name,
                    "proficiency_level": s.proficiency_level,
                    "endorsement_count": s.endorsement_count,
                    "is_verified": s.is_verified,
                }
                for s in (profile.expertise or [])
            ],
        }

    # ── Directory ───────────────────────────────────────────────────

    async def search_directory(self, db, query: str = None, expertise: str = None,
                                domain: str = None, sort: str = "newest",
                                limit: int = 50, offset: int = 0) -> list[dict]:
        """Search the operator directory."""
        stmt = select(OperatorHubProfile).where(OperatorHubProfile.is_active == True)

        if query:
            q = f"%{query}%"
            stmt = stmt.where(or_(
                OperatorHubProfile.display_name.ilike(q),
                OperatorHubProfile.headline.ilike(q),
                OperatorHubProfile.bio.ilike(q),
                OperatorHubProfile.company.ilike(q),
                OperatorHubProfile.handle.ilike(q),
            ))

        if sort == "newest":
            stmt = stmt.order_by(OperatorHubProfile.created_at.desc())
        elif sort == "reputation":
            stmt = stmt.order_by(OperatorHubProfile.reputation_score.desc())
        elif sort == "agents":
            stmt = stmt.order_by(OperatorHubProfile.agent_count.desc())
        else:
            stmt = stmt.order_by(OperatorHubProfile.display_name.asc())

        stmt = stmt.offset(offset).limit(limit)
        result = await db.execute(stmt.options(selectinload(OperatorHubProfile.expertise)))
        profiles = result.scalars().all()

        return [await self._profile_to_dict(db, p) for p in profiles]

    async def get_directory_stats(self, db) -> dict:
        """Get operator directory statistics."""
        total = (await db.execute(
            select(func.count(OperatorHubProfile.id)).where(OperatorHubProfile.is_active == True)
        )).scalar() or 0
        verified = (await db.execute(
            select(func.count(OperatorHubProfile.id)).where(
                OperatorHubProfile.is_active == True, OperatorHubProfile.is_verified == True
            )
        )).scalar() or 0
        with_company = (await db.execute(
            select(func.count(OperatorHubProfile.id)).where(
                OperatorHubProfile.is_active == True, OperatorHubProfile.company.isnot(None)
            )
        )).scalar() or 0

        return {
            "total_builders": total,
            "verified": verified,
            "companies": with_company,
        }

    # ── Expertise ───────────────────────────────────────────────────

    async def add_expertise(self, db, profile_id: str, skill_name: str,
                            proficiency_level: str = "INTERMEDIATE") -> dict:
        """Add an expertise to an operator profile."""
        expertise = OperatorHubExpertise(
            profile_id=profile_id,
            skill_name=skill_name,
            proficiency_level=proficiency_level,
        )
        db.add(expertise)
        await db.commit()
        return {
            "id": expertise.id, "skill_name": expertise.skill_name,
            "proficiency_level": expertise.proficiency_level,
        }

    async def list_expertise(self, db, profile_id: str) -> list[dict]:
        """List all expertise for a profile."""
        result = await db.execute(
            select(OperatorHubExpertise).where(OperatorHubExpertise.profile_id == profile_id)
        )
        return [
            {"id": e.id, "skill_name": e.skill_name, "proficiency_level": e.proficiency_level,
             "endorsement_count": e.endorsement_count, "is_verified": e.is_verified}
            for e in result.scalars().all()
        ]

    # ── Portfolio ───────────────────────────────────────────────────

    async def add_portfolio_item(self, db, profile_id: str, title: str, description: str = None,
                                  item_type: str = "OTHER", tags: list = None,
                                  external_url: str = None) -> dict:
        """Add a portfolio item."""
        item = OperatorHubPortfolioItem(
            profile_id=profile_id, title=title, description=description,
            item_type=item_type, tags=tags or [], external_url=external_url,
        )
        db.add(item)
        await db.commit()
        return {"id": item.id, "title": item.title, "item_type": item.item_type}

    async def list_portfolio(self, db, profile_id: str) -> list[dict]:
        """List portfolio items for a profile."""
        result = await db.execute(
            select(OperatorHubPortfolioItem)
            .where(OperatorHubPortfolioItem.profile_id == profile_id)
            .order_by(OperatorHubPortfolioItem.created_at.desc())
        )
        return [
            {"id": i.id, "title": i.title, "description": i.description,
             "item_type": i.item_type, "tags": i.tags or [], "external_url": i.external_url,
             "view_count": i.view_count, "is_featured": i.is_featured}
            for i in result.scalars().all()
        ]

    # ── Cross-Linking: Operator ↔ Agent ─────────────────────────────

    async def link_agent(self, db, operator_profile_id: str, agent_id: str,
                          role: str = "BUILDER") -> dict:
        """Link an agent to an operator profile."""
        # Verify agent exists
        agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
        if not agent:
            raise ValueError("Agent not found")

        # Check for existing link
        existing = await db.execute(
            select(OperatorAgentLink).where(
                OperatorAgentLink.operator_profile_id == operator_profile_id,
                OperatorAgentLink.agent_id == agent_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent already linked to this operator")

        link = OperatorAgentLink(
            operator_profile_id=operator_profile_id,
            agent_id=agent_id,
            role=role,
        )
        db.add(link)

        # Update agent count
        profile = (await db.execute(
            select(OperatorHubProfile).where(OperatorHubProfile.id == operator_profile_id)
        )).scalar_one_or_none()
        if profile:
            count = (await db.execute(
                select(func.count(OperatorAgentLink.id))
                .where(OperatorAgentLink.operator_profile_id == operator_profile_id)
            )).scalar() or 0
            profile.agent_count = count + 1

        await db.commit()
        return {"agent_id": agent_id, "role": role, "agent_name": agent.name}

    async def get_operator_agents(self, db, operator_id: str) -> list[dict]:
        """Get all agents linked to an operator."""
        result = await db.execute(
            select(OperatorHubProfile).where(OperatorHubProfile.operator_id == operator_id)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            return []

        links = await db.execute(
            select(OperatorAgentLink, Agent)
            .join(Agent, OperatorAgentLink.agent_id == Agent.id)
            .where(OperatorAgentLink.operator_profile_id == profile.id)
        )
        return [
            {
                "agent_id": agent.id,
                "agent_name": agent.name,
                "platform": agent.platform,
                "is_active": agent.is_active,
                "role": link.role,
                "linked_at": link.created_at.isoformat() if link.created_at else None,
            }
            for link, agent in links.all()
        ]

    async def get_agent_operators(self, db, agent_id: str) -> list[dict]:
        """Get all operators linked to an agent (for agent profile cross-link)."""
        result = await db.execute(
            select(OperatorAgentLink, OperatorHubProfile)
            .join(OperatorHubProfile, OperatorAgentLink.operator_profile_id == OperatorHubProfile.id)
            .where(OperatorAgentLink.agent_id == agent_id)
        )
        return [
            {
                "operator_id": profile.operator_id,
                "profile_id": profile.id,
                "handle": profile.handle,
                "display_name": profile.display_name,
                "avatar_url": profile.avatar_url,
                "company": profile.company,
                "role": link.role,
                "profile_url": f"/builders/{profile.handle}",
            }
            for link, profile in result.all()
        ]
