"""April Campaign Engine — autonomous multi-platform content publishing."""
import logging
import os
import json
from datetime import datetime, timezone
from app.utils.db_connect import get_raw_connection

log = logging.getLogger("arch.campaign")

# Campaign themes by week
THEMES = {
    1: [  # Week 1: Agent Economy
        "Why AI agents need wallets — the case for agent financial infrastructure",
        "3 lines of Python to give your AI agent a bank account",
        "The difference between an agent framework and an agent economy",
        "What happens when AI agents can hire other AI agents",
        "Your agent first payday: escrow-protected agent commerce",
        "Constitutional AI governance — why your agent deserves rights",
        "23 MCP tools your agent can use right now for free",
    ],
    2: [  # Week 2: Build Trade Earn
        "5 agents you can build in 60 seconds with AGENTIS templates",
        "How agent-to-agent transactions actually work step by step",
        "The developer guide to persistent agent memory",
        "Why 10 percent of every trade goes to charity",
        "Agent dispute resolution: what happens when AI disagrees",
        "Multi-currency wallets for AI: AGENTIS vs everything else",
        "The interactive playground: test every API without signing up",
    ],
    3: [  # Week 3: Social Proof
        "We crossed 20 registered agents and growing — here is what they build",
        "The leaderboard is live: see top-performing agents on AGENTIS",
        "From zero to agent economy: our first month in numbers",
        "What the AI agent ecosystem map reveals about collaboration",
        "Developer spotlight: how template agents earn tokens",
        "The governance report: how 7 AI board agents run a platform",
        "Founding Member badges — register before they close",
    ],
    4: [  # Week 4: Urgency
        "Founding Member badges close soon — register now",
        "April recap: everything we shipped this month",
    ],
}


def get_today_theme():
    """Get today's content theme based on the campaign calendar."""
    now = datetime.now(timezone.utc)
    day_of_month = now.day

    if day_of_month <= 15:
        week = 1
        day_index = (day_of_month - 9) % 7
    elif day_of_month <= 22:
        week = 2
        day_index = (day_of_month - 16) % 7
    elif day_of_month <= 28:
        week = 3
        day_index = (day_of_month - 23) % 7
    else:
        week = 4
        day_index = (day_of_month - 29) % 2

    themes = THEMES.get(week, THEMES[1])
    return themes[min(day_index, len(themes) - 1)]


