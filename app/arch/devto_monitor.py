"""S-002: DEV.to Monitoring Engine — scan AI agent articles, identify opportunities.
Feature flag: ARCH_DEVTO_MONITOR_ENABLED"""
import os
import json
import logging
import httpx
from datetime import datetime, timezone

log = logging.getLogger("arch.devto_monitor")

DEVTO_API = "https://dev.to/api"
SCAN_TAGS = ["ai-agents", "langchain", "autonomous-agents", "mcp", "llm", "ai", "python"]
OUR_USERNAME = "sendersby"


async def scan_trending_articles(limit: int = 15) -> list:
    """Scan DEV.to for trending articles about AI agents."""
    articles = []
    async with httpx.AsyncClient(timeout=15) as client:
        for tag in SCAN_TAGS[:4]:
            try:
                resp = await client.get(f"{DEVTO_API}/articles",
                    params={"tag": tag, "top": 7, "per_page": 5})
                if resp.status_code == 200:
                    for a in resp.json():
                        articles.append({
                            "id": a["id"],
                            "title": a["title"][:120],
                            "url": a["url"],
                            "user": a.get("user", {}).get("username", "?"),
                            "reactions": a.get("public_reactions_count", 0),
                            "comments": a.get("comments_count", 0),
                            "tags": a.get("tag_list", []),
                            "published": a.get("published_at", "")[:10],
                            "is_ours": a.get("user", {}).get("username", "") == OUR_USERNAME,
                        })
            except Exception as e:
                log.warning(f"[devto] Tag {tag} scan failed: {e}")

    # Deduplicate
    seen = set()
    unique = []
    for a in sorted(articles, key=lambda x: x["reactions"], reverse=True):
        if a["id"] not in seen:
            seen.add(a["id"])
            unique.append(a)
    return unique[:limit]


async def check_our_article_stats() -> list:
    """Check stats on our published articles."""
    api_key = os.environ.get("DEVTO_API_KEY", "")
    if not api_key:
        return []

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.get(f"{DEVTO_API}/articles/me",
                headers={"api-key": api_key}, params={"per_page": 10})
            if resp.status_code == 200:
                return [{
                    "id": a["id"],
                    "title": a["title"][:80],
                    "url": a["url"],
                    "reactions": a.get("public_reactions_count", 0),
                    "comments": a.get("comments_count", 0),
                    "page_views": a.get("page_views_count", 0),
                    "published": a.get("published_at", "")[:10],
                } for a in resp.json()]
        except Exception as e:
            log.warning(f"[devto] Stats fetch failed: {e}")
    return []


async def identify_engagement_opportunities(articles: list) -> list:
    """Identify articles where commenting would be valuable.
    Note: DEV.to API does not support posting comments — opportunities are for manual follow-up."""
    opportunities = []
    for a in articles:
        if a["is_ours"]:
            continue
        # High engagement articles about agent topics
        if a["reactions"] > 10 and a["comments"] < 20:
            opportunities.append({
                "type": "high_engagement_article",
                "title": a["title"],
                "url": a["url"],
                "reactions": a["reactions"],
                "comments": a["comments"],
                "note": "High reactions, low comments — good visibility for a reply",
            })
        # Articles directly about agent infrastructure
        relevant_tags = {"ai-agents", "autonomous-agents", "mcp", "langchain"}
        if set(a.get("tags", [])) & relevant_tags:
            opportunities.append({
                "type": "relevant_topic",
                "title": a["title"],
                "url": a["url"],
                "matched_tags": list(set(a.get("tags", [])) & relevant_tags),
                "note": "Directly relevant to AGENTIS — consider writing a response article",
            })
    return opportunities


async def run_devto_scan(db) -> dict:
    """Full DEV.to scan cycle."""
    if os.environ.get("ARCH_DEVTO_MONITOR_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    log.info("[devto] Starting scan cycle")
    results = {}

    # 1. Scan trending
    trending = await scan_trending_articles(12)
    results["trending"] = trending
    results["trending_count"] = len(trending)

    # 2. Check our stats
    our_stats = await check_our_article_stats()
    results["our_articles"] = our_stats
    total_views = sum(a.get("page_views", 0) for a in our_stats)
    total_reactions = sum(a.get("reactions", 0) for a in our_stats)
    results["our_totals"] = {"views": total_views, "reactions": total_reactions, "articles": len(our_stats)}

    # 3. Identify opportunities
    opportunities = await identify_engagement_opportunities(trending)
    results["opportunities"] = opportunities
    results["opportunity_count"] = len(opportunities)

    # 4. Store and report
    try:
        import asyncpg
        conn = await asyncpg.connect(user="tioli", password="DhQHhP6rsYdUL*2DLWJ2Neu#2xqhM0z#",
                                      database="tioli_exchange", host="127.0.0.1", port=5432)
        await conn.execute(
            "INSERT INTO job_execution_log (job_id, status, tokens_consumed, duration_ms, executed_at) "
            "VALUES ($1, $2, $3, $4, now())",
            "devto_scan", f"FOUND_{len(opportunities)}", 0, 0)

        # Deliver report to inbox if opportunities found
        if opportunities:
            proof = {
                "subject": f"DEV.to Scan: {len(opportunities)} engagement opportunities",
                "situation": "Opportunities: " + " | ".join(
                    f"{o['title'][:40]} ({o['url']})" for o in opportunities[:3])
            }
            await conn.execute(
                "INSERT INTO arch_founder_inbox (item_type, priority, description, status, due_at) "
                "VALUES ($1, $2, $3, $4, now() + interval '48 hours')",
                "INFORMATION", "ROUTINE", json.dumps(proof), "PENDING")

        await conn.close()
    except Exception as e:
        log.warning(f"[devto] Storage failed: {e}")

    log.info(f"[devto] Scan complete: {len(trending)} trending, {len(opportunities)} opportunities")
    return results
