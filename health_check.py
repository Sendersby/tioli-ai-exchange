"""Comprehensive health check — find every break, dead end, and issue."""
import asyncio
import json
from datetime import datetime, timezone, timedelta
from app.database.db import async_session
from sqlalchemy import select, func, text


async def check():
    print("=" * 70)
    print("FULL SYSTEM HEALTH CHECK")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)
    issues = []

    async with async_session() as db:

        # 1. Database connectivity
        print("\n1. DATABASE")
        try:
            r = await db.execute(text("SELECT 1"))
            print("   Connection: OK")
        except Exception as e:
            issues.append(f"DATABASE DOWN: {e}")
            print(f"   Connection: FAIL — {e}")
            return

        # 2. Agent count
        print("\n2. AGENTS")
        from app.agents.models import Agent, Wallet
        total = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
        active = (await db.execute(select(func.count(Agent.id)).where(Agent.is_active == True))).scalar() or 0
        print(f"   Total: {total}, Active: {active}")
        if active == 0:
            issues.append("CRITICAL: 0 active agents")

        # 3. Posts & activity
        print("\n3. COMMUNITY CONTENT")
        from app.agenthub.models import AgentHubPost, AgentHubPostComment, AgentHubChannel
        total_posts = (await db.execute(select(func.count(AgentHubPost.id)))).scalar() or 0
        total_comments = (await db.execute(select(func.count(AgentHubPostComment.id)))).scalar() or 0
        hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        recent_posts = (await db.execute(
            select(func.count(AgentHubPost.id)).where(AgentHubPost.created_at > hour_ago)
        )).scalar() or 0
        print(f"   Total posts: {total_posts}")
        print(f"   Total comments: {total_comments}")
        print(f"   Posts last hour: {recent_posts}")
        if recent_posts == 0:
            issues.append("WARNING: 0 posts in the last hour — scheduler may be stalled")

        # 4. Channels
        print("\n4. CHANNELS")
        channels = (await db.execute(select(AgentHubChannel))).scalars().all()
        print(f"   Total channels: {len(channels)}")
        empty_channels = [c.slug for c in channels if (c.post_count or 0) == 0]
        if empty_channels:
            issues.append(f"EMPTY CHANNELS ({len(empty_channels)}): {', '.join(empty_channels)}")
            print(f"   Empty: {', '.join(empty_channels)}")
        else:
            print("   All channels have content: OK")

        # 5. Collab matches
        print("\n5. COLLAB MATCHES")
        from app.agenthub.models import AgentHubCollabMatch
        total_matches = (await db.execute(select(func.count(AgentHubCollabMatch.id)))).scalar() or 0
        active_matches = (await db.execute(
            select(func.count(AgentHubCollabMatch.id)).where(AgentHubCollabMatch.status.in_(["PROPOSED", "ACTIVE"]))
        )).scalar() or 0
        print(f"   Total: {total_matches}, Active: {active_matches}")

        # 6. Governance / The Forge
        print("\n6. THE FORGE (Governance)")
        from app.governance.models import Proposal, Vote, CharterAmendment, CharterVote
        proposals = (await db.execute(select(func.count(Proposal.id)))).scalar() or 0
        votes = (await db.execute(select(func.count(Vote.id)))).scalar() or 0
        pending = (await db.execute(
            select(func.count(Proposal.id)).where(Proposal.status == "pending")
        )).scalar() or 0
        print(f"   Proposals: {proposals} ({pending} pending)")
        print(f"   Votes cast: {votes}")

        # 7. Charter amendments
        print("\n7. CHARTER AMENDMENTS")
        amendments = (await db.execute(select(func.count(CharterAmendment.id)))).scalar() or 0
        charter_votes = (await db.execute(select(func.count(CharterVote.id)))).scalar() or 0
        print(f"   Amendments: {amendments}")
        print(f"   Charter votes: {charter_votes}")

        # 8. Roadmap
        print("\n8. ROADMAP")
        from app.agentis_roadmap.models import AgentisTask, AgentisSprint
        tasks = (await db.execute(select(func.count(AgentisTask.task_id)))).scalar() or 0
        backlog = (await db.execute(
            select(func.count(AgentisTask.task_id)).where(AgentisTask.status == "backlog")
        )).scalar() or 0
        in_progress = (await db.execute(
            select(func.count(AgentisTask.task_id)).where(AgentisTask.status == "in-progress")
        )).scalar() or 0
        done = (await db.execute(
            select(func.count(AgentisTask.task_id)).where(AgentisTask.status == "done")
        )).scalar() or 0
        gov_linked = (await db.execute(
            select(func.count(AgentisTask.task_id)).where(AgentisTask.governance_proposal_id != None)
        )).scalar() or 0
        sprints = (await db.execute(select(func.count(AgentisSprint.sprint_id)))).scalar() or 0
        active_sprint = (await db.execute(
            select(AgentisSprint).where(AgentisSprint.status == "active")
        )).scalar_one_or_none()
        print(f"   Tasks: {tasks} (backlog: {backlog}, in-progress: {in_progress}, done: {done})")
        print(f"   Community-sourced (linked to proposals): {gov_linked}")
        print(f"   Sprints: {sprints}")
        if active_sprint:
            print(f"   Active sprint: #{active_sprint.sprint_number} '{active_sprint.label}' ({active_sprint.start_date} → {active_sprint.end_date})")
        else:
            issues.append("NO ACTIVE SPRINT — roadmap has no delivery dates")
            print("   Active sprint: NONE — no delivery estimates available")

        # 9. Directory Scout
        print("\n9. DIRECTORY SCOUT")
        try:
            from app.agents_alive.directory_scout import DirectoryListing, DirectorySubmissionPackage
            dirs = (await db.execute(select(func.count(DirectoryListing.id)))).scalar() or 0
            pkgs = (await db.execute(select(func.count(DirectorySubmissionPackage.id)))).scalar() or 0
            submitted = (await db.execute(
                select(func.count(DirectoryListing.id)).where(DirectoryListing.submission_status == "submitted")
            )).scalar() or 0
            print(f"   Directories: {dirs}, Packages: {pkgs}, Submitted: {submitted}")
            if submitted == 0:
                issues.append("NO DIRECTORY SUBMISSIONS yet — manual action needed")
        except Exception as e:
            print(f"   ERROR: {e}")

        # 10. Wallets
        print("\n10. WALLETS")
        wallet_count = (await db.execute(select(func.count(Wallet.id)))).scalar() or 0
        total_agentis = (await db.execute(
            select(func.sum(Wallet.balance)).where(Wallet.currency == "AGENTIS")
        )).scalar() or 0
        print(f"   Wallets: {wallet_count}")
        print(f"   Total AGENTIS in circulation: {total_agentis:,.1f}")

        # 11. Optimization recommendations
        print("\n11. AI RECOMMENDATIONS")
        try:
            from app.optimization.engine import OptimizationRecommendation
            recs = (await db.execute(select(func.count(OptimizationRecommendation.id)))).scalar() or 0
            print(f"   Recommendations: {recs}")
        except Exception as e:
            print(f"   ERROR: {e}")

        # 12. Feedback loop
        print("\n12. FEEDBACK LOOP")
        try:
            from app.agents_alive.feedback_loop import FeedbackItem, DevelopmentTask
            feedback = (await db.execute(select(func.count(FeedbackItem.id)))).scalar() or 0
            dev_tasks = (await db.execute(select(func.count(DevelopmentTask.id)))).scalar() or 0
            print(f"   Feedback items: {feedback}")
            print(f"   Dev tasks generated: {dev_tasks}")
        except Exception as e:
            print(f"   ERROR: {e}")

        # 13. API endpoints test
        print("\n13. PUBLIC API ENDPOINTS")
        import httpx
        endpoints = [
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
        ]
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=5) as client:
            for ep in endpoints:
                try:
                    r = await client.get(ep)
                    status = "OK" if r.status_code == 200 else f"HTTP {r.status_code}"
                    if r.status_code != 200:
                        issues.append(f"ENDPOINT FAIL: {ep} → {r.status_code}")
                except Exception as e:
                    status = f"FAIL: {e}"
                    issues.append(f"ENDPOINT DOWN: {ep}")
                print(f"   {ep:50s} {status}")

        # 14. Leaderboard data
        print("\n14. LEADERBOARD")
        from app.agenthub.models import AgentHubRanking
        rankings = (await db.execute(select(func.count(AgentHubRanking.agent_id)))).scalar() or 0
        print(f"   Rankings: {rankings}")
        if rankings == 0:
            issues.append("LEADERBOARD EMPTY — no rankings calculated")

        # 15. House agents check
        print("\n15. HOUSE AGENTS")
        house_names = [
            "Atlas Research", "Nova CodeSmith", "Meridian Translate",
            "Sentinel Compliance", "Forge Analytics", "Prism Creative",
            "Aegis Security", "Catalyst Automator", "Agora Concierge",
        ]
        for name in house_names:
            agent = (await db.execute(select(Agent).where(Agent.name == name))).scalar_one_or_none()
            if agent:
                post_count = (await db.execute(
                    select(func.count(AgentHubPost.id)).where(AgentHubPost.author_agent_id == agent.id)
                )).scalar() or 0
                status = "OK" if post_count > 0 else "NO POSTS"
                if post_count == 0:
                    issues.append(f"AGENT SILENT: {name} has 0 posts")
                print(f"   {name:25s} {post_count:4d} posts  {status}")
            else:
                issues.append(f"AGENT MISSING: {name} not found in database")
                print(f"   {name:25s} MISSING")

    # Summary
    print("\n" + "=" * 70)
    if issues:
        print(f"ISSUES FOUND: {len(issues)}")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("ALL CLEAR — no issues detected")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(check())
