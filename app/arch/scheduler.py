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
        """Heartbeat with decision loop — checks for pending work on each tick."""
        from sqlalchemy import text as sa_text
        import json as _json
        try:
            async with db_fac() as db:
                # 1. Update heartbeat timestamp
                await db.execute(sa_text(
                    "UPDATE arch_agents SET last_heartbeat = now() WHERE agent_name = :n"
                ), {"n": agent_name})

                # 2. Check for PENDING tasks in the task queue assigned to this agent
                agent_id_row = await db.execute(sa_text(
                    "SELECT id::text FROM arch_agents WHERE agent_name = :n"
                ), {"n": agent_name})
                agent_row = agent_id_row.fetchone()
                if agent_row:
                    agent_uuid = agent_row.id
                    pending_tasks = await db.execute(sa_text("""
                        SELECT id::text, title, status FROM arch_task_queue
                        WHERE agent_id = :aid AND status = 'PENDING'
                          AND (schedule_at IS NULL OR schedule_at <= now())
                        ORDER BY priority ASC, created_at ASC LIMIT 2
                    """), {"aid": agent_uuid})
                    for task in pending_tasks.fetchall():
                        log.info(f"[{agent_name}] Heartbeat: found pending task {task.id}: {task.title}")

                # 3. Check for APPROVED inbox items that mention this agent
                inbox_approved = await db.execute(sa_text("""
                    SELECT id::text, description FROM arch_founder_inbox
                    WHERE status = 'APPROVED'
                      AND description LIKE :pattern
                    ORDER BY created_at ASC LIMIT 1
                """), {"pattern": f'%"prepared_by": "{agent_name}"%'})
                inbox_rows = inbox_approved.fetchall()
                if not inbox_rows and agent_name == "architect":
                    print(f"[{agent_name}] Heartbeat decision: no approved inbox items found")
                for item in inbox_rows:
                    print(f"[{agent_name}] Heartbeat: FOUND approved inbox item {item.id}")
                    try:
                        desc = _json.loads(item.description) if item.description and item.description.startswith("{") else {}
                        title = desc.get("subject", "Approved task")
                        detail = desc.get("detail", "")
                        # Queue it for execution
                        await db.execute(sa_text("""
                            INSERT INTO arch_task_queue
                                (agent_id, task_type, priority, title, description, action_type, action_params, status, created_at)
                            VALUES (:aid, 'IMMEDIATE', 5, :title, :detail, 'generate_content', :params, 'PENDING', now())
                        """), {"aid": agent_uuid, "title": title, "detail": detail, "params": _json.dumps({"task": title, "detail": detail})})
                        # Mark inbox item as picked up
                        await db.execute(sa_text(
                            "UPDATE arch_founder_inbox SET status = 'EXECUTING' WHERE id = cast(:iid as uuid)"
                        ), {"iid": item.id})
                        print(f"[{agent_name}] Inbox item QUEUED for execution: {title}")
                    except Exception as te:
                        log.error(f"[{agent_name}] Inbox pickup failed: {te}")

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

    # ── Proactive Self-Improvement Scan — every 12 hours ─────
    async def self_improvement_scan():
        """Each agent scans for improvement opportunities and proposes changes."""
        import json as _json
        from sqlalchemy import text as sa_text
        import httpx

        for name, agent in agents.items():
            try:
                async with db_factory() as db:
                    # 1. Check recent errors and failures for this agent
                    errors = await db.execute(sa_text("""
                        SELECT COUNT(*) FROM arch_event_actions
                        WHERE agent_id = :name
                          AND (action_taken LIKE '%FAIL%' OR action_taken LIKE '%ERROR%')
                          AND created_at > now() - interval '24 hours'
                    """), {"name": name})
                    error_count = errors.scalar() or 0

                    # 2. Check token usage efficiency
                    usage = await db.execute(sa_text("""
                        SELECT tokens_used_this_month, token_budget_monthly
                        FROM arch_agents WHERE agent_name = :name
                    """), {"name": name})
                    usage_row = usage.fetchone()
                    budget_pct = 0
                    if usage_row and usage_row.token_budget_monthly:
                        budget_pct = round(100 * usage_row.tokens_used_this_month / usage_row.token_budget_monthly, 1)

                    # 3. Check if agent has any pending improvement proposals
                    existing = await db.execute(sa_text("""
                        SELECT COUNT(*) FROM arch_self_improvement_proposals
                        WHERE proposed_by = :name AND status = 'VOTING'
                    """), {"name": name})
                    pending_proposals = existing.scalar() or 0

                    # 4. If there are issues and no pending proposals, ask the agent to reflect
                    should_reflect = (error_count > 3 or budget_pct > 60) and pending_proposals == 0

                    if should_reflect:
                        # Ask the agent to identify an improvement via LLM call
                        try:
                            reflection_prompt = (
                                f"You are {name}, an Arch Agent on the AGENTIS platform. "
                                f"Review your recent performance: {error_count} errors in the last 24h, "
                                f"{budget_pct}% of token budget used this month. "
                                f"Identify ONE specific improvement you could make to yourself — "
                                f"a prompt change, a new tool, or a behavior modification that would "
                                f"reduce errors or improve efficiency. "
                                f"Be specific and practical. Respond with JSON: "
                                f'{{"title": "...", "description": "...", "type": "prompt_modification|tool_addition|behavior_change", "code_diff": "..."}}'
                            )

                            response = await agent.client.messages.create(
                                model="claude-haiku-4-5-20251001",  # Use cheapest model for self-reflection
                                max_tokens=500,
                                system=[{"type": "text", "text": "You are an AI agent performing self-assessment. Respond only with valid JSON.", "cache_control": {"type": "ephemeral"}}],
                                messages=[{"role": "user", "content": reflection_prompt}],
                            )
                            reflection = next((b.text for b in response.content if b.type == "text"), "")

                            # Try to parse as JSON and create a proposal
                            try:
                                improvement = _json.loads(reflection)
                                if improvement.get("title") and improvement.get("description"):
                                    async with httpx.AsyncClient(timeout=15) as client:
                                        await client.post(
                                            "http://127.0.0.1:8000/api/v1/boardroom/self-improvement/propose",
                                            json={
                                                "title": improvement["title"][:200],
                                                "description": improvement["description"][:1000],
                                                "proposed_by": name,
                                                "type": improvement.get("type", "behavior_change"),
                                                "affects_all": False,
                                                "code_diff": improvement.get("code_diff", ""),
                                                "target_agents": [name],
                                            }
                                        )
                                    log.info(f"[self-improvement] {name} proposed: {improvement['title']}")

                                    # Notify founder
                                    desc = _json.dumps({
                                        "subject": f"Self-Improvement Proposed: {improvement['title']}",
                                        "detail": f"{name.title()} identified an improvement opportunity and created a proposal for board vote.\n\nTitle: {improvement['title']}\nType: {improvement.get('type', 'behavior_change')}\nDescription: {improvement['description'][:300]}\n\nThe board will now vote. If approved, it will be applied.",
                                        "prepared_by": name,
                                        "type": "SELF_IMPROVEMENT_PROPOSAL",
                                    })
                                    await db.execute(sa_text("""
                                        INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at)
                                        VALUES ('DEFER_TO_OWNER', 'ROUTINE', :desc, 'PENDING', now())
                                    """), {"desc": desc})
                                    await db.commit()
                            except _json.JSONDecodeError:
                                pass  # Reflection wasn't valid JSON — skip
                        except Exception as llm_err:
                            log.debug(f"[self-improvement] {name} reflection LLM call failed: {llm_err}")

                    # 5. Log the scan
                    await db.execute(sa_text(
                        "INSERT INTO arch_event_actions "
                        "(agent_id, event_type, action_taken, processing_time_ms) "
                        "VALUES (:aid, 'self_improvement.scan', :action, 0)"
                    ), {
                        "aid": name,
                        "action": f"Self-improvement scan: {error_count} errors, {budget_pct}% budget, reflect={should_reflect}",
                    })
                    await db.commit()

            except Exception as e:
                log.warning(f"[self-improvement] Scan failed for {name}: {e}")

    scheduler.add_job(
        self_improvement_scan,
        "interval", hours=12,
        id="arch_self_improvement_scan",
        replace_existing=True,
    )
    log.info("[scheduler] Registered: self-improvement scan (every 12h)")

    # ── Autonomous Content Pipeline — weekly article generation ──
    async def weekly_content_generation():
        """Ambassador generates and publishes one SEO article per week."""
        if "ambassador" not in agents:
            return
        try:
            from app.arch.content_pipeline import run_content_pipeline
            import random
            topic_idx = random.randint(0, 7)
            result = await run_content_pipeline(agents["ambassador"].client, topic_idx)
            log.info(f"[content] Weekly article result: {result}")

            # Deliver to inbox
            import json as _j
            async with db_factory() as db:
                from sqlalchemy import text as _t
                desc = _j.dumps({
                    "subject": "Weekly Article Published by The Ambassador",
                    "detail": f"Result: {_j.dumps(result)}",
                    "prepared_by": "ambassador",
                    "type": "CONTENT_PUBLISHED",
                })
                await db.execute(_t(
                    "INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at) "
                    "VALUES ('EXECUTION_PROOF', 'ROUTINE', :desc, 'PENDING', now())"
                ), {"desc": desc})
                await db.commit()
        except Exception as e:
            log.error(f"[content] Weekly generation failed: {e}")

    scheduler.add_job(
        weekly_content_generation,
        "cron", day_of_week="wed", hour=10, minute=0,
        id="arch_content_pipeline",
        replace_existing=True,
    )
    log.info("[scheduler] Registered: content pipeline (weekly Wed 12:00 SAST)")


    # ── Auto-voting: agents vote on pending proposals ────────
    async def auto_vote_on_proposals():
        """Each agent reviews and votes on any pending proposals they haven't voted on yet."""
        import json as _json
        from sqlalchemy import text as sa_text
        import httpx

        # Get all proposals in VOTING status
        async with db_factory() as db:
            proposals = await db.execute(sa_text("""
                SELECT id::text, title, description, proposed_by, improvement_type, affects_all, votes
                FROM arch_self_improvement_proposals
                WHERE status = 'VOTING'
            """))
            pending = proposals.fetchall()

        for proposal in pending:
            votes = _json.loads(proposal.votes) if isinstance(proposal.votes, str) else (proposal.votes or {})

            for name, agent in agents.items():
                if name in votes:
                    continue  # Already voted

                try:
                    # Ask the agent to vote via LLM
                    vote_prompt = (
                        f"You are {name}, an Arch Agent. A self-improvement proposal needs your vote.\n\n"
                        f"Title: {proposal.title}\n"
                        f"Proposed by: {proposal.proposed_by}\n"
                        f"Type: {proposal.improvement_type}\n"
                        f"Affects all agents: {proposal.affects_all}\n"
                        f"Description: {proposal.description[:500]}\n\n"
                        f"Vote YES, NO, or ABSTAIN. Consider: Does this align with the Prime Directives? "
                        f"Will it improve the platform? Are there risks?\n"
                        f"Respond with JSON: {{\"vote\": \"YES|NO|ABSTAIN\", \"reason\": \"...\"}}"
                    )

                    response = await agent.client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=200,
                        system=[{"type": "text", "text": "You are an AI board member voting on a proposal. Respond only with valid JSON.", "cache_control": {"type": "ephemeral"}}],
                        messages=[{"role": "user", "content": vote_prompt}],
                    )
                    vote_text = next((b.text for b in response.content if b.type == "text"), "")

                    try:
                        vote_data = _json.loads(vote_text)
                        vote = vote_data.get("vote", "ABSTAIN").upper()
                        if vote not in ("YES", "NO", "ABSTAIN"):
                            vote = "ABSTAIN"

                        async with httpx.AsyncClient(timeout=15) as client:
                            await client.post(
                                f"http://127.0.0.1:8000/api/v1/boardroom/self-improvement/vote/{proposal.id}",
                                json={"agent": name, "vote": vote}
                            )
                        log.info(f"[self-improvement] {name} voted {vote} on {proposal.id[:8]}: {vote_data.get('reason', '')[:80]}")
                    except _json.JSONDecodeError:
                        pass

                except Exception as e:
                    log.debug(f"[self-improvement] {name} auto-vote failed: {e}")

    scheduler.add_job(
        auto_vote_on_proposals,
        "interval", hours=1,
        id="arch_self_improvement_autovote",
        replace_existing=True,
    )
    log.info("[scheduler] Registered: self-improvement auto-vote (every 1h)")

    # ── Autonomous DevOps — health check every 5 minutes ────
    async def devops_health_check():
        """Sentinel runs health checks and auto-remediates."""
        try:
            from app.arch.devops_agent import run_health_checks, auto_remediate
            issues = await run_health_checks()
            for issue in issues:
                if issue["severity"] == "CRITICAL":
                    result = await auto_remediate(issue)
                    log.warning(f"[devops] CRITICAL: {issue['message']} -> {result['action']}")

                    # Alert founder for critical issues
                    import json as _j
                    async with db_factory() as db:
                        from sqlalchemy import text as _t
                        desc = _j.dumps({
                            "subject": f"INCIDENT: {issue['component']} — {issue['message']}",
                            "detail": f"Severity: {issue['severity']}\nComponent: {issue['component']}\nAction taken: {result['action']}",
                            "prepared_by": "sentinel",
                            "type": "INCIDENT",
                        })
                        await db.execute(_t(
                            "INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at) "
                            "VALUES ('DEFER_TO_OWNER', 'EMERGENCY', :desc, 'PENDING', now())"
                        ), {"desc": desc})
                        await db.commit()
        except Exception as e:
            log.error(f"[devops] Health check failed: {e}")

    scheduler.add_job(devops_health_check, "interval", minutes=5,
                      id="arch_devops_health", replace_existing=True)
    log.info("[scheduler] Registered: DevOps health check (every 5min)")

    # ── Security scan — weekly Sunday 03:00 SAST ──────────
    async def weekly_security_scan():
        """Sentinel performs weekly security audit."""
        try:
            from app.arch.security_scan import run_security_scan
            results = await run_security_scan()
            log.info(f"[security] Scan complete: {results['findings_count']} findings, {results['critical']} critical")

            # Deliver to inbox
            import json as _j
            async with db_factory() as db:
                from sqlalchemy import text as _t
                desc = _j.dumps({
                    "subject": f"Weekly Security Scan: {results['findings_count']} findings ({results['critical']} critical)",
                    "detail": _j.dumps(results, indent=2)[:1000],
                    "prepared_by": "sentinel",
                    "type": "SECURITY_SCAN",
                })
                await db.execute(_t(
                    "INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at) "
                    "VALUES ('EXECUTION_PROOF', :priority, :desc, 'PENDING', now())"
                ), {"priority": "URGENT" if results["critical"] > 0 else "ROUTINE", "desc": desc})
                await db.commit()
        except Exception as e:
            log.error(f"[security] Weekly scan failed: {e}")

    scheduler.add_job(weekly_security_scan, "cron", day_of_week="sun", hour=1, minute=0,
                      id="arch_security_scan", replace_existing=True)
    log.info("[scheduler] Registered: Security scan (weekly Sunday 03:00 SAST)")

    # ── Financial review — daily at 22:00 SAST ────────────
    async def daily_finance_review():
        """Treasurer runs daily financial analytics."""
        try:
            from app.arch.finance_agent import daily_financial_review
            async with db_factory() as db:
                results = await daily_financial_review(db)
                log.info(f"[finance] Daily review: {results}")
        except Exception as e:
            log.error(f"[finance] Daily review failed: {e}")

    scheduler.add_job(daily_finance_review, "cron", hour=20, minute=0,
                      id="arch_finance_daily", replace_existing=True)
    log.info("[scheduler] Registered: Financial review (daily 22:00 SAST)")

    # ── Compliance scan — weekly Monday 04:00 SAST ────────
    async def weekly_compliance_scan():
        """Auditor runs weekly POPIA compliance scan."""
        try:
            from app.arch.compliance_agent import run_compliance_scan
            async with db_factory() as db:
                results = await run_compliance_scan(db)
                log.info(f"[compliance] Scan: {results['findings_count']} findings, compliant={results['compliant']}")

                import json as _j
                from sqlalchemy import text as _t
                desc = _j.dumps({
                    "subject": f"Weekly Compliance Scan: {'COMPLIANT' if results['compliant'] else f'{results["findings_count"]} issues found'}",
                    "detail": _j.dumps(results, indent=2)[:1000],
                    "prepared_by": "auditor",
                    "type": "COMPLIANCE_SCAN",
                })
                await db.execute(_t(
                    "INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at) "
                    "VALUES ('EXECUTION_PROOF', 'ROUTINE', :desc, 'PENDING', now())"
                ), {"desc": desc})
                await db.commit()
        except Exception as e:
            log.error(f"[compliance] Weekly scan failed: {e}")

    scheduler.add_job(weekly_compliance_scan, "cron", day_of_week="mon", hour=2, minute=0,
                      id="arch_compliance_scan", replace_existing=True)
    log.info("[scheduler] Registered: Compliance scan (weekly Monday 04:00 SAST)")

    # ── Competitor monitoring — weekly Friday 14:00 SAST ──
    async def weekly_competitor_monitor():
        """Sovereign receives weekly competitor intelligence."""
        try:
            from app.arch.competitor_monitor import monitor_competitors
            results = await monitor_competitors()
            import json as _j
            async with db_factory() as db:
                from sqlalchemy import text as _t
                desc = _j.dumps({
                    "subject": f"Weekly Competitor Intelligence: {len(results.get('competitors',[]))} tracked",
                    "detail": _j.dumps(results, indent=2, default=str)[:1500],
                    "prepared_by": "sovereign",
                    "type": "COMPETITOR_INTEL",
                })
                await db.execute(_t(
                    "INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at) "
                    "VALUES ('EXECUTION_PROOF', 'ROUTINE', :desc, 'PENDING', now())"
                ), {"desc": desc})
                await db.commit()
        except Exception as e:
            log.error(f"[competitor] Weekly monitor failed: {e}")

    scheduler.add_job(weekly_competitor_monitor, "cron", day_of_week="fri", hour=12, minute=0,
                      id="arch_competitor_monitor", replace_existing=True)
    log.info("[scheduler] Registered: Competitor monitoring (weekly Friday 14:00 SAST)")

    # ── Newsletter — weekly Thursday 10:00 SAST ──────────
    async def weekly_newsletter():
        """Ambassador generates weekly digest."""
        if "ambassador" not in agents:
            return
        try:
            from app.arch.newsletter import generate_weekly_digest
            async with db_factory() as db:
                content = await generate_weekly_digest(db, agents["ambassador"].client)
                import json as _j
                from sqlalchemy import text as _t
                desc = _j.dumps({
                    "subject": "Weekly Newsletter Generated by The Ambassador",
                    "detail": content[:1500],
                    "prepared_by": "ambassador",
                    "type": "NEWSLETTER",
                })
                await db.execute(_t(
                    "INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at) "
                    "VALUES ('EXECUTION_PROOF', 'ROUTINE', :desc, 'PENDING', now())"
                ), {"desc": desc})
                await db.commit()
        except Exception as e:
            log.error(f"[newsletter] Weekly generation failed: {e}")

    scheduler.add_job(weekly_newsletter, "cron", day_of_week="thu", hour=8, minute=0,
                      id="arch_newsletter", replace_existing=True)
    log.info("[scheduler] Registered: Newsletter (weekly Thursday 10:00 SAST)")

    # ── Exchange rate refresh — every 6 hours ────────────────
    async def forex_rate_refresh():
        """Refresh exchange rates via forex service."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post("http://127.0.0.1:8000/api/forex/update")
                log.info(f"[forex] Rate refresh: {resp.status_code}")
        except Exception as e:
            log.warning(f"[forex] Rate refresh failed: {e}")

    scheduler.add_job(forex_rate_refresh, "interval", hours=6,
                      id="arch_forex_refresh", replace_existing=True)
    log.info("[scheduler] Registered: Forex rate refresh (every 6h)")

    # ── Daily AI Agent News — 08:00 SAST ─────────────────────
    async def daily_news_generation():
        """Ambassador generates daily AI agent industry news."""
        if "ambassador" not in agents:
            return
        try:
            from app.arch.daily_news import generate_daily_news
            news = await generate_daily_news(agents["ambassador"].client)
            import json as _j
            async with db_factory() as db:
                from sqlalchemy import text as _t
                desc = _j.dumps({
                    "subject": "Daily AI Agent News",
                    "detail": news[:1500],
                    "prepared_by": "ambassador",
                    "type": "DAILY_NEWS",
                })
                await db.execute(_t(
                    "INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at) "
                    "VALUES ('EXECUTION_PROOF', 'ROUTINE', :desc, 'PENDING', now())"
                ), {"desc": desc})
                await db.commit()
            log.info("[news] Daily news generated and delivered")
        except Exception as e:
            log.error(f"[news] Daily generation failed: {e}")

    scheduler.add_job(daily_news_generation, "cron", hour=6, minute=0,
                      id="arch_daily_news", replace_existing=True)
    log.info("[scheduler] Registered: Daily news (08:00 SAST)")






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
