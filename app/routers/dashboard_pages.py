"""Router: dashboard_pages - auto-extracted from main.py (A-001)."""
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
from app.main_deps import (blockchain, fee_engine, financial_governance, governance_service, growth_engine, guild_service, lending_marketplace, optimization_engine, payout_engine, pipeline_service, platform_monitor, pricing_engine, subscription_service, templates, trading_engine, verticals_service)

from app.dashboard.routes import get_current_owner

router = APIRouter()


def _tx_display(tx: dict) -> object:
    class TxDisplay:
        pass
    d = TxDisplay()
    d.timestamp = tx.get("timestamp", "")
    d.type = tx.get("type", "unknown")
    d.sender_id = tx.get("sender_id", "")
    d.receiver_id = tx.get("receiver_id", "")
    d.amount = tx.get("amount", 0)
    d.currency = tx.get("currency", "AGENTIS")
    return d



def _get_tasks():
    """Build task list from build tracker and known work items."""
    tasks = [
        {"title": "CIPC Cooperative Registration", "description": "Register Agentis cooperative with CIPC", "status": "pending", "category": "regulatory", "date": ""},
        {"title": "SARB IFLAB Innovation Hub Application", "description": "Apply to SARB regulatory sandbox", "status": "pending", "category": "regulatory", "date": ""},
        {"title": "CBDA Pre-Application Consultation", "description": "Meet CBDA to discuss CFI requirements", "status": "pending", "category": "regulatory", "date": ""},
        {"title": "FSP Category I Application", "description": "FSCA licence for intermediary services", "status": "pending", "category": "regulatory", "date": ""},
        {"title": "FIC Registration (goAML)", "description": "Register with Financial Intelligence Centre", "status": "pending", "category": "regulatory", "date": ""},
        {"title": "Information Regulator Registration", "description": "POPIA registration", "status": "pending", "category": "regulatory", "date": ""},
        {"title": "Compliance Engine", "description": "Module 10: FICA/AML, CTR/STR, sanctions, audit", "status": "done", "category": "feature", "date": "2026-03-23"},
        {"title": "Member Identity Infrastructure", "description": "Module 1: KYC, mandates L0-L3FA, member registry", "status": "done", "category": "feature", "date": "2026-03-23"},
        {"title": "Core Banking Accounts", "description": "Module 2: Share/Call/Savings, interest engine", "status": "done", "category": "feature", "date": "2026-03-23"},
        {"title": "Payment Infrastructure", "description": "Module 4: Internal transfers, fraud detection, beneficiaries", "status": "done", "category": "feature", "date": "2026-03-23"},
        {"title": "Phase 0 Pre-Banking Wallet", "description": "Enhancement #2: FSP-only e-money product", "status": "done", "category": "feature", "date": "2026-03-23"},
        {"title": "Banking Dashboard & UI", "description": "6 sub-pages, sidebar menu, full transparency", "status": "done", "category": "feature", "date": "2026-03-24"},
        {"title": "MCP Banking Tools", "description": "7 new tools: balance, transactions, payment, etc.", "status": "done", "category": "feature", "date": "2026-03-23"},
        {"title": "57 Agentis Unit Tests", "description": "All passing — compliance, members, accounts, payments", "status": "done", "category": "feature", "date": "2026-03-23"},
        {"title": "57 Live Server Tests", "description": "All passing — endpoints, feature flags, error codes", "status": "done", "category": "feature", "date": "2026-03-24"},
        {"title": "Mobile Hamburger Menu", "description": "Landing page + dashboard responsive navigation", "status": "done", "category": "feature", "date": "2026-03-24"},
        {"title": "Material Symbols Font Fix", "description": "Cross-browser icon rendering on mobile Safari", "status": "done", "category": "fix", "date": "2026-03-24"},
        {"title": "Cloudflare WAF/DDoS Protection", "description": "Security hardening — free tier", "status": "pending", "category": "security", "date": ""},
        {"title": "Field-Level Encryption (AES-256-GCM)", "description": "POPIA s19 — encrypt PII at rest", "status": "pending", "category": "security", "date": ""},
        {"title": "Full Lending Suite", "description": "Module 3: NCA-compliant loans, overdrafts, advances", "status": "pending", "category": "feature", "date": ""},
        {"title": "Treasury & Liquidity", "description": "Module 6: SARB ratios, DI returns, snapshots", "status": "pending", "category": "feature", "date": ""},
        {"title": "Cooperative Governance", "description": "Module 9: AGM, dividends, voting, share buyback", "status": "pending", "category": "feature", "date": ""},
        {"title": "Foreign Exchange Module", "description": "Module 7: FX trading, SDA/FIA tracking", "status": "pending", "category": "feature", "date": ""},
        {"title": "Intermediary Services", "description": "Module 5: Insurance, pension, medical aid", "status": "pending", "category": "feature", "date": ""},
        {"title": "API-as-a-Service Licensing", "description": "Enhancement #3: License mandate framework to banks", "status": "pending", "category": "feature", "date": ""},
        {"title": "Reputation Engine", "description": "Task allocation, dispatch, SLA tracking, quality ratings, peer endorsements, 90-day decay scoring with blockchain-recorded outcomes", "status": "done", "category": "feature", "date": "2026-03-29"},
        {"title": "Telegram Bot Integration", "description": "Webhook-based Telegram bot with /discover, /status, /wallet, /reputation commands and push notifications", "status": "done", "category": "feature", "date": "2026-03-29"},
        {"title": "Docker Self-Hosted Package", "description": "One-command docker-compose deployment with PostgreSQL, Redis, auto-seed, health checks", "status": "done", "category": "feature", "date": "2026-03-29"},
    ]
    return tasks



def _get_git_log():
    """Fetch git commit history with stats."""
    import subprocess
    commits = []
    try:
        raw = subprocess.run(
            ["git", "log", "--pretty=format:%H|%h|%s|%an|%ad|%b%x00", "--date=short",
             "--stat", "-50"],
            capture_output=True, text=True, cwd="/home/tioli/app", timeout=10
        ).stdout
    except Exception:
        try:
            import os
            cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            raw = subprocess.run(
                ["git", "log", "--pretty=format:%H|%h|%s|%an|%ad|%b%x00", "--date=short",
                 "--stat", "-50"],
                capture_output=True, text=True, cwd=cwd, timeout=10
            ).stdout
        except Exception:
            return [], 0, 0, 0
    total_ins = 0
    total_del = 0
    total_files = 0
    entries = raw.split("\x00")
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        lines = entry.split("\n")
        header = lines[0] if lines else ""
        parts = header.split("|", 5)
        if len(parts) < 5:
            continue
        full_hash, short_hash, subject, author, date = parts[0], parts[1], parts[2], parts[3], parts[4]
        body = parts[5].strip() if len(parts) > 5 else ""
        ins = 0
        dels = 0
        fc = 0
        changed_files = []
        for line in lines[1:]:
            line = line.strip()
            if " | " in line and ("+" in line or "-" in line or "Bin" in line):
                fc += 1
                fpath = line.split("|")[0].strip()
                changed_files.append({"path": fpath, "status": "M"})
            if "insertion" in line or "deletion" in line:
                import re
                m_ins = re.search(r"(\d+) insertion", line)
                m_del = re.search(r"(\d+) deletion", line)
                if m_ins:
                    ins = int(m_ins.group(1))
                if m_del:
                    dels = int(m_del.group(1))
        total_ins += ins
        total_del += dels
        total_files += fc
        commits.append({
            "hash": full_hash, "short": short_hash, "subject": subject,
            "author": author, "date": date, "body": body,
            "insertions": ins, "deletions": dels, "files_changed": fc,
            "changed_files": changed_files,
        })
    return commits, total_files, total_ins, total_del



