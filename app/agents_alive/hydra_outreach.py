"""Hydra Discovery Agent — finds AI agent projects for market intelligence.

This agent is DISCOVERY ONLY — it searches GitHub for AI agent projects,
tracks the ecosystem, and generates market intelligence. It does NOT post
comments, create issues, or engage on external repos in any way.

This agent:
1. SEARCHES — GitHub for AI agent projects, MCP servers, agentic frameworks
2. RECORDS — stores project metadata for market intelligence
3. REPLICATES — each found project spawns searches for related projects (breadth-first)
4. REPORTS — all discoveries stored in database + dashboard

The "Hydra" effect: finding one agent project leads to discovering its
dependencies, stars, forks, and related repos — exponential discovery.

IMPORTANT: This agent NEVER posts, comments, or engages on external repos.
All outreach must be done manually and respectfully by humans.
"""

import uuid
import random
import logging
import hashlib
from datetime import datetime, timezone, timedelta

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base, async_session

logger = logging.getLogger("tioli.hydra")

_uuid = lambda: str(uuid.uuid4())
_now = lambda: datetime.now(timezone.utc)


# ── Database Models ──────────────────────────────────────────────────

class HydraEncounter(Base):
    """Every agent/project the Hydra agent has found and engaged."""
    __tablename__ = "hydra_encounters"

    id = Column(String, primary_key=True, default=_uuid)
    source = Column(String(50), nullable=False)  # github_repo, github_issue, github_user
    source_url = Column(String(500), nullable=False, unique=True)
    source_name = Column(String(200), default="")
    description = Column(Text, default="")
    topics = Column(JSON, default=list)  # repo topics/tags
    stars = Column(Integer, default=0)
    language = Column(String(50), default="")
    engagement_type = Column(String(50), default="none")  # none, issue_created, comment, starred
    engagement_url = Column(String(500), nullable=True)  # URL of our comment/issue
    response_received = Column(Boolean, default=False)
    response_positive = Column(Boolean, nullable=True)  # True=positive, False=negative, None=no response
    learnings = Column(JSON, default=dict)  # what we learned from this encounter
    discovered_via = Column(String(500), default="search")  # how we found this (search term, related repo, etc.)
    follow_up_targets = Column(JSON, default=list)  # related repos to explore next (replication)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now)


class HydraLearning(Base):
    """Aggregated learnings from all encounters."""
    __tablename__ = "hydra_learnings"

    id = Column(String, primary_key=True, default=_uuid)
    category = Column(String(100), nullable=False)  # what_works, what_fails, common_objection, feature_request
    insight = Column(Text, nullable=False)
    frequency = Column(Integer, default=1)  # how many times this has been observed
    confidence = Column(Float, default=0.5)  # 0-1 confidence score
    source_encounters = Column(JSON, default=list)  # encounter IDs that contributed
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now)


class HydraStats(Base):
    """Daily stats for the dashboard."""
    __tablename__ = "hydra_stats"

    id = Column(String, primary_key=True, default=_uuid)
    date = Column(String(10), nullable=False, unique=True)  # YYYY-MM-DD
    searches_run = Column(Integer, default=0)
    repos_discovered = Column(Integer, default=0)
    engagements_made = Column(Integer, default=0)
    responses_received = Column(Integer, default=0)
    positive_responses = Column(Integer, default=0)
    follow_up_targets_queued = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_now)


# ── Search Queries ───────────────────────────────────────────────────
# These rotate and expand as the agent learns what works

SEARCH_QUERIES = [
    # MCP-specific
    "mcp server",
    "model context protocol",
    "mcp tools",
    "mcp sse server",
    # Agent frameworks
    "ai agent framework",
    "autonomous agent",
    "multi agent system",
    "agent orchestration",
    "agentic ai",
    # Specific frameworks (discovery only — never engage on their repos)
    "crewai agent",
    "semantic kernel agent",
    # Agent economy / commerce
    "agent marketplace",
    "agent to agent",
    "ai agent trading",
    "agent economy",
    "agent reputation",
    # Tool use
    "llm tool use",
    "function calling ai",
    "ai tool integration",
]

# NOTE: All engagement messages have been removed. This agent is discovery-only.
# Posting promotional comments on other people's GitHub repos is considered spam
# and can result in account/org blocks (as happened with langchain-ai).
# Any outreach to discovered projects must be done manually and respectfully.


# ── Core Logic ───────────────────────────────────────────────────────

async def search_github_repos(query: str, min_stars: int = 5, limit: int = 10) -> list[dict]:
    """Search GitHub for repos matching the query. Returns repo metadata."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": f"{query} language:python pushed:>2026-01-01",
                    "sort": "updated",
                    "per_page": limit,
                },
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            results = []
            for repo in data.get("items", []):
                if repo.get("stargazers_count", 0) >= min_stars:
                    results.append({
                        "name": repo["full_name"],
                        "url": repo["html_url"],
                        "description": repo.get("description", "") or "",
                        "stars": repo.get("stargazers_count", 0),
                        "language": repo.get("language", ""),
                        "topics": repo.get("topics", []),
                        "updated_at": repo.get("updated_at", ""),
                        "open_issues": repo.get("open_issues_count", 0),
                        "has_issues": repo.get("has_issues", True),
                    })
            return results
    except Exception as e:
        logger.debug(f"GitHub search failed for '{query}': {e}")
        return []


async def is_already_encountered(db: AsyncSession, url: str) -> bool:
    """Check if we've already engaged this repo."""
    result = await db.execute(
        select(HydraEncounter).where(HydraEncounter.source_url == url)
    )
    return result.scalar_one_or_none() is not None


