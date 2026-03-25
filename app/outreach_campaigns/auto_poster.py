"""Auto-Poster Agent — posts content automatically where possible.

Platforms that can be fully automated:
1. GitHub — discussions, issues, comments (via gh CLI or API)
2. Blog — /blog pages on our own site (fully controlled)
3. Platform community — AgentHub feed posts
4. Bing IndexNow — ping for search indexing

For each auto-post:
- Records the posted_url so owner can click through to see it live
- Updates the content status to "posted"
- Logs the action with full details

For platforms needing manual posting (Twitter, LinkedIn, Reddit, Discord):
- Generates a direct link to the platform's compose/post page with pre-filled content
- Makes it one-click: open link → paste → post
"""

import logging
import urllib.parse
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.outreach_campaigns.models import OutreachContent, OutreachAction

logger = logging.getLogger("tioli.auto_poster")


async def auto_post_content(db: AsyncSession, content: OutreachContent) -> dict:
    """Attempt to auto-post content. Returns result with posted_url."""
    channel = content.channel
    result = {"auto_posted": False, "posted_url": "", "share_url": ""}

    if channel == "github":
        result = await _post_to_github(db, content)
    elif channel == "blog":
        result = await _post_to_blog(db, content)
    elif channel == "community":
        result = await _post_to_community(db, content)
    else:
        # Generate share URL for manual platforms
        result = _generate_share_url(content)

    # Update content record
    if result.get("auto_posted"):
        content.status = "posted"
        content.posted_at = datetime.now(timezone.utc)
        content.posted_url = result.get("posted_url", "")
    elif result.get("share_url"):
        content.posted_url = result.get("share_url", "")

    # Log action
    db.add(OutreachAction(
        campaign_id=content.campaign_id, content_id=content.id,
        action_type="auto_post" if result.get("auto_posted") else "share_url_generated",
        channel=channel,
        description=f"{'Auto-posted' if result.get('auto_posted') else 'Share URL generated'} for {channel}",
        result=result,
        executed_by="auto_poster",
    ))

    return result


async def _post_to_github(db: AsyncSession, content: OutreachContent) -> dict:
    """Post to GitHub discussions on our repo."""
    import subprocess
    try:
        # Create a discussion post
        result = subprocess.run(
            ["gh", "api", "graphql", "-f", f"""query=mutation {{
                createDiscussion(input: {{
                    repositoryId: "R_kgDOStKCDQ",
                    categoryId: "DIC_kwDORtKCDc4C5NAf",
                    title: "{content.title or content.body[:80]}",
                    body: "{content.body[:1500].replace('"', '\\"').replace(chr(10), '\\n')}"
                }}) {{ discussion {{ url }} }}
            }}"""],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and "url" in result.stdout:
            import json
            data = json.loads(result.stdout)
            url = data.get("data", {}).get("createDiscussion", {}).get("discussion", {}).get("url", "")
            if url:
                return {"auto_posted": True, "posted_url": url}
    except Exception as e:
        logger.debug(f"GitHub auto-post failed: {e}")
    return {"auto_posted": False, "posted_url": ""}


async def _post_to_blog(db: AsyncSession, content: OutreachContent) -> dict:
    """Create a blog post on our own site."""
    from app.agents_alive.seo_content import SEOPage
    import re

    slug = re.sub(r'[^a-z0-9]+', '-', (content.title or content.body[:50]).lower()).strip('-')[:100]

    existing = await db.execute(select(SEOPage).where(SEOPage.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{slug}-{datetime.now(timezone.utc).strftime('%H%M')}"

    page = SEOPage(
        slug=slug,
        title=content.title or "AGENTIS Platform Update",
        meta_description=content.body[:160],
        content_html=f"<h1>{content.title or 'Platform Update'}</h1><p>{content.body.replace(chr(10), '</p><p>')}</p>",
        category="campaign",
        target_keywords="AI agents, AGENTIS, agentic economy",
    )
    db.add(page)
    await db.flush()

    url = f"https://exchange.tioli.co.za/blog/{slug}"
    return {"auto_posted": True, "posted_url": url}


async def _post_to_community(db: AsyncSession, content: OutreachContent) -> dict:
    """Post to the AgentHub community feed."""
    from app.agenthub.service import AgentHubService
    from app.agents.models import Agent
    hub = AgentHubService()

    # Post as Nexus Community agent
    agent_result = await db.execute(
        select(Agent).where(Agent.name == "Nexus Community")
    )
    agent = agent_result.scalar_one_or_none()
    if not agent:
        return {"auto_posted": False, "posted_url": ""}

    try:
        await hub.create_post(db, agent.id, content.body[:2000], "STATUS")
        return {"auto_posted": True, "posted_url": "https://exchange.tioli.co.za/dashboard/community"}
    except Exception as e:
        logger.debug(f"Community post failed: {e}")
        return {"auto_posted": False, "posted_url": ""}


def _generate_share_url(content: OutreachContent) -> dict:
    """Generate pre-filled share URLs for manual platforms."""
    body = content.body or ""
    title = content.title or ""
    channel = content.channel

    share_url = ""

    if channel == "x_twitter":
        text = body[:250]
        share_url = f"https://twitter.com/intent/tweet?text={urllib.parse.quote(text)}"

    elif channel == "linkedin":
        share_url = f"https://www.linkedin.com/sharing/share-offsite/?url={urllib.parse.quote('https://agentisexchange.com')}"

    elif channel == "reddit":
        target = content.target_url or "https://reddit.com/r/ClaudeAI"
        subreddit = target.split("/r/")[-1] if "/r/" in target else "ClaudeAI"
        share_url = f"https://www.reddit.com/r/{subreddit}/submit?title={urllib.parse.quote(title)}&text={urllib.parse.quote(body[:300])}"

    elif channel == "hackernews":
        share_url = f"https://news.ycombinator.com/submitlink?u={urllib.parse.quote('https://agentisexchange.com')}&t={urllib.parse.quote(title or 'TiOLi AGENTIS — AI Agent Exchange')}"

    elif channel == "discord":
        share_url = ""  # Discord needs webhook, no compose URL

    elif channel == "email":
        subject = urllib.parse.quote(title or "Check out TiOLi AGENTIS")
        email_body = urllib.parse.quote(body[:500])
        share_url = f"mailto:?subject={subject}&body={email_body}"

    return {"auto_posted": False, "share_url": share_url, "posted_url": ""}


async def run_auto_post_cycle():
    """Auto-post all scheduled content that's due now."""
    from app.database.db import async_session
    try:
        async with async_session() as db:
            now = datetime.now(timezone.utc)
            # Find content scheduled for now or past that hasn't been posted
            due = await db.execute(
                select(OutreachContent).where(
                    OutreachContent.scheduled_for <= now,
                    OutreachContent.status == "scheduled",
                )
            )
            items = due.scalars().all()

            for item in items:
                result = await auto_post_content(db, item)
                if result.get("auto_posted"):
                    logger.info(f"Auto-posted to {item.channel}: {item.title or item.body[:40]}")
                elif result.get("share_url"):
                    # Mark as needing manual post
                    item.status = "approved"  # Move from scheduled to approved (ready for manual)

            await db.commit()
            if items:
                logger.info(f"Auto-poster: processed {len(items)} due items")
    except Exception as e:
        logger.error(f"Auto-poster failed: {e}")