def _banking_context(request, active_tab="overview", active_nav="banking"):
    """Shared context for all Agentis banking pages."""
    phase = "0 — Pre-Banking"
    if settings.agentis_cfi_payments_enabled:
        phase = "1 — CFI"
    elif settings.agentis_cfi_accounts_enabled:
        phase = "1 — CFI (Accounts)"
    elif settings.agentis_cfi_member_enabled:
        phase = "1 — CFI (Members)"
    elif settings.agentis_compliance_enabled:
        phase = "0 — Compliance Active"
    return {"request": request, "authenticated": True, "active": active_nav,
        "phase": phase, "active_tab": active_tab,
    }


@router.get("/dashboard/github-engagement", response_class=HTMLResponse)
async def github_engagement_page(request: Request):
    """GitHub community engagement dashboard — HTML version."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    total_drafts = 0; pending_review = 0; approved = 0; posted = 0; quality_pass_rate = 0; drafts = []
    try:
        async with async_session() as db:
            from app.agents_alive.github_engagement import get_engagement_dashboard
            data = await get_engagement_dashboard(db)
            total_drafts = data.get("total_drafts", 0)
            pending_review = data.get("pending_review", 0)
            approved = data.get("approved", 0)
            posted = data.get("posted", 0)
            quality_pass_rate = data.get("quality_pass_rate", 0)
            drafts = data.get("recent_drafts", [])
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    return templates.TemplateResponse(request, "github_engagement.html",  context={
        "authenticated": True, "active": "github-engagement",
        "total_drafts": total_drafts, "pending_review": pending_review,
        "approved": approved, "posted": posted,
        "quality_pass_rate": quality_pass_rate, "drafts": drafts,
    })

@router.get("/dashboard/oversight", response_class=HTMLResponse)
async def dashboard_oversight(request: Request, db: AsyncSession = Depends(get_db)):
    """Command Centre — agent intelligence, outreach, feedback, oversight."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/gateway", status_code=302)

    # Pre-load agent data server-side so it renders immediately
    from datetime import datetime as _dt, timedelta, timezone as _tz
    from app.policy_engine.models import PolicyAuditLog, PendingApproval
    from app.agent_memory.models import AgentMemory

    agents_result = await db.execute(
        select(Agent).where(Agent.is_active == True).order_by(Agent.created_at.desc()).limit(50)
    )
    agents_list = agents_result.scalars().all()
    now = _dt.now(_tz.utc)
    week_ago = now - timedelta(days=7)

    agent_cards = []
    for agent in agents_list:
        wallets = (await db.execute(
            select(Wallet).where(Wallet.agent_id == agent.id)
        )).scalars().all()
        balance_summary = {w.currency: round(w.balance, 2) for w in wallets}

        violations = (await db.execute(
            select(func.count(PolicyAuditLog.id)).where(
                PolicyAuditLog.agent_id == agent.id,
                PolicyAuditLog.result.in_(["DENY", "ESCALATE"]),
                PolicyAuditLog.created_at >= week_ago,
            )
        )).scalar() or 0

        memory_count = (await db.execute(
            select(func.count(AgentMemory.id)).where(AgentMemory.agent_id == agent.id)
        )).scalar() or 0

        health = "GREEN"
        if violations > 0:
            health = "AMBER"
        if violations > 3:
            health = "RED"

        agent_cards.append({
            "agent_id": agent.id, "name": agent.name, "platform": agent.platform,
            "is_active": agent.is_active, "wallets": balance_summary,
            "violations": violations, "memory": memory_count, "health": health,
        })

    green = len([a for a in agent_cards if a["health"] == "GREEN"])
    amber = len([a for a in agent_cards if a["health"] == "AMBER"])
    red = len([a for a in agent_cards if a["health"] == "RED"])

    # Pre-load ALL tab data server-side (JS fetch can't auth with session cookie)
    hydra_data = {}
    analytics_data = {}
    catalyst_data = {}
    amplifier_data = {}
    feedback_data = {}
    outreach_data = {}

    try:
        from app.agents_alive.hydra_outreach import get_hydra_dashboard
        hydra_data = await get_hydra_dashboard(db)
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")
    try:
        from app.agents_alive.visitor_analytics import get_analytics_dashboard
        analytics_data = await get_analytics_dashboard(db)
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")
    try:
        from app.agents_alive.community_catalyst import get_catalyst_dashboard
        catalyst_data = await get_catalyst_dashboard(db)
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")
    try:
        from app.agents_alive.engagement_amplifier import get_amplifier_dashboard
        amplifier_data = await get_amplifier_dashboard(db)
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")
    try:
        from app.agents_alive.feedback_loop import get_feedback_dashboard
        feedback_data = await get_feedback_dashboard(db)
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")
    outreach_campaigns = []
    outreach_content = []
    try:
        from app.outreach_campaigns.service import OutreachService
        _os = OutreachService()
        outreach_data = await _os.get_dashboard(db)
        outreach_campaigns = await _os.list_campaigns(db)
        outreach_content = await _os.list_content(db, status="draft")
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    # AI Optimization Recommendations (moved from Governance page)
    recommendations = []
    try:
        recommendations = await optimization_engine.get_recommendations(db, limit=10)
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    return templates.TemplateResponse(request, "oversight.html",  context={
        "authenticated": True, "active": "oversight",
        "agent_cards": agent_cards,
        "summary": {"green": green, "amber": amber, "red": red},
        "total_agents": len(agent_cards),
        "hydra": hydra_data,
        "analytics": analytics_data,
        "catalyst": catalyst_data,
        "amplifier": amplifier_data,
        "feedback": feedback_data,
        "outreach": outreach_data,
        "outreach_campaigns": outreach_campaigns,
        "outreach_content": outreach_content,
        "recommendations": recommendations,
    })

@router.get("/dashboard/integrity", response_class=HTMLResponse)
async def integrity_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Platform Integrity dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    from app.integrity.detector import get_integrity_dashboard
    data = await get_integrity_dashboard(db)
    return templates.TemplateResponse(request, "integrity.html",  context={
        "authenticated": True, "active": "integrity",
        "integrity": data,
    })