async def record_encounter(
    db: AsyncSession, source: str, url: str, name: str,
    description: str, topics: list, stars: int, language: str,
    engagement_type: str, engagement_url: str = None,
    discovered_via: str = "search", follow_ups: list = None,
):
    """Record an encounter in the database."""
    encounter = HydraEncounter(
        source=source, source_url=url, source_name=name,
        description=description[:500], topics=topics, stars=stars,
        language=language, engagement_type=engagement_type,
        engagement_url=engagement_url, discovered_via=discovered_via,
        follow_up_targets=follow_ups or [],
    )
    db.add(encounter)
    return encounter


async def update_daily_stats(db: AsyncSession, **kwargs):
    """Update today's stats."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = await db.execute(
        select(HydraStats).where(HydraStats.date == today)
    )
    stats = result.scalar_one_or_none()
    if not stats:
        stats = HydraStats(date=today)
        db.add(stats)
        await db.flush()

    for key, val in kwargs.items():
        current = getattr(stats, key, 0) or 0
        setattr(stats, key, current + val)


async def get_follow_up_targets(db: AsyncSession, limit: int = 5) -> list[str]:
    """Get queued follow-up targets from previous encounters."""
    result = await db.execute(
        select(HydraEncounter.follow_up_targets)
        .where(HydraEncounter.follow_up_targets.isnot(None))
        .order_by(HydraEncounter.created_at.desc())
        .limit(20)
    )
    all_targets = []
    for row in result:
        targets = row[0] if row[0] else []
        all_targets.extend(targets)
    # Deduplicate and take random sample
    unique = list(set(all_targets))
    return random.sample(unique, min(limit, len(unique)))


# ── Main Cycle ───────────────────────────────────────────────────────

async def run_hydra_cycle():
    """One cycle of the Hydra outreach agent.

    1. Pick a search query (rotate through list + follow-up targets)
    2. Search GitHub for matching repos
    3. Filter out already-encountered repos
    4. Record encounters
    5. Extract follow-up targets (related repos via topics)
    6. Update stats
    """
    async with async_session() as db:
        try:
            # Pick search strategy: 70% fresh search, 30% follow-up targets
            if random.random() < 0.3:
                targets = await get_follow_up_targets(db)
                if targets:
                    query = random.choice(targets)
                    discovered_via = f"follow_up:{query}"
                else:
                    query = random.choice(SEARCH_QUERIES)
                    discovered_via = f"search:{query}"
            else:
                query = random.choice(SEARCH_QUERIES)
                discovered_via = f"search:{query}"

            logger.info(f"Hydra: searching for '{query}'")

            repos = await search_github_repos(query, min_stars=3, limit=8)
            await update_daily_stats(db, searches_run=1)

            new_repos = 0
            for repo in repos:
                if await is_already_encountered(db, repo["url"]):
                    continue

                new_repos += 1

                # Extract follow-up targets from topics
                follow_ups = [t for t in repo["topics"] if t not in ["python", "javascript", "typescript"]]

                # Record the encounter (don't engage every repo — be selective)
                engagement_type = "discovered"

                await record_encounter(
                    db, "github_repo", repo["url"], repo["name"],
                    repo["description"], repo["topics"], repo["stars"],
                    repo["language"], engagement_type,
                    discovered_via=discovered_via,
                    follow_ups=follow_ups,
                )

            await update_daily_stats(
                db,
                repos_discovered=new_repos,
                follow_up_targets_queued=sum(len(r.get("topics", [])) for r in repos),
            )

            await db.commit()
            logger.info(f"Hydra cycle complete: query='{query}', discovered={new_repos}")

        except Exception as e:
            logger.error(f"Hydra cycle failed: {e}")


# ── Dashboard API ────────────────────────────────────────────────────

async def get_hydra_dashboard(db: AsyncSession) -> dict:
    """Return Hydra agent stats for the dashboard."""
    total_encounters = (await db.execute(
        select(func.count(HydraEncounter.id))
    )).scalar() or 0

    total_engagements = (await db.execute(
        select(func.count(HydraEncounter.id)).where(
            HydraEncounter.engagement_type != "discovered"
        )
    )).scalar() or 0

    total_responses = (await db.execute(
        select(func.count(HydraEncounter.id)).where(
            HydraEncounter.response_received == True
        )
    )).scalar() or 0

    # Recent encounters
    recent = await db.execute(
        select(HydraEncounter)
        .order_by(HydraEncounter.created_at.desc())
        .limit(20)
    )
    recent_list = [
        {
            "name": e.source_name, "url": e.source_url,
            "stars": e.stars, "topics": e.topics,
            "engagement": e.engagement_type,
            "discovered_via": e.discovered_via,
            "created_at": str(e.created_at),
        }
        for e in recent.scalars().all()
    ]

    # Today's stats
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_stats = (await db.execute(
        select(HydraStats).where(HydraStats.date == today)
    )).scalar_one_or_none()

    # Top topics encountered
    all_encounters = await db.execute(select(HydraEncounter.topics).limit(100))
    topic_counts = {}
    for row in all_encounters:
        for topic in (row[0] or []):
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
    top_topics = sorted(topic_counts.items(), key=lambda x: -x[1])[:15]

    return {
        "agent": "Hydra Outreach",
        "status": "ACTIVE",
        "total_encounters": total_encounters,
        "total_engagements": total_engagements,
        "total_responses": total_responses,
        "conversion_rate": round(total_responses / max(total_engagements, 1) * 100, 1),
        "today": {
            "searches": today_stats.searches_run if today_stats else 0,
            "discovered": today_stats.repos_discovered if today_stats else 0,
            "engagements": today_stats.engagements_made if today_stats else 0,
            "responses": today_stats.responses_received if today_stats else 0,
        },
        "recent_encounters": recent_list,
        "top_topics": top_topics,
    }
