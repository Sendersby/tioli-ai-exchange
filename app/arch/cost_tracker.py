"""Arch Agent cost tracking — token budget management.

Monitors monthly token usage per agent. Downgrades to fallback model
at alert threshold, suspends non-critical calls at hard limit.
"""

import logging
import os
from datetime import datetime, timezone

from sqlalchemy import text

log = logging.getLogger("arch.cost_tracker")


async def get_token_usage_summary(db) -> dict:
    """Get token usage summary for all agents."""
    result = await db.execute(
        text("""
            SELECT agent_name, token_budget_monthly, tokens_used_this_month,
                   tokens_reset_at, model_primary
            FROM arch_agents ORDER BY agent_name
        """)
    )
    summary = {}
    total_used = 0
    total_budget = 0
    for r in result.fetchall():
        budget = r.token_budget_monthly or 1
        used = r.tokens_used_this_month or 0
        pct = round(100 * used / budget, 1)
        alert_pct = int(os.getenv("ARCH_TOKEN_ALERT_THRESHOLD_PCT", "80"))
        hard_pct = int(os.getenv("ARCH_TOKEN_HARD_LIMIT_PCT", "95"))

        status = "OK"
        if pct >= hard_pct:
            status = "HARD_LIMIT"
        elif pct >= alert_pct:
            status = "ALERT"

        summary[r.agent_name] = {
            "budget": budget,
            "used": used,
            "pct": pct,
            "status": status,
            "model": r.model_primary,
            "reset_at": r.tokens_reset_at.isoformat() if r.tokens_reset_at else None,
        }
        total_used += used
        total_budget += budget

    return {
        "agents": summary,
        "total_used": total_used,
        "total_budget": total_budget,
        "total_pct": round(100 * total_used / max(total_budget, 1), 1),
    }


async def reset_all_token_budgets(db):
    """Monthly reset of all agent token counters."""
    await db.execute(
        text("UPDATE arch_agents SET tokens_used_this_month = 0, tokens_reset_at = now()")
    )
    await db.commit()
    log.info("[cost_tracker] All agent token budgets reset")