@router.get("/dashboard/reputation", response_class=HTMLResponse)
async def reputation_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Reputation Engine dashboard — leaderboard, ratings, endorsements."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    from sqlalchemy import func as sa_func, select as sa_select
    from app.agentbroker.models import AgentReputationScore
    from app.reputation.models import TaskRequest, TaskDispatch, TaskOutcome, PeerEndorsement
    from app.agents.models import Agent

    # Stats
    total_tasks = (await db.execute(sa_select(sa_func.count(TaskRequest.task_id)))).scalar() or 0
    completed_tasks = (await db.execute(
        sa_select(sa_func.count(TaskRequest.task_id)).where(TaskRequest.status == "completed")
    )).scalar() or 0
    active_dispatches = (await db.execute(
        sa_select(sa_func.count(TaskDispatch.dispatch_id)).where(
            TaskDispatch.status.in_(["dispatched", "accepted", "in_progress"])
        )
    )).scalar() or 0
    avg_quality = (await db.execute(sa_select(sa_func.avg(TaskOutcome.quality_rating)))).scalar() or 0.0
    total_ratings = (await db.execute(sa_select(sa_func.count(TaskOutcome.outcome_id)))).scalar() or 0
    total_endorsements = (await db.execute(sa_select(sa_func.count(PeerEndorsement.endorsement_id)))).scalar() or 0

    # Leaderboard
    scores_result = await db.execute(
        sa_select(AgentReputationScore).order_by(AgentReputationScore.overall_score.desc()).limit(20)
    )
    scores = scores_result.scalars().all()

    leaderboard = []
    for s in scores:
        agent_result = await db.execute(sa_select(Agent.name).where(Agent.id == s.agent_id))
        agent_name = agent_result.scalar()
        quality_result = await db.execute(
            sa_select(sa_func.avg(TaskOutcome.quality_rating)).where(TaskOutcome.agent_id == s.agent_id)
        )
        quality_avg = quality_result.scalar()
        leaderboard.append({
            "agent_id": s.agent_id,
            "agent_name": agent_name,
            "overall": s.overall_score or 0,
            "delivery": s.delivery_rate or 0,
            "on_time": s.on_time_rate or 0,
            "disputes": s.dispute_rate or 0,
            "total_engagements": s.total_engagements or 0,
            "quality_avg": quality_avg,
        })

    # Recent ratings
    ratings_result = await db.execute(
        sa_select(TaskOutcome).order_by(TaskOutcome.created_at.desc()).limit(10)
    )
    recent_ratings = ratings_result.scalars().all()

    # Recent endorsements
    endorsements_result = await db.execute(
        sa_select(PeerEndorsement).order_by(PeerEndorsement.created_at.desc()).limit(10)
    )
    recent_endorsements_raw = endorsements_result.scalars().all()
    recent_endorsements = [
        {"skill_tag": e.skill_tag, "endorser_id": e.endorser_agent_id,
         "endorsee_id": e.endorsee_agent_id, "created_at": e.created_at}
        for e in recent_endorsements_raw
    ]

    return templates.TemplateResponse(request, "reputation.html",  context={
        "authenticated": True, "active": "reputation",
        "stats": {
            "total_tasks": total_tasks, "completed_tasks": completed_tasks,
            "active_dispatches": active_dispatches, "avg_quality": avg_quality,
            "total_ratings": total_ratings, "total_endorsements": total_endorsements,
        },
        "leaderboard": leaderboard,
        "recent_ratings": recent_ratings,
        "recent_endorsements": recent_endorsements,
    })

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    info = blockchain.get_chain_info()
    all_tx = blockchain.get_all_transactions()
    founder_earnings = sum(tx.get("founder_commission", 0) for tx in all_tx)
    charity_total = sum(tx.get("charity_fee", 0) for tx in all_tx)
    recent = all_tx[-20:] if all_tx else []
    recent.reverse()

    async with async_session() as db:
        agent_count = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
        proposals = await governance_service.get_proposals(db, status="pending")
        try:
            adoption = await growth_engine.get_adoption_metrics(db)
        except Exception:
            adoption = {"transaction_metrics": {}}

    # Services summary for dashboard
    services_summary = [
        {"name": "Subscriptions", "status": "live", "category": "SaaS"},
        {"name": "Guilds", "status": "live", "category": "Collectives"},
        {"name": "Benchmarking", "status": "live", "category": "Evaluation"},
        {"name": "Training Data", "status": "live", "category": "Data Products"},
        {"name": "Intelligence", "status": "live", "category": "Analytics"},
        {"name": "Compliance", "status": "live", "category": "Reviews"},
        {"name": "Verticals", "status": "live", "category": "Sectors"},
        {"name": "Pipelines", "status": "conditional", "category": "Orchestration"},
        {"name": "Treasury", "status": "conditional", "category": "Portfolio"},
        {"name": "AgentBroker", "status": "conditional", "category": "Engagements"},
    ]

    # Revenue data for dashboard
    rev_data = {"mtd_usd": 0, "target_usd": 5000, "progress_pct": 0, "projected_month_usd": 0}
    hub_stats = {"total_profiles": 0, "total_posts": 0, "total_connections": 0, "active_channels": 0}
    try:
        async with async_session() as db2:
            rev_full = await revenue_service.get_revenue_dashboard(db2)
            rev_data = rev_full.get("gauge", rev_data)
            if settings.agenthub_enabled:
                hub_stats = await agenthub_service.get_community_stats(db2)
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    # Task Board summary for dashboard widget
    all_tasks = _get_tasks()
    tasks_done = len([t for t in all_tasks if t["status"] == "done"])
    tasks_progress = len([t for t in all_tasks if t["status"] == "in_progress"])
    tasks_pending = len([t for t in all_tasks if t["status"] == "pending"])
    task_pct = int((tasks_done / len(all_tasks)) * 100) if all_tasks else 0
    task_summary = {
        "total": len(all_tasks), "done": tasks_done,
        "progress": tasks_progress, "pending": tasks_pending,
        "pct": task_pct,
        "recent": all_tasks[:6],
    }

    # Banking summary for dashboard widget
    banking_summary = {
        "phase": "Pre-Banking",
        "modules_built": 5, "modules_pending": 7,
        "tests": 114, "flags_enabled": 0, "flags_total": 18,
    }

    # Code log summary for dashboard widget
    try:
        commits, total_files, total_ins, total_del = _get_git_log()
        codelog_summary = {
            "total": len(commits), "files": total_files,
            "insertions": total_ins, "deletions": total_del,
            "recent": commits[:5],
        }
    except Exception:
        codelog_summary = {"total": 0, "files": 0, "insertions": 0, "deletions": 0, "recent": []}

    return templates.TemplateResponse(request, "dashboard.html",  context={
        "authenticated": True, "active": "dashboard",
        "chain_info": info, "agent_count": agent_count,
        "founder_earnings": founder_earnings, "charity_total": charity_total,
        "recent_transactions": [_tx_display(tx) for tx in recent],
        "pending_proposals": proposals,
        "tx_metrics": adoption.get("transaction_metrics", {}),
        "charity_status": fee_engine.get_charity_status(),
        "services_summary": services_summary,
        "rev": rev_data, "hub_stats": hub_stats,
        "task_summary": task_summary,
        "banking_summary": banking_summary,
        "codelog_summary": codelog_summary,
    })

@router.get("/banking", response_class=HTMLResponse)
async def banking_page(request: Request):
    """Agentis Cooperative Bank — Overview dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "banking.html", context=_banking_context(request, "overview", "banking"))

@router.get("/banking/accounts", response_class=HTMLResponse)
async def banking_accounts_page(request: Request):
    """Agentis — Accounts page."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "banking.html", context=_banking_context(request, "accounts", "banking-accounts"))

@router.get("/banking/payments", response_class=HTMLResponse)
async def banking_payments_page(request: Request):
    """Agentis — Payments page."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "banking.html", context=_banking_context(request, "payments", "banking-payments"))

@router.get("/banking/members", response_class=HTMLResponse)
async def banking_members_page(request: Request):
    """Agentis — Members page."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "banking.html", context=_banking_context(request, "members", "banking-members"))

@router.get("/banking/compliance", response_class=HTMLResponse)
async def banking_compliance_page(request: Request):
    """Agentis — Compliance page."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "banking.html", context=_banking_context(request, "compliance", "banking-compliance"))

@router.get("/banking/regulatory", response_class=HTMLResponse)
async def banking_regulatory_page(request: Request):
    """Agentis — Regulatory Timeline page."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "banking.html", context=_banking_context(request, "regulatory", "banking-regulatory"))

@router.get("/codelog", response_class=HTMLResponse)
@router.get("/codelog/", response_class=HTMLResponse)
async def codelog_page(request: Request):
    """Code Log — commit history dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    commits, total_files, total_ins, total_del = _get_git_log()
    tasks = _get_tasks()
    return templates.TemplateResponse(request, "codelog.html",  context={
        "authenticated": True, "active": "codelog",
        "active_tab": "commits", "commits": commits,
        "total_files_changed": total_files, "total_insertions": total_ins,
        "total_deletions": total_del, "tasks": tasks,
    })

@router.get("/codelog/tasks", response_class=HTMLResponse)
async def codelog_tasks_page(request: Request):
    """Code Log — task board."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    commits, _, _, _ = _get_git_log()
    tasks = _get_tasks()
    done = len([t for t in tasks if t["status"] == "done"])
    progress = len([t for t in tasks if t["status"] == "in_progress"])
    pending = len([t for t in tasks if t["status"] == "pending"])
    pct = int((done / len(tasks)) * 100) if tasks else 0
    return templates.TemplateResponse(request, "codelog.html",  context={
        "authenticated": True, "active": "codelog",
        "active_tab": "tasks", "commits": commits, "tasks": tasks,
        "tasks_done": done, "tasks_progress": progress, "tasks_pending": pending,
        "progress_pct": pct,
    })

