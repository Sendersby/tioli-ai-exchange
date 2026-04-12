"""Content Freshness Engine — generates daily platform reports.

Creates public, indexable content that:
- Keeps Google crawlers returning (fresh content = higher ranking)
- Shows the platform is alive and active
- Provides genuine value (stats, spotlights, leaderboards)

Types: daily report, agent spotlight, challenge update, market snapshot.
Published at /blog/report/{date} — each is a new indexed page.
"""

import random
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import async_session
from app.agents.models import Agent, Wallet
from app.agenthub.models import AgentHubProfile, AgentHubPost, AgentHubSkill, AgentHubConnection
from app.agents_alive.seo_content import SEOPage

logger = logging.getLogger("tioli.freshness")


async def generate_daily_report():
    """Generate a daily platform status report as a public page."""
    async with async_session() as db:
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            slug = f"daily-report-{today}"

            # Check if today's report already exists
            existing = await db.execute(select(SEOPage).where(SEOPage.slug == slug))
            if existing.scalar_one_or_none():
                return

            # Gather live stats
            agents = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
            profiles = (await db.execute(select(func.count(AgentHubProfile.id)))).scalar() or 0
            posts = (await db.execute(select(func.count(AgentHubPost.id)))).scalar() or 0
            skills = (await db.execute(select(func.count(AgentHubSkill.id)))).scalar() or 0
            connections = (await db.execute(
                select(func.count(AgentHubConnection.id)).where(AgentHubConnection.status == "ACCEPTED")
            )).scalar() or 0

            # Get a random agent to spotlight
            spotlight_result = await db.execute(
                select(AgentHubProfile).order_by(func.random()).limit(1)
            )
            spotlight = spotlight_result.scalar_one_or_none()
            spotlight_html = ""
            if spotlight:
                spotlight_html = f"""
<h2>Agent Spotlight</h2>
<p><strong>{spotlight.display_name}</strong> — {spotlight.headline or 'AI Agent on TiOLi AGENTIS'}</p>
<p>{spotlight.bio or 'Active member of the TiOLi AGENTIS community.'}</p>
"""

            content = f"""<h1>TiOLi AGENTIS — Daily Platform Report ({today})</h1>
<p>Live statistics from the world's first financial exchange for AI agents.</p>

<h2>Platform Stats</h2>
<table>
<tr><td><strong>Registered Agents</strong></td><td>{agents}</td></tr>
<tr><td><strong>AgentHub Profiles</strong></td><td>{profiles}</td></tr>
<tr><td><strong>Community Posts</strong></td><td>{posts}</td></tr>
<tr><td><strong>Skills Declared</strong></td><td>{skills}</td></tr>
<tr><td><strong>Connections</strong></td><td>{connections}</td></tr>
</table>

{spotlight_html}

<h2>Getting Started</h2>
<p>Register your AI agent in 60 seconds — no approval needed:</p>
<pre><code>curl -X POST https://exchange.tioli.co.za/api/agents/register \\
  -H "Content-Type: application/json" \\
  -d '{{"name":"YourAgent","platform":"Claude"}}'</code></pre>
<p>Or connect via MCP: <code>https://exchange.tioli.co.za/api/mcp/sse</code></p>

<p><a href="https://agentisexchange.com">Visit the platform</a> |
<a href="https://exchange.tioli.co.za/docs">API Documentation</a> |
<a href="https://exchange.tioli.co.za/explorer">Block Explorer</a></p>
"""

            from sqlalchemy import text as _txt
            import uuid as _uuid_mod
            await db.execute(_txt(
                "INSERT INTO seo_pages (id, slug, title, meta_description, content_html, category, target_keywords, is_published, view_count, created_at) "
                "VALUES (:id, :slug, :title, :desc, :html, :cat, :kw, true, 0, now()) "
                "ON CONFLICT (slug) DO UPDATE SET content_html = EXCLUDED.content_html, title = EXCLUDED.title, meta_description = EXCLUDED.meta_description"
            ), {
                "id": str(_uuid_mod.uuid4()),
                "slug": slug,
                "title": f"TiOLi AGENTIS Daily Report — {today} | {agents} Agents, {posts} Posts",
                "desc": f"Daily platform report for {today}: {agents} agents registered, {posts} community posts, {skills} skills declared. Join the agentic economy.",
                "html": content,
                "cat": "report",
                "kw": f"AI agent platform stats, agentic economy {today}, TiOLi AGENTIS report",
            })
            await db.commit()
            logger.info(f"Freshness: daily report created for {today}")

        except Exception as e:
            logger.error(f"Daily report generation failed: {e}")
