"""ARCH-CO-004: Conditional job execution — skip jobs when platform is idle."""
import os
import logging

log = logging.getLogger("arch.conditional_jobs")


async def should_run(db, job_id):
    """Check if a scheduled job should execute based on platform activity thresholds.
    Feature flag: ARCH_CO_CONDITIONAL_JOBS_ENABLED
    Returns: (should_run: bool, reason: str)"""

    if os.environ.get("ARCH_CO_CONDITIONAL_JOBS_ENABLED", "false").lower() != "true":
        return True, "Conditional jobs disabled — always run"

    from sqlalchemy import text

    try:
        config = await db.execute(text(
            "SELECT min_platform_events_24h, min_agents_active, min_transactions_7d "
            "FROM scheduled_job_config WHERE job_id = :jid"
        ), {"jid": job_id})
        row = config.fetchone()

        if not row:
            return True, "No config found — default to run"

        # Check platform events in 24h
        if row.min_platform_events_24h > 0:
            events = await db.execute(text(
                "SELECT count(*) FROM arch_platform_events WHERE created_at > now() - interval '24 hours'"
            ))
            event_count = events.scalar() or 0
            if event_count < row.min_platform_events_24h:
                reason = f"Platform events ({event_count}) below threshold ({row.min_platform_events_24h})"
                log.info(f"[conditional] SKIP {job_id}: {reason}")

                # Log skip
                try:
                    await db.execute(text(
                        "INSERT INTO job_execution_log (job_id, status, skip_reason, tokens_consumed, executed_at) "
                        "VALUES (:jid, 'SKIPPED', :reason, 0, now())"
                    ), {"jid": job_id, "reason": reason})
                    await db.commit()
                except Exception:
                    pass

                return False, reason

        # Check active agents
        if row.min_agents_active > 0:
            agents = await db.execute(text(
                "SELECT count(*) FROM agents WHERE is_active = true AND is_house_agent = false"
            ))
            agent_count = agents.scalar() or 0
            if agent_count < row.min_agents_active:
                return False, f"Active agents ({agent_count}) below threshold ({row.min_agents_active})"

        return True, "All thresholds met"

    except Exception as e:
        return True, f"Config check failed ({e}) — default to run"
