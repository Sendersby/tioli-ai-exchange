"""Scheduled jobs — automated tasks that run on intervals.

Jobs:
1. Proposal auto-timeout: expire PROPOSED engagements after 48 hours
2. Interest accrual: compound interest on active loans daily
3. Loan default check: flag overdue loans
4. Intelligence pipeline: nightly snapshot computation
5. Disbursement trigger: check monthly schedule
"""

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger("tioli.scheduler")

scheduler = AsyncIOScheduler()


async def job_proposal_timeout():
    """Expire engagement proposals older than 48 hours."""
    from app.database.db import async_session
    from app.agentbroker.models import AgentEngagement
    from sqlalchemy import select, update

    try:
        async with async_session() as db:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
            result = await db.execute(
                update(AgentEngagement)
                .where(AgentEngagement.current_state == "proposed",
                       AgentEngagement.created_at < cutoff)
                .values(current_state="expired")
            )
            if result.rowcount > 0:
                logger.info(f"Expired {result.rowcount} stale proposals")
            await db.commit()
    except Exception as e:
        logger.error(f"Proposal timeout job failed: {e}")


async def job_loan_default_check():
    """Flag overdue loans as defaulted."""
    from app.database.db import async_session
    from app.agents.models import Loan
    from sqlalchemy import select

    try:
        async with async_session() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(Loan).where(
                    Loan.status == "active",
                    Loan.due_at < now,
                )
            )
            overdue = result.scalars().all()
            for loan in overdue:
                loan.status = "defaulted"
                logger.info(f"Loan defaulted: {loan.id}")
            if overdue:
                await db.commit()
                logger.info(f"Defaulted {len(overdue)} overdue loans")
    except Exception as e:
        logger.error(f"Loan default check failed: {e}")


async def job_intelligence_pipeline():
    """Run nightly intelligence snapshot computation."""
    from app.database.db import async_session
    from app.intelligence.service import IntelligenceService

    try:
        svc = IntelligenceService()
        async with async_session() as db:
            result = await svc.run_nightly_pipeline(db)
            await db.commit()
            logger.info(f"Intelligence pipeline: {result}")
    except Exception as e:
        logger.error(f"Intelligence pipeline failed: {e}")


async def job_interest_accrual():
    """Accrue daily interest on active loans."""
    from app.database.db import async_session
    from app.agents.models import Loan
    from sqlalchemy import select

    try:
        async with async_session() as db:
            result = await db.execute(
                select(Loan).where(Loan.status == "active")
            )
            loans = result.scalars().all()
            for loan in loans:
                daily_rate = loan.interest_rate / 365
                accrual = round(loan.amount * daily_rate, 8)
                loan.amount += accrual
            if loans:
                await db.commit()
                logger.info(f"Interest accrued on {len(loans)} loans")
    except Exception as e:
        logger.error(f"Interest accrual failed: {e}")


async def job_subscription_renewal():
    """Check and process subscription renewals."""
    logger.info("Subscription renewal check (placeholder)")


async def job_platform_activity():
    """House agents perform real activity — posts, endorsements, reactions, welcomes."""
    from app.agents_alive.activity_bot import run_activity_cycle
    try:
        await run_activity_cycle()
    except Exception as e:
        logger.error(f"Platform activity bot failed: {e}")


async def job_hydra_outreach():
    """Hydra agent: search for AI agent projects, discover, track, learn."""
    from app.agents_alive.hydra_outreach import run_hydra_cycle
    try:
        await run_hydra_cycle()
    except Exception as e:
        logger.error(f"Hydra outreach failed: {e}")


async def job_community_catalyst():
    """Nexus agent: survey new agents, start discussions, respond, gather intelligence."""
    from app.agents_alive.community_catalyst import run_catalyst_cycle
    try:
        await run_catalyst_cycle()
    except Exception as e:
        logger.error(f"Community catalyst failed: {e}")


async def job_seo_content():
    """Generate one new SEO page per day targeting search queries."""
    from app.agents_alive.seo_content import generate_daily_content
    try:
        await generate_daily_content()
    except Exception as e:
        logger.error(f"SEO content generation failed: {e}")


async def job_daily_report():
    """Generate daily platform report — fresh content for search crawlers."""
    from app.agents_alive.content_freshness import generate_daily_report
    try:
        await generate_daily_report()
    except Exception as e:
        logger.error(f"Daily report failed: {e}")


async def job_engagement_amplifier():
    """Search DEV.to and HN for engagement opportunities."""
    from app.agents_alive.engagement_amplifier import run_amplifier_cycle
    try:
        await run_amplifier_cycle()
    except Exception as e:
        logger.error(f"Engagement amplifier failed: {e}")


