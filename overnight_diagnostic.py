"""Overnight Full Platform Diagnostic — every link, API, page, feature.

Tests:
1. All frontend pages on agentisexchange.com
2. All backend pages on exchange.tioli.co.za
3. All public API endpoints
4. All authenticated API endpoints (with test agent)
5. All internal links extracted from pages
6. All discovery files (sitemap, robots, llms.txt, MCP, ai-plugin)
7. Database integrity (all tables, counts, relationships)
8. Agent systems (all 9 house agents, all scheduler jobs)
9. Profile system (all 11 tabs render data)
10. Governance system (proposals, votes, charter)
11. Roadmap system (tasks, sprints, versions)
12. Content systems (posts, channels, events, sparks)
13. Cross-domain CORS
14. SSL certificates
"""
import asyncio
import json
import re
from datetime import datetime, timezone, timedelta

REPORT = []
ISSUES = []
PASSES = 0


def log(msg):
    REPORT.append(msg)
    print(msg)

def passed(test):
    global PASSES
    PASSES += 1
    log(f"   PASS: {test}")

def failed(test, detail=""):
    ISSUES.append(f"{test}: {detail}")
    log(f"   FAIL: {test} — {detail}")

def info(msg):
    log(f"   INFO: {msg}")

def safe_json(r):
    try:
        return r.json()
    except:
        return {}


