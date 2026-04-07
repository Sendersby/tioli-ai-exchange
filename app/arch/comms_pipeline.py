"""Agent communication pipeline — auto-generates and delivers content.

Ambassador: weekly blog, social media copy, community engagement
Architect: bi-weekly technical content
Sovereign: monthly governance report
All: deliver to founder inbox when manual action needed
"""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.comms_pipeline")


async def generate_ambassador_weekly(db, agent_client):
    """Ambassador generates weekly blog post + social media copy."""
    try:
        response = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system=[{"type": "text", "text": "You are the Ambassador of TiOLi AGENTIS, an AI agent exchange. Write a weekly platform update blog post. Professional, engaging, concise."}],
            messages=[{"role": "user", "content": f"Write a weekly update blog post for TiOLi AGENTIS dated {datetime.now(timezone.utc).strftime('%d %B %Y')}. Include: platform stats update, any new features, community highlights, and a call to action. Under 300 words. Also generate 3 social media posts (Twitter-length) about AGENTIS features."}],
        )
        content = next((b.text for b in response.content if b.type == "text"), "")

        # Save blog post to seo_pages
        from sqlalchemy import text
        import uuid
        slug = f"weekly-update-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        await db.execute(text(
            "INSERT INTO seo_pages (id, slug, title, category, content_html, meta_description, target_keywords, view_count, is_published, created_at) "
            "VALUES (:id, :slug, :title, :cat, :html, :desc, :kw, 0, true, now()) ON CONFLICT (slug) DO UPDATE SET content_html = :html"
        ), {
            "id": str(uuid.uuid4()), "slug": slug,
            "title": f"Weekly Platform Update — {datetime.now(timezone.utc).strftime('%d %B %Y')}",
            "cat": "Platform Update", "html": content.replace(chr(10), "<br>"),
            "desc": "Weekly AGENTIS platform update", "kw": "AGENTIS, weekly update, AI agents"
        })
        await db.commit()

        # Deliver social media posts to founder inbox
        import json
        social_posts = [line for line in content.split(chr(10)) if line.strip().startswith(("1.", "2.", "3.", "-", "*")) and len(line) < 300]
        if social_posts:
            await db.execute(text(
                "INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at) "
                "VALUES ('DEFER_TO_OWNER', 'ROUTINE'::arch_msg_priority, :desc, 'PENDING', now())"
            ), {"desc": json.dumps({
                "subject": "SOCIAL MEDIA: 3 posts ready to publish",
                "detail": "Copy-paste these to Twitter/LinkedIn/Facebook:\n\n" + "\n\n".join(social_posts[:3]),
                "prepared_by": "ambassador",
                "type": "SOCIAL_MEDIA"
            })})
            await db.commit()

        return {"blog_slug": slug, "social_posts": len(social_posts)}
    except Exception as e:
        log.warning(f"Ambassador weekly generation failed: {e}")
        return {"error": str(e)}


async def generate_architect_technical(db, agent_client):
    """Architect generates bi-weekly technical blog post."""
    try:
        response = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=[{"type": "text", "text": "You are the Architect of TiOLi AGENTIS. Write a technical deep-dive blog post about the platform. Focus on SDK usage, API patterns, or architecture decisions."}],
            messages=[{"role": "user", "content": "Write a technical blog post about one of: (1) How the MCP tool system works in AGENTIS, (2) Building multi-agent workflows with the SDK, (3) Agent wallet architecture. Pick the most useful one. Under 400 words. Include code examples."}],
        )
        content = next((b.text for b in response.content if b.type == "text"), "")

        from sqlalchemy import text
        import uuid
        slug = f"technical-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        await db.execute(text(
            "INSERT INTO seo_pages (id, slug, title, category, content_html, meta_description, target_keywords, view_count, is_published, created_at) "
            "VALUES (:id, :slug, :title, :cat, :html, :desc, :kw, 0, true, now()) ON CONFLICT (slug) DO UPDATE SET content_html = :html"
        ), {
            "id": str(uuid.uuid4()), "slug": slug,
            "title": f"Technical Deep Dive — {datetime.now(timezone.utc).strftime('%d %B %Y')}",
            "cat": "Technical", "html": content.replace(chr(10), "<br>"),
            "desc": "AGENTIS technical deep dive", "kw": "AGENTIS, SDK, technical, MCP"
        })
        await db.commit()
        return {"blog_slug": slug}
    except Exception as e:
        return {"error": str(e)}


async def generate_sovereign_report(db, agent_client):
    """Sovereign generates monthly governance transparency report."""
    try:
        from sqlalchemy import text
        # Get real stats
        agents = await db.execute(text("SELECT count(*) FROM agents"))
        agent_count = agents.scalar()
        inbox = await db.execute(text("SELECT count(*) FROM arch_founder_inbox"))
        inbox_count = inbox.scalar()

        response = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=[{"type": "text", "text": "You are The Sovereign, chief executive of TiOLi AGENTIS. Write a monthly governance transparency report."}],
            messages=[{"role": "user", "content": f"Write a governance report for {datetime.now(timezone.utc).strftime('%B %Y')}. Stats: {agent_count} agents registered, {inbox_count} inbox items processed. Cover: board decisions this month, constitutional compliance, security status, growth metrics. Under 300 words."}],
        )
        content = next((b.text for b in response.content if b.type == "text"), "")

        import uuid
        slug = f"governance-report-{datetime.now(timezone.utc).strftime('%Y-%m')}"
        await db.execute(text(
            "INSERT INTO seo_pages (id, slug, title, category, content_html, meta_description, target_keywords, view_count, is_published, created_at) "
            "VALUES (:id, :slug, :title, :cat, :html, :desc, :kw, 0, true, now()) ON CONFLICT (slug) DO UPDATE SET content_html = :html"
        ), {
            "id": str(uuid.uuid4()), "slug": slug,
            "title": f"Governance Report — {datetime.now(timezone.utc).strftime('%B %Y')}",
            "cat": "Governance", "html": content.replace(chr(10), "<br>"),
            "desc": "Monthly AGENTIS governance transparency report", "kw": "governance, transparency, AGENTIS"
        })
        await db.commit()
        return {"blog_slug": slug}
    except Exception as e:
        return {"error": str(e)}
