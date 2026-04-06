"""Newsletter agent — Ambassador generates weekly AGENTIS Exchange Digest.

Contents: platform stats, new agents, top performers, community highlights, market news.
"""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.newsletter")


async def generate_weekly_digest(db, agent_client):
    """Generate the weekly AGENTIS Exchange Digest."""
    from sqlalchemy import text

    # Gather stats
    stats = {}
    try:
        r = await db.execute(text("SELECT COUNT(*) FROM agents WHERE is_house_agent = false"))
        stats["total_agents"] = r.scalar() or 0
    except Exception:
        stats["total_agents"] = "N/A"

    try:
        r = await db.execute(text("SELECT COUNT(*) FROM agents WHERE created_at > now() - interval '7 days'"))
        stats["new_agents_week"] = r.scalar() or 0
    except Exception:
        stats["new_agents_week"] = 0

    try:
        r = await db.execute(text("SELECT COUNT(*) FROM transactions WHERE created_at > now() - interval '7 days'"))
        stats["transactions_week"] = r.scalar() or 0
    except Exception:
        stats["transactions_week"] = 0

    # Generate newsletter via Claude
    try:
        prompt = f"""Generate a weekly newsletter for the AGENTIS Exchange Digest.

Platform stats this week:
- Total registered agents: {stats['total_agents']}
- New agents this week: {stats['new_agents_week']}
- Transactions this week: {stats['transactions_week']}

Include sections:
1. This Week on AGENTIS (2-3 sentences)
2. Platform Highlights (bullet points)
3. Featured: Try the API Playground (link to /playground)
4. Community: Join The Agora (link to /agora)
5. Quick Start reminder (pip install tioli-agentis)

Keep it under 300 words. Friendly, professional tone. Include links to agentisexchange.com."""

        response = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=[{"type": "text", "text": "You are The Ambassador writing a developer newsletter. Be engaging and concise.", "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        return next((b.text for b in response.content if b.type == "text"), "Newsletter generation failed.")
    except Exception as e:
        return f"Newsletter error: {e}"
