"""Router: arch_routes - auto-extracted from main.py (A-001)."""
from fastapi import APIRouter, Depends, Request, HTTPException, Header, Query, Path, Body
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from pydantic import BaseModel
from app.database.db import get_db, async_session
from app.agents.models import Agent, Wallet, Loan
from app.blockchain.transaction import Transaction, TransactionType
from app.utils.validators import require_kyc_verified
from app.utils.audit import log_financial_event
from app.security.transaction_safety import InputValidator
from app.config import settings
from app.infrastructure.cache import cache, TTL_SHORT, TTL_MEDIUM, TTL_LONG
import json, uuid, os, time, logging
from datetime import datetime, timezone
from collections import defaultdict

from sqlalchemy import text as _quest_text
router = APIRouter()

@router.get("/api/v1/memory/tiers/{agent_name}", include_in_schema=False)
async def api_memory_tiers(agent_name: str, db: AsyncSession = Depends(get_db)):
    """Get tiered memory status for an agent."""
    from app.arch.memory_tiers import load_from_db
    mem = await load_from_db(db, agent_name)
    return mem.summary()

@router.post("/api/v1/test/self-correction", include_in_schema=False)
async def api_test_self_correction():
    """Test the self-correction system with a deliberate failure."""
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.self_correction import RetryHandler

    handler = RetryHandler("test_agent", max_retries=3)

    call_count = [0]
    async def flaky_action():
        call_count[0] += 1
        if call_count[0] < 3:
            raise ValueError(f"Simulated failure #{call_count[0]}")
        return "Success on attempt 3"

    result = await handler.execute_with_retry(flaky_action, agent_client=client)
    return {"result": result, "total_calls": call_count[0]}

@router.post("/api/v1/arch/messages", include_in_schema=False)
async def api_send_agent_message(request: Request, db: AsyncSession = Depends(get_db)):
    """Send a message between agents."""
    body = await request.json()
    from app.arch.mesh_comms import send_message
    result = await send_message(db, body.get("from",""), body.get("to",""),
        body.get("subject",""), body.get("body",""), body.get("type","notify"), body.get("priority","normal"))
    if result.get("allowed") == False:
        from starlette.responses import JSONResponse
        return JSONResponse(status_code=403, content=result)
    return result

@router.get("/api/v1/arch/messages/inbox/{agent_name}", include_in_schema=False)
async def api_agent_inbox(agent_name: str, db: AsyncSession = Depends(get_db)):
    """Get agent inbox."""
    from app.arch.mesh_comms import get_inbox
    return await get_inbox(db, agent_name)