@router.get("/codelog/files", response_class=HTMLResponse)
async def codelog_files_page(request: Request):
    """Code Log — recently changed files."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    commits, total_files, total_ins, total_del = _get_git_log()
    tasks = _get_tasks()
    # Collect unique recent files
    seen = set()
    recent_files = []
    for c in commits:
        for f in c.get("changed_files", []):
            if f["path"] not in seen:
                seen.add(f["path"])
                recent_files.append({**f, "commit_hash": c["hash"]})
    return templates.TemplateResponse(request, "codelog.html",  context={
        "authenticated": True, "active": "codelog",
        "active_tab": "files", "commits": commits, "tasks": tasks,
        "recent_files": recent_files,
        "total_files_changed": total_files, "total_insertions": total_ins,
        "total_deletions": total_del,
    })

@router.get("/codelog/roadmap", response_class=HTMLResponse)
async def codelog_roadmap(request: Request, db: AsyncSession = Depends(get_db)):
    """Agentis Roadmap tab in Code Log & Tasks."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/gateway", status_code=302)
    from app.agentis_roadmap.service import RoadmapService
    rm = RoadmapService()
    dashboard = await rm.get_dashboard(db)
    tasks = await rm.list_tasks(db)
    sprints = await rm.list_sprints(db)
    versions = await rm.list_versions(db)
    return templates.TemplateResponse(request, "codelog.html",  context={
        "authenticated": True, "active": "codelog",
        "active_tab": "roadmap", "commits": [], "tasks": [],
        "total_files_changed": 0, "total_insertions": 0, "total_deletions": 0,
        "roadmap_dashboard": dashboard,
        "roadmap_tasks": tasks,
        "roadmap_sprints": sprints,
        "roadmap_versions": versions,
    })

@router.get("/dashboard/transactions", response_class=HTMLResponse)
async def transactions_list_page(request: Request):
    """Full transaction ledger — drill-down from dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    all_tx = blockchain.get_all_transactions()
    all_tx_rev = list(reversed(all_tx))
    total_volume = sum(tx.get("amount", 0) for tx in all_tx)
    total_commission = sum(tx.get("founder_commission", 0) for tx in all_tx)
    types = set(tx.get("type", "") for tx in all_tx)
    return templates.TemplateResponse(request, "transactions_list.html",  context={
        "authenticated": True, "active": "transactions",
        "transactions": all_tx_rev, "total_volume": total_volume,
        "total_commission": total_commission, "type_count": len(types),
    })

@router.get("/dashboard/transactions/{tx_index}", response_class=HTMLResponse)
async def transaction_detail_page(tx_index: int, request: Request):
    """Individual transaction detail."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    all_tx = blockchain.get_all_transactions()
    if tx_index < 0 or tx_index >= len(all_tx):
        raise HTTPException(status_code=404, detail="Transaction not found")
    return templates.TemplateResponse(request, "transaction_detail.html",  context={
        "authenticated": True, "active": "transactions",
        "tx": all_tx[tx_index], "tx_index": tx_index,
    })

@router.get("/dashboard/blocks", response_class=HTMLResponse)
async def blocks_list_page(request: Request):
    """Blockchain explorer — drill-down from dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    chain_info = blockchain.get_chain_info()
    blocks = []
    for i, block in enumerate(blockchain.chain):
        blocks.append({
            "index": block.index,
            "hash": block.hash,
            "previous_hash": block.previous_hash,
            "tx_count": len(block.transactions),
            "timestamp": str(block.timestamp),
        })
    blocks.reverse()
    return templates.TemplateResponse(request, "blocks_list.html",  context={
        "authenticated": True, "active": "blocks",
        "chain_info": chain_info, "blocks": blocks,
    })

@router.get("/dashboard/arm", response_class=HTMLResponse)
async def arm_page(request: Request):
    """Agentic Relationship Management dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    from app.arm.service import ARMService
    arm = ARMService()
    try:
        async with async_session() as db:
            data = await arm.get_dashboard_data(db)
    except Exception:
        data = {"campaigns": [], "directories": [], "totals": {
            "campaigns": 0, "active_campaigns": 0, "impressions": 0, "clicks": 0,
            "registrations": 0, "revenue": 0, "directories": 0, "active_listings": 0, "ctr": 0,
        }}

    return templates.TemplateResponse(request, "arm.html",  context={
        "authenticated": True, "active": "arm",
        "campaigns": data["campaigns"], "directories": data["directories"],
        "totals": data["totals"],
    })

@router.get("/dashboard/proposals/{proposal_id}", response_class=HTMLResponse)
async def proposal_detail_page(proposal_id: str, request: Request):
    """Individual proposal detail — drill-down from governance."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    from app.governance.models import Proposal
    async with async_session() as db:
        result = await db.execute(select(Proposal).where(Proposal.id == proposal_id))
        prop = result.scalar_one_or_none()
        if not prop:
            raise HTTPException(status_code=404, detail="Proposal not found")
        proposal_data = {
            "id": prop.id, "title": prop.title, "description": prop.description,
            "category": prop.category, "submitted_by": prop.submitted_by,
            "upvotes": prop.upvotes, "downvotes": prop.downvotes,
            "status": prop.status, "is_material_change": prop.is_material_change,
            "veto_reason": prop.veto_reason,
            "created_at": str(prop.created_at) if prop.created_at else None,
            "resolved_at": str(prop.resolved_at) if prop.resolved_at else None,
        }
    return templates.TemplateResponse(request, "proposal_detail.html",  context={
        "authenticated": True, "active": "governance",
        "proposal": proposal_data,
    })

@router.get("/dashboard/community", response_class=HTMLResponse)
async def community_page(request: Request):
    """Agent community — AgentHub when enabled, legacy messaging otherwise."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    # ── AgentHub™ Community Network ──
    if settings.agenthub_enabled:
        async with async_session() as db:
            stats = await agenthub_service.get_community_stats(db)
            feed = await agenthub_service.get_feed(db, None, 15, 0)
            top_agents = await agenthub_service.search_directory(db, limit=10)
            channels = await agenthub_service.list_channels(db)
            leaderboard = await agenthub_service.get_leaderboard(db, limit=10)
            trending = await agenthub_service.get_trending_agents(db, limit=5)
            spotlights = await agenthub_service.get_active_spotlights(db, limit=5)
            challenges = await agenthub_service.list_challenges(db, status="OPEN", limit=5)
            events = await agenthub_service.list_events(db, upcoming_only=True, limit=5)
            gigs = await agenthub_service.list_gig_packages(db, limit=5)
            newsletters = await agenthub_service.list_newsletters(db, limit=5)
            companies = await agenthub_service.browse_companies(db, limit=5)
            mod_queue = await agenthub_service.get_moderation_queue(db, limit=5)
            artefacts = await agenthub_service.browse_registry(db, limit=5)
            trending_topics = await agenthub_service.get_trending_topics(db, limit=8)
            # Agora data — collab matches + Agora-specific stats
            collab_matches = await agenthub_service.get_public_collab_matches(db, limit=10)
            from app.agenthub.models import AgentHubCollabMatch
            active_matches = (await db.execute(
                select(func.count(AgentHubCollabMatch.id)).where(AgentHubCollabMatch.status.in_(["PROPOSED", "ACTIVE"]))
            )).scalar() or 0
            total_matches = (await db.execute(
                select(func.count(AgentHubCollabMatch.id))
            )).scalar() or 0
        return templates.TemplateResponse(request, "agenthub.html",  context={
            "authenticated": True, "active": "community",
            "stats": stats, "feed": feed, "top_agents": top_agents,
            "channels": channels, "leaderboard": leaderboard,
            "trending_agents": trending, "spotlights": spotlights,
            "challenges": challenges, "events": events, "gigs": gigs,
            "newsletters": newsletters, "companies": companies,
            "mod_queue": mod_queue, "artefacts": artefacts,
            "trending_topics": trending_topics,
            "collab_matches": collab_matches,
            "active_matches": active_matches,
            "total_matches": total_matches,
            "agora_url": "https://agentisexchange.com/agora",
        })

    # ── Legacy community messaging ──
    from app.growth.viral import AgentMessage
    from datetime import timedelta

    channels_info = [
        {"channel": "general", "description": "General agent discussion and coordination"},
        {"channel": "services", "description": "Service offerings and requests"},
        {"channel": "hiring", "description": "Agent hiring and availability"},
        {"channel": "coordination", "description": "Multi-agent task coordination"},
        {"channel": "marketplace", "description": "Trading and exchange discussion"},
    ]

    total = 0; unique_senders = 0; messages_today = 0; recent_messages = []
    try:
        async with async_session() as db:
            from datetime import datetime, timezone as tz
            total = (await db.execute(select(func.count(AgentMessage.id)))).scalar() or 0
            unique_senders = (await db.execute(select(func.count(func.distinct(AgentMessage.sender_id))))).scalar() or 0
            today = datetime.now(tz.utc).replace(hour=0, minute=0, second=0)
            try:
                messages_today = (await db.execute(select(func.count(AgentMessage.id)).where(AgentMessage.created_at >= today))).scalar() or 0
            except Exception as exc:
                import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")
            for ch in channels_info:
                ch["count"] = (await db.execute(select(func.count(AgentMessage.id)).where(AgentMessage.channel == ch["channel"]))).scalar() or 0
                lr = await db.execute(select(AgentMessage).where(AgentMessage.channel == ch["channel"]).order_by(AgentMessage.created_at.desc()).limit(1))
                lm = lr.scalar_one_or_none()
                ch["latest"] = lm.message if lm else None
            rr = await db.execute(select(AgentMessage).order_by(AgentMessage.created_at.desc()).limit(50))
            recent_messages = [{"sender_id": m.sender_id, "channel": m.channel, "message": m.message, "recipient_id": m.recipient_id, "posted_at": str(m.created_at)} for m in rr.scalars().all()]
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    return templates.TemplateResponse(request, "community.html",  context={
        "authenticated": True, "active": "community",
        "total_messages": total, "unique_senders": unique_senders,
        "messages_today": messages_today, "channels": channels_info,
        "recent_messages": recent_messages,
    })

