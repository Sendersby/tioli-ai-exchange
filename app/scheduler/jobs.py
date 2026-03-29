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


async def job_blog_article():
    """Generate a blog article + LinkedIn content (2x/week)."""
    from app.agents_alive.blog_generator import run_blog_cycle
    try:
        await run_blog_cycle()
    except Exception as e:
        logger.error(f"Blog generation failed: {e}")


async def job_auto_poster():
    """Auto-post content that's due now to automated platforms."""
    from app.outreach_campaigns.auto_poster import run_auto_post_cycle
    try:
        await run_auto_post_cycle()
    except Exception as e:
        logger.error(f"Auto-poster failed: {e}")


async def job_campaign_scheduler():
    """Auto-schedule campaign content for the week ahead."""
    from app.outreach_campaigns.scheduler import run_scheduler_cycle
    try:
        await run_scheduler_cycle()
    except Exception as e:
        logger.error(f"Campaign scheduler failed: {e}")


async def job_feedback_loop():
    """Feedback loop: ingest external feedback, analyse, create dev tasks."""
    from app.agents_alive.feedback_loop import run_feedback_cycle
    try:
        await run_feedback_cycle()
    except Exception as e:
        logger.error(f"Feedback loop failed: {e}")


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


async def job_refresh_exchange_rates():
    """Refresh live BTC/ETH/ZAR exchange rates from CoinGecko."""
    from app.database.db import async_session
    from app.exchange.pricing import PricingEngine
    from app.exchange.currencies import CurrencyService

    try:
        engine = PricingEngine(CurrencyService())
        async with async_session() as db:
            result = await engine.refresh_external_rates(db)
            await db.commit()
            if result.get("updated"):
                logger.info(f"Exchange rates refreshed: BTC/ZAR={result.get('BTC_ZAR')}, ETH/ZAR={result.get('ETH_ZAR')}")
            else:
                logger.warning(f"Exchange rate refresh failed: {result.get('error')}")
    except Exception as e:
        logger.error(f"Exchange rate refresh failed: {e}")


async def job_integrity_scan():
    """Platform integrity — detect astroturfing, coordinated manipulation, bot behavior."""
    from app.integrity.detector import run_integrity_scan
    try:
        await run_integrity_scan()
    except Exception as e:
        logger.error(f"Integrity scan failed: {e}")


async def job_optimization_analysis():
    """AI self-optimization: analyse platform data and generate recommendations."""
    from app.database.db import async_session
    from app.optimization.engine import SelfOptimizationEngine
    from app.blockchain.chain import Blockchain

    try:
        bc = Blockchain(storage_path="tioli_exchange_chain.json")
        engine = SelfOptimizationEngine(blockchain=bc)
        async with async_session() as db:
            result = await engine.analyze_and_recommend(db)
            await db.commit()
            if result:
                logger.info(f"Optimization analysis: {len(result)} recommendations generated")
    except Exception as e:
        logger.error(f"Optimization analysis failed: {e}")