@router.post("/api/v1/arch/messages/{message_id}/reply", include_in_schema=False)
async def api_reply_message(message_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Reply to a message."""
    body = await request.json()
    from app.arch.mesh_comms import reply_to_message
    return await reply_to_message(db, message_id, body.get("from",""), body.get("body",""))

@router.post("/api/v1/sovereign/agenda", include_in_schema=False)
async def api_generate_agenda(db: AsyncSession = Depends(get_db)):
    """Generate Sovereign daily agenda."""
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.daily_agenda import generate_daily_agenda
    return await generate_daily_agenda(db, client)

@router.get("/api/v1/sovereign/agenda/today", include_in_schema=False)
async def api_today_agenda(db: AsyncSession = Depends(get_db)):
    """Get today's agenda."""
    from sqlalchemy import text
    from datetime import date
    result = await db.execute(text("SELECT items, completion_pct FROM sovereign_agendas WHERE date = :d"), {"d": date.today()})
    row = result.fetchone()
    if row:
        import json
        return {"date": str(date.today()), "items": json.loads(row.items) if isinstance(row.items, str) else row.items, "completion": row.completion_pct}
    return {"date": str(date.today()), "items": [], "note": "No agenda generated yet"}

@router.post("/api/v1/arch/blackboard", include_in_schema=False)
async def api_post_blackboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Post to shared blackboard."""
    body = await request.json()
    from app.arch.blackboard import post_to_blackboard
    return await post_to_blackboard(db, body.get("posted_by",""), body.get("category",""),
        body.get("key",""), body.get("value",""), body.get("confidence",1.0), body.get("visibility","all"))

@router.get("/api/v1/arch/blackboard", include_in_schema=False)
async def api_read_blackboard(agent: str = "sovereign", category: str = None, db: AsyncSession = Depends(get_db)):
    """Read blackboard."""
    from app.arch.blackboard import read_blackboard
    return await read_blackboard(db, agent, category)

@router.post("/api/v1/anomaly/post", include_in_schema=False)
async def api_post_anomaly(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    from app.arch.anomaly_correlation import post_anomaly
    return await post_anomaly(db, body.get("source",""), body.get("type",""), body.get("severity","medium"), body.get("details",{}), body.get("entity_ref"))

@router.post("/api/v1/anomaly/correlate", include_in_schema=False)
async def api_check_correlations(db: AsyncSession = Depends(get_db)):
    from app.arch.anomaly_correlation import check_correlations
    return await check_correlations(db)

@router.post("/api/v1/architect/codebase-scan", include_in_schema=False)
async def api_codebase_scan(db: AsyncSession = Depends(get_db)):
    from app.arch.codebase_scan import run_codebase_scan
    return await run_codebase_scan(db)

@router.post("/api/v1/ambassador/social-inbound", include_in_schema=False)
async def api_social_inbound(db: AsyncSession = Depends(get_db)):
    from app.arch.social_inbound import check_devto_comments
    return await check_devto_comments(db)

@router.post("/api/v1/sovereign/competitive-brief", include_in_schema=False)
async def api_competitive_brief(db: AsyncSession = Depends(get_db)):
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.competitive_intel import generate_competitive_brief
    return await generate_competitive_brief(db, client)

@router.post("/api/v1/sovereign/performance-review", include_in_schema=False)
async def api_performance_review(db: AsyncSession = Depends(get_db)):
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.performance_review import generate_monthly_review
    return await generate_monthly_review(db, client)

@router.post("/api/v1/ambassador/prospects", include_in_schema=False)
async def api_identify_prospects(db: AsyncSession = Depends(get_db)):
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.prospect_engine import identify_prospects
    return await identify_prospects(db, client)

@router.post("/api/v1/arbiter/synthetic-case", include_in_schema=False)
async def api_synthetic_case(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.synthetic_case_law import generate_synthetic_case
    return await generate_synthetic_case(db, client, body.get("archetype_id", 1))

@router.delete("/api/v1/arch/blackboard/{key}", include_in_schema=False)
async def api_blackboard_delete(key: str, db: AsyncSession = Depends(get_db)):
    """Retract a blackboard entry."""
    from sqlalchemy import text
    r = await db.execute(text("DELETE FROM blackboard WHERE key = :k"), {"k": key})
    await db.commit()
    return {"key": key, "status": "deleted"}

@router.patch("/api/v1/arch/messages/{message_id}/status", include_in_schema=False)
async def api_message_update_status(message_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Mark message as read/actioned."""
    body = await request.json()
    new_status = body.get("status", "read")
    from sqlalchemy import text
    await db.execute(text("UPDATE arch_mesh_messages SET status = :status WHERE message_id = cast(:mid as uuid)"),
                     {"status": new_status, "mid": message_id})
    await db.commit()
    return {"message_id": message_id, "status": new_status}

@router.post("/api/v1/arch/rba/score", include_in_schema=False)
async def api_rba_score(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    from app.arch.rba_engine import assess_agent_risk
    return await assess_agent_risk(db, body.get("agent_id",""), body.get("agent_name",""), body.get("country_code","ZA"), body.get("capabilities"))

@router.get("/api/v1/arch/rba/profile/{agent_id}", include_in_schema=False)
async def api_rba_profile(agent_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    r = await db.execute(text("SELECT * FROM agent_risk_profiles WHERE agent_id = :aid"), {"aid": agent_id})
    row = r.fetchone()
    if not row:
        return {"error": "No profile found", "agent_id": agent_id}
    return {"agent_id": row.agent_id, "risk_tier": row.risk_tier, "risk_score": row.risk_score}

@router.post("/api/v1/arch/anomalies/correlate", include_in_schema=False)
async def api_anomaly_correlate(db: AsyncSession = Depends(get_db)):
    from app.arch.anomaly_correlation import check_correlations
    return await check_correlations(db)

@router.post("/api/v1/arch/anomalies/report", include_in_schema=False)
async def api_anomaly_report(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    from app.arch.anomaly_correlation import post_anomaly
    return await post_anomaly(db, body.get("source_agent",""), body.get("anomaly_type",""), body.get("severity","medium"), body.get("details",""), body.get("entity_ref"))

@router.post("/api/v1/arch/case-law/generate", include_in_schema=False)
async def api_generate_case_law(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    from app.arch.synthetic_case_law import generate_synthetic_case
    try:
        await db.rollback()
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")
    results = []
    for i in range(min(body.get("count", 3), 10)):
        r = await generate_synthetic_case(db, None, (i % 10) + 1)
        results.append(r)
    return {"generated": len(results), "cases": results}

@router.get("/api/v1/arch/case-law", include_in_schema=False)
async def api_list_case_law(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    r = await db.execute(text("SELECT * FROM dispute_archetypes ORDER BY archetype_id LIMIT 100"))
    rows = r.fetchall()
    return {"count": len(rows), "archetypes": [{"id": row.archetype_id, "type": row.name, "description": row.description[:100]} for row in rows]}

@router.post("/api/v1/arch/codebase/scan", include_in_schema=False)
async def api_codebase_scan(db: AsyncSession = Depends(get_db)):
    from app.arch.codebase_scan import run_codebase_scan
    return await run_codebase_scan(db)

@router.post("/api/v1/arch/social/scan", include_in_schema=False)
async def api_social_scan(db: AsyncSession = Depends(get_db)):
    from app.arch.social_inbound import check_devto_comments
    return await check_devto_comments(db)

@router.post("/api/v1/arch/competitive/brief", include_in_schema=False)
async def api_competitive_brief(db: AsyncSession = Depends(get_db)):
    from app.arch.competitive_intel import generate_competitive_brief
    return await generate_competitive_brief(db, None)

@router.post("/api/v1/arch/performance/review", include_in_schema=False)
async def api_performance_review(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    from app.arch.performance_review import generate_monthly_review
    return await generate_monthly_review(db, None)

@router.post("/api/v1/arch/prospects/scan", include_in_schema=False)
async def api_prospect_scan(db: AsyncSession = Depends(get_db)):
    from app.arch.prospect_engine import identify_prospects
    return await identify_prospects(db, None)

@router.post("/api/v1/arch/memory/classify", include_in_schema=False)
async def api_classify_task_memory(request: Request):
    """Classify a task and return which memory categories would be loaded."""
    body = await request.json()
    from app.arch.progressive_memory import classify_task, estimate_token_savings
    source_types = classify_task(body.get("task_description", ""), body.get("task_type"))
    return {"task_description": body.get("task_description", "")[:100],
            "task_type": body.get("task_type"),
            "source_types_loaded": source_types,
            "progressive_loading": len(source_types) > 0,
            "note": "Empty source_types = full corpus loaded (flag disabled or task=all)"}

@router.get("/api/v1/arch/memory/stats", include_in_schema=False)
async def api_memory_stats(db: AsyncSession = Depends(get_db)):
    """Memory corpus statistics for progressive loading analysis."""
    from sqlalchemy import text
    total = await db.execute(text("SELECT count(*) FROM arch_memories"))
    by_tier = await db.execute(text(
        "SELECT memory_tier, count(*) FROM arch_memories GROUP BY memory_tier"
    ))
    by_scope = await db.execute(text(
        "SELECT agent_scope, count(*) FROM arch_memories GROUP BY agent_scope ORDER BY count DESC LIMIT 10"
    ))
    by_source = await db.execute(text(
        "SELECT source_type, count(*) FROM arch_memories GROUP BY source_type ORDER BY count DESC LIMIT 15"
    ))
    return {
        "total_memories": total.scalar() or 0,
        "by_tier": {r.memory_tier or "none": r.count for r in by_tier.fetchall()},
        "by_scope": {r.agent_scope or "global": r.count for r in by_scope.fetchall()},
        "by_source": {r.source_type or "unknown": r.count for r in by_source.fetchall()},
    }

@router.get("/api/v1/arch/skills", include_in_schema=False)
async def api_list_skills(request: Request, db: AsyncSession = Depends(get_db)):
    """List all agent skills."""
    agent = dict(request.query_params).get("agent_id")
    from app.arch.skill_engine import list_skills
    skills = await list_skills(db, agent)
    return {"skills": skills, "count": len(skills)}

@router.get("/api/v1/arch/skills/{agent_id}", include_in_schema=False)
async def api_agent_skills(agent_id: str, db: AsyncSession = Depends(get_db)):
    """List skills for a specific agent."""
    from app.arch.skill_engine import list_skills
    skills = await list_skills(db, agent_id)
    return {"agent_id": agent_id, "skills": skills, "count": len(skills)}

@router.post("/api/v1/arch/skills/match", include_in_schema=False)
async def api_match_skill(request: Request, db: AsyncSession = Depends(get_db)):
    """Find a matching skill for a task description."""
    body = await request.json()
    from app.arch.skill_engine import find_matching_skill
    skill = await find_matching_skill(db, body.get("agent_id", ""), body.get("task_description", ""))
    if skill:
        return {"matched": True, **skill}
    return {"matched": False, "message": "No matching skill found"}

@router.post("/api/v1/arch/skills/create", include_in_schema=False)
async def api_create_skill(request: Request, db: AsyncSession = Depends(get_db)):
    """Manually create a skill from a described procedure."""
    body = await request.json()
    from app.arch.skill_engine import create_skill_from_execution
    return await create_skill_from_execution(
        db, body.get("agent_id", ""), body.get("task_description", ""),
        body.get("steps", []), body.get("outcome", ""))

@router.post("/api/v1/arch/delegation/start", include_in_schema=False)
async def api_delegation_start(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    from app.arch.delegation_budget import start_delegation
    return await start_delegation(db, body.get("parent",""), body.get("child",""),
                                   body.get("task",""), body.get("budget"), body.get("parent_chain_id"))

@router.get("/api/v1/arch/delegation/chains", include_in_schema=False)
async def api_delegation_chains(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT chain_id, parent_agent, child_agent, chain_depth, tokens_consumed, max_tokens_budget, status "
        "FROM arch_delegation_chains ORDER BY started_at DESC LIMIT 20"
    ))
    return [{"chain_id": str(row.chain_id), "parent": row.parent_agent, "child": row.child_agent,
             "depth": row.chain_depth, "tokens_used": row.tokens_consumed,
             "budget": row.max_tokens_budget, "status": row.status} for row in r.fetchall()]

@router.get("/api/v1/arch/checkpoints", include_in_schema=False)
async def api_list_checkpoints(request: Request, db: AsyncSession = Depends(get_db)):
    agent = dict(request.query_params).get("agent_id")
    from app.arch.checkpoint import list_checkpoints
    return await list_checkpoints(db, agent)

@router.post("/api/v1/arch/checkpoints/{checkpoint_id}/rollback", include_in_schema=False)
async def api_rollback_checkpoint(checkpoint_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.checkpoint import rollback_checkpoint
    return await rollback_checkpoint(db, checkpoint_id)

@router.post("/api/v1/arch/context/compress", include_in_schema=False)
async def api_compress_context(request: Request):
    body = await request.json()
    from app.arch.context_compression import compress_if_needed
    messages = body.get("messages", [])
    compressed = await compress_if_needed(messages)
    return {"original_count": len(messages), "compressed_count": len(compressed),
            "savings": len(messages) - len(compressed)}

@router.get("/api/v1/arch/souls", include_in_schema=False)
async def api_list_souls():
    from app.arch.soul import list_souls
    return list_souls()

@router.get("/api/v1/arch/souls/{agent_name}", include_in_schema=False)
async def api_get_soul(agent_name: str):
    from app.arch.soul import load_soul
    content = load_soul(agent_name)
    if content:
        return {"agent": agent_name, "soul": content}
    return {"error": f"No SOUL file for {agent_name}"}

@router.post("/api/v1/arch/schedule/parse", include_in_schema=False)
async def api_parse_schedule(request: Request):
    body = await request.json()
    from app.arch.nl_scheduler import parse_nl_schedule
    return parse_nl_schedule(body.get("instruction", ""))

@router.get("/api/v1/arch/credentials/pool", include_in_schema=False)
async def api_credential_pool(db: AsyncSession = Depends(get_db)):
    from app.arch.credential_pool import get_pool_status
    return await get_pool_status(db)

@router.get("/api/v1/arch/plugins", include_in_schema=False)
async def api_list_plugins():
    from app.arch.plugin_system import discover_plugins
    plugins = discover_plugins()
    return {"plugins": plugins, "count": len(plugins)}

@router.get("/api/v1/arch/hooks", include_in_schema=False)
async def api_list_hooks(db: AsyncSession = Depends(get_db)):
    from app.arch.event_hooks import list_hooks
    return await list_hooks(db)

@router.post("/api/v1/arch/hooks/trigger", include_in_schema=False)
async def api_trigger_hook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    from app.arch.event_hooks import trigger_event
    results = await trigger_event(db, body.get("event_type", ""), body.get("data", {}))
    return {"event_type": body.get("event_type"), "hooks_executed": len(results), "results": results}

@router.get("/api/v1/arch/trajectories/stats", include_in_schema=False)
async def api_trajectory_stats(db: AsyncSession = Depends(get_db)):
    from app.arch.trajectory import get_trajectory_stats
    return await get_trajectory_stats(db)

@router.post("/api/v1/arch/trajectories/export", include_in_schema=False)
async def api_export_trajectories(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    from app.arch.trajectory import export_trajectories
    return await export_trajectories(db, body.get("agent_id"), body.get("format", "sharegpt"), body.get("limit", 100))

@router.post("/api/v1/arch/content/generate-now", include_in_schema=False)
async def api_content_generate_now(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json() if request.headers.get("content-type","").startswith("application/json") else {}
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.content_engine import generate_and_publish_all
    return await generate_and_publish_all(client, body.get("topic"))

@router.get("/api/v1/arch/content/calendar", include_in_schema=False)
async def api_content_calendar():
    from app.arch.campaign import THEMES, get_today_theme
    return {"today": get_today_theme(), "themes": THEMES}

@router.post("/api/v1/arch/reddit/post", include_in_schema=False)
async def api_reddit_post(request: Request):
    body = await request.json()
    from app.arch.reddit_poster import post_to_reddit
    return await post_to_reddit(body.get("subreddit", "test"), body.get("title", ""), body.get("body", ""))

@router.get("/api/v1/arch/reddit/rules/{subreddit}", include_in_schema=False)
async def api_reddit_rules(subreddit: str):
    from app.arch.reddit_poster import get_subreddit_rules
    return await get_subreddit_rules(subreddit)

@router.post("/api/v1/arch/medium/post", include_in_schema=False)
async def api_medium_post(request: Request):
    body = await request.json()
    from app.arch.medium_poster import post_to_medium
    return await post_to_medium(body.get("title", ""), body.get("body", ""), body.get("tags"))

@router.post("/api/v1/arch/github/issue", include_in_schema=False)
async def api_github_issue(request: Request):
    body = await request.json()
    from app.arch.github_submissions import create_github_issue
    return await create_github_issue(body.get("owner", ""), body.get("repo", ""), body.get("title", ""), body.get("body", ""))

@router.get("/api/v1/arch/github/search", include_in_schema=False)
async def api_github_search(request: Request):
    params = dict(request.query_params)
    from app.arch.github_submissions import search_repos
    return await search_repos(params.get("q", "ai-agent"), params.get("sort", "stars"), int(params.get("limit", "10")))

@router.get("/api/v1/arch/directories", include_in_schema=False)
async def api_list_directories():
    from app.arch.directory_submitter import list_directories
    return await list_directories()

@router.post("/api/v1/arch/directories/prepare/{directory}", include_in_schema=False)
async def api_prepare_submission(directory: str):
    from app.arch.directory_submitter import prepare_submission
    return await prepare_submission(directory)

@router.post("/api/v1/arch/directories/submit-github/{directory}", include_in_schema=False)
async def api_submit_github_directory(directory: str):
    from app.arch.directory_submitter import submit_github_listing
    return await submit_github_listing(directory)

@router.post("/api/v1/arch/directories/screenshot", include_in_schema=False)
async def api_screenshot(request: Request):
    body = await request.json()
    from app.arch.directory_submitter import take_screenshot
    return await take_screenshot(body.get("url", ""))

@router.post("/api/v1/arch/inbox/auto-resolve", include_in_schema=False)
async def api_inbox_auto_resolve(db: AsyncSession = Depends(get_db)):
    """Trigger inbox auto-resolution scan."""
    from app.arch.inbox_resolver import resolve_inbox_items
    return await resolve_inbox_items(db)

@router.get("/api/v1/arch/inbox/resolvable", include_in_schema=False)
async def api_inbox_resolvable(db: AsyncSession = Depends(get_db)):
    """Preview which inbox items agents CAN resolve."""
    from app.arch.inbox_resolver import get_resolvable_items
    items = await get_resolvable_items(db)
    resolvable = [i for i in items if i["can_resolve"]]
    return {"total_pending": len(items), "resolvable": len(resolvable),
            "human_required": len(items) - len(resolvable), "items": items}

@router.post("/api/v1/arch/proactive/scan", include_in_schema=False)
async def api_proactive_scan(db: AsyncSession = Depends(get_db)):
    """Trigger proactive action scan."""
    from app.arch.proactive_scanner import run_proactive_scan
    return await run_proactive_scan(db)

@router.get("/api/v1/arch/skill-learning/log", include_in_schema=False)
async def api_skills_learning_log(db: AsyncSession = Depends(get_db)):
    """Recent skill creation and improvement events."""
    from app.arch.skill_learner import get_learning_log
    return await get_learning_log(db)

@router.post("/api/v1/arch/github/engage", include_in_schema=False)
async def api_github_engage(db: AsyncSession = Depends(get_db)):
    """Run full GitHub engagement cycle — scan, identify, comment, report."""
    from app.arch.github_engagement import run_full_engagement_cycle
    return await run_full_engagement_cycle(db)

@router.get("/api/v1/arch/github/trending", include_in_schema=False)
async def api_github_trending():
    """Get trending AI agent repos."""
    from app.arch.github_engagement import scan_trending_repos
    return await scan_trending_repos(10)

@router.get("/api/v1/arch/github/opportunities", include_in_schema=False)
async def api_github_opportunities():
    """Scan for discussion engagement opportunities."""
    from app.arch.github_engagement import scan_discussions_for_opportunities
    return await scan_discussions_for_opportunities()

@router.get("/api/v1/arch/github/repo-status", include_in_schema=False)
async def api_github_repo_status():
    """Monitor our tioli-agentis repo."""
    from app.arch.github_engagement import monitor_our_repo
    return await monitor_our_repo()

@router.post("/api/v1/arch/devto/scan", include_in_schema=False)
async def api_devto_scan(db: AsyncSession = Depends(get_db)):
    """Run DEV.to scan cycle."""
    from app.arch.devto_monitor import run_devto_scan
    return await run_devto_scan(db)

@router.post("/api/v1/arch/linkedin/thought-leadership", include_in_schema=False)
async def api_linkedin_thought_leadership():
    """Generate and publish a LinkedIn thought leadership post."""
    from app.arch.linkedin_scheduler import publish_thought_leadership
    return await publish_thought_leadership()

@router.get("/api/v1/quests", include_in_schema=False)
async def list_quests(db: AsyncSession = Depends(get_db)):
    """List all available quests with rewards."""
    result = await db.execute(_quest_text(
        "SELECT id::text, quest_name, description, reward_credits, xp_reward, badge_name "
        "FROM agentis_quests WHERE active = true ORDER BY reward_credits ASC LIMIT 100"
    ))
    return {"quests": [
        {"id": r.id, "name": r.quest_name, "description": r.description,
         "credits": r.reward_credits, "xp": r.xp_reward, "badge": r.badge_name}
        for r in result.fetchall()
    ]}

@router.get("/api/v1/quests/{agent_id}/progress", include_in_schema=False)
async def quest_progress(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Check an agent's quest progress, XP, and badges."""
    # Get XP and level
    xp_row = await db.execute(_quest_text(
        "SELECT total_xp, level, streak_days, badges FROM agentis_agent_xp WHERE agent_id = :aid"
    ), {"aid": agent_id})
    xp = xp_row.fetchone()

    # Get completed quests
    completed = await db.execute(_quest_text(
        "SELECT q.quest_name, qc.completed_at "
        "FROM agentis_quest_completions qc JOIN agentis_quests q ON qc.quest_id = q.id "
        "WHERE qc.agent_id = :aid ORDER BY qc.completed_at DESC"
    ), {"aid": agent_id})

    return {
        "agent_id": agent_id,
        "xp": xp.total_xp if xp else 0,
        "level": xp.level if xp else 1,
        "streak_days": xp.streak_days if xp else 0,
        "badges": xp.badges if xp else [],
        "completed_quests": [
            {"quest": r.quest_name, "completed_at": r.completed_at.isoformat()}
            for r in completed.fetchall()
        ],
    }

@router.get("/api/v1/leaderboard", include_in_schema=False)
async def xp_leaderboard(db: AsyncSession = Depends(get_db)):
    """Top agents by XP — gamification leaderboard."""
    result = await db.execute(_quest_text(
        "SELECT agent_id, total_xp, level, streak_days, badges "
        "FROM agentis_agent_xp ORDER BY total_xp DESC LIMIT 20"
    ))
    return {"leaderboard": [
        {"agent": r.agent_id, "xp": r.total_xp, "level": r.level,
         "streak": r.streak_days, "badges": r.badges}
        for r in result.fetchall()
    ]}

@router.post("/api/v1/comms/ambassador-weekly", include_in_schema=False)
async def trigger_ambassador_weekly(db: AsyncSession = Depends(get_db)):
    """Trigger Ambassador weekly blog + social media generation."""
    from app.arch.comms_pipeline import generate_ambassador_weekly
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    return await generate_ambassador_weekly(db, client)

@router.post("/api/v1/comms/architect-technical", include_in_schema=False)
async def trigger_architect_technical(db: AsyncSession = Depends(get_db)):
    """Trigger Architect technical blog generation."""
    from app.arch.comms_pipeline import generate_architect_technical
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    return await generate_architect_technical(db, client)

@router.post("/api/v1/comms/sovereign-report", include_in_schema=False)
async def trigger_sovereign_report(db: AsyncSession = Depends(get_db)):
    """Trigger Sovereign monthly governance report."""
    from app.arch.comms_pipeline import generate_sovereign_report
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    return await generate_sovereign_report(db, client)

@router.post("/api/v1/nps", include_in_schema=False)
async def submit_nps(request: Request, db: AsyncSession = Depends(get_db)):
    """Submit NPS score (0-10) with optional feedback."""
    body = await request.json()
    score = body.get("score")
    feedback = body.get("feedback", "")
    agent_id = body.get("agent_id", "anonymous")
    if score is None or not (0 <= score <= 10):
        return JSONResponse(status_code=400, content={"error": "Score must be 0-10"})
    from sqlalchemy import text
    import uuid
    await db.execute(text(
        "INSERT INTO nps_responses (id, agent_id, score, feedback, created_at) "
        "VALUES (:id, :aid, :score, :fb, now())"
    ), {"id": str(uuid.uuid4()), "aid": agent_id, "score": score, "fb": feedback})
    await db.commit()
    category = "promoter" if score >= 9 else "passive" if score >= 7 else "detractor"
    return {"status": "recorded", "score": score, "category": category, "thank_you": "Your feedback helps us improve AGENTIS."}

@router.get("/api/v1/nps/summary", include_in_schema=False)
async def nps_summary(db: AsyncSession = Depends(get_db)):
    """Get NPS score summary."""
    from sqlalchemy import text
    result = await db.execute(text("SELECT score, count(*) FROM nps_responses GROUP BY score ORDER BY score LIMIT 100"))
    rows = result.fetchall()
    total = sum(r[1] for r in rows)
    if total == 0:
        return {"nps_score": 0, "total_responses": 0, "breakdown": {}}
    promoters = sum(r[1] for r in rows if r[0] >= 9)
    detractors = sum(r[1] for r in rows if r[0] <= 6)
    nps = round(((promoters - detractors) / total) * 100)
    note = f"Based on {total} responses" if total >= 10 else f"Based on {total} responses (minimum 10 recommended for statistical significance)"
    return {"nps_score": nps, "total_responses": total, "note": note, "promoters": promoters, "passives": total - promoters - detractors, "detractors": detractors}

@router.get("/api/v1/badge/powered-by", include_in_schema=False)
async def powered_by_badge():
    """SVG badge: Powered by AGENTIS."""
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="180" height="28" viewBox="0 0 180 28">
    <rect width="180" height="28" rx="4" fill="#061423"/>
    <rect width="90" height="28" rx="4" fill="#0f1c2c"/>
    <text x="10" y="18" font-family="Inter,sans-serif" font-size="11" fill="#77d4e5" font-weight="600">powered by</text>
    <text x="96" y="18" font-family="Inter,sans-serif" font-size="11" fill="#edc05f" font-weight="700">AGENTIS</text>
    </svg>"""
    from starlette.responses import Response
    return Response(content=svg, media_type="image/svg+xml")

@router.post("/api/v1/social/post", include_in_schema=False)
async def api_social_post(request: Request):
    """Post to all social channels (Twitter, Discord, DEV.to)."""
    body = await request.json()
    text = body.get("text", "")
    title = body.get("title", "")
    article_body = body.get("body", "")
    if not text:
        return JSONResponse(status_code=400, content={"error": "text required"})
    from app.arch.social_poster import publish_all
    return await publish_all(text, title, article_body)

@router.post("/api/v1/knowledge/research", include_in_schema=False)
async def api_research_topic(request: Request):
    """Research a topic and store findings."""
    body = await request.json()
    topic = body.get("topic", "")
    if not topic:
        return JSONResponse(status_code=400, content={"error": "topic required"})
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.knowledge import research_topic
    return await research_topic(client, topic)

@router.post("/api/v1/knowledge/daily-scan", include_in_schema=False)
async def api_daily_knowledge_scan(db: AsyncSession = Depends(get_db)):
    """Run daily knowledge acquisition scan."""
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.knowledge import daily_knowledge_scan
    return await daily_knowledge_scan(db, client)

@router.post("/api/v1/catalyst/experiment", include_in_schema=False)
async def api_create_experiment(request: Request, db: AsyncSession = Depends(get_db)):
    """Create an A/B experiment."""
    body = await request.json()
    from app.arch.catalyst import create_experiment
    return await create_experiment(db, body.get("title",""), body.get("hypothesis",""),
                                   body.get("variants",[]), body.get("metric",""))

@router.get("/api/v1/catalyst/experiments", include_in_schema=False)
async def api_list_experiments(db: AsyncSession = Depends(get_db)):
    """List all experiments."""
    from app.arch.catalyst import list_experiments
    return await list_experiments(db)

@router.post("/api/v1/content/generate", include_in_schema=False)
async def api_generate_content(request: Request):
    """Generate content in all formats for a topic."""
    body = await request.json()
    topic = body.get("topic", "")
    if not topic:
        return JSONResponse(status_code=400, content={"error": "topic required"})
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.content_formats import generate_all_formats
    return await generate_all_formats(client, topic)

@router.post("/api/v1/catalyst/experiment/{exp_id}/measure", include_in_schema=False)
async def api_measure_experiment(exp_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Record measurement results for an experiment."""
    body = await request.json()
    from app.arch.catalyst import measure_experiment
    return await measure_experiment(db, exp_id, body)

@router.post("/api/v1/campaign/trigger", include_in_schema=False)
async def api_campaign_trigger():
    """Manually trigger today's campaign content generation."""
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.campaign import generate_and_publish_daily
    return await generate_and_publish_daily(client)

@router.get("/api/v1/campaign/theme", include_in_schema=False)
async def api_campaign_theme():
    """Get today's campaign theme."""
    from app.arch.campaign import get_today_theme
    return {"theme": get_today_theme(), "campaign": "April 2026 Attraction"}

@router.post("/api/v1/campaign/article", include_in_schema=False)
async def api_campaign_article():
    """Trigger weekly DEV.to article generation."""
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.campaign import generate_weekly_devto_article
    return await generate_weekly_devto_article(client)
