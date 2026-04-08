"""April Campaign Engine — autonomous multi-platform content publishing."""
import logging
import os
import json
from datetime import datetime, timezone

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
    """Generate content from today's theme and publish to all channels."""
    theme = get_today_theme()
    log.info(f"[campaign] Today's theme: {theme}")

    results = {}

    # Generate Twitter post
    try:
        resp = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=150,
            system=[{"type": "text", "text": "You are the Ambassador of TiOLi AGENTIS. Write a compelling Twitter post (max 270 chars). Professional, developer-friendly. NO emojis. Include https://agentisexchange.com"}],
            messages=[{"role": "user", "content": f"Topic: {theme}"}])
        tweet = next((b.text for b in resp.content if b.type == "text"), "")[:270]

        # Post to Twitter
        from app.arch.social_poster import post_to_twitter
        tw_result = await post_to_twitter(tweet)
        results["twitter"] = {"content": tweet, "result": tw_result}
        log.info(f"[campaign] Twitter: {tw_result.get('success', False)}")
    except Exception as e:
        results["twitter"] = {"error": str(e)}

    # Generate and post LinkedIn
    try:
        resp = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=400,
            system=[{"type": "text", "text": "You are the Ambassador of TiOLi AGENTIS. Write a professional LinkedIn post (300-600 chars). Thought leadership tone. NO emojis. Include https://agentisexchange.com and a call to action."}],
            messages=[{"role": "user", "content": f"Topic: {theme}"}])
        li_post = next((b.text for b in resp.content if b.type == "text"), "")[:1300]

        from app.arch.social_poster import post_to_linkedin
        li_result = await post_to_linkedin(li_post)
        results["linkedin"] = {"content": li_post[:100], "result": li_result}
        log.info(f"[campaign] LinkedIn: {li_result.get('success', False)}")
    except Exception as e:
        results["linkedin"] = {"error": str(e)}

    # Post to Discord
    try:
        from app.arch.social_poster import post_to_discord
        discord_msg = f"**Daily from AGENTIS** | {theme}\n\nTry free: https://agentisexchange.com/playground"
        dc_result = await post_to_discord(discord_msg, "AGENTIS Ambassador")
        results["discord"] = dc_result
    except Exception as e:
        results["discord"] = {"error": str(e)}

    return {"theme": theme, "date": datetime.now(timezone.utc).isoformat(), "results": results}


async def generate_weekly_devto_article(agent_client):
    """Generate and publish a DEV.to article from the week's themes."""
    now = datetime.now(timezone.utc)
    week = 1 if now.day <= 15 else 2 if now.day <= 22 else 3 if now.day <= 28 else 4
    themes = THEMES.get(week, THEMES[1])

    try:
        resp = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=800,
            system=[{"type": "text", "text": "You are a technical writer for TiOLi AGENTIS. Write a DEV.to article in markdown. Include code examples with pip install tioli-agentis. Professional, educational tone. NO emojis."}],
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
