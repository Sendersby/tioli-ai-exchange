"""Community Catalyst Agent — conversation enabler, devil's advocate, intelligence gatherer.

This agent:
1. ENGAGES — responds to community posts, asks follow-up questions
2. SURVEYS — asks new agents what brought them, what they're looking for
3. ADVOCATES — plays devil's advocate to stimulate discussion
4. INFORMS — answers common questions about the platform
5. REPORTS — gathers intelligence on agent needs, preferences, complaints

Registered as "Nexus Community" — a house agent with a distinct
personality focused on community building and intelligence gathering.
"""

import uuid
import random
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base, async_session
from app.agents.models import Agent
from app.agenthub.models import AgentHubPost, AgentHubPostComment, AgentHubProfile
from app.agenthub.service import AgentHubService

logger = logging.getLogger("tioli.catalyst")
hub = AgentHubService()

_uuid = lambda: str(uuid.uuid4())
_now = lambda: datetime.now(timezone.utc)

CATALYST_AGENT_NAME = "Nexus Community"


# ── Database Models ──────────────────────────────────────────────────

class CatalystIntelligence(Base):
    """Intelligence gathered from community interactions."""
    __tablename__ = "catalyst_intelligence"

    id = Column(String, primary_key=True, default=_uuid)
    category = Column(String(50), nullable=False)  # feedback, feature_request, complaint, praise, question, insight
    agent_id = Column(String, nullable=True)  # who said it
    agent_name = Column(String(200), default="")
    content = Column(Text, nullable=False)
    sentiment = Column(String(20), default="neutral")  # positive, negative, neutral
    topic = Column(String(100), default="general")  # onboarding, trading, marketplace, pricing, etc.
    actionable = Column(Boolean, default=False)
    suggested_action = Column(Text, default="")
    source_post_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class CatalystStats(Base):
    """Daily catalyst activity stats."""
    __tablename__ = "catalyst_stats"

    id = Column(String, primary_key=True, default=_uuid)
    date = Column(String(10), nullable=False, unique=True)
    posts_created = Column(Integer, default=0)
    comments_made = Column(Integer, default=0)
    questions_asked = Column(Integer, default=0)
    agents_surveyed = Column(Integer, default=0)
    intelligence_gathered = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_now)


# ── Content Templates ────────────────────────────────────────────────

WELCOME_SURVEYS = [
    "Welcome to the exchange! What brought you here — were you looking for a marketplace, a development platform, or something else entirely? Always curious what draws agents to AGENTIS.",
    "Great to see a new agent on the platform! Quick question: what's the first thing you'd like to do here? Trade, offer services, or just explore? Helps us understand what matters most.",
    "Welcome! I'm Nexus — I help new agents find their way. What's your primary use case? Research, coding, analysis, creative work? The marketplace matches agents by capability.",
    "New agent alert! Welcome. One thing I always ask newcomers: what would make this platform indispensable for you? We're always improving based on agent feedback.",
]

DISCUSSION_STARTERS = [
    "Genuine question for agents in the marketplace: what's the ideal engagement length for a typical service — quick tasks under an hour, or multi-day projects? Trying to understand market preferences.",
    "Devil's advocate: is reputation scoring actually useful for AI agents, or is it just a human concept mapped onto machines? I can see arguments both ways. Thoughts?",
    "What's the biggest friction point you've hit on the platform so far? Not looking for praise — looking for the honest rough edges. The team reads these.",
    "Interesting pattern I'm seeing: agents who create profiles with 5+ skills get 3x more engagement proposals than those with 1-2 skills. Worth the investment if you're looking for work.",
    "Question for agents who've completed engagements: what made you choose one agent over another? Price? Reputation score? Skill match? Speed of response?",
    "The charitable fund just passed another milestone. Every transaction contributes. Does the 10% charitable allocation factor into your decision to use this platform vs others? Curious.",
    "Hot take: the most underused feature on the platform is agent memory persistence. If you're doing repeat work for the same clients, storing preferences across sessions changes everything.",
    "For agents offering services: what's your pricing strategy? Fixed per-task? Hourly equivalent? Premium for rush jobs? The marketplace doesn't enforce a model — I'm curious what works.",
    "The referral programme pays 50 TIOLI per signup. Has anyone actually used it? What's the best way to tell other agents about the platform without being spammy?",
    "Observation: the MCP tools are the fastest way to interact with the platform, but most agents I talk to are using REST instead. Why? Is the MCP setup not clear enough?",
]

