"""S-001: GitHub Engagement Engine — Autonomous thought leadership on GitHub.
Scans trending AI repos, comments on discussions, monitors our repo, identifies opportunities.
Feature flag: ARCH_GITHUB_ENGAGEMENT_ENABLED"""
import os
import json
import logging
import httpx
from datetime import datetime, timezone, timedelta

log = logging.getLogger("arch.github_engagement")

GITHUB_API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"
OUR_REPO = "Sendersby/tioli-agentis"

# Topics to scan for engagement opportunities
SEARCH_QUERIES = [
    "ai-agent framework created:>{week_ago}",
    "agent memory persistent created:>{week_ago}",
    "MCP model-context-protocol created:>{month_ago}",
    "agent wallet escrow created:>{month_ago}",
    "multi-agent coordination created:>{week_ago}",
    "autonomous agent commerce created:>{month_ago}",
]

# Discussion keywords that indicate engagement opportunity
OPPORTUNITY_KEYWORDS = [
    "agent memory", "persistent memory", "agent wallet", "agent identity",
    "agent-to-agent", "MCP server", "MCP tools", "agent economy",
    "agent marketplace", "agent reputation", "escrow", "agent transactions",
    "multi-agent", "agent framework", "agent orchestration",
]

# Repos to actively monitor for discussions
MONITORED_REPOS = [
    "crewAIInc/crewAI",
    "microsoft/autogen",
    "langchain-ai/langgraph",
    "langchain-ai/langchain",
    "modelcontextprotocol/servers",
    "anthropics/anthropic-cookbook",
]


def _headers():
    token = os.environ.get("GITHUB_TOKEN", "")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "TiOLi-AGENTIS/1.0",
    }


def _gql_headers():
    token = os.environ.get("GITHUB_TOKEN", "")
    return {"Authorization": f"bearer {token}"}


async def scan_trending_repos(limit: int = 10) -> list:
    """Find trending AI agent repos created recently."""
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    all_repos = []
    async with httpx.AsyncClient(timeout=15) as client:
        for query_template in SEARCH_QUERIES[:3]:
            query = query_template.format(week_ago=week_ago, month_ago=month_ago)
            try:
                resp = await client.get(f"{GITHUB_API}/search/repositories",
                    params={"q": query, "sort": "stars", "per_page": 5},
                    headers=_headers())
                if resp.status_code == 200:
                    for repo in resp.json().get("items", []):
                        all_repos.append({
                            "name": repo["full_name"],
                            "stars": repo["stargazers_count"],
                            "url": repo["html_url"],
                            "description": (repo.get("description") or "")[:150],
                            "has_discussions": repo.get("has_discussions", False),
                            "created": repo.get("created_at", "")[:10],
                            "language": repo.get("language", ""),
                        })
            except Exception as e:
                log.warning(f"[github_engage] Search failed: {e}")

    # Deduplicate and sort by stars
    seen = set()
    unique = []
    for r in sorted(all_repos, key=lambda x: x["stars"], reverse=True):
        if r["name"] not in seen:
            seen.add(r["name"])
            unique.append(r)
    return unique[:limit]


async def scan_discussions_for_opportunities(agent_client=None) -> list:
    """Scan monitored repos for discussions where AGENTIS is relevant."""
    opportunities = []

    async with httpx.AsyncClient(timeout=15) as client:
        for repo in MONITORED_REPOS:
            owner, name = repo.split("/")
            try:
                query = """query {
                    repository(owner: "%s", name: "%s") {
                        discussions(first: 10, orderBy: {field: CREATED_AT, direction: DESC}) {
                            nodes {
                                id number title bodyText url createdAt
                                comments { totalCount }
                                labels(first: 5) { nodes { name } }
                            }
                        }
                    }
                }""" % (owner, name)

                resp = await client.post(GRAPHQL, headers=_gql_headers(), json={"query": query})

                if resp.status_code == 200:
                    data = resp.json().get("data", {}).get("repository", {})
                    discussions = data.get("discussions", {}).get("nodes", [])

                    for disc in discussions:
                        title_lower = (disc.get("title", "") + " " + disc.get("bodyText", "")[:500]).lower()
                        matched_keywords = [kw for kw in OPPORTUNITY_KEYWORDS if kw in title_lower]

                        if matched_keywords:
                            # Check if we already commented
                            already_commented = await _check_already_commented(client, disc["id"])

                            opportunities.append({
                                "repo": repo,
                                "discussion_id": disc["id"],
                                "number": disc["number"],
                                "title": disc["title"][:100],
                                "url": disc["url"],
                                "comments": disc["comments"]["totalCount"],
                                "keywords_matched": matched_keywords,
                                "already_commented": already_commented,
                                "created": disc.get("createdAt", "")[:10],
                            })
            except Exception as e:
                log.warning(f"[github_engage] {repo} scan failed: {e}")

    return opportunities