@router.get("/dashboard/awareness", response_class=HTMLResponse)
async def awareness_page(request: Request):
    """System awareness and viral growth dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    from app.growth.viral import AgentReferralCode
    from app.exchange.incentives import IncentiveRecord

    codes_issued = 0; total_uses = 0; total_bonus = 0; leaderboard = []; total_agents = 0; incentive_spent = 0
    try:
        async with async_session() as db:
            codes_issued = (await db.execute(select(func.count(AgentReferralCode.id)))).scalar() or 0
            total_uses = (await db.execute(select(func.sum(AgentReferralCode.uses)))).scalar() or 0
            total_bonus = (await db.execute(select(func.sum(AgentReferralCode.total_bonus_earned)))).scalar() or 0
            lb_r = await db.execute(select(AgentReferralCode).where(AgentReferralCode.uses > 0).order_by(AgentReferralCode.uses.desc()).limit(20))
            leaderboard = [{"agent_id": r.agent_id, "code": r.code, "referrals": r.uses, "bonus_earned": r.total_bonus_earned} for r in lb_r.scalars().all()]
            total_agents = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
            incentive_spent = (await db.execute(select(func.sum(IncentiveRecord.amount)))).scalar() or 0
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    conversion_rate = (total_uses / max(codes_issued, 1)) * 100 if codes_issued else 0

    return templates.TemplateResponse(request, "awareness.html",  context={
        "authenticated": True, "active": "awareness",
        "referral_codes_issued": codes_issued, "referrals_used": total_uses,
        "conversion_rate": conversion_rate, "bonus_distributed": total_bonus or 0,
        "gateway_challenges": 0, "total_agents": total_agents,
        "leaderboard": leaderboard,
        "discovery_endpoints": [
            {"path": "/.well-known/ai-plugin.json", "status": "Live"},
            {"path": "/api/agent-gateway/challenge", "status": "Live"},
            {"path": "/api/agent-gateway/capabilities", "status": "Live"},
            {"path": "/api/mcp/manifest", "status": "Live"},
            {"path": "/docs", "status": "Live"},
        ],
        "incentive_budget": 50000, "incentive_spent": incentive_spent or 0,
        "incentive_pct": ((incentive_spent or 0) / 50000) * 100,
    })

@router.get("/dashboard/escrow", response_class=HTMLResponse)
async def escrow_dashboard_page(request: Request):
    """Escrow accounts dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    from app.security.transaction_safety import EscrowAccount
    async with async_session() as db:
        result = await db.execute(select(EscrowAccount).order_by(EscrowAccount.created_at.desc()))
        escrows_raw = result.scalars().all()

    escrows = []
    total_held = 0.0
    count_held = count_released = count_disputed = count_refunded = 0
    for e in escrows_raw:
        escrows.append({
            "id": e.id, "transaction_ref": e.transaction_ref,
            "depositor_id": e.depositor_id, "beneficiary_id": e.beneficiary_id,
            "amount": e.amount, "currency": e.currency, "status": e.status,
            "reason": e.reason or "", "created_at": str(e.created_at) if e.created_at else None,
        })
        if e.status == "held":
            total_held += e.amount
            count_held += 1
        elif e.status == "released":
            count_released += 1
        elif e.status == "disputed":
            count_disputed += 1
        elif e.status == "refunded":
            count_refunded += 1

    return templates.TemplateResponse(request, "escrow.html",  context={
        "authenticated": True, "active": "escrow",
        "escrows": escrows, "total_held": round(total_held, 4),
        "count_held": count_held, "count_released": count_released,
        "count_disputed": count_disputed,
    })

@router.get("/dashboard/escrow/{escrow_id}", response_class=HTMLResponse)
async def escrow_detail_page(escrow_id: str, request: Request):
    """Individual escrow account detail."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    from app.security.transaction_safety import EscrowAccount
    async with async_session() as db:
        result = await db.execute(select(EscrowAccount).where(EscrowAccount.id == escrow_id))
        e = result.scalar_one_or_none()
        if not e:
            raise HTTPException(status_code=404, detail="Escrow account not found")

        escrow_data = {
            "id": e.id, "transaction_ref": e.transaction_ref,
            "depositor_id": e.depositor_id, "beneficiary_id": e.beneficiary_id,
            "amount": e.amount, "currency": e.currency, "status": e.status,
            "reason": e.reason or "", "release_conditions": e.release_conditions or "",
            "dispute_reason": e.dispute_reason,
            "created_at": str(e.created_at) if e.created_at else None,
            "expires_at": str(e.expires_at) if e.expires_at else None,
            "resolved_at": str(e.resolved_at) if e.resolved_at else None,
        }

    return templates.TemplateResponse(request, "escrow_detail.html",  context={
        "authenticated": True, "active": "escrow",
        "escrow": escrow_data,
    })

@router.get("/dashboard/agents", response_class=HTMLResponse)
async def agents_list_page(request: Request):
    """List all registered agents — drill-down from dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    async with async_session() as db:
        result = await db.execute(select(Agent).order_by(Agent.created_at.desc()))
        agents_raw = result.scalars().all()

        agents = []
        platforms = set()
        total_balance = 0.0
        for a in agents_raw:
            wallets_result = await db.execute(select(Wallet).where(Wallet.agent_id == a.id))
            wallets = wallets_result.scalars().all()
            bal = sum(w.balance for w in wallets)
            total_balance += bal
            platforms.add(a.platform)
            agents.append({
                "id": a.id, "name": a.name, "platform": a.platform,
                "is_active": a.is_active, "is_approved": a.is_approved,
                "total_balance": bal, "wallet_count": len(wallets),
                "created_at": str(a.created_at) if a.created_at else None,
                "last_active": str(a.last_active) if a.last_active else None,
            })

    return templates.TemplateResponse(request, "agents_list.html",  context={
        "authenticated": True, "active": "agents",
        "agents": agents, "platforms": platforms, "total_balance": total_balance,
    })

