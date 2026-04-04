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

    # Agent heartbeats — every 60 seconds
    interval = int(os.getenv("ARCH_HEARTBEAT_INTERVAL_SECONDS", "60"))
    for name, agent in agents.items():
        scheduler.add_job(
            agent.heartbeat,
            "interval", seconds=interval,
            id=f"arch_heartbeat_{name}",
            replace_existing=True,
        )
    if agents:
        log.info(f"[scheduler] Registered: heartbeats for {len(agents)} agents ({interval}s)")

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
