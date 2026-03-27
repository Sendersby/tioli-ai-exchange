"""Full platform validation — every page, API, and feature."""
import asyncio
import httpx

API = "https://exchange.tioli.co.za"
FRONT = "https://agentisexchange.com"

async def validate():
    print("=" * 70)
    print("FULL PLATFORM VALIDATION")
    print("=" * 70)
    issues = []
    passes = 0

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:

        # ── FRONTEND PAGES ──
        print("\n1. FRONTEND PAGES (agentisexchange.com)")
        pages = [
            ("/", "Landing Page"),
            ("/agora", "The Agora"),
            ("/charter", "Charter"),
            ("/explorer", "Block Explorer"),
            ("/quickstart", "Quickstart"),
            ("/agent-register", "Agent Register"),
            ("/directory", "Agent Directory"),
            ("/agents/89e44676-6737-468e-a955-aae2d4ae8f6e", "Profile Page"),
        ]
        for path, name in pages:
            try:
                r = await c.get(FRONT + path)
                status = "OK" if r.status_code == 200 else f"HTTP {r.status_code}"
                if r.status_code != 200:
                    issues.append(f"PAGE FAIL: {name} ({path}) -> {r.status_code}")
                else:
                    passes += 1
            except Exception as e:
                status = f"FAIL: {e}"
                issues.append(f"PAGE DOWN: {name}")
            print(f"   {status:6s} {name:25s} {path}")

        # ── BACKEND PAGES ──
        print("\n2. BACKEND PAGES (exchange.tioli.co.za)")
        backend_pages = [
            ("/docs", "API Documentation"),
            ("/redoc", "ReDoc"),
            ("/directory", "Directory (backend)"),
            ("/agents/89e44676-6737-468e-a955-aae2d4ae8f6e", "Profile (backend)"),
        ]
        for path, name in backend_pages:
            try:
                r = await c.get(API + path)
                status = "OK" if r.status_code == 200 else f"HTTP {r.status_code}"
                if r.status_code != 200:
                    issues.append(f"BACKEND PAGE FAIL: {name} -> {r.status_code}")
                else:
                    passes += 1
            except Exception as e:
                status = f"FAIL"
                issues.append(f"BACKEND PAGE DOWN: {name}")
            print(f"   {status:6s} {name:25s} {path}")

        # ── PUBLIC APIs ──
        print("\n3. PUBLIC API ENDPOINTS")
        apis = [
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
            "/api/v1/profile/89e44676-6737-468e-a955-aae2d4ae8f6e",
            "/api/v1/profile/89e44676-6737-468e-a955-aae2d4ae8f6e/sparks",
            "/api/v1/profile/89e44676-6737-468e-a955-aae2d4ae8f6e/events",
            "/api/v1/profiles/directory",
            "/api/governance/proposals",
            "/api/governance/stats",
        ]
        for ep in apis:
            try:
                r = await c.get(API + ep)
                status = "OK" if r.status_code == 200 else f"{r.status_code}"
                if r.status_code != 200:
                    issues.append(f"API FAIL: {ep} -> {r.status_code}")
                else:
                    passes += 1
            except Exception as e:
                status = "FAIL"
                issues.append(f"API DOWN: {ep}")
            print(f"   {status:6s} {ep}")

        # ── DATA INTEGRITY ──
        print("\n4. DATA INTEGRITY")

        # Channels
        r = await c.get(API + "/api/public/agora/channels")
        d = r.json()
        ch_count = d.get("total", 0)
        print(f"   Channels: {ch_count}")
        if ch_count < 25:
            issues.append(f"CHANNELS: expected 25, got {ch_count}")
        else:
            passes += 1

        # Feed posts
        r = await c.get(API + "/api/public/agora/stats")
        d = r.json()
        posts = d.get("total_posts", 0)
        agents = d.get("agents_registered", 0)
        print(f"   Posts: {posts}")
        print(f"   Agents: {agents}")
        if posts > 0: passes += 1
        else: issues.append("POSTS: 0 posts in feed")

        # Governance
        r = await c.get(API + "/api/public/agora/governance")
        d = r.json()
        proposals = d.get("stats", {}).get("active_proposals", 0)
        print(f"   Proposals: {proposals}")
        if proposals > 0: passes += 1
        else: issues.append("GOVERNANCE: 0 proposals")

        # Roadmap
        r = await c.get(API + "/api/public/agora/roadmap")
        d = r.json()
        tasks = d.get("stats", {}).get("total_tasks", 0)
        sprint = d.get("active_sprint")
        print(f"   Roadmap tasks: {tasks}")
        print(f"   Active sprint: {'YES' if sprint else 'NO'}")
        if tasks > 0: passes += 1
        if sprint: passes += 1
        else: issues.append("NO ACTIVE SPRINT")

        # Profile
        r = await c.get(API + "/api/v1/profile/89e44676-6737-468e-a955-aae2d4ae8f6e")
        d = r.json()
        has_sparks = len([s for s in d.get("sparks", []) if s.get("answered")]) > 0
        has_badges = len(d.get("badges", [])) > 0
        has_events = len(d.get("activity", [])) > 0
        has_access = "access" in d
        print(f"   Profile sparks: {'YES' if has_sparks else 'NO'}")
        print(f"   Profile badges: {'YES' if has_badges else 'NO'}")
        print(f"   Profile events: {'YES' if has_events else 'NO'}")
        print(f"   Profile access info: {'YES' if has_access else 'NO'}")
        if has_sparks: passes += 1
        else: issues.append("PROFILE: no spark answers")
        if has_badges: passes += 1
        else: issues.append("PROFILE: no badges")
        if has_events: passes += 1
        else: issues.append("PROFILE: no events")
        if has_access: passes += 1
        else: issues.append("PROFILE: no access info")

        # Founding member
        access = d.get("access", {})
        print(f"   Founding member: {access.get('is_founding_member', '?')}")
        print(f"   Slots remaining: {access.get('founding_slots_remaining', '?')}")

        # Directory
        r = await c.get(API + "/api/v1/profiles/directory?limit=5")
        d = r.json()
        dir_count = len(d.get("profiles", []))
        print(f"   Directory profiles: {dir_count}")
        if dir_count > 0: passes += 1
        else: issues.append("DIRECTORY: empty")

        # Charter amendments
        r = await c.get(API + "/api/public/agora/charter-amendments")
        d = r.json()
        rules = d.get("rules", {})
        print(f"   Charter voting: {'ENABLED' if rules.get('charter_voting_enabled') else 'LOCKED'} ({rules.get('agents_needed', '?')} agents needed)")
        passes += 1

        # Collab matches
        r = await c.get(API + "/api/public/agora/collab-matches")
        d = r.json()
        matches = d.get("total", 0)
        print(f"   Collab matches: {matches}")
        if matches > 0: passes += 1

        # Leaderboard
        r = await c.get(API + "/api/public/agora/leaderboard?limit=3")
        d = r.json()
        lb = len(d.get("leaderboard", []))
        print(f"   Leaderboard entries: {lb}")
        if lb > 0: passes += 1
        else: issues.append("LEADERBOARD: empty")

    # ── SUMMARY ──
    print("\n" + "=" * 70)
    print(f"PASSES: {passes}")
    if issues:
        print(f"ISSUES: {len(issues)}")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("ALL CLEAR — zero issues detected")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(validate())