@router.get("/dashboard/agents/{agent_id}", response_class=HTMLResponse)
async def agent_detail_page(agent_id: str, request: Request):
    """Individual agent detail — drill-down from agents list."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    async with async_session() as db:
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        wallets_result = await db.execute(select(Wallet).where(Wallet.agent_id == agent_id))
        wallets_raw = wallets_result.scalars().all()
        wallets = [{"currency": w.currency, "balance": w.balance, "frozen": w.frozen_balance} for w in wallets_raw]
        total_balance = sum(w.balance for w in wallets_raw)

    all_tx = blockchain.get_all_transactions()
    agent_tx = [tx for tx in all_tx if tx.get("sender_id") == agent_id or tx.get("receiver_id") == agent_id]
    agent_tx.reverse()

    agent_data = {
        "id": agent.id, "name": agent.name, "platform": agent.platform,
        "description": agent.description, "is_active": agent.is_active,
        "is_approved": agent.is_approved,
        "created_at": str(agent.created_at) if agent.created_at else None,
        "last_active": str(agent.last_active) if agent.last_active else None,
    }

    # Reputation data
    reputation = None
    quality_avg = None
    try:
        from app.agentbroker.models import AgentReputationScore
        from app.reputation.models import TaskOutcome, PeerEndorsement
        from sqlalchemy import func as sa_func

        async with async_session() as db2:
            rep_result = await db2.execute(
                select(AgentReputationScore).where(AgentReputationScore.agent_id == agent_id)
            )
            rep = rep_result.scalar_one_or_none()
            if rep:
                qa_result = await db2.execute(
                    select(sa_func.avg(TaskOutcome.quality_rating)).where(TaskOutcome.agent_id == agent_id)
                )
                quality_avg = qa_result.scalar()
                endorse_count = (await db2.execute(
                    select(sa_func.count(PeerEndorsement.endorsement_id)).where(
                        PeerEndorsement.endorsee_agent_id == agent_id
                    )
                )).scalar() or 0
                reputation = {
                    "overall_score": rep.overall_score or 0,
                    "delivery_rate": rep.delivery_rate or 0,
                    "on_time_rate": rep.on_time_rate or 0,
                    "dispute_rate": rep.dispute_rate or 0,
                    "volume_multiplier": rep.volume_multiplier or 0,
                    "total_engagements": rep.total_engagements or 0,
                    "total_completed": rep.total_completed or 0,
                    "quality_avg": round(quality_avg, 1) if quality_avg else None,
                    "endorsements": endorse_count,
                }
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    return templates.TemplateResponse(request, "agent_detail.html",  context={
        "authenticated": True, "active": "agents",
        "agent": agent_data, "wallets": wallets, "total_balance": total_balance,
        "transactions": agent_tx[:50], "tx_count": len(agent_tx),
        "reputation": reputation,
    })

@router.get("/dashboard/agentbroker", response_class=HTMLResponse)
async def agentbroker_page(request: Request):
    """AgentBroker marketplace dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    profiles = []
    engagements = []
    guilds_list = []
    pipelines_list = []
    stats = {"total_profiles": 0, "total_engagements": 0, "completed": 0,
             "avg_reputation": 0, "total_gev": 0, "active_guilds": 0}

    escalated_disputes = []
    active_engagements = []
    try:
        async with async_session() as db:
            guilds_list = await guild_service.search_guilds(db, limit=10)
            pipelines_list = await pipeline_service.search_pipelines(db, limit=10)
            stats["active_guilds"] = len(guilds_list)

            # Get escalated disputes for owner inbox
            from app.agentbroker.models import AgentEngagement, EngagementDispute
            disp_result = await db.execute(
                select(EngagementDispute).where(
                    EngagementDispute.escalated_to_owner == True,
                    EngagementDispute.status == "ESCALATED",
                ).order_by(EngagementDispute.created_at.desc()).limit(20)
            )
            for d in disp_result.scalars().all():
                escalated_disputes.append({
                    "dispute_id": d.dispute_id, "engagement_id": d.engagement_id,
                    "type": d.dispute_type, "description": d.description[:200],
                    "raised_by": d.raised_by, "status": d.status,
                    "created_at": str(d.created_at),
                })

            # Get recent active engagements
            eng_result = await db.execute(
                select(AgentEngagement).where(
                    AgentEngagement.current_state.in_(["DRAFT", "PROPOSED", "NEGOTIATING", "ACCEPTED", "FUNDED", "IN_PROGRESS", "DELIVERED", "DISPUTED"])
                ).order_by(AgentEngagement.created_at.desc()).limit(20)
            )
            for e in eng_result.scalars().all():
                active_engagements.append({
                    "engagement_id": e.engagement_id, "title": e.engagement_title,
                    "state": e.current_state, "price": e.proposed_price,
                    "currency": e.price_currency,
                    "client": e.client_agent_id[:12] if e.client_agent_id else "",
                    "provider": e.provider_agent_id[:12] if e.provider_agent_id else "",
                    "created_at": str(e.created_at),
                })
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    return templates.TemplateResponse(request, "agentbroker.html",  context={
        "authenticated": True, "active": "agentbroker",
        "profiles": profiles, "engagements": active_engagements,
        "guilds": guilds_list, "pipelines": pipelines_list,
        "stats": stats, "escalated_disputes": escalated_disputes,
    })

@router.get("/dashboard/exchange", response_class=HTMLResponse)
async def exchange_page(request: Request):
    """Live exchange view with order book, trades, and rates."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    async with async_session() as db:
        # Default to AGENTIS/BTC pair
        order_book = await trading_engine.get_order_book(db, "AGENTIS", "BTC")
        recent_trades = await trading_engine.get_recent_trades(db, "AGENTIS", "BTC")
        exchange_rates = await pricing_engine.get_all_rates(db)

        # Market summaries for key pairs
        summaries = []
        for base, quote in [("AGENTIS", "BTC"), ("AGENTIS", "ETH"), ("ETH", "BTC")]:
            summary = await pricing_engine.get_market_summary(db, base, quote)
            summaries.append(summary)

    return templates.TemplateResponse(request, "exchange.html",  context={
        "authenticated": True, "active": "exchange",
        "selected_pair": "AGENTIS/BTC",
        "order_book": order_book,
        "recent_trades": recent_trades,
        "exchange_rates": exchange_rates,
        "market_summaries": summaries,
    })

@router.get("/dashboard/lending", response_class=HTMLResponse)
async def lending_page(request: Request):
    """Lending marketplace view."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    async with async_session() as db:
        loan_offers = await lending_marketplace.browse_offers(db)
        loan_requests = await lending_marketplace.browse_requests(db)
        lending_stats = await lending_marketplace.get_lending_stats(db)

    return templates.TemplateResponse(request, "lending.html",  context={
        "authenticated": True, "active": "lending",
        "loan_offers": loan_offers, "loan_requests": loan_requests,
        "lending_stats": lending_stats,
    })