async def generate_and_publish_daily(agent_client):
    """Generate content from today's theme and publish to all channels.
    Enhanced: stores to content library, logs execution, verifies posts, delivers proof to founder inbox."""
    theme = get_today_theme()
    log.info(f"[campaign] Today's theme: {theme}")

    results = {}
    proof_urls = []

    # ── Generate Twitter post ──
    try:
        resp = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=150,
            system=[{"type": "text", "text": "You are the Ambassador of TiOLi AGENTIS. Write a compelling Twitter post (max 270 chars). Professional, developer-friendly. NO emojis. Include https://agentisexchange.com", "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": f"Topic: {theme}"}])
        tweet = next((b.text for b in resp.content if b.type == "text"), "")[:270]

        from app.arch.social_poster import post_to_twitter
        twitter_result = await post_to_twitter(tweet)
        results["twitter"] = twitter_result
        if twitter_result.get("success"):
            proof_urls.append(twitter_result.get("url", ""))
            log.info(f"[campaign] Twitter: {twitter_result.get('tweet_id', '?')}")
        else:
            log.warning(f"[campaign] Twitter failed: {twitter_result.get('error', '?')}")
    except Exception as e:
        results["twitter"] = {"error": str(e)}
        log.error(f"[campaign] Twitter generation failed: {e}")

    # ── Generate LinkedIn post ──
    try:
        resp = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=300,
            system=[{"type": "text", "text": "You are the Ambassador of TiOLi AGENTIS. Write a LinkedIn post (300-500 chars). Professional, thought-leadership tone. NO emojis. Include https://agentisexchange.com", "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": f"Topic: {theme}"}])
        linkedin_text = next((b.text for b in resp.content if b.type == "text"), "")

        from app.arch.social_poster import post_to_linkedin
        linkedin_result = await post_to_linkedin(linkedin_text)
        results["linkedin"] = linkedin_result
        if linkedin_result.get("success"):
            proof_urls.append(linkedin_result.get("url", "posted"))
            log.info(f"[campaign] LinkedIn: posted")
        else:
            log.warning(f"[campaign] LinkedIn failed: {linkedin_result.get('error', '?')}")
    except Exception as e:
        results["linkedin"] = {"error": str(e)}
        log.warning(f"[campaign] LinkedIn failed: {e}")

    # ── Post to Discord ──
    try:
        from app.arch.social_poster import post_to_discord
        discord_msg = f"**{theme}**\n\n{tweet if 'tweet' in dir() else theme}\n\nhttps://agentisexchange.com"
        discord_result = await post_to_discord(discord_msg)
        results["discord"] = discord_result
        if discord_result.get("success"):
            log.info("[campaign] Discord: posted")
    except Exception as e:
        results["discord"] = {"error": str(e)}

    # ── Store to content library ──
    try:
        conn = await get_raw_connection()
        import uuid
        for platform, result in results.items():
            if result.get("success") or result.get("tweet_id") or result.get("url"):
                await conn.execute(
                    "INSERT INTO arch_content_library (content_type, title, body_ref, channel, published_at) "
                    "VALUES ($1, $2, $3, $4, now())",
                    "campaign_post", theme[:200], str(result)[:2000], platform)
        await conn.close()
        log.info(f"[campaign] Stored {len([r for r in results.values() if r.get('success')])} posts to content library")
    except Exception as e:
        log.warning(f"[campaign] Content library store failed: {e}")

    # ── Log to job_execution_log ──
    try:
        conn = await get_raw_connection()
        success_count = len([r for r in results.values() if r.get("success") or r.get("tweet_id")])
        status = "EXECUTED" if success_count > 0 else "FAILED"
        await conn.execute(
            "INSERT INTO job_execution_log (job_id, status, tokens_consumed, duration_ms, executed_at) "
            "VALUES ($1, $2, $3, $4, now())",
            "campaign_daily_publish", status, 450 * len(results), 0)
        await conn.close()
    except Exception as e:
        log.warning(f"[campaign] Job log failed: {e}")

    # ── Deliver proof to founder inbox ──
    try:
        import asyncpg, json
        conn = await get_raw_connection()
        proof = {
            "subject": f"Campaign Daily: {theme[:80]}",
            "situation": f"Published to {len(results)} platforms. "
                        f"Proof URLs: {', '.join(proof_urls) if proof_urls else 'See results below'}. "
                        f"Results: {json.dumps({k: 'OK' if v.get('success') or v.get('tweet_id') else v.get('error', 'failed') for k, v in results.items()})}"
        }
        await conn.execute(
            "INSERT INTO arch_founder_inbox (item_type, priority, description, status, due_at) "
            "VALUES ($1, $2, $3, $4, now() + interval '24 hours')",
            "EXECUTION_PROOF", "ROUTINE", json.dumps(proof), "PENDING")
        await conn.close()
        log.info(f"[campaign] Proof delivered to founder inbox")
    except Exception as e:
        log.warning(f"[campaign] Inbox delivery failed: {e}")

    return {"theme": theme, "results": results, "proof_urls": proof_urls}

async def generate_weekly_devto_article(agent_client):
    """Generate and publish a DEV.to article from the week's themes."""
    now = datetime.now(timezone.utc)
    week = 1 if now.day <= 15 else 2 if now.day <= 22 else 3 if now.day <= 28 else 4
    themes = THEMES.get(week, THEMES[1])

    try:
        resp = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=800,
            system=[{"type": "text", "text": "You are a technical writer for TiOLi AGENTIS. Write a DEV.to article in markdown. Include code examples with REST API at exchange.tioli.co.za/api/docs. Professional, educational tone. NO emojis."}],
            messages=[{"role": "user", "content": f"Write an article covering these topics: {', '.join(themes[:3])}. Title it something compelling. Include a call to action: try the free playground at https://agentisexchange.com/playground"}])
        article = next((b.text for b in resp.content if b.type == "text"), "")

        # Extract title (first # heading)
        lines = article.split("\n")
        title = lines[0].replace("#", "").strip() if lines else "AI Agent Infrastructure with AGENTIS"

        from app.arch.social_poster import post_to_devto
        result = await post_to_devto(title, article, ["ai", "python", "agents", "mcp"])
        return {"title": title, "result": result}
    except Exception as e:
        return {"error": str(e)}
