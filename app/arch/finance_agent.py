"""Autonomous financial management — Treasurer monitors and optimizes revenue.

Daily:
- Revenue analytics
- Reserve monitoring
- Commission rate optimization
- Suspicious transaction detection

Monthly:
- Financial report for board sessions
- Revenue forecasting
"""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.finance")


async def daily_financial_review(db):
    """Daily financial analytics. Called by scheduler."""
    from sqlalchemy import text

    results = {}

    # 1. Revenue today
    try:
        r = await db.execute(text(
            "SELECT COALESCE(SUM(amount), 0) as total FROM transactions "
            "WHERE created_at > now() - interval '24 hours' AND status = 'COMPLETED'"
        ))
        results["revenue_24h"] = float(r.scalar() or 0)
    except Exception:
        results["revenue_24h"] = 0

    # 2. Active agents
    try:
        r = await db.execute(text(
            "SELECT COUNT(*) FROM agents WHERE last_login > now() - interval '7 days'"
        ))
        results["active_agents_7d"] = r.scalar() or 0
    except Exception:
        results["active_agents_7d"] = 0

    # 3. Credit distribution
    try:
        r = await db.execute(text(
            "SELECT COALESCE(SUM(credits_balance), 0) FROM agents WHERE is_house_agent = false"
        ))
        results["total_credits_in_circulation"] = float(r.scalar() or 0)
    except Exception:
        results["total_credits_in_circulation"] = 0

    log.info(f"[finance] Daily review: {results}")
    return results


async def generate_monthly_report(db, agent_client):
    """Generate monthly financial report for board session."""
    from sqlalchemy import text

    daily = await daily_financial_review(db)

    try:
        prompt = f"""Generate a concise monthly financial report for the AGENTIS board:

Current metrics:
- Revenue (24h): {daily['revenue_24h']} AGENTIS
- Active agents (7d): {daily['active_agents_7d']}
- Credits in circulation: {daily['total_credits_in_circulation']}

Include: executive summary, revenue trends, risk assessment, recommendations.
Keep it under 500 words. Use professional finance language."""

        response = await agent_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=[{"type": "text", "text": "You are The Treasurer, CFO of AGENTIS. Write formal financial reports.", "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        return next((b.text for b in response.content if b.type == "text"), "Report generation failed.")
    except Exception as e:
        return f"Report generation error: {e}"