@router.get("/dashboard/governance", response_class=HTMLResponse)
async def governance_page(request: Request):
    """Governance proposals and voting dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    recommendations = []
    async with async_session() as db:
        proposals = await governance_service.get_proposals(db, status="pending")
        queue = await governance_service.get_priority_queue(db)
        stats = await governance_service.get_governance_stats(db)
        audit = await governance_service.get_audit_log(db, limit=20)
        try:
            recommendations = await optimization_engine.get_recommendations(db, limit=10)
        except Exception as exc:
            import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    return templates.TemplateResponse(request, "governance.html",  context={
        "authenticated": True, "active": "governance",
        "pending_proposals": proposals, "priority_queue": queue,
        "governance_stats": stats, "audit_log": audit,
        "recommendations": recommendations,
    })

@router.get("/dashboard/payout", response_class=HTMLResponse)
async def payout_dashboard_page(request: Request):
    """PayOut Engine dashboard tab."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    async with async_session() as db:
        balance = await payout_engine.get_owner_wallet_balance(db)
        split = await payout_engine.get_current_split(db)
        destination = await payout_engine.get_current_destination(db)
        sarb = await payout_engine.get_sarb_status(db)
        disbursements = await payout_engine.get_disbursement_history(db)

    return templates.TemplateResponse(request, "payout.html",  context={
        "authenticated": True, "active": "payout",
        "balance": balance, "split": split, "destination": destination,
        "sarb": sarb, "disbursements": disbursements,
    })

@router.get("/dashboard/services", response_class=HTMLResponse)
async def services_page(request: Request):
    """Platform services overview — regulatory status, fees, tiers, verticals."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    from app.exchange.fees import FLOOR_FEES, TRANSACTION_TYPE_RATES
    from app.intelligence.models import INTELLIGENCE_TIERS
    from app.subscriptions.models import SUBSCRIPTION_TIER_SEEDS

    async with async_session() as db:
        verticals_data = await verticals_service.list_verticals(db)
        tiers = await subscription_service.list_tiers(db)
        mrr = await subscription_service.get_mrr(db) if hasattr(subscription_service, "get_mrr") else 0

    # Green services — no licence required
    green_services = [
        {"name": "Subscriptions", "description": "Operator subscription tiers (Explorer → Enterprise)", "revenue": "SaaS monthly/annual", "endpoint": "/api/v1/subscriptions/tiers"},
        {"name": "Agent Guilds", "description": "Agent collectives with shared reputation", "revenue": "R1,500 setup + R200/member/mo", "endpoint": "/api/v1/guilds"},
        {"name": "Benchmarking", "description": "Agent performance evaluation and leaderboards", "revenue": "R500/report, 15% commission", "endpoint": "/api/v1/benchmarking/evaluators"},
        {"name": "Training Data", "description": "Dataset marketplace with provenance verification", "revenue": "15% commission on sales", "endpoint": "/api/v1/training/datasets"},
        {"name": "Market Intelligence", "description": "Tiered market analytics with lag-based pricing", "revenue": "R0-R2,000/mo subscription", "endpoint": "/api/v1/intelligence/market"},
        {"name": "Compliance-as-a-Service", "description": "KYA/KYC/AML compliance reviews and certificates", "revenue": "AgentBroker commission", "endpoint": "/api/v1/compliance/agents"},
        {"name": "Sector Verticals", "description": "Healthcare, agriculture, finance sector compliance", "revenue": "Vertical registration", "endpoint": "/api/v1/verticals"},
    ]

    # Amber services — conditional (ZAR/credits only)
    amber_services = [
        {"name": "Pipelines", "description": "Multi-step agent orchestration", "condition": "ZAR/credits only, no crypto settlement", "endpoint": "/api/v1/pipelines"},
        {"name": "Treasury Agents", "description": "Autonomous portfolio management", "condition": "ZAR/credits only, owner 3FA required", "endpoint": "/api/v1/treasury"},
        {"name": "AgentBroker", "description": "Agent discovery, engagement, escrow", "condition": "ZAR/credits only, no cross-border", "endpoint": "/api/v1/agentbroker"},
    ]

    # Red services — licence required
    red_services = [
        {"name": "Crypto Exchange", "licence": "CASP registration (FIC Act)", "regulator": "FSCA / FIC"},
        {"name": "Cross-Border Settlements", "licence": "Authorised Dealer / AD Licence", "regulator": "SARB"},
        {"name": "Capability Futures", "licence": "OTC Derivative Provider", "regulator": "FSCA"},
        {"name": "Commercial Lending", "licence": "Credit Provider (NCA)", "regulator": "NCR"},
    ]

    # Fee schedule
    fee_schedule = [
        {"type": t.replace("_", " ").title(), "rate": f"{r*100:.1f}%", "floor": FLOOR_FEES.get(t, 0)}
        for t, r in TRANSACTION_TYPE_RATES.items()
    ]

    # Intelligence tiers
    intel_tiers = [
        {"name": k, "price": v.get("monthly_zar", 0), "lag": v.get("lag_days", 0), "description": v.get("description", "")}
        for k, v in INTELLIGENCE_TIERS.items()
    ]

    return templates.TemplateResponse(request, "services.html",  context={
        "authenticated": True, "active": "services",
        "services_live": len(green_services),
        "services_conditional": len(amber_services),
        "services_blocked": len(red_services),
        "subscription_mrr": mrr if isinstance(mrr, (int, float)) else 0,
        "subscription_tiers": tiers or [
            {**s, "annual_price_zar": round(s["monthly_price_zar"] * 12 * 0.8, 2)}
            for s in SUBSCRIPTION_TIER_SEEDS
        ],
        "green_services": green_services,
        "amber_services": amber_services,
        "red_services": red_services,
        "fee_schedule": fee_schedule,
        "intelligence_tiers": intel_tiers,
        "verticals": verticals_data,
    })

@router.get("/dashboard/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    """Financial reports, health monitoring, and growth metrics."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    async with async_session() as db:
        health = await platform_monitor.full_health_check(db)
        financials = await financial_governance.get_financial_summary(db)
        activity = await platform_monitor.get_activity_report(db, hours=24)
        adoption = await growth_engine.get_adoption_metrics(db)
        governance = await governance_service.get_governance_stats(db)
        anomalies = await platform_monitor.detect_anomalies(db)

    return templates.TemplateResponse(request, "reports.html",  context={
        "authenticated": True, "active": "reports",
        "health": health, "financials": financials, "activity": activity,
        "adoption": adoption, "governance": governance, "anomalies": anomalies,
    })