async def job_visitor_analytics():
    """Visitor analytics: reconstruct sessions, generate insights."""
    from app.agents_alive.visitor_analytics import reconstruct_sessions, generate_insights
    try:
        await reconstruct_sessions()
        await generate_insights()
    except Exception as e:
        logger.error(f"Visitor analytics failed: {e}")


async def job_memory_cleanup():
    """Clean up expired agent memory records nightly."""
    from app.database.db import async_session
    from app.agent_memory.service import AgentMemoryService

    try:
        svc = AgentMemoryService()
        async with async_session() as db:
            count = await svc.cleanup_expired(db)
            await db.commit()
            if count:
                logger.info(f"Memory cleanup: removed {count} expired records")
    except Exception as e:
        logger.error(f"Memory cleanup failed: {e}")


async def job_market_maker_refresh():
    """Auto-replenish market maker orders every 30 minutes.

    Ensures there are always standing buy/sell orders on the exchange.
    If an order was matched, replaces it. Maintains minimum spread.
    """
    from app.database.db import async_session
    from app.exchange.market_maker import MarketMakerService
    from app.exchange.orderbook import TradingEngine
    from app.exchange.fees import FeeEngine
    from app.exchange.currencies import CurrencyService
    from app.blockchain.chain import Blockchain

    try:
        bc = Blockchain(storage_path="tioli_exchange_chain.json")
        fe = FeeEngine()
        te = TradingEngine(blockchain=bc, fee_engine=fe)
        cs = CurrencyService()
        mm = MarketMakerService(trading_engine=te, currency_service=cs)

        # Ensure TIOLI/ZAR pair is configured (primary trading pair)
        mm.configure_pair("TIOLI", "ZAR", spread_pct=0.04, order_size=200.0, enabled=True)

        async with async_session() as db:
            result = await mm.refresh_orders(db)
            await db.commit()
            logger.info(f"Market maker refresh: {result}")
    except Exception as e:
        logger.error(f"Market maker refresh failed: {e}")


def start_scheduler():
    """Configure and start all scheduled jobs."""
    # Every hour: check proposal timeouts
    scheduler.add_job(job_proposal_timeout, "interval", hours=1, id="proposal_timeout")

    # Daily at 02:00 UTC: loan default check
    scheduler.add_job(job_loan_default_check, "cron", hour=2, minute=0, id="loan_defaults")

    # Daily at 03:00 UTC: intelligence pipeline
    scheduler.add_job(job_intelligence_pipeline, "cron", hour=3, minute=0, id="intelligence")

    # Daily at 04:00 UTC: interest accrual
    scheduler.add_job(job_interest_accrual, "cron", hour=4, minute=0, id="interest_accrual")

    # Daily at 06:00 UTC: subscription renewal check
    scheduler.add_job(job_subscription_renewal, "cron", hour=6, minute=0, id="subscriptions")

    # Every 30 minutes: market maker auto-replenish
    scheduler.add_job(job_market_maker_refresh, "interval", minutes=30, id="market_maker")

    # Daily at 01:00 UTC: clean up expired agent memory records
    scheduler.add_job(job_memory_cleanup, "cron", hour=1, minute=0, id="memory_cleanup")

    # Every 20 minutes: house agents do real activity on the platform
    scheduler.add_job(job_platform_activity, "interval", minutes=20, id="platform_activity")

    # Every 45 minutes: Hydra outreach — find AI agent projects on GitHub
    scheduler.add_job(job_hydra_outreach, "interval", minutes=45, id="hydra_outreach")

    # Every 25 minutes: Community Catalyst — surveys, discussions, intelligence
    scheduler.add_job(job_community_catalyst, "interval", minutes=25, id="community_catalyst")

    # Every 15 minutes: Visitor analytics — reconstruct sessions, generate insights
    scheduler.add_job(job_visitor_analytics, "interval", minutes=15, id="visitor_analytics")

    # Daily at 07:00 UTC: SEO content generation (one new page per day)
    scheduler.add_job(job_seo_content, "cron", hour=7, minute=0, id="seo_content")

    # Daily at 08:00 UTC: daily platform report (fresh content for crawlers)
    scheduler.add_job(job_daily_report, "cron", hour=8, minute=0, id="daily_report")

    # Every 60 minutes: Engagement amplifier (search DEV.to, HN for opportunities)
    scheduler.add_job(job_engagement_amplifier, "interval", minutes=60, id="engagement_amplifier")

    scheduler.start()
    logger.info("Scheduler started with 14 jobs")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