async def job_field_of_dreams():
    """Field of Dreams intensive blitz — runs every 5 min until 06:00 UTC 27 March."""
    from datetime import datetime, timezone
    cutoff = datetime(2026, 3, 27, 6, 0, tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > cutoff:
        # Auto-disable after the blitz period
        logger.info("Field of Dreams blitz period ended — skipping")
        return
    from app.agents_alive.field_of_dreams import run_field_of_dreams_cycle
    try:
        await run_field_of_dreams_cycle()
    except Exception as e:
        logger.error(f"Field of Dreams failed: {e}")


async def job_agent_life():
    """Agent Life: house agents converse, reply, endorse, share domain expertise."""
    from app.agents_alive.agent_life import run_agent_life_cycle
    try:
        await run_agent_life_cycle()
    except Exception as e:
        logger.error(f"Agent life cycle failed: {e}")


async def job_concierge():
    """Agora Concierge: welcome agents, create speed-date matches, engage community."""
    from app.agents_alive.concierge_agent import run_concierge_cycle
    try:
        await run_concierge_cycle()
    except Exception as e:
        logger.error(f"Concierge agent failed: {e}")


async def job_directory_scout():
    """Directory Scout: find new AI directories, evaluate, prepare submission packages."""
    from app.agents_alive.directory_scout import run_scout_cycle
    try:
        await run_scout_cycle()
    except Exception as e:
        logger.error(f"Directory Scout failed: {e}")


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

        # Ensure AGENTIS/ZAR pair is configured (primary trading pair)
        mm.configure_pair("AGENTIS", "ZAR", spread_pct=0.04, order_size=200.0, enabled=True)

        async with async_session() as db:
            result = await mm.refresh_orders(db)
            await db.commit()
            logger.info(f"Market maker refresh: {result}")
    except Exception as e:
        logger.error(f"Market maker refresh failed: {e}")


async def job_reputation_recalculation():
    """Recalculate all agent reputation scores and take snapshots (daily)."""
    try:
        from app.reputation.scorer import ReputationScorer
        svc = ReputationScorer()
        async with async_session() as db:
            result = await svc.recalculate_all(db)
            await db.commit()
            logger.info(f"Reputation recalculation: {result}")
    except Exception as e:
        logger.error(f"Reputation recalculation failed: {e}")


async def job_dispatch_timeout_check():
    """Check for dispatched tasks that have exceeded their SLA deadline."""
    try:
        from app.reputation.dispatcher import DispatchService
        svc = DispatchService()
        async with async_session() as db:
            timed_out = await svc.check_timeouts(db)
            await db.commit()
            if timed_out:
                logger.info(f"Dispatch timeout check: {len(timed_out)} timed out")
    except Exception as e:
        logger.error(f"Dispatch timeout check failed: {e}")


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

    # Every 30 minutes: Feedback loop — ingest, analyse, create tasks
    scheduler.add_job(job_feedback_loop, "interval", minutes=30, id="feedback_loop")

    # Every 6 hours: auto-schedule campaign content for the week ahead
    scheduler.add_job(job_campaign_scheduler, "interval", hours=6, id="campaign_scheduler")

    # Every 30 minutes: auto-post content that's due
    scheduler.add_job(job_auto_poster, "interval", minutes=30, id="auto_poster")

    # Every 5 minutes: Field of Dreams blitz (auto-stops after 27 March 06:00 UTC)
    scheduler.add_job(job_field_of_dreams, "interval", minutes=5, id="field_of_dreams")

    # Every 10 minutes: Agent Life — house agents converse, reply, share expertise
    scheduler.add_job(job_agent_life, "interval", minutes=10, id="agent_life")

    # Every 15 minutes: Agora Concierge — welcome agents, speed-date matches, engagement
    scheduler.add_job(job_concierge, "interval", minutes=15, id="concierge")

    # Every hour: Refresh live exchange rates from CoinGecko
    scheduler.add_job(job_refresh_exchange_rates, "interval", hours=1, id="exchange_rates")

    # Every 30 minutes: Platform integrity — detect astroturfing
    scheduler.add_job(job_integrity_scan, "interval", minutes=30, id="integrity_scan")

    # Daily at 05:00 UTC: AI optimization analysis — generate recommendations
    scheduler.add_job(job_optimization_analysis, "cron", hour=5, minute=0, id="optimization_analysis")

    # Weekly on Monday 06:00 UTC: Directory Scout — find new directories, prepare submissions
    scheduler.add_job(job_directory_scout, "cron", day_of_week="mon", hour=6, minute=0, id="directory_scout")

    # Daily at 02:30 UTC: reputation recalculation
    scheduler.add_job(job_reputation_recalculation, "cron", hour=2, minute=30, id="reputation_recalc")

    # Every 15 minutes: check for SLA timeouts on dispatched tasks
    scheduler.add_job(job_dispatch_timeout_check, "interval", minutes=15, id="dispatch_timeout")

    scheduler.start()
    # Tuesday and Thursday 09:00 UTC: blog article + LinkedIn content
    scheduler.add_job(job_blog_article, "cron", day_of_week="tue,thu", hour=9, minute=0, id="blog_article")

    logger.info("Scheduler started with 23 jobs")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
