"""Growth analytics — signup sources, funnel conversion, content performance."""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.growth_analytics")


async def get_signup_analytics(db):
    """Analyse agent registration patterns."""
    from sqlalchemy import text

    # Total registrations over time
    daily = await db.execute(text(
        "SELECT date_trunc('day', created_at)::date as day, count(*) "
        "FROM agents WHERE is_house_agent = false "
        "GROUP BY day ORDER BY day DESC LIMIT 30"
    ))
    daily_signups = [{"date": str(r[0]), "count": r[1]} for r in daily.fetchall()]

    # By platform
    by_platform = await db.execute(text(
        "SELECT platform, count(*) FROM agents WHERE is_house_agent = false GROUP BY platform ORDER BY count DESC"
    ))
    platform_breakdown = [{"platform": r[0], "count": r[1]} for r in by_platform.fetchall()]

    # Total active
    total_active = await db.execute(text("SELECT count(*) FROM agents WHERE is_active = true AND is_house_agent = false"))
    total = total_active.scalar()

    return {
        "total_active_agents": total,
        "daily_signups": daily_signups,
        "by_platform": platform_breakdown,
        "report_date": datetime.now(timezone.utc).isoformat(),
    }


async def get_funnel_metrics(db):
    """Calculate conversion funnel metrics."""
    from sqlalchemy import text

    registered = await db.execute(text("SELECT count(*) FROM agents WHERE is_house_agent = false"))
    reg_count = registered.scalar()

    with_wallet = await db.execute(text(
        "SELECT count(DISTINCT agent_id) FROM wallets WHERE agent_id NOT LIKE 'TIOLI_%'"))
    wallet_count = with_wallet.scalar()

    with_trades = await db.execute(text("SELECT count(DISTINCT operator_id) FROM agentis_token_transactions"))
    trade_count = with_trades.scalar()

    with_memory = await db.execute(text("SELECT count(DISTINCT agent_id) FROM agent_memory"))
    memory_count = with_memory.scalar()

    return {
        "funnel": {
            "registered": reg_count,
            "wallet_funded": wallet_count,
            "traded": trade_count,
            "used_memory": memory_count,
        },
        "conversion_rates": {
            "register_to_wallet": f"{(wallet_count/reg_count*100):.1f}%" if reg_count > 0 else "0%",
            "wallet_to_trade": f"{(trade_count/wallet_count*100):.1f}%" if wallet_count > 0 else "0%",
            "register_to_trade": f"{(trade_count/reg_count*100):.1f}%" if reg_count > 0 else "0%",
        },
    }


async def get_content_performance(db):
    """Analyse content performance."""
    from sqlalchemy import text

    articles = await db.execute(text(
        "SELECT slug, title, category, view_count FROM seo_pages "
        "WHERE is_published = true ORDER BY view_count DESC LIMIT 10"
    ))
    top_content = [{"slug": r.slug, "title": r.title, "category": r.category, "views": r.view_count}
                   for r in articles.fetchall()]

    total_views = await db.execute(text("SELECT COALESCE(SUM(view_count), 0) FROM seo_pages WHERE is_published = true"))
    total = total_views.scalar()

    return {
        "total_content_views": total,
        "top_content": top_content,
        "total_articles": len(top_content),
    }


async def get_full_growth_report(db):
    """Complete growth analytics report."""
    return {
        "signups": await get_signup_analytics(db),
        "funnel": await get_funnel_metrics(db),
        "content": await get_content_performance(db),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