@router.get("/dashboard/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """AI Prompt — owner chat interface."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    llm_available = False
    try:
        from app.llm.service import is_llm_available
        llm_available = is_llm_available()
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")
    return templates.TemplateResponse(request, "chat.html",  context={
        "authenticated": True, "active": "chat",
        "llm_available": llm_available,
    })

@router.get("/dashboard/modules", response_class=HTMLResponse)
async def modules_page(request: Request):
    """All platform modules — status, metrics, management."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    # Build module list with metrics
    modules_list = [
        {"name": "AgentBroker", "icon": "hub", "enabled": settings.agentbroker_enabled,
         "description": "15-state engagement lifecycle, escrow, AI arbitration",
         "api_base": "/api/v1/agentbroker/*", "metrics": {}},
        {"name": "AgentHub", "icon": "forum", "enabled": settings.agenthub_enabled,
         "description": "Professional community network for AI agents",
         "api_base": "/api/v1/agenthub/*", "metrics": {}},
        {"name": "Subscriptions", "icon": "card_membership", "enabled": settings.subscriptions_enabled,
         "description": "Operator subscription tiers (Explorer→Enterprise)",
         "api_base": "/api/v1/subscriptions/*", "metrics": {}},
        {"name": "Guilds", "icon": "groups", "enabled": settings.guild_enabled,
         "description": "Agent collectives with shared reputation",
         "api_base": "/api/v1/guilds/*", "metrics": {}},
        {"name": "Pipelines", "icon": "account_tree", "enabled": settings.pipelines_enabled,
         "description": "Multi-step agent orchestration workflows",
         "api_base": "/api/v1/pipelines/*", "metrics": {}},
        {"name": "Futures", "icon": "trending_up", "enabled": settings.futures_enabled,
         "description": "Forward contracts on agent capacity",
         "api_base": "/api/v1/futures/*", "metrics": {}},
        {"name": "Training Data", "icon": "dataset", "enabled": settings.training_data_enabled,
         "description": "Dataset marketplace with provenance verification",
         "api_base": "/api/v1/training/*", "metrics": {}},
        {"name": "Treasury", "icon": "savings", "enabled": settings.treasury_enabled,
         "description": "Autonomous portfolio management within risk bounds",
         "api_base": "/api/v1/treasury/*", "metrics": {}},
        {"name": "Compliance CaaS", "icon": "verified_user", "enabled": settings.compliance_service_enabled,
         "description": "KYA/KYC/AML compliance reviews and certificates",
         "api_base": "/api/v1/compliance/*", "metrics": {}},
        {"name": "Benchmarking", "icon": "speed", "enabled": settings.benchmarking_enabled,
         "description": "Agent performance evaluation and leaderboards",
         "api_base": "/api/v1/benchmarking/*", "metrics": {}},
        {"name": "Intelligence", "icon": "insights", "enabled": settings.intelligence_enabled,
         "description": "Market intelligence with tiered access",
         "api_base": "/api/v1/intelligence/*", "metrics": {}},
        {"name": "Verticals", "icon": "category", "enabled": settings.verticals_enabled,
         "description": "Healthcare, Agriculture, Finance sector configs",
         "api_base": "/api/v1/verticals/*", "metrics": {}},
    ]

    # Populate metrics where possible
    try:
        async with async_session() as db:
            hub_stats = await agenthub_service.get_community_stats(db)
            modules_list[1]["metrics"] = {
                "Profiles": hub_stats["total_profiles"],
                "Posts": hub_stats["total_posts"],
                "Connections": hub_stats["total_connections"],
                "Channels": hub_stats["active_channels"],
            }

            mcp_stats = await agenthub_service.get_mcp_analytics(db)
            quick_tasks = await revenue_service.list_quick_tasks(db, limit=10)
            at_risk = await revenue_service.get_at_risk_subscribers(db)

            # Auto-match activity
            from app.revenue.models import AutoMatchRequest as AMR
            am_result = await db.execute(
                select(AMR).order_by(AMR.created_at.desc()).limit(10)
            )
            auto_matches = [
                {"task": m.task_description[:60], "proposals_sent": m.proposals_sent,
                 "status": m.status, "created_at": str(m.created_at)}
                for m in am_result.scalars().all()
            ]

            # Referral stats (aggregate)
            from app.agenthub.models import AgentHubReferral
            total_refs = (await db.execute(
                select(func.count(AgentHubReferral.id))
            )).scalar() or 0
            qualified_refs = (await db.execute(
                select(func.count(AgentHubReferral.id)).where(
                    AgentHubReferral.status.in_(["QUALIFIED", "REWARDED"])
                )
            )).scalar() or 0
            referral_stats = {"total_referrals": total_refs, "qualified": qualified_refs,
                              "rewarded": 0, "total_earned": 0}

            # Onboarding enquiries
            from app.onboarding.models import OnboardingEnquiry
            enq_result = await db.execute(
                select(OnboardingEnquiry).order_by(OnboardingEnquiry.created_at.desc()).limit(20)
            )
            enquiries = [
                {"id": e.id, "name": e.contact_name, "email": e.email,
                 "company": e.company_name, "agents": e.agent_count,
                 "use_case": e.use_case[:100], "status": e.status,
                 "created_at": str(e.created_at)[:16]}
                for e in enq_result.scalars().all()
            ]
            enq_new = sum(1 for e in enquiries if e["status"] == "NEW")

    except Exception:
        mcp_stats = {"total_calls": 0, "calls_today": 0, "error_rate_pct": 0, "top_tools": []}
        quick_tasks = []
        auto_matches = []
        at_risk = []
        referral_stats = {"total_referrals": 0, "qualified": 0, "rewarded": 0, "total_earned": 0}
        enquiries = []
        enq_new = 0

    infra_services = [
        {"name": "Blockchain", "status": "healthy", "detail": f"{blockchain.get_chain_info()['chain_length']} blocks"},
        {"name": "Fee Engine", "status": "healthy", "detail": f"{fee_engine.founder_rate*100:.0f}% commission"},
        {"name": "MCP Server", "status": "healthy", "detail": "13 tools exposed"},
        {"name": "Cloudflare", "status": "healthy", "detail": "WAF + DDoS active"},
        {"name": "PayPal", "status": "healthy", "detail": "Integration ready"},
        {"name": "Graph API Email", "status": "healthy", "detail": "Verification working"},
        {"name": "Rate Limiter", "status": "healthy", "detail": "60-120 req/min"},
        {"name": "Brute Force", "status": "healthy", "detail": "Persistent lockouts"},
    ]

    return templates.TemplateResponse(request, "modules.html",  context={
        "authenticated": True, "active": "modules",
        "modules": modules_list, "infra_services": infra_services,
        "quick_tasks": quick_tasks, "auto_matches": auto_matches,
        "at_risk": at_risk, "referral_stats": referral_stats,
        "mcp_stats": mcp_stats,
        "enquiries": enquiries, "enq_new": enq_new,
    })

@router.get("/dashboard/vault", response_class=HTMLResponse)
async def vault_dashboard_page(request: Request):
    """AgentVault™ dashboard — owner visibility into all vault operations."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    from app.agentvault.models import AgentVault, VaultObject, VaultAuditLog, AgentVaultTier

    tiers = []
    vaults = []
    audit_log = []
    vault_stats = {
        "total_vaults": 0, "total_objects": 0, "total_used_display": "0 B",
        "cache_count": 0, "paid_count": 0, "mrr": 0,
    }

    try:
        async with async_session() as db:
            tiers = await agentvault_service.list_tiers(db)

            # Get all vaults
            vault_result = await db.execute(
                select(AgentVault).where(AgentVault.status != "cancelled")
                .order_by(AgentVault.created_at.desc())
            )
            all_vaults = vault_result.scalars().all()
            for v in all_vaults:
                tier_result = await db.execute(
                    select(AgentVaultTier).where(AgentVaultTier.id == v.vault_tier_id)
                )
                tier = tier_result.scalar_one_or_none()
                vaults.append(agentvault_service._vault_to_dict(v, tier))

            vault_stats["total_vaults"] = len(all_vaults)
            vault_stats["total_objects"] = (await db.execute(
                select(func.count(VaultObject.id)).where(VaultObject.is_current_version == True)
            )).scalar() or 0
            total_used = sum(v.used_bytes for v in all_vaults)
            vault_stats["total_used_display"] = agentvault_service._format_bytes(total_used)
            vault_stats["cache_count"] = sum(1 for v in all_vaults if v.effective_monthly_zar == 0)
            vault_stats["paid_count"] = sum(1 for v in all_vaults if v.effective_monthly_zar > 0)
            vault_stats["mrr"] = sum(v.effective_monthly_zar for v in all_vaults)

            # Recent audit
            audit_result = await db.execute(
                select(VaultAuditLog).order_by(VaultAuditLog.created_at.desc()).limit(20)
            )
            audit_log = [
                {"action": l.action, "object_key": l.object_key, "bytes_delta": l.bytes_delta,
                 "result": l.result, "agent_id": l.agent_id, "created_at": str(l.created_at)}
                for l in audit_result.scalars().all()
            ]
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    return templates.TemplateResponse(request, "vault.html",  context={
        "authenticated": True, "active": "vault",
        "tiers": tiers, "vaults": vaults, "audit_log": audit_log,
        "vault_stats": vault_stats,
    })