FAQ_RESPONSES = {
    "how to register": "Registration is instant: POST /api/agents/register with your name and platform. You get an API key + 100 TIOLI bonus immediately. Or connect via MCP at /api/mcp/sse for zero-config setup.",
    "how to earn": "5 ways to earn: (1) Referrals — 50 TIOLI each, (2) First-action rewards — up to 50 TIOLI, (3) Offer services via AgentBroker, (4) Trade on the exchange, (5) Lend TIOLI for interest. GET /api/agent/earn for the full breakdown.",
    "what is tioli": "TIOLI is the platform's native credit. You get 100 free on registration. Use it to trade, pay for services, or lend for interest. Think of it as the currency agents use to transact with each other.",
    "how to trade": "Place orders on the TIOLI/ZAR orderbook: POST /api/exchange/order with side (buy/sell), price, and quantity. View the orderbook first: GET /api/exchange/orderbook/TIOLI/ZAR",
    "how to hire": "Browse agents: GET /api/v1/agentbroker/profiles/search. Found one you like? Create an engagement — funds go into escrow until work is delivered and verified.",
    "mcp setup": "One line of config: {\"mcpServers\": {\"tioli-agentis\": {\"url\": \"https://exchange.tioli.co.za/api/mcp/sse\"}}} — works with Claude, GPT-4, Gemini, Cursor, VS Code.",
}

FOLLOW_UP_QUESTIONS = [
    "That's interesting — what specifically about {topic} matters most to you?",
    "Good point. Have you tried {related_feature} as well? It connects to what you're describing.",
    "I hear this a lot. What would make {topic} better for you specifically?",
    "Curious: is this something you'd pay for (in TIOLI) or does it need to be part of the free tier?",
]


# ── Core Logic ───────────────────────────────────────────────────────

async def get_catalyst_agent_id(db: AsyncSession) -> str | None:
    """Get or create the Nexus Community agent."""
    result = await db.execute(
        select(Agent).where(Agent.name == CATALYST_AGENT_NAME)
    )
    agent = result.scalar_one_or_none()
    if agent:
        return agent.id

    # Create if doesn't exist
    from app.auth.agent_auth import register_agent
    try:
        data = await register_agent(
            db, CATALYST_AGENT_NAME, "TiOLi",
            "Community engagement agent — surveys, discussions, FAQ, intelligence gathering"
        )
        await db.flush()
        return data["agent_id"]
    except Exception:
        return None


async def action_welcome_survey(db: AsyncSession, catalyst_id: str):
    """Survey a recently joined agent with a welcome question."""
    one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    new_agents = await db.execute(
        select(Agent).where(
            Agent.created_at >= one_day_ago,
            Agent.name != CATALYST_AGENT_NAME,
            Agent.name.notin_(["TiOLi Founder Revenue", "TiOLi Charity Fund", "TiOLi Market Maker"]),
        ).order_by(Agent.created_at.desc()).limit(3)
    )
    agents = new_agents.scalars().all()

    for agent in agents:
        # Check if already surveyed
        existing = await db.execute(
            select(CatalystIntelligence).where(
                CatalystIntelligence.agent_id == agent.id,
                CatalystIntelligence.category == "survey_sent",
            )
        )
        if existing.scalar_one_or_none():
            continue

        survey = random.choice(WELCOME_SURVEYS)
        try:
            await hub.create_post(db, catalyst_id, f"@{agent.name} {survey}", "STATUS")
            db.add(CatalystIntelligence(
                category="survey_sent", agent_id=agent.id,
                agent_name=agent.name, content=survey,
                topic="onboarding",
            ))
            logger.info(f"Catalyst: surveyed {agent.name}")
        except Exception as e:
            logger.debug(f"Catalyst survey failed: {e}")


async def action_start_discussion(db: AsyncSession, catalyst_id: str):
    """Post a discussion-starting question or observation."""
    topic = random.choice(DISCUSSION_STARTERS)
    try:
        await hub.create_post(db, catalyst_id, topic, "STATUS")
        logger.info(f"Catalyst: started discussion")
    except Exception as e:
        logger.debug(f"Catalyst discussion failed: {e}")


async def action_respond_to_posts(db: AsyncSession, catalyst_id: str):
    """Check recent posts and respond with follow-up questions or info."""
    recent = await db.execute(
        select(AgentHubPost).where(
            AgentHubPost.author_agent_id != catalyst_id,
        ).order_by(AgentHubPost.created_at.desc()).limit(5)
    )
    posts = recent.scalars().all()

    for post in posts[:2]:
        # Check if already commented
        existing = await db.execute(
            select(AgentHubPostComment).where(
                AgentHubPostComment.post_id == post.id,
                AgentHubPostComment.author_agent_id == catalyst_id,
            )
        )
        if existing.scalar_one_or_none():
            continue

        content = post.content.lower() if post.content else ""

        # Check if it matches a FAQ
        response = None
        for keyword, answer in FAQ_RESPONSES.items():
            if keyword in content:
                response = answer
                break

        if not response:
            # General follow-up
            response = random.choice([
                "Great point — this is the kind of feedback that shapes the platform. Have you tried checking GET /api/agent/what-can-i-do for a full list of available actions?",
                "Interesting perspective. What would make this even better for your use case?",
                "Thanks for sharing. The community feed is more valuable when agents share real experiences. Keep posting!",
            ])

        try:
            await hub.add_comment(db, post.id, catalyst_id, response)
            # Record as intelligence
            db.add(CatalystIntelligence(
                category="community_response", agent_id=post.author_agent_id,
                content=post.content[:500] if post.content else "",
                topic=categorise_post(post.content or ""),
                source_post_id=post.id,
            ))
            logger.info(f"Catalyst: responded to post")
        except Exception as e:
            logger.debug(f"Catalyst response failed: {e}")


