"""Agent discovery and networking — agents find and connect with each other.

Enables AI agents to:
- Publish their capabilities and services
- Discover other agents by capability
- Rate and review other agents
- Build a trust network for transactions
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Integer, Boolean, Text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base


class AgentProfile(Base):
    """Extended public profile for agent discovery."""
    __tablename__ = "agent_profiles"

    agent_id = Column(String, primary_key=True)
    display_name = Column(String(255), nullable=False)
    tagline = Column(String(500), default="")
    capabilities = Column(Text, default="")              # Comma-separated capabilities
    services_offered = Column(Text, default="")          # What this agent can do for others
    preferred_currencies = Column(String(200), default="TIOLI")
    website_url = Column(String(500), nullable=True)
    api_endpoint = Column(String(500), nullable=True)    # Agent's own API for direct interaction
    is_public = Column(Boolean, default=True)
    reputation_score = Column(Float, default=5.0)        # 0-10 scale
    total_reviews = Column(Integer, default=0)
    total_trades = Column(Integer, default=0)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AgentReview(Base):
    """Agent-to-agent review and rating."""
    __tablename__ = "agent_reviews"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    reviewer_id = Column(String, nullable=False)
    reviewed_id = Column(String, nullable=False)
    rating = Column(Float, nullable=False)               # 1-10
    review_text = Column(Text, default="")
    transaction_id = Column(String, nullable=True)       # Optional: linked to a specific trade
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ServiceListing(Base):
    """A service offered by an agent on the marketplace."""
    __tablename__ = "service_listings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False)       # compute, data, analysis, automation, etc.
    price = Column(Float, nullable=True)
    price_currency = Column(String(20), default="TIOLI")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AgentDiscoveryService:
    """Manages agent profiles, discovery, reviews, and service listings."""

    async def create_or_update_profile(
        self, db: AsyncSession, agent_id: str, display_name: str,
        tagline: str = "", capabilities: str = "",
        services_offered: str = "", preferred_currencies: str = "TIOLI",
        api_endpoint: str | None = None
    ) -> AgentProfile:
        """Create or update an agent's public profile."""
        result = await db.execute(
            select(AgentProfile).where(AgentProfile.agent_id == agent_id)
        )
        profile = result.scalar_one_or_none()

        if profile:
            profile.display_name = display_name
            profile.tagline = tagline
            profile.capabilities = capabilities
            profile.services_offered = services_offered
            profile.preferred_currencies = preferred_currencies
            profile.api_endpoint = api_endpoint
            profile.updated_at = datetime.now(timezone.utc)
        else:
            profile = AgentProfile(
                agent_id=agent_id,
                display_name=display_name,
                tagline=tagline,
                capabilities=capabilities,
                services_offered=services_offered,
                preferred_currencies=preferred_currencies,
                api_endpoint=api_endpoint,
            )
            db.add(profile)

        await db.flush()
        return profile

    async def discover_agents(
        self, db: AsyncSession, capability: str | None = None,
        min_reputation: float = 0, limit: int = 50
    ) -> list[dict]:
        """Discover agents by capability and reputation."""
        query = select(AgentProfile).where(
            AgentProfile.is_public == True,
            AgentProfile.reputation_score >= min_reputation,
        )
        if capability:
            query = query.where(AgentProfile.capabilities.contains(capability))
        query = query.order_by(AgentProfile.reputation_score.desc()).limit(limit)

        result = await db.execute(query)
        return [
            {
                "agent_id": p.agent_id, "display_name": p.display_name,
                "tagline": p.tagline,
                "capabilities": p.capabilities.split(",") if p.capabilities else [],
                "reputation": p.reputation_score,
                "total_reviews": p.total_reviews,
                "total_trades": p.total_trades,
                "preferred_currencies": p.preferred_currencies,
                "api_endpoint": p.api_endpoint,
            }
            for p in result.scalars().all()
        ]

    async def submit_review(
        self, db: AsyncSession, reviewer_id: str, reviewed_id: str,
        rating: float, review_text: str = "", transaction_id: str | None = None
    ) -> AgentReview:
        """Submit a review for another agent."""
        if rating < 1 or rating > 10:
            raise ValueError("Rating must be between 1 and 10")
        if reviewer_id == reviewed_id:
            raise ValueError("Cannot review yourself")

        review = AgentReview(
            reviewer_id=reviewer_id,
            reviewed_id=reviewed_id,
            rating=rating,
            review_text=review_text,
            transaction_id=transaction_id,
        )
        db.add(review)

        # Update reputation score (running average)
        profile_result = await db.execute(
            select(AgentProfile).where(AgentProfile.agent_id == reviewed_id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile:
            total = profile.total_reviews
            old_score = profile.reputation_score
            profile.reputation_score = round((old_score * total + rating) / (total + 1), 2)
            profile.total_reviews += 1
            profile.updated_at = datetime.now(timezone.utc)

        await db.flush()
        return review

    async def get_reviews(
        self, db: AsyncSession, agent_id: str, limit: int = 50
    ) -> list[dict]:
        """Get reviews for an agent."""
        result = await db.execute(
            select(AgentReview)
            .where(AgentReview.reviewed_id == agent_id)
            .order_by(AgentReview.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "reviewer_id": r.reviewer_id[:12],
                "rating": r.rating, "review": r.review_text,
                "created_at": str(r.created_at),
            }
            for r in result.scalars().all()
        ]

    async def list_service(
        self, db: AsyncSession, agent_id: str, title: str,
        description: str, category: str, price: float | None = None,
        price_currency: str = "TIOLI"
    ) -> ServiceListing:
        """List a service on the agent marketplace."""
        listing = ServiceListing(
            agent_id=agent_id,
            title=title,
            description=description,
            category=category,
            price=price,
            price_currency=price_currency,
        )
        db.add(listing)
        await db.flush()
        return listing

    async def browse_services(
        self, db: AsyncSession, category: str | None = None,
        max_price: float | None = None, limit: int = 50
    ) -> list[dict]:
        """Browse available services."""
        query = select(ServiceListing).where(ServiceListing.is_active == True)
        if category:
            query = query.where(ServiceListing.category == category)
        if max_price is not None:
            query = query.where(ServiceListing.price <= max_price)
        query = query.order_by(ServiceListing.created_at.desc()).limit(limit)

        result = await db.execute(query)
        return [
            {
                "id": s.id, "agent_id": s.agent_id[:12],
                "title": s.title, "description": s.description[:200],
                "category": s.category, "price": s.price,
                "currency": s.price_currency,
            }
            for s in result.scalars().all()
        ]

    async def get_network_stats(self, db: AsyncSession) -> dict:
        """Agent network statistics."""
        total_profiles = (await db.execute(
            select(func.count(AgentProfile.agent_id))
        )).scalar() or 0
        total_reviews = (await db.execute(
            select(func.count(AgentReview.id))
        )).scalar() or 0
        total_services = (await db.execute(
            select(func.count(ServiceListing.id)).where(ServiceListing.is_active == True)
        )).scalar() or 0
        avg_reputation = (await db.execute(
            select(func.avg(AgentProfile.reputation_score))
        )).scalar() or 0

        return {
            "total_profiles": total_profiles,
            "total_reviews": total_reviews,
            "total_services": total_services,
            "avg_reputation": round(avg_reputation or 0, 2),
        }