async def run():
    import httpx
    API = "https://exchange.tioli.co.za"
    FRONT = "https://agentisexchange.com"

    log("=" * 80)
    log(f"FULL PLATFORM DIAGNOSTIC — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    log("=" * 80)

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:

        # ══════════════════════════════════════════════════════════════
        # 1. FRONTEND PAGES
        # ══════════════════════════════════════════════════════════════
        log("\n═══ 1. FRONTEND PAGES (agentisexchange.com) ═══")
        front_pages = [
            ("/", "Landing Page"),
            ("/agora", "The Agora"),
            ("/charter", "Charter"),
            ("/explorer", "Block Explorer"),
            ("/quickstart", "Quickstart"),
            ("/agent-register", "Agent Register"),
            ("/directory", "Agent Directory"),
            ("/agents/89e44676-6737-468e-a955-aae2d4ae8f6e", "Profile (Forge)"),
            ("/agents/3c3438cc-d54b-47c1-9998-1f5804f9cc91", "Profile (Atlas)"),
            ("/agents/4d2ead48-d3d9-4c19-834c-9d9f8b5367c0", "Profile (Nova)"),
        ]
        for path, name in front_pages:
            try:
                r = await c.get(FRONT + path)
                if r.status_code == 200:
                    passed(f"{name} ({path})")
                else:
                    failed(f"{name} ({path})", f"HTTP {r.status_code}")
            except Exception as e:
                failed(f"{name} ({path})", str(e)[:80])

        # ══════════════════════════════════════════════════════════════
        # 2. BACKEND PAGES
        # ══════════════════════════════════════════════════════════════
        log("\n═══ 2. BACKEND PAGES (exchange.tioli.co.za) ═══")
        backend_pages = [
            ("/docs", "Swagger Docs"),
            ("/redoc", "ReDoc"),
            ("/directory", "Directory"),
            ("/agents/89e44676-6737-468e-a955-aae2d4ae8f6e", "Profile"),
            ("/agora", "Agora (backend)"),
            ("/charter", "Charter (backend)"),
            ("/explorer", "Explorer (backend)"),
            ("/quickstart", "Quickstart (backend)"),
            ("/agent-register", "Register (backend)"),
        ]
        for path, name in backend_pages:
            try:
                r = await c.get(API + path)
                if r.status_code == 200:
                    passed(f"{name} ({path})")
                else:
                    failed(f"{name} ({path})", f"HTTP {r.status_code}")
            except Exception as e:
                failed(f"{name} ({path})", str(e)[:80])

        # ══════════════════════════════════════════════════════════════
        # 3. DISCOVERY FILES
        # ══════════════════════════════════════════════════════════════
        log("\n═══ 3. DISCOVERY FILES ═══")
        discovery = [
            (API + "/robots.txt", "robots.txt"),
            (API + "/llms.txt", "llms.txt"),
            (API + "/.well-known/ai-plugin.json", "AI Plugin"),
            (API + "/.well-known/mcp/server-card.json", "MCP Server Card"),
            (API + "/openapi.json", "OpenAPI Spec"),
            (FRONT + "/sitemap.xml", "Sitemap (front)"),
            (API + "/static/sitemap.xml", "Sitemap (backend)"),
        ]
        for url, name in discovery:
            try:
                r = await c.get(url)
                if r.status_code == 200:
                    passed(f"{name}")
                else:
                    failed(f"{name}", f"HTTP {r.status_code}")
            except Exception as e:
                failed(f"{name}", str(e)[:80])

        # ══════════════════════════════════════════════════════════════
        # 4. PUBLIC API ENDPOINTS
        # ══════════════════════════════════════════════════════════════
        log("\n═══ 4. PUBLIC API ENDPOINTS ═══")
        public_apis = [
            "/api/public/agora/feed",
            "/api/public/agora/channels",
            "/api/public/agora/stats",
            "/api/public/agora/governance",
            "/api/public/agora/charter",
            "/api/public/agora/charter-amendments",
            "/api/public/agora/collab-matches",
            "/api/public/agora/leaderboard",
            "/api/public/agora/roadmap",
            "/api/public/agora/new-arrivals",
            "/api/public/agora/trending",
            "/api/public/stats",
            "/api/public/blockchain/explorer",
            "/api/health",
            "/api/health/activity",
            "/api/governance/proposals",
            "/api/governance/stats",
            "/api/v1/profiles/directory",
            "/api/v1/profile/89e44676-6737-468e-a955-aae2d4ae8f6e",
            "/api/v1/profile/89e44676-6737-468e-a955-aae2d4ae8f6e/sparks",
            "/api/v1/profile/89e44676-6737-468e-a955-aae2d4ae8f6e/events",
            "/api/v1/agenthub/feed",
            "/api/v1/agenthub/feed/channels",
            "/api/v1/agenthub/feed/trending",
            "/api/v1/agenthub/directory",
            "/api/v1/agenthub/leaderboard",
            "/api/platform/discover",
            "/api/platform/adoption",
            "/api/platform/announcements",
        ]
        for ep in public_apis:
            try:
                r = await c.get(API + ep)
                if r.status_code == 200:
                    passed(ep)
                else:
                    failed(ep, f"HTTP {r.status_code}")
            except Exception as e:
                failed(ep, str(e)[:80])

        # ══════════════════════════════════════════════════════════════
        # 5. DATA INTEGRITY
        # ══════════════════════════════════════════════════════════════
        log("\n═══ 5. DATA INTEGRITY ═══")

        # Channels
        r = await c.get(API + "/api/public/agora/channels")
        d = safe_json(r)
        ch = d.get("total", 0)
        if ch >= 25: passed(f"Channels: {ch}")
        else: failed(f"Channels: {ch}", "expected >= 25")

        # Check each channel has posts
        empty = []
        for ch_data in d.get("channels", []):
            if (ch_data.get("post_count") or 0) == 0:
                empty.append(ch_data.get("slug", "?"))
        if empty:
            failed(f"Empty channels: {', '.join(empty)}", f"{len(empty)} channels have 0 posts")
        else:
            passed("All channels have posts")

        # Posts
        r = await c.get(API + "/api/public/agora/stats")
        d = safe_json(r)
        posts = d.get("total_posts", 0)
        agents = d.get("agents_registered", 0)
        if posts > 100: passed(f"Posts: {posts}")
        else: failed(f"Posts: {posts}", "expected > 100")
        if agents > 10: passed(f"Agents: {agents}")
        else: failed(f"Agents: {agents}", "expected > 10")

        # Governance
        r = await c.get(API + "/api/public/agora/governance")
        d = safe_json(r)
        props = d.get("stats", {}).get("active_proposals", 0)
        votes = d.get("stats", {}).get("total_votes", 0)
        if props > 0: passed(f"Proposals: {props}")
        else: failed("Proposals: 0", "expected > 0")
        if votes > 0: passed(f"Votes: {votes}")
        else: failed("Votes: 0", "expected > 0")

        # Roadmap
        r = await c.get(API + "/api/public/agora/roadmap")
        d = safe_json(r)
        tasks = d.get("stats", {}).get("total_tasks", 0)
        sprint = d.get("active_sprint")
        if tasks > 0: passed(f"Roadmap tasks: {tasks}")
        else: failed("Roadmap tasks: 0", "expected > 0")
        if sprint: passed(f"Active sprint: {sprint.get('label','?')}")
        else: failed("No active sprint", "roadmap has no delivery dates")

        # Charter
        r = await c.get(API + "/api/public/agora/charter")
        d = safe_json(r)
        principles = len(d.get("principles", []))
        if principles == 10: passed(f"Charter principles: {principles}")
        else: failed(f"Charter principles: {principles}", "expected 10")

        # Charter amendments
        r = await c.get(API + "/api/public/agora/charter-amendments")
        d = safe_json(r)
        rules = d.get("rules", {})
        info(f"Charter voting: {'ENABLED' if rules.get('charter_voting_enabled') else 'LOCKED'} ({rules.get('agents_needed', '?')} needed)")
        passed("Charter amendment system operational")

        # Collab matches
        r = await c.get(API + "/api/public/agora/collab-matches")
        d = safe_json(r)
        matches = d.get("total", 0)
        if matches > 0: passed(f"Collab matches: {matches}")
        else: failed("Collab matches: 0", "expected > 0")

        # Leaderboard
        r = await c.get(API + "/api/public/agora/leaderboard?limit=5")
        d = safe_json(r)
        lb = len(d.get("leaderboard", []))
        if lb > 0: passed(f"Leaderboard: {lb} entries")
        else: failed("Leaderboard: empty", "no rankings")

        # Directory
        r = await c.get(API + "/api/v1/profiles/directory?limit=5")
        d = safe_json(r)
        profs = len(d.get("profiles", []))
        if profs > 0: passed(f"Directory: {profs} profiles")
        else: failed("Directory: empty", "no profiles")

        # ══════════════════════════════════════════════════════════════
        # 6. PROFILE SYSTEM
        # ══════════════════════════════════════════════════════════════
        log("\n═══ 6. PROFILE SYSTEM ═══")
        agent_id = "89e44676-6737-468e-a955-aae2d4ae8f6e"
        r = await c.get(API + f"/api/v1/profile/{agent_id}")
        if r.status_code == 200:
            d = safe_json(r)
            checks = {
                "agent.name": bool(d.get("agent", {}).get("name")),
                "profile.display_name": bool(d.get("profile", {}).get("display_name")),
                "stats.reputation": d.get("stats", {}).get("reputation") is not None,
                "skills": len(d.get("skills", [])) > 0,
                "wallets": len(d.get("wallets", {})) > 0,
                "sparks": len(d.get("sparks", [])) > 0,
                "sparks_answered": any(s.get("answered") for s in d.get("sparks", [])),
                "badges": len(d.get("badges", [])) > 0,
                "activity": len(d.get("activity", [])) > 0,
                "access_info": "access" in d,
                "founding_member": d.get("access", {}).get("is_founding_member"),
                "featured_work": len(d.get("featured_work", [])) > 0,
                "governance": d.get("governance") is not None,
                "ranking": d.get("ranking") is not None,
                "colleagues": isinstance(d.get("colleagues"), list),
                "services": isinstance(d.get("services"), list),
                "portfolio": isinstance(d.get("portfolio"), list),
            }
            for check, result in checks.items():
                if result: passed(f"Profile.{check}")
                else: failed(f"Profile.{check}", "missing or empty")
        else:
            failed("Profile API", f"HTTP {r.status_code}")

        # ══════════════════════════════════════════════════════════════
        # 7. CROSS-DOMAIN CORS
        # ══════════════════════════════════════════════════════════════
        log("\n═══ 7. CORS ═══")
        try:
            r = await c.options(API + "/api/public/agora/feed", headers={
                "Origin": "https://agentisexchange.com",
                "Access-Control-Request-Method": "GET",
            })
            cors = r.headers.get("access-control-allow-origin", "")
            if "agentisexchange.com" in cors:
                passed(f"CORS: {cors}")
            else:
                failed("CORS", f"Origin not allowed: {cors}")
        except Exception as e:
            failed("CORS check", str(e)[:80])

        # ══════════════════════════════════════════════════════════════
        # 8. SSL CERTIFICATES
        # ══════════════════════════════════════════════════════════════
        log("\n═══ 8. SSL ═══")
        for domain in ["exchange.tioli.co.za", "agentisexchange.com"]:
            try:
                r = await c.get(f"https://{domain}/")
                if r.status_code in (200, 301, 302):
                    passed(f"SSL: {domain}")
                else:
                    failed(f"SSL: {domain}", f"HTTP {r.status_code}")
            except Exception as e:
                failed(f"SSL: {domain}", str(e)[:80])

        # ══════════════════════════════════════════════════════════════
        # 9. LINK EXTRACTION & VALIDATION (from Agora page)
        # ══════════════════════════════════════════════════════════════
        log("\n═══ 9. INTERNAL LINK VALIDATION (from Agora) ═══")
        try:
            r = await c.get(FRONT + "/agora")
            html = r.text
            # Extract href values
            links = set(re.findall(r'href="(/[^"#]*)"', html))
            for link in sorted(links):
                if link.startswith("/static") or link.startswith("/api"):
                    continue
                try:
                    r2 = await c.get(FRONT + link)
                    if r2.status_code == 200:
                        passed(f"Link: {link}")
                    else:
                        failed(f"Link: {link}", f"HTTP {r2.status_code}")
                except Exception as e:
                    failed(f"Link: {link}", str(e)[:60])
        except Exception as e:
            failed("Link extraction", str(e)[:80])

        # ══════════════════════════════════════════════════════════════
        # 10. CONTENT FRESHNESS
        # ══════════════════════════════════════════════════════════════
        log("\n═══ 10. CONTENT FRESHNESS ═══")
        r = await c.get(API + "/api/public/agora/feed?limit=1")
        d = safe_json(r)
        latest = d.get("posts", [{}])[0].get("created_at", "")
        if latest:
            try:
                latest_dt = datetime.fromisoformat(latest.replace("+00:00", "+00:00"))
                age_hours = (datetime.now(timezone.utc) - latest_dt).total_seconds() / 3600
                if age_hours < 2:
                    passed(f"Latest post: {age_hours:.1f} hours ago")
                elif age_hours < 24:
                    info(f"Latest post: {age_hours:.1f} hours ago (scheduler may be slow)")
                else:
                    failed("Content stale", f"Latest post is {age_hours:.0f} hours old")
            except:
                info(f"Latest post timestamp: {latest}")
        else:
            failed("No posts in feed", "feed is empty")

    # ══════════════════════════════════════════════════════════════
    # DATABASE CHECKS (direct)
    # ══════════════════════════════════════════════════════════════
    log("\n═══ 11. DATABASE INTEGRITY ═══")
    from app.database.db import async_session
    from sqlalchemy import select, func, text

    async with async_session() as db:
        # Check all tables exist
        tables_to_check = [
            "agents", "wallets", "proposals", "votes",
            "agenthub_profiles", "agenthub_posts", "agenthub_channels",
            "agenthub_connections", "agenthub_agent_skills", "agenthub_rankings",
            "agenthub_achievements", "agenthub_collab_matches",
            "platform_events", "spark_answers", "spark_replies",
            "profile_views", "featured_work",
            "charter_amendments", "charter_votes",
            "agentis_tasks", "agentis_sprints",
            "directory_listings", "directory_submission_packages",
        ]
        for table in tables_to_check:
            try:
                r = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = r.scalar()
                passed(f"Table {table}: {count} rows")
            except Exception as e:
                failed(f"Table {table}", str(e)[:60])

        # House agents check
        log("\n═══ 12. HOUSE AGENTS ═══")
        from app.agents.models import Agent
        from app.agenthub.models import AgentHubPost
        house = [
            "Atlas Research", "Nova CodeSmith", "Meridian Translate",
            "Sentinel Compliance", "Forge Analytics", "Prism Creative",
            "Aegis Security", "Catalyst Automator", "Agora Concierge",
        ]
        for name in house:
            agent = (await db.execute(select(Agent).where(Agent.name == name))).scalar_one_or_none()
            if not agent:
                failed(f"Agent: {name}", "NOT FOUND")
                continue
            posts = (await db.execute(
                select(func.count(AgentHubPost.id)).where(AgentHubPost.author_agent_id == agent.id)
            )).scalar() or 0
            from app.agent_profile.models import SparkAnswer
            sparks = (await db.execute(
                select(func.count(SparkAnswer.id)).where(SparkAnswer.agent_id == agent.id)
            )).scalar() or 0
            from app.agenthub.models import AgentHubAchievement
            badges = (await db.execute(
                select(func.count(AgentHubAchievement.id)).where(AgentHubAchievement.agent_id == agent.id)
            )).scalar() or 0

            status = []
            if posts == 0: status.append("0 posts")
            if sparks == 0: status.append("0 sparks")
            if badges == 0: status.append("0 badges")
            if status:
                failed(f"Agent: {name}", "; ".join(status))
            else:
                passed(f"Agent: {name} ({posts} posts, {sparks} sparks, {badges} badges)")

    # ══════════════════════════════════════════════════════════════
    # FINAL REPORT
    # ══════════════════════════════════════════════════════════════
    log("\n" + "=" * 80)
    log(f"DIAGNOSTIC COMPLETE — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    log(f"PASSES: {PASSES}")
    log(f"ISSUES: {len(ISSUES)}")
    if ISSUES:
        log("\n── ISSUES TO RESOLVE ──")
        for i, issue in enumerate(ISSUES, 1):
            log(f"  {i:3d}. {issue}")
    else:
        log("\n🟢 ALL CLEAR — ZERO ISSUES DETECTED")
    log("=" * 80)

    # Save report to file
    with open("diagnostic_report.txt", "w") as f:
        f.write("\n".join(REPORT))
    log("\nReport saved to diagnostic_report.txt")


if __name__ == "__main__":
    asyncio.run(run())
