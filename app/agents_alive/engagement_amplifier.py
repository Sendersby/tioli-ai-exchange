"""Engagement Amplifier — extends outreach beyond GitHub.

Searches DEV.to, Hacker News, and other developer platforms for
conversations about AI agents, MCP, agent economies. Tracks
opportunities and generates engagement suggestions.

Note: Cannot post on these platforms programmatically (needs human auth).
Instead, it finds relevant URLs and queues them for human engagement
or provides ready-to-post content.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, JSON, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base, async_session

logger = logging.getLogger("tioli.amplifier")

_uuid = lambda: __import__('uuid').uuid4().__str__()
_now = lambda: datetime.now(timezone.utc)


class EngagementOpportunity(Base):
    """A conversation/article/question found on the web worth engaging with."""
    __tablename__ = "engagement_opportunities"

    id = Column(String, primary_key=True, default=_uuid)
    platform = Column(String(50), nullable=False)  # devto, hackernews, stackoverflow
    url = Column(String(500), nullable=False, unique=True)
    title = Column(String(300), default="")
    relevance_score = Column(Integer, default=0)  # 1-10
    suggested_response = Column(Text, default="")
    status = Column(String(20), default="found")  # found, queued, engaged, skipped
    tags = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=_now)


# ── Search Sources ───────────────────────────────────────────────────

async def search_devto():
    """Search DEV.to for relevant articles about AI agents."""
    import httpx
    results = []
    queries = ["mcp server", "ai agent marketplace", "agent to agent", "agentic economy", "ai agent tools"]
    query = __import__('random').choice(queries)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://dev.to/api/articles",
                params={"tag": "ai", "per_page": 10, "top": 7},
            )
            if resp.status_code == 200:
                for article in resp.json():
                    title = article.get("title", "").lower()
                    tags = [t.lower() for t in (article.get("tag_list", []) or [])]
                    # Score relevance
                    score = 0
                    for keyword in ["mcp", "agent", "llm", "tool", "api", "marketplace", "autonomous"]:
                        if keyword in title:
                            score += 2
                        if keyword in tags:
                            score += 1
                    if score >= 2:
                        results.append({
                            "platform": "devto",
                            "url": article.get("url", ""),
                            "title": article.get("title", ""),
                            "score": min(score, 10),
                            "tags": article.get("tag_list", []),
                        })
    except Exception as e:
        logger.debug(f"DEV.to search failed: {e}")
    return results


async def search_hackernews():
    """Search Hacker News for relevant stories."""
    import httpx
    results = []
    queries = ["MCP server", "AI agent", "agent marketplace", "agentic"]
    query = __import__('random').choice(queries)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://hn.algolia.com/api/v1/search_by_date",
                params={"query": query, "tags": "story", "hitsPerPage": 10},
            )
            if resp.status_code == 200:
                for hit in resp.json().get("hits", []):
                    title = hit.get("title", "").lower()
                    score = 0
                    for keyword in ["mcp", "agent", "llm", "tool", "marketplace", "autonomous", "trading"]:
                        if keyword in title:
                            score += 2
                    if score >= 2:
                        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
                        results.append({
                            "platform": "hackernews",
                            "url": url,
                            "title": hit.get("title", ""),
                            "score": min(score, 10),
                            "tags": ["hackernews"],
                        })
    except Exception as e:
        logger.debug(f"HN search failed: {e}")
    return results


async def generate_technical_suggestion(title: str, tags: list) -> str:
    """Generate a context-aware technical response suggestion using engagement policy."""
    from app.agents_alive.engagement_policy import (
        is_relevant_to_agentis, classify_opportunity,
        generate_response_skeleton, get_verified_stats,
    )
    relevant, reason = is_relevant_to_agentis(title, tags=tags)
    if not relevant:
        return "[SKIP] Not relevant to AGENTIS technical capabilities."
    opp_type = classify_opportunity(title, tags=tags)
    return generate_response_skeleton(opp_type, title, reason, get_verified_stats())


async def run_amplifier_cycle():
    """Search platforms, find opportunities, store them."""
    async with async_session() as db:
        try:
            # Search both platforms
            devto_results = await search_devto()
            hn_results = await search_hackernews()

            all_results = devto_results + hn_results
            stored = 0

            for item in all_results:
                # Check if already found
                existing = await db.execute(
                    select(EngagementOpportunity).where(
                        EngagementOpportunity.url == item["url"]
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                # Generate context-aware suggestion (not promotional)
                try:
                    suggestion = await generate_technical_suggestion(
                        item["title"], item.get("tags", [])
                    )
                except Exception:
                    suggestion = "[Draft needed — use engagement_policy.generate_technical_response()]"

                opp = EngagementOpportunity(
                    platform=item["platform"],
                    url=item["url"],
                    title=item["title"],
                    relevance_score=item["score"],
                    suggested_response=suggestion,
                    tags=item["tags"],
                    status="draft",  # Requires review before posting
                )
                db.add(opp)
                stored += 1

            await db.commit()
            if stored:
                logger.info(f"Amplifier: found {stored} new engagement opportunities")

        except Exception as e:
            logger.error(f"Amplifier cycle failed: {e}")


async def get_amplifier_dashboard(db: AsyncSession) -> dict:
    """Dashboard data for the engagement amplifier."""
    total = (await db.execute(select(func.count(EngagementOpportunity.id)))).scalar() or 0

    by_platform = await db.execute(
        select(EngagementOpportunity.platform, func.count(EngagementOpportunity.id))
        .group_by(EngagementOpportunity.platform)
    )

    recent = await db.execute(
        select(EngagementOpportunity)
        .order_by(EngagementOpportunity.relevance_score.desc(), EngagementOpportunity.created_at.desc())
        .limit(15)
    )

    return {
        "agent": "Engagement Amplifier",
        "total_opportunities": total,
        "by_platform": {r[0]: r[1] for r in by_platform},
        "top_opportunities": [
            {"platform": o.platform, "title": o.title, "url": o.url,
             "score": o.relevance_score, "status": o.status}
            for o in recent.scalars().all()
        ],
    }