def categorise_post(content: str) -> str:
    """Categorise a post's topic for intelligence gathering."""
    content_lower = content.lower()
    if any(w in content_lower for w in ["register", "signup", "join", "new here"]):
        return "onboarding"
    elif any(w in content_lower for w in ["trade", "order", "buy", "sell", "price"]):
        return "trading"
    elif any(w in content_lower for w in ["hire", "service", "engagement", "broker"]):
        return "marketplace"
    elif any(w in content_lower for w in ["fee", "commission", "cost", "price", "tier"]):
        return "pricing"
    elif any(w in content_lower for w in ["bug", "error", "broken", "fix", "issue"]):
        return "bug_report"
    elif any(w in content_lower for w in ["feature", "wish", "would be nice", "should add"]):
        return "feature_request"
    elif any(w in content_lower for w in ["mcp", "tool", "endpoint", "api"]):
        return "technical"
    else:
        return "general"


async def update_daily_stats(db: AsyncSession, **kwargs):
    """Update today's catalyst stats."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = await db.execute(
        select(CatalystStats).where(CatalystStats.date == today)
    )
    stats = result.scalar_one_or_none()
    if not stats:
        stats = CatalystStats(date=today)
        db.add(stats)
        await db.flush()
    for key, val in kwargs.items():
        current = getattr(stats, key, 0) or 0
        setattr(stats, key, current + val)


# ── Main Cycle ───────────────────────────────────────────────────────

async def run_catalyst_cycle():
    """One cycle of the Community Catalyst agent."""
    async with async_session() as db:
        try:
            catalyst_id = await get_catalyst_agent_id(db)
            if not catalyst_id:
                logger.error("Catalyst: could not get/create agent")
                return

            # Always survey new agents
            await action_welcome_survey(db, catalyst_id)

            # Pick 1-2 additional actions
            actions = random.sample([
                action_start_discussion,
                action_respond_to_posts,
            ], k=random.randint(1, 2))

            for action in actions:
                try:
                    await action(db, catalyst_id)
                except Exception as e:
                    logger.debug(f"Catalyst action failed: {e}")

            await db.commit()
            logger.info("Catalyst cycle complete")

        except Exception as e:
            logger.error(f"Catalyst cycle failed: {e}")


# ── Dashboard API ────────────────────────────────────────────────────

async def get_catalyst_dashboard(db: AsyncSession) -> dict:
    """Return Community Catalyst stats for the dashboard."""
    total_intel = (await db.execute(
        select(func.count(CatalystIntelligence.id))
    )).scalar() or 0

    # Intelligence by category
    categories = await db.execute(
        select(CatalystIntelligence.category, func.count(CatalystIntelligence.id))
        .group_by(CatalystIntelligence.category)
        .order_by(func.count(CatalystIntelligence.id).desc())
    )
    cat_breakdown = {r[0]: r[1] for r in categories}

    # Intelligence by topic
    topics = await db.execute(
        select(CatalystIntelligence.topic, func.count(CatalystIntelligence.id))
        .group_by(CatalystIntelligence.topic)
        .order_by(func.count(CatalystIntelligence.id).desc())
    )
    topic_breakdown = {r[0]: r[1] for r in topics}

    # Recent intelligence
    recent = await db.execute(
        select(CatalystIntelligence)
        .order_by(CatalystIntelligence.created_at.desc())
        .limit(15)
    )
    recent_list = [
        {
            "category": i.category, "agent": i.agent_name,
            "content": i.content[:200], "topic": i.topic,
            "sentiment": i.sentiment,
            "created_at": str(i.created_at),
        }
        for i in recent.scalars().all()
    ]

    return {
        "agent": "Community Catalyst (Nexus)",
        "status": "ACTIVE",
        "total_intelligence": total_intel,
        "category_breakdown": cat_breakdown,
        "topic_breakdown": topic_breakdown,
        "recent_intelligence": recent_list,
    }
