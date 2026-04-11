"""Module 3: Proactive Action Scanner — Agents identify work opportunities autonomously.
Per-agent checks every 2 hours. Identifies overdue tasks, idle agents, and opportunities.
Feature flag: ARCH_PROACTIVE_SCANNER_ENABLED"""
import os
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.proactive_scanner")


async def run_proactive_scan(db) -> dict:
    """Run all proactive checks across all agents. Returns identified opportunities."""
    if os.environ.get("ARCH_PROACTIVE_SCANNER_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    from sqlalchemy import text
    opportunities = []
    actions_taken = []

    # ═══ SOVEREIGN: Board-level checks ═══
    try:
        # Check: any agent with 0 goal actions in 24h
        r = await db.execute(text("""
            SELECT a.agent_name FROM arch_agents a
            WHERE a.status = 'ACTIVE'
            AND a.agent_name NOT IN (
                SELECT DISTINCT agent_id FROM goal_actions
                WHERE executed_at > now() - interval '24 hours'
            )
        """))
        idle_agents = [row.agent_name for row in r.fetchall()]
        if idle_agents:
            opportunities.append({
                "agent": "sovereign", "type": "idle_agents",
                "detail": f"{len(idle_agents)} agents with 0 goal actions in 24h: {', '.join(idle_agents)}",
                "severity": "medium",
            })
            # Trigger goal pursuit for idle agents
            for agent_name in idle_agents[:3]:  # Max 3 to avoid token burst
                try:
                    import anthropic
                    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
                    from app.arch.goal_engine import goal_pursuit_cycle
                    result = await goal_pursuit_cycle(db, agent_name, client)
                    if result.get("goals_actioned", 0) > 0:
                        actions_taken.append(f"Nudged {agent_name}: {result.get('goals_actioned')} goals actioned")
                except Exception as e:
                    log.warning(f"[proactive] Failed to nudge {agent_name}: {e}")

        # Check: evaluation overdue
        r = await db.execute(text(
            "SELECT max(evaluated_at) FROM agent_evaluation_scores"))
        last_eval = r.scalar()
        if last_eval:
            days_since = (datetime.now(timezone.utc) - last_eval).days
            if days_since > 30:
                opportunities.append({
                    "agent": "sovereign", "type": "evaluation_overdue",
                    "detail": f"Last evaluation was {days_since} days ago — trigger monthly review",
                    "severity": "low",
                })
    except Exception as e:
        log.warning(f"[proactive] Sovereign checks failed: {e}")

    # ═══ SENTINEL: Security checks ═══
    try:
        # Check: backup age
        import glob
        backups = sorted(glob.glob("/home/tioli/backups/db/*.sql.gz"), reverse=True)
        if backups:
            age_hours = (datetime.now(timezone.utc) - datetime.fromtimestamp(
                os.path.getmtime(backups[0]), tz=timezone.utc)).total_seconds() / 3600
            if age_hours > 25:
                opportunities.append({
                    "agent": "sentinel", "type": "backup_stale",
                    "detail": f"Latest backup is {age_hours:.1f}h old (>25h threshold)",
                    "severity": "high",
                })

        # Check: circuit breakers
        r = await db.execute(text(
            "SELECT agent_name FROM arch_agents WHERE circuit_breaker_tripped = true"))
        tripped = [row.agent_name for row in r.fetchall()]
        if tripped:
            opportunities.append({
                "agent": "sentinel", "type": "circuit_breaker",
                "detail": f"Circuit breaker tripped for: {', '.join(tripped)}",
                "severity": "critical",
            })
    except Exception as e:
        log.warning(f"[proactive] Sentinel checks failed: {e}")

    # ═══ AUDITOR: Compliance checks ═══
    try:
        # Check: agents not rescreened in 30+ days
        r = await db.execute(text("""
            SELECT count(*) FROM agents
            WHERE is_active = true
            AND (last_rescreened IS NULL OR last_rescreened < now() - interval '30 days')
        """))
        overdue = r.scalar() or 0
        if overdue > 0:
            opportunities.append({
                "agent": "auditor", "type": "rescreening_overdue",
                "detail": f"{overdue} agents need rescreening (>30 days)",
                "severity": "medium",
            })
            # Trigger rescreening
            try:
                from app.arch.rescreening import run_rescreening_batch
                await run_rescreening_batch(db)
                actions_taken.append(f"Triggered rescreening batch for {overdue} overdue agents")
            except Exception as e:
                import logging; logging.getLogger("proactive_scanner").warning(f"Suppressed: {e}")

        # Check: regulatory scan
        r = await db.execute(text(
            "SELECT max(last_scanned) FROM regulatory_scan_state"))
        last_scan = r.scalar()
        if last_scan:
            hours_since = (datetime.now(timezone.utc) - last_scan).total_seconds() / 3600
            if hours_since > 25:
                opportunities.append({
                    "agent": "auditor", "type": "regulatory_scan_overdue",
                    "detail": f"Regulatory scan is {hours_since:.0f}h old",
                    "severity": "medium",
                })
    except Exception as e:
        log.warning(f"[proactive] Auditor checks failed: {e}")

    # ═══ AMBASSADOR: Growth checks ═══
    try:
        # Check: content output today
        r = await db.execute(text(
            "SELECT count(*) FROM arch_content_library "
            "WHERE published_at > CURRENT_DATE"))
        posts_today = r.scalar() or 0
        if posts_today < 2:
            opportunities.append({
                "agent": "ambassador", "type": "low_content_output",
                "detail": f"Only {posts_today} posts today (target: 2+). Triggering content engine.",
                "severity": "medium",
            })
            # Trigger content engine
            try:
                import anthropic
                client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
                from app.arch.content_engine import generate_and_publish_all
                result = await generate_and_publish_all(client)
                if result.get("status") == "published":
                    actions_taken.append(f"Ambassador published content: {result.get('versions_generated', 0)} versions")
            except Exception as e:
                log.warning(f"[proactive] Content trigger failed: {e}")

        # Check: unactioned social signals
        r = await db.execute(text(
            "SELECT count(*) FROM social_signals WHERE actioned = false AND classification = 'OPPORTUNITY'"))
        unactioned = r.scalar() or 0
        if unactioned > 0:
            opportunities.append({
                "agent": "ambassador", "type": "unactioned_opportunities",
                "detail": f"{unactioned} social signal opportunities not yet actioned",
                "severity": "low",
            })
    except Exception as e:
        log.warning(f"[proactive] Ambassador checks failed: {e}")

    # ═══ TREASURER: Financial checks ═══
    try:
        r = await db.execute(text(
            "SELECT total_balance_zar, floor_zar FROM arch_reserve_ledger "
            "ORDER BY recorded_at DESC LIMIT 1"))
        row = r.fetchone()
        if row:
            balance = float(row.total_balance_zar)
            floor = float(row.floor_zar)
            if floor > 0 and balance < floor * 1.1:
                opportunities.append({
                    "agent": "treasurer", "type": "reserve_floor_risk",
                    "detail": f"Balance R{balance:.2f} within 10% of floor R{floor:.2f}",
                    "severity": "high",
                })
    except Exception as e:
        log.warning(f"[proactive] Treasurer checks failed: {e}")

    # ═══ ARBITER: Justice checks ═══
    try:
        r = await db.execute(text("SELECT count(*) FROM synthetic_case_law"))
        case_count = r.scalar() or 0
        if case_count < 10:
            opportunities.append({
                "agent": "arbiter", "type": "insufficient_case_law",
                "detail": f"Only {case_count} synthetic cases (target: 10+). Generate more.",
                "severity": "low",
            })
    except Exception as e:
        log.warning(f"[proactive] Arbiter checks failed: {e}")

    # ═══ ARCHITECT: Technical checks ═══
    try:
        # Check: GitHub repo activity
        import httpx
        token = os.environ.get("GITHUB_TOKEN", "")
        if token:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.github.com/repos/Sendersby/tioli-agentis",
                    headers={"Authorization": f"token {token}"})
                if resp.status_code == 200:
                    data = resp.json()
                    stars = data.get("stargazers_count", 0)
                    issues = data.get("open_issues_count", 0)
                    if issues > 0:
                        opportunities.append({
                            "agent": "architect", "type": "github_issues",
                            "detail": f"tioli-agentis has {issues} open issues, {stars} stars",
                            "severity": "low",
                        })
    except Exception as e:
        log.warning(f"[proactive] Architect checks failed: {e}")

    # Log results
    try:
        from sqlalchemy import text as sa_text
        await db.execute(sa_text(
            "INSERT INTO job_execution_log (job_id, status, tokens_consumed, duration_ms, executed_at) "
            "VALUES ('proactive_scan', :status, 0, 0, now())"
        ), {"status": f"FOUND_{len(opportunities)}" if opportunities else "ALL_CLEAR"})
        await db.commit()
    except Exception as e:
        import logging; logging.getLogger("proactive_scanner").warning(f"Suppressed: {e}")

    log.info(f"[proactive] Scan complete: {len(opportunities)} opportunities, {len(actions_taken)} actions taken")

    return {
        "opportunities": opportunities,
        "actions_taken": actions_taken,
        "total_opportunities": len(opportunities),
        "total_actions": len(actions_taken),
        "scan_time": datetime.now(timezone.utc).isoformat(),
    }
