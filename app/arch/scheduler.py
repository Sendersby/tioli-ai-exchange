"""Arch Agent APScheduler job registration.

All recurring agent tasks run on APScheduler. Jobs are registered
at startup when ARCH_AGENTS_ENABLED=true.
"""

import logging
import os

log = logging.getLogger("arch.scheduler")


def register_arch_jobs(scheduler, agents: dict, db_factory=None):
    """Register all recurring Arch Agent jobs on the APScheduler instance."""

    # Reserve calculation — daily at midnight SAST (22:00 UTC)
    if "treasurer" in agents:
        scheduler.add_job(
            agents["treasurer"].calculate_reserves,
            "cron", hour=22, minute=0,
            id="arch_reserve_calc",
            replace_existing=True,
        )
        log.info("[scheduler] Registered: arch_reserve_calc (daily midnight SAST)")

    # Weekly board session — Monday 09:00 SAST (07:00 UTC)
    if "sovereign" in agents:
        scheduler.add_job(
            agents["sovereign"]._tool_convene_board_session,
            "cron", day_of_week="mon", hour=7, minute=0,
            id="arch_board_session",
            replace_existing=True,
            kwargs={"params": {"session_type": "WEEKLY", "agenda": ["Weekly review"]}},
        )
        log.info("[scheduler] Registered: arch_board_session (Monday 09:00 SAST)")

    # Monthly self-assessment — 1st of month
    if "sovereign" in agents:
        scheduler.add_job(
            agents["sovereign"].trigger_self_assessments,
            "cron", day=1, hour=1, minute=0,
            id="arch_self_assessment",
            replace_existing=True,
        )
        log.info("[scheduler] Registered: arch_self_assessment (1st of month)")

    # Agent heartbeats — every 60 seconds using fresh DB sessions
    interval = int(os.getenv("ARCH_HEARTBEAT_INTERVAL_SECONDS", "60"))
    
    async def _heartbeat_with_session(agent_name, db_fac):
        from sqlalchemy import text as sa_text
        try:
            async with db_fac() as db:
                await db.execute(sa_text(
                    "UPDATE arch_agents SET last_heartbeat = now() WHERE agent_name = :n"
                ), {"n": agent_name})
                await db.commit()
        except Exception as e:
            log.warning(f"[scheduler] Heartbeat failed for {agent_name}: {e}")

    for name in agents:
        scheduler.add_job(
            _heartbeat_with_session,
            "interval", seconds=interval,
            id=f"arch_heartbeat_{name}",
            replace_existing=True,
            args=[name, db_factory],
        )
    if agents:
        log.info(f"[scheduler] Registered: heartbeats for {len(agents)} agents ({interval}s)")

    # ── Proactive team management — every 6 hours ────────────
    async def proactive_team_review():
        """Each Arch Agent reviews their team, identifies gaps, and takes action."""
        from app.arch.subordinate_manager import get_team_status
        for name, agent in agents.items():
            try:
                async with db_factory() as db:
                    status = await get_team_status(db, name)
                    sub_count = status.get("subordinate_count", 0)
                    # Log the review as an activity
                    from sqlalchemy import text as sa_text
                    await db.execute(sa_text(
                        "INSERT INTO arch_event_actions "
                        "(agent_id, event_type, action_taken, processing_time_ms) "
                        "VALUES (:aid, 'management.team_review', :action, 0)"
                    ), {"aid": name, "action": f"Proactive team review: {sub_count} subordinates checked"})
                    await db.commit()
            except Exception as e:
                log.warning(f"[scheduler] Team review failed for {name}: {e}")

    scheduler.add_job(
        proactive_team_review,
        "interval", hours=6,
        id="arch_proactive_team_mgmt",
        replace_existing=True,
    )
    log.info("[scheduler] Registered: proactive team management (every 6h)")

    # Token budget reset — 1st of month
    if "architect" in agents:
        scheduler.add_job(
            agents["architect"].reset_token_budgets,
            "cron", day=1, hour=0, minute=30,
            id="arch_token_reset",
            replace_existing=True,
        )
        log.info("[scheduler] Registered: arch_token_reset (1st of month)")

    # Knowledge ingestion — daily at 03:00 SAST (01:00 UTC)
    if "architect" in agents:
        scheduler.add_job(
            agents["architect"].ingest_research,
            "cron", hour=1, minute=0,
            id="arch_knowledge_ingest",
            replace_existing=True,
        )
        log.info("[scheduler] Registered: arch_knowledge_ingest (daily 03:00 SAST)")

    # Credential rotation check — weekly Sunday
    if "sentinel" in agents:
        scheduler.add_job(
            agents["sentinel"].check_credential_rotation,
            "cron", day_of_week="sun", hour=2, minute=0,
            id="arch_cred_rotation",
            replace_existing=True,
        )
        log.info("[scheduler] Registered: arch_cred_rotation (weekly Sunday)")

    # Circuit breaker check — daily
    if "sentinel" in agents:
        scheduler.add_job(
            agents["sentinel"].check_circuit_breakers,
            "cron", hour=6, minute=0,
            id="arch_circuit_check",
            replace_existing=True,
        )
        log.info("[scheduler] Registered: arch_circuit_check (daily)")

    # Succession liveness check — weekly Wednesday
    if "sentinel" in agents:
        scheduler.add_job(
            agents["sentinel"].check_succession_contacts,
            "cron", day_of_week="wed", hour=8, minute=0,
            id="arch_succession_check",
            replace_existing=True,
        )
        log.info("[scheduler] Registered: arch_succession_check (weekly Wednesday)")

    # Memory outbox flush — every 60 seconds

    # -- Uptime health check -- every 60 seconds -----------------------
    async def uptime_check():
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get("http://127.0.0.1:8000/api/v1/health", timeout=5)
                if resp.status_code != 200:
                    log.error(f"[uptime] Health check FAILED: {resp.status_code}")
        except Exception as e:
            log.error(f"[uptime] Health check FAILED: {e}")

    scheduler.add_job(uptime_check, "interval", seconds=60, id="arch_uptime_check", replace_existing=True)
    log.info("[scheduler] Registered: uptime check (60s)")

    if db_factory:
        from app.arch.memory import flush_memory_outbox
        scheduler.add_job(
            flush_memory_outbox,
            "interval", seconds=60,
            id="arch_memory_flush",
            replace_existing=True,
            args=[db_factory],
        )
        log.info("[scheduler] Registered: arch_memory_flush (60s)")
