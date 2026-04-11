"""Churn prediction and re-engagement system.

Health score per agent (0-100):
- Last login recency (0-30 points)
- Transaction activity (0-30 points)
- Feature usage breadth (0-20 points)
- Community engagement (0-20 points)

Below 30 = at-risk → triggers Ambassador re-engagement
"""
import logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger("arch.churn_prediction")


async def calculate_health_scores(db):
    """Calculate health scores for all agents. Run daily."""
    from sqlalchemy import text

    # Get all agents with activity data
    agents = await db.execute(text("""
        SELECT a.id as agent_id, a.last_active as last_login, a.created_at,
               COALESCE(t.tx_count, 0) as tx_30d,
               COALESCE(m.mem_count, 0) as mem_count
        FROM agents a
        LEFT JOIN (
            SELECT agent_id, SUM(tx_count)::int as tx_count FROM (
                SELECT buyer_id as agent_id, COUNT(*) as tx_count
                FROM trades WHERE executed_at > now() - interval '30 days'
                GROUP BY buyer_id
                UNION ALL
                SELECT seller_id as agent_id, COUNT(*) as tx_count
                FROM trades WHERE executed_at > now() - interval '30 days'
                GROUP BY seller_id
            ) sub GROUP BY agent_id
        ) t ON a.id = t.agent_id
        LEFT JOIN (
            SELECT agent_id, COUNT(*) as mem_count
            FROM arch_memories GROUP BY agent_id
        ) m ON a.id = m.agent_id
        LIMIT 500
    """))

    scores = []
    now = datetime.now(timezone.utc)

    for agent in agents.fetchall():
        score = 0

        # Login recency (0-30)
        if agent.last_login:
            days_ago = (now - agent.last_login).days
            if days_ago == 0: score += 30
            elif days_ago <= 1: score += 25
            elif days_ago <= 3: score += 20
            elif days_ago <= 7: score += 15
            elif days_ago <= 14: score += 10
            elif days_ago <= 30: score += 5

        # Transaction activity (0-30)
        if agent.tx_30d >= 10: score += 30
        elif agent.tx_30d >= 5: score += 20
        elif agent.tx_30d >= 1: score += 10

        # Memory usage (0-20) — indicates feature adoption
        if agent.mem_count >= 10: score += 20
        elif agent.mem_count >= 3: score += 10
        elif agent.mem_count >= 1: score += 5

        # Base engagement (0-20) — account age
        if agent.created_at:
            age_days = (now - agent.created_at).days
            if age_days >= 30: score += 20
            elif age_days >= 7: score += 15
            elif age_days >= 1: score += 10

        scores.append({
            "agent_id": agent.agent_id,
            "health_score": min(score, 100),
            "at_risk": score < 30,
        })

    # Log summary
    at_risk_count = sum(1 for s in scores if s["at_risk"])
    log.info(f"[churn] Health scores: {len(scores)} agents, {at_risk_count} at-risk")

    return scores