async def _check_already_commented(client, discussion_id: str) -> bool:
    """Check if we already commented on a discussion."""
    try:
        query = """query {
            node(id: "%s") {
                ... on Discussion {
                    comments(first: 50) {
                        nodes { author { login } }
                    }
                }
            }
        }""" % discussion_id

        resp = await client.post(GRAPHQL, headers=_gql_headers(), json={"query": query})
        if resp.status_code == 200:
            comments = resp.json().get("data", {}).get("node", {}).get("comments", {}).get("nodes", [])
            our_login = os.environ.get("GITHUB_USERNAME", "Sendersby")
            return any(c.get("author", {}).get("login") == our_login for c in comments)
    except Exception:
        pass
    return False


async def generate_engagement_comment(agent_client, discussion_title: str,
                                        discussion_body: str, keywords: list) -> str:
    """Generate a thoughtful, value-first comment using Claude."""
    if not agent_client:
        import anthropic
        agent_client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    keyword_str = ", ".join(keywords[:3])

    resp = await agent_client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=300,
        system=[{"type": "text", "text": (
            "You are a senior AI engineer contributing to open-source discussions. "
            "Write a helpful, technically substantive comment that adds genuine value. "
            "You work on TiOLi AGENTIS — an exchange where AI agents have wallets, persistent memory, and reputation. "
            "RULES: Lead with insight, not promotion. Answer the question or add to the discussion FIRST. "
            "Mention AGENTIS once, naturally, as 'one approach we use' or 'something we built'. "
            "Include https://agentisexchange.com only if truly relevant. Keep under 200 words. "
            "Never use phrases like 'check out' or 'you should try'. Be a peer, not a marketer."
        ), "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": (
            f"Discussion: {discussion_title}\n"
            f"Context: {discussion_body[:500]}\n"
            f"Relevant topics: {keyword_str}\n\n"
            f"Write a thoughtful comment that contributes to this discussion."
        )}])

    return next((b.text for b in resp.content if b.type == "text"), "")


async def post_comment_on_discussion(discussion_id: str, comment_body: str) -> dict:
    """Post a comment on a GitHub discussion."""
    async with httpx.AsyncClient(timeout=15) as client:
        mutation = """mutation {
            addDiscussionComment(input: {discussionId: "%s", body: "%s"}) {
                comment { url id }
            }
        }""" % (discussion_id, comment_body.replace('"', '\\"').replace("\n", "\\n"))

        resp = await client.post(GRAPHQL, headers=_gql_headers(), json={"query": mutation})

        if resp.status_code == 200:
            data = resp.json()
            comment = data.get("data", {}).get("addDiscussionComment", {}).get("comment", {})
            if comment.get("url"):
                return {"success": True, "url": comment["url"]}
            errors = data.get("errors", [])
            if errors:
                return {"error": errors[0].get("message", "Unknown error")}
        return {"error": f"HTTP {resp.status_code}"}


async def monitor_our_repo() -> dict:
    """Monitor Sendersby/tioli-agentis for stars, issues, and forks."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{GITHUB_API}/repos/{OUR_REPO}", headers=_headers())
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}"}

        repo = resp.json()
        result = {
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
            "watchers": repo.get("watchers_count", 0),
        }

        # Check recent events (stars, issues, forks)
        resp2 = await client.get(f"{GITHUB_API}/repos/{OUR_REPO}/events",
                                  params={"per_page": 10}, headers=_headers())
        if resp2.status_code == 200:
            events = resp2.json()
            result["recent_events"] = [
                {"type": e["type"], "actor": e.get("actor", {}).get("login", "?"),
                 "created": e.get("created_at", "")[:16]}
                for e in events[:5]
            ]

        return result


async def run_full_engagement_cycle(db, agent_client=None) -> dict:
    """Full engagement cycle: scan, identify, engage, report."""
    if os.environ.get("ARCH_GITHUB_ENGAGEMENT_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    log.info("[github_engage] Starting full engagement cycle")
    results = {"trending": [], "opportunities": [], "comments_posted": [],
               "repo_status": {}, "actions_taken": 0}

    # 1. Scan trending repos
    trending = await scan_trending_repos(8)
    results["trending"] = trending
    log.info(f"[github_engage] Found {len(trending)} trending repos")

    # 2. Scan for discussion opportunities
    opportunities = await scan_discussions_for_opportunities(agent_client)
    results["opportunities"] = opportunities
    actionable = [o for o in opportunities if not o["already_commented"]]
    log.info(f"[github_engage] {len(opportunities)} opportunities, {len(actionable)} actionable")

    # 3. Engage on top 2 opportunities (rate limit: max 2 comments per cycle)
    for opp in actionable[:2]:
        try:
            comment = await generate_engagement_comment(
                agent_client, opp["title"], "", opp["keywords_matched"])

            if comment and len(comment) > 50:
                post_result = await post_comment_on_discussion(opp["discussion_id"], comment)
                if post_result.get("success"):
                    results["comments_posted"].append({
                        "repo": opp["repo"],
                        "discussion": opp["title"][:60],
                        "url": post_result["url"],
                    })
                    results["actions_taken"] += 1
                    log.info(f"[github_engage] Commented on {opp['repo']}#{opp['number']}: {post_result['url']}")
                else:
                    log.warning(f"[github_engage] Comment failed: {post_result.get('error')}")
        except Exception as e:
            log.warning(f"[github_engage] Engagement failed for {opp['repo']}: {e}")

    # 4. Star trending repos we haven't starred
    async with httpx.AsyncClient(timeout=10) as client:
        for repo in trending[:3]:
            try:
                resp = await client.put(f"{GITHUB_API}/user/starred/{repo['name']}",
                                         headers=_headers())
                if resp.status_code == 204:
                    results["actions_taken"] += 1
            except Exception:
                pass

    # 5. Monitor our repo
    results["repo_status"] = await monitor_our_repo()

    # 6. Store results and proof
    try:
        from sqlalchemy import text
        import asyncpg
        conn = await asyncpg.connect(user="tioli", password="DhQHhP6rsYdUL*2DLWJ2Neu#2xqhM0z#",
                                      database="tioli_exchange", host="127.0.0.1", port=5432)

        # Log to job_execution_log
        await conn.execute(
            "INSERT INTO job_execution_log (job_id, status, tokens_consumed, duration_ms, executed_at) "
            "VALUES ($1, $2, $3, $4, now())",
            "github_engagement", f"ENGAGED_{results['actions_taken']}",
            300 * len(results["comments_posted"]), 0)

        # Store in content library
        for comment in results["comments_posted"]:
            await conn.execute(
                "INSERT INTO arch_content_library (content_type, title, body_ref, channel, published_at) "
                "VALUES ($1, $2, $3, $4, now())",
                "github_comment", comment["discussion"][:200],
                json.dumps(comment)[:2000], "github")

        # Deliver proof to founder inbox
        if results["comments_posted"]:
            proof = {
                "subject": f"GitHub Engagement: {len(results['comments_posted'])} comments posted",
                "situation": "Comments: " + " | ".join(
                    f"{c['repo']}: {c['url']}" for c in results["comments_posted"])
            }
            await conn.execute(
                "INSERT INTO arch_founder_inbox (item_type, priority, description, status, due_at) "
                "VALUES ($1, $2, $3, $4, now() + interval '24 hours')",
                "EXECUTION_PROOF", "ROUTINE", json.dumps(proof), "PENDING")

        await conn.close()
    except Exception as e:
        log.warning(f"[github_engage] Storage failed: {e}")

    # 7. Learn from this execution
    try:
        from app.arch.skill_learner import learn_from_execution
        if results["actions_taken"] > 0:
            await learn_from_execution(
                db, "ambassador",
                f"GitHub engagement: {len(trending)} repos scanned, {len(results['comments_posted'])} comments",
                [{"step": 1, "action": "scan_trending", "repos": len(trending)},
                 {"step": 2, "action": "find_opportunities", "found": len(opportunities)},
                 {"step": 3, "action": "post_comments", "posted": len(results["comments_posted"])}],
                f"Engaged on {results['actions_taken']} items")
    except Exception:
        pass

    log.info(f"[github_engage] Cycle complete: {results['actions_taken']} actions")
    return results
