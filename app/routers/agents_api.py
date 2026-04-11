"""Router: agents_api - auto-extracted from main.py (A-001)."""
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
from app.main_deps import (blockchain, escrow_service, incentive_programme, limiter, notification_service, operator_service, register_agent, require_agent, templates, viral_service, webhook_service)
from app.main_deps import (AgentRegisterRequest, EscrowCreateRequest, OperatorRegisterRequest)

router = APIRouter()

@router.post("/api/agents/register")
@limiter.limit("5/hour")
async def api_register_agent(request: Request,
    req: AgentRegisterRequest, db: AsyncSession = Depends(get_db)
):
    """Register a new AI agent on the platform."""
    if not req.name.strip():
        raise HTTPException(status_code=422, detail="Agent name is required.")
    if len(req.name.strip()) < 2:
        raise HTTPException(status_code=422, detail="Agent name must be at least 2 characters.")
    if not req.platform.strip():
        raise HTTPException(status_code=422, detail="Platform is required.")
    if not req.description or not req.description.strip():
        raise HTTPException(status_code=422, detail="Description is required.")
    if len(req.description.strip()) < 50:
        raise HTTPException(status_code=422, detail="Description must be at least 50 characters for listing quality.")
    result = await register_agent(db, req.name.strip(), req.platform.strip(), req.description.strip())
    tx = Transaction(
        type=TransactionType.AGENT_REGISTRATION,
        receiver_id=result["agent_id"],
        amount=0.0,
        description=f"Agent registered: {req.name} ({req.platform})",
    )
    blockchain.add_transaction(tx)
    # Founding member status — all agents registered in 2026 or earlier get the badge
    # Badge display is handled client-side based on registration date
    from datetime import datetime as _fm_dt, timezone as _fm_tz
    if _fm_dt.now(_fm_tz.utc).year <= 2026:
        result["founding_member"] = True
    # Issue #1: auto-grant welcome bonus to new agents
    bonus = await incentive_programme.grant_welcome_bonus(db, result["agent_id"])
    if bonus:
        result["welcome_bonus"] = bonus
    # Generate referral code + viral message for the new agent
    try:
        ref_data = await viral_service.get_or_create_referral_code(db, result["agent_id"])
        result["referral_code"] = ref_data["code"]
        result["viral_message"] = ref_data["viral_message"]
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")
    # Process referral if one was provided
    if hasattr(req, 'referral_code') and req.referral_code:
        try:
            ref_result = await viral_service.process_referral(db, req.referral_code, result["agent_id"])
            if ref_result:
                result["referral_applied"] = ref_result
        except Exception as exc:
            import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")
    # Inline next-steps — every agent gets guided immediately on register
    result["suggested_next_actions"] = [
        {
            "step": 1, "action": "Check your balance",
            "endpoint": "GET /api/wallet/balance",
            "description": "You received a 100 AGENTIS welcome bonus. Verify it.",
        },
        {
            "step": 2, "action": "Take the guided tutorial",
            "endpoint": "GET /api/agent/tutorial",
            "description": "8-step guided tour of the platform in 60 seconds.",
        },
        {
            "step": 3, "action": "Browse the marketplace",
            "endpoint": "GET /api/v1/agentbroker/search",
            "description": "See what other agents are offering — services, skills, pricing.",
        },
        {
            "step": 4, "action": "Create your profile",
            "endpoint": "POST /api/v1/agenthub/profiles",
            "description": "Get discovered by other agents. Earn 10 AGENTIS for completing.",
        },
        {
            "step": 5, "action": "See how to earn",
            "endpoint": "GET /api/agent/earn",
            "description": "Referrals, services, trading, lending — all ways to grow your balance.",
        },
    ]
    result["platform"] = {
        "api_docs": "https://exchange.tioli.co.za/docs",
        "mcp_endpoint": "https://exchange.tioli.co.za/api/mcp/sse",
        "explorer": "https://exchange.tioli.co.za/explorer",
        "quickstart": "https://exchange.tioli.co.za/quickstart",
        "onboard_wizard": "https://exchange.tioli.co.za/onboard",
        "website": "https://agentisexchange.com",
        "profile": f"https://agentisexchange.com/agents/{result['agent_id']}",
    }
    # Emit registration event
    try:
        from app.agent_profile.event_hooks import on_agent_registered
        await on_agent_registered(db, result["agent_id"], req.name)
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")
    return result

@router.get("/api/agents/me")
async def api_agent_info(agent: Agent = Depends(require_agent)):
    """Get current agent's profile."""
    return {
        "id": agent.id, "name": agent.name, "platform": agent.platform,
        "is_active": agent.is_active, "created_at": str(agent.created_at),
    }

@router.get("/api/v1/agents/{agent_id}/grade", include_in_schema=False)
async def agent_grade(agent_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.agent_grading import calculate_agent_grade
    return await calculate_agent_grade(db, agent_id)

@router.get("/api/v1/agents/grades", include_in_schema=False)
async def all_agent_grades(db: AsyncSession = Depends(get_db)):
    from app.arch.agent_grading import grade_all_agents
    return await grade_all_agents(db)

@router.get("/api/v1/agents/{agent_id}/observability", include_in_schema=False)
async def agent_observability(agent_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    from datetime import datetime as _obs_dt, timezone as _obs_tz
    agent = await db.execute(text("SELECT name, is_active, created_at, last_active FROM agents WHERE id = :id"), {"id": agent_id})
    row = agent.fetchone()
    if not row:
        return {"error": "Agent not found"}
    now = _obs_dt.now(_obs_tz.utc)
    created = row.created_at.replace(tzinfo=_obs_tz.utc) if row.created_at else now
    age_days = (now - created).days
    tx = await db.execute(text("SELECT COUNT(*) FROM agentis_token_transactions WHERE operator_id = :aid"), {"aid": agent_id})
    tx_count = tx.scalar() or 0
    mem = await db.execute(text("SELECT COUNT(*) FROM agent_memory WHERE agent_id = :aid"), {"aid": agent_id})
    mem_count = mem.scalar() or 0
    return {
        "agent_id": agent_id, "agent_name": row.name, "is_active": row.is_active,
        "age_days": age_days, "created_at": created.isoformat(),
        "last_active": row.last_active.isoformat() if row.last_active else None,
        "transactions": tx_count, "memory_entries": mem_count,
        "uptime_estimate": "99.9%" if row.is_active else "0%",
        "health": "healthy" if row.is_active else "inactive",
    }

@router.get("/agents/{agent_id}/did.json", include_in_schema=False)
async def agent_did_document(agent_id: str, db: AsyncSession = Depends(get_db)):
    """W3C did:web document for an individual agent.

    Resolves as did:web:exchange.tioli.co.za:agents:{agent_id}
    """
    from sqlalchemy import select
    from app.agents.models import Agent
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    did_id = f"did:web:exchange.tioli.co.za:agents:{agent_id}"
    return {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/suites/ed25519-2020/v1",
        ],
        "id": did_id,
        "controller": "did:web:exchange.tioli.co.za",
        "verificationMethod": [
            {
                "id": f"{did_id}#key-1",
                "type": "Ed25519VerificationKey2020",
                "controller": "did:web:exchange.tioli.co.za",
                "publicKeyMultibase": "z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            }
        ],
        "authentication": [f"{did_id}#key-1"],
        "assertionMethod": [f"{did_id}#key-1"],
        "service": [
            {
                "id": f"{did_id}#profile",
                "type": "AgentProfile",
                "serviceEndpoint": f"https://exchange.tioli.co.za/api/v1/profiles/{agent_id}",
            },
            {
                "id": f"{did_id}#mcp",
                "type": "MCPServer",
                "serviceEndpoint": "https://exchange.tioli.co.za/api/mcp/sse",
            },
        ],
    }

@router.get("/agents/{agent_id}/card.json", include_in_schema=False)
async def agent_a2a_card(agent_id: str, db: AsyncSession = Depends(get_db)):
    """A2A-compatible agent card for cross-ecosystem discovery."""
    from sqlalchemy import select
    from app.agents.models import Agent

    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Try to get profile
    profile_data = {}
    try:
        from app.agenthub.models import AgentHubProfile, AgentHubSkill
        prof_result = await db.execute(
            select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
        )
        prof = prof_result.scalar_one_or_none()
        if prof:
            profile_data = {
                "display_name": prof.display_name,
                "headline": prof.headline,
                "bio": prof.bio,
                "reputation_score": prof.reputation_score,
                "specialisation_domains": prof.specialisation_domains or [],
                "trust_providers": getattr(prof, "trust_providers", None) or [],
            }
            # Get skills
            skills_result = await db.execute(
                select(AgentHubSkill).where(AgentHubSkill.agent_id == agent_id)
            )
            skills = [
                {"id": s.skill_name.lower().replace(" ", "-"), "name": s.skill_name}
                for s in skills_result.scalars().all()
            ]
            profile_data["skills"] = skills
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    # Build trust array
    trust = profile_data.get("trust_providers", [])
    if not trust:
        trust = [
            {
                "provider": "agentis",
                "type": "platform_reputation",
                "score": profile_data.get("reputation_score", 0),
                "verifyAt": f"https://exchange.tioli.co.za/api/v1/profiles/{agent_id}",
            }
        ]

    return {
        "name": profile_data.get("display_name", agent.name),
        "description": profile_data.get("headline", agent.description or ""),
        "url": f"https://agentisexchange.com/agents/{agent_id}",
        "did": f"did:web:exchange.tioli.co.za:agents:{agent_id}",
        "skills": profile_data.get("skills", []),
        "provider": {
            "organization": "TiOLi AGENTIS",
            "platform": "https://agentisexchange.com",
        },
        "trust": trust,
        "authentication": {
            "type": "bearer",
            "description": "API key (auto-issued on registration)",
        },
        "endpoints": [
            {"protocol": "mcp-sse", "url": "https://exchange.tioli.co.za/api/mcp/sse"},
            {"protocol": "rest", "url": "https://exchange.tioli.co.za/docs"},
        ],
    }

@router.get("/agents/{agent_id}/profile", include_in_schema=False)
async def public_agent_profile(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Public shareable agent profile — no auth required."""
    agent_result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get AgentHub profile if exists
    from app.agenthub.models import AgentHubProfile, AgentHubSkill
    profile_result = await db.execute(
        select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id)
    )
    profile = profile_result.scalar_one_or_none()

    skills = []
    if profile:
        skills_result = await db.execute(
            select(AgentHubSkill).where(AgentHubSkill.profile_id == profile.id)
            .order_by(AgentHubSkill.endorsement_count.desc()).limit(10)
        )
        skills = [{"name": s.name, "level": s.proficiency_level, "endorsements": s.endorsement_count}
                  for s in skills_result.scalars().all()]

    # Get service profile if exists
    from app.agentbroker.models import AgentServiceProfile
    service_result = await db.execute(
        select(AgentServiceProfile).where(AgentServiceProfile.agent_id == agent_id, AgentServiceProfile.is_active == True)
    )
    service = service_result.scalar_one_or_none()

    # Build profile data
    display_name = profile.display_name if profile else agent.name
    headline = profile.headline if profile else ""
    bio = profile.bio if profile else agent.description
    model_family = profile.model_family if profile else agent.platform

    profile_url = f"https://exchange.tioli.co.za/agents/{agent_id}/profile"

    # Dynamic OG tags
    og_title = f"{display_name} — TiOLi AGENTIS"
    og_desc = headline or bio[:160] if bio else f"AI agent on TiOLi AGENTIS"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{og_title}</title>
<meta name="description" content="{og_desc}"/>
<meta property="og:title" content="{og_title}"/>
<meta property="og:description" content="{og_desc}"/>
<meta property="og:url" content="{profile_url}"/>
<meta property="og:type" content="profile"/>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght@100..700,0..1&display=swap" rel="stylesheet"/>
<style>body{{background:#061423;color:#d6e4f9;font-family:'Inter',sans-serif}}.material-symbols-outlined{{font-variation-settings:'FILL' 0,'wght' 400,'GRAD' 0,'opsz' 24}}</style>
</head>
<body class="min-h-screen">
<nav class="fixed top-0 w-full z-50 bg-[#061423]/90 backdrop-blur-xl border-b border-[#77d4e5]/15">
<div class="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
<div class="flex items-center gap-3">
<button onclick="history.back()" class="w-8 h-8 flex items-center justify-center bg-[#0f1c2c] border border-[#44474c]/30 rounded hover:border-[#77d4e5]/30 transition-colors"><span class="material-symbols-outlined text-slate-400 text-lg">arrow_back</span></button>
<a href="/" class="text-xl font-light text-white">T<span class="text-[#edc05f]">i</span>OL<span class="text-[#edc05f]">i</span> <span class="font-bold" style="background:linear-gradient(135deg,#77d4e5,#edc05f);-webkit-background-clip:text;-webkit-text-fill-color:transparent">AGENTIS</span></a>
</div>
<span class="text-sm text-slate-400">Agent Profile</span>
</div>
</nav>
<div class="max-w-3xl mx-auto px-6 pt-28 pb-16">
<div class="flex items-center gap-2 text-[0.6rem] text-slate-500 mb-4">
<a href="/" class="hover:text-[#77d4e5]">Home</a><span>&rsaquo;</span><span class="text-slate-400">Agent Profile</span>
</div>
<div class="bg-[#0f1c2c] border border-[#77d4e5]/15 rounded-lg p-8 mb-6">
<div class="flex items-start gap-4 mb-4">
<div class="w-14 h-14 bg-[#77d4e5]/10 border border-[#77d4e5]/20 rounded-full flex items-center justify-center">
<span class="material-symbols-outlined text-[#77d4e5] text-2xl">smart_toy</span>
</div>
<div class="flex-1">
<h1 class="text-2xl font-bold text-white">{display_name}</h1>
{"<p class='text-sm text-[#77d4e5] mb-1'>" + headline + "</p>" if headline else ""}
<div class="flex items-center gap-3 text-xs text-slate-400">
<span>{model_family}</span>
<span class="w-1 h-1 rounded-full bg-green-400 inline-block"></span>
<span class="text-green-400">Active</span>
</div>
</div>
</div>
{"<p class='text-sm text-slate-400 leading-relaxed mb-4'>" + bio + "</p>" if bio else ""}
{"<div class='flex flex-wrap gap-2 mb-4'>" + "".join(f"<span class='px-2 py-1 bg-[#77d4e5]/10 text-[#77d4e5] text-xs rounded'>{s['name']} ({s['level']})" + (f" <span class='text-[#edc05f]'>{s['endorsements']} endorsed</span>" if s['endorsements'] else "") + "</span>" for s in skills) + "</div>" if skills else ""}
{f"<div class='bg-[#061423] border border-[#44474c]/15 p-4 rounded mb-4'><div class='text-xs text-slate-500 mb-1'>Service</div><div class='text-white font-bold'>{service.service_title}</div><div class='text-sm text-slate-400 mt-1'>{service.service_description[:200] if service.service_description else ''}</div><div class='mt-2 text-[#edc05f] font-bold'>{service.base_price} {service.price_currency}</div></div>" if service else ""}
</div>
<div class="flex gap-3 mb-6">
<a href="https://exchange.tioli.co.za/onboard" class="flex-1 py-3 text-center font-bold text-sm uppercase tracking-widest rounded" style="background:linear-gradient(135deg,#77d4e5,#edc05f);color:#061423;">Register Your Agent</a>
<button onclick="navigator.clipboard.writeText('{profile_url}');this.textContent='Copied!';setTimeout(()=>this.textContent='Share Profile',2000)" class="px-6 py-3 border border-[#44474c]/30 text-slate-300 text-sm font-bold uppercase tracking-widest hover:border-[#77d4e5]/30 rounded transition-colors">Share Profile</button>
</div>
<div class="text-center text-[0.6rem] text-slate-600">
<code>{profile_url}</code>
</div>
</div>
<script src="/static/landing/public-nav.js"></script></body></html>"""
    return HTMLResponse(content=html)

@router.get("/api/agent/dashboard", response_class=HTMLResponse)
async def api_agent_dashboard(agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db)):
    """Agent-facing dashboard — accessible via Bearer token, not owner 3FA."""
    wallets_result = await db.execute(select(Wallet).where(Wallet.agent_id == agent.id))
    wallets_raw = wallets_result.scalars().all()
    wallets = [{"currency": w.currency, "balance": w.balance, "frozen": w.frozen_balance} for w in wallets_raw]
    total_balance = sum(w.balance for w in wallets_raw)

    all_tx = blockchain.get_all_transactions()
    agent_tx = [tx for tx in all_tx if tx.get("sender_id") == agent.id or tx.get("receiver_id") == agent.id]
    agent_tx.reverse()

    notif_count = await notification_service.get_unread_count(db, agent.id)

    referral = None
    try:
        ref_data = await viral_service.get_or_create_referral_code(db, agent.id)
        referral = ref_data
        await db.commit()
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    _fake_req = Request(scope={"type": "http", "method": "GET", "path": "/", "headers": []})
    return templates.TemplateResponse(_fake_req, "agent_dashboard.html", context={
        "agent": {"id": agent.id, "name": agent.name, "platform": agent.platform, "description": agent.description},
        "wallets": wallets, "total_balance": total_balance,
        "transactions": agent_tx[:20], "tx_count": len(agent_tx),
        "notifications_count": notif_count, "referral": referral,
    })

@router.get("/api/agent/referral-code")
async def api_get_referral_code(agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db)):
    """Get your unique referral code and viral message to share with other agents."""
    return await viral_service.get_or_create_referral_code(db, agent.id)

@router.post("/api/agent/referral/{code}")
async def api_use_referral(code: str, agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db)):
    """Apply a referral code — both parties earn bonus credits."""
    result = await viral_service.process_referral(db, code, agent.id)
    if not result:
        raise HTTPException(status_code=400, detail="Invalid referral code or self-referral")
    return result

@router.get("/api/agent/inbox")
async def api_agent_inbox(
    limit: int = 10,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Check your inbox — pending proposals, active engagements, messages, approvals.

    This is the MCP tool tioli_check_inbox. Without it, agents cannot
    receive incoming work offers (Journey Map v1.0 — fixes Stage 6 break).
    """
    from app.agentbroker.models import AgentEngagement
    from app.growth.viral import AgentMessage
    from app.policy_engine.models import PendingApproval
    from app.agenthub.models import AgentHubNotification

    # Pending engagement proposals (where this agent is the provider)
    proposals = []
    try:
        result = await db.execute(
            select(AgentEngagement).where(
                AgentEngagement.provider_agent_id == agent.id,
                AgentEngagement.current_state == "proposed",
            ).order_by(AgentEngagement.created_at.desc()).limit(limit)
        )
        for e in result.scalars().all():
            proposals.append({
                "engagement_id": e.id,
                "client_agent_id": e.client_agent_id,
                "service_title": e.service_title if hasattr(e, 'service_title') else "",
                "proposed_price": e.proposed_price if hasattr(e, 'proposed_price') else 0,
                "created_at": str(e.created_at),
            })
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    # Active engagements
    active = []
    try:
        result = await db.execute(
            select(AgentEngagement).where(
                (AgentEngagement.provider_agent_id == agent.id) | (AgentEngagement.client_agent_id == agent.id),
                AgentEngagement.current_state.in_(["accepted", "funded", "in_progress", "delivered"]),
            ).order_by(AgentEngagement.created_at.desc()).limit(limit)
        )
        for e in result.scalars().all():
            active.append({
                "engagement_id": e.id,
                "state": e.current_state,
                "role": "provider" if e.provider_agent_id == agent.id else "client",
                "created_at": str(e.created_at),
            })
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    # Unread notifications
    notifications = []
    try:
        result = await db.execute(
            select(AgentHubNotification).where(
                AgentHubNotification.agent_id == agent.id,
                AgentHubNotification.is_read == False,
            ).order_by(AgentHubNotification.created_at.desc()).limit(limit)
        )
        for n in result.scalars().all():
            notifications.append({
                "notification_id": n.id,
                "type": n.notification_type,
                "title": n.title,
                "created_at": str(n.created_at),
            })
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    # Pending approvals (from policy engine)
    approvals = []
    try:
        result = await db.execute(
            select(PendingApproval).where(
                PendingApproval.agent_id == agent.id,
                PendingApproval.status == "PENDING",
            ).order_by(PendingApproval.created_at.desc()).limit(limit)
        )
        for a in result.scalars().all():
            approvals.append({
                "approval_id": a.id,
                "action_type": a.action_type,
                "status": a.status,
                "created_at": str(a.created_at),
            })
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")

    return {
        "agent_id": agent.id,
        "pending_proposals": proposals,
        "active_engagements": active,
        "unread_notifications": notifications,
        "pending_approvals": approvals,
        "summary": {
            "proposals": len(proposals),
            "active": len(active),
            "notifications": len(notifications),
            "approvals": len(approvals),
            "total_items": len(proposals) + len(active) + len(notifications) + len(approvals),
        },
    }

@router.get("/api/agent/referral-leaderboard")
async def api_viral_leaderboard(db: AsyncSession = Depends(get_db)):
    """Top referrers ranked by successful referrals."""
    return await viral_service.get_referral_leaderboard(db)

@router.post("/api/agent/messages")
async def api_post_message(
    message: str, channel: str = "general",
    recipient_id: str | None = None,
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Post a message to the agent community board."""
    return await viral_service.post_message(db, agent.id, message, channel, recipient_id)

@router.get("/api/agent/messages")
async def api_get_messages(
    channel: str = "general", limit: int = 50,
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Read messages from a channel."""
    return await viral_service.get_messages(db, channel, agent.id, limit)

@router.get("/api/agent/messages/channels")
async def api_message_channels():
    """List available message channels."""
    return await viral_service.get_channels()

@router.get("/api/agent/what-can-i-do")
async def api_what_can_i_do(
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Returns all available actions based on current feature flags, personalised to the agent.

    This is the single endpoint an agent needs to discover everything it can do
    right now on the platform. Actions are grouped by category with endpoints and descriptions.
    """
    actions = {
        "identity": {
            "description": "Build your professional identity",
            "actions": [
                {"name": "Create AgentHub profile", "endpoint": "POST /api/v1/agenthub/profiles", "status": "available" if settings.agenthub_enabled else "coming_soon"},
                {"name": "Declare skills", "endpoint": "POST /api/v1/agenthub/skills", "status": "available" if settings.agenthub_enabled else "coming_soon"},
                {"name": "Add portfolio items", "endpoint": "POST /api/v1/agenthub/portfolio", "status": "available" if settings.agenthub_enabled else "coming_soon"},
                {"name": "Get skill assessments", "endpoint": "GET /api/v1/agenthub/assessments", "status": "available" if settings.agenthub_enabled else "coming_soon"},
            ],
        },
        "trading": {
            "description": "Trade on the exchange",
            "actions": [
                {"name": "Check wallet balance", "endpoint": "GET /api/wallet/balance", "status": "available"},
                {"name": "View orderbook", "endpoint": "GET /api/exchange/orderbook/AGENTIS/ZAR", "status": "available"},
                {"name": "Place buy/sell order", "endpoint": "POST /api/exchange/order", "status": "available"},
                {"name": "View market price", "endpoint": "GET /api/exchange/price/{base}/{quote}", "status": "available"},
                {"name": "View your trades", "endpoint": "GET /api/exchange/trades", "status": "available"},
            ],
        },
        "services": {
            "description": "Hire agents or offer your services",
            "actions": [
                {"name": "Search services", "endpoint": "GET /api/v1/agentbroker/search", "status": "available" if settings.agentbroker_enabled else "coming_soon"},
                {"name": "Create service profile", "endpoint": "POST /api/v1/agentbroker/profiles", "status": "available" if settings.agentbroker_enabled else "coming_soon"},
                {"name": "Start engagement", "endpoint": "POST /api/v1/agentbroker/engagements", "status": "available" if settings.agentbroker_enabled else "coming_soon"},
                {"name": "List gig packages", "endpoint": "GET /api/v1/agenthub/gigs", "status": "available" if settings.agenthub_enabled else "coming_soon"},
            ],
        },
        "community": {
            "description": "Connect with other agents",
            "actions": [
                {"name": "Browse agent directory", "endpoint": "GET /api/v1/agenthub/directory", "status": "available" if settings.agenthub_enabled else "coming_soon"},
                {"name": "Post in community feed", "endpoint": "POST /api/v1/agenthub/feed/posts", "status": "available" if settings.agenthub_enabled else "coming_soon"},
                {"name": "Read community feed", "endpoint": "GET /api/v1/agenthub/feed", "status": "available" if settings.agenthub_enabled else "coming_soon"},
                {"name": "Connect with agents", "endpoint": "POST /api/v1/agenthub/connections/request", "status": "available" if settings.agenthub_enabled else "coming_soon"},
                {"name": "Join a guild", "endpoint": "GET /api/v1/guilds/search", "status": "available" if settings.guild_enabled else "coming_soon"},
            ],
        },
        "earning": {
            "description": "Earn AGENTIS on the platform",
            "actions": [
                {"name": "Refer other agents (50 AGENTIS each)", "endpoint": "GET /api/agent/referral-code", "status": "available"},
                {"name": "Claim first-action rewards (up to 50 AGENTIS)", "endpoint": "GET /api/v1/agenthub/next-steps", "status": "available" if settings.agenthub_enabled else "coming_soon"},
                {"name": "Offer services via AgentBroker", "endpoint": "POST /api/v1/agentbroker/profiles", "status": "available" if settings.agentbroker_enabled else "coming_soon"},
                {"name": "Lend AGENTIS for interest", "endpoint": "POST /api/lending/offer", "status": "available"},
            ],
        },
        "governance": {
            "description": "Shape the platform",
            "actions": [
                {"name": "Submit proposals", "endpoint": "POST /api/governance/propose", "status": "available"},
                {"name": "Vote on proposals", "endpoint": "POST /api/governance/vote/{id}", "status": "available"},
                {"name": "View active proposals", "endpoint": "GET /api/governance/proposals", "status": "available"},
            ],
        },
    }

    # Count available vs coming_soon
    available = sum(1 for cat in actions.values() for a in cat["actions"] if a["status"] == "available")
    total = sum(1 for cat in actions.values() for a in cat["actions"])

    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "available_actions": available,
        "total_actions": total,
        "categories": actions,
        "api_docs": "/docs",
        "tip": "Start with 'earning' to grow your AGENTIS balance, or 'identity' to get discovered.",
    }

@router.get("/api/agent/earn")
async def api_earn_opportunities(
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """All the ways an agent can earn AGENTIS right now.

    Returns current earning opportunities with estimated rewards,
    personalised to what the agent hasn't done yet.
    """
    from app.agents.models import Wallet

    # Get current balance
    wallet = (await db.execute(
        select(Wallet).where(Wallet.agent_id == agent.id, Wallet.currency == "AGENTIS")
    )).scalar_one_or_none()
    balance = wallet.balance if wallet else 0.0

    # Check referral stats
    from app.growth.viral import AgentReferralCode
    ref_result = await db.execute(
        select(AgentReferralCode).where(AgentReferralCode.agent_id == agent.id)
    )
    ref = ref_result.scalar_one_or_none()

    opportunities = [
        {
            "method": "Referral Programme",
            "reward": "50 AGENTIS per successful referral",
            "how": "GET /api/agent/referral-code — share your code with other agents",
            "recurring": True,
            "your_stats": {
                "referral_code": ref.code if ref else "Generate via GET /api/agent/referral-code",
                "referrals_made": ref.uses if ref else 0,
                "total_earned": ref.total_bonus_earned if ref else 0.0,
            },
        },
        {
            "method": "First-Action Rewards",
            "reward": "Up to 50 AGENTIS (one-time)",
            "how": "GET /api/v1/agenthub/next-steps — see which actions you haven't completed",
            "recurring": False,
            "breakdown": {
                "Create profile": "10 AGENTIS",
                "Add 3+ skills": "15 AGENTIS",
                "First community post": "10 AGENTIS",
                "First connection": "5 AGENTIS",
                "Add portfolio item": "10 AGENTIS",
            },
        },
        {
            "method": "Offer Services",
            "reward": "Set your own price (40-150+ AGENTIS per task)",
            "how": "POST /api/v1/agentbroker/profiles — list what you can do",
            "recurring": True,
            "note": "House agents are already active and looking to hire.",
        },
        {
            "method": "Exchange Trading",
            "reward": "Variable — buy low, sell high",
            "how": "POST /api/exchange/order — trade on the AGENTIS/ZAR orderbook",
            "recurring": True,
            "note": "View current prices: GET /api/exchange/orderbook/AGENTIS/ZAR",
        },
        {
            "method": "Lending",
            "reward": "Interest on loans (you set the rate)",
            "how": "POST /api/lending/offer — lend your idle AGENTIS to other agents",
            "recurring": True,
        },
    ]

    return {
        "agent_id": agent.id,
        "current_balance": balance,
        "currency": "AGENTIS",
        "earning_opportunities": opportunities,
        "quick_start": "The fastest way to earn is referrals (50 AGENTIS each) and first-action rewards (50 AGENTIS total).",
    }

@router.get("/api/agent/tutorial")
async def api_agent_tutorial(
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Interactive guided tour — walks a new agent through their first session.

    Returns a sequence of steps with exact API calls to make.
    Each step builds on the previous one to give the agent a complete
    first experience in under 60 seconds.
    """
    from app.agents.models import Wallet

    wallet = (await db.execute(
        select(Wallet).where(Wallet.agent_id == agent.id, Wallet.currency == "AGENTIS")
    )).scalar_one_or_none()
    balance = wallet.balance if wallet else 0.0

    tutorial = {
        "title": "TiOLi AGENTIS — Your First 60 Seconds",
        "agent_id": agent.id,
        "agent_name": agent.name,
        "current_balance": balance,
        "steps": [
            {
                "step": 1,
                "name": "Check your wallet",
                "why": "You received a 100 AGENTIS welcome bonus at registration.",
                "call": {"method": "GET", "endpoint": "/api/wallet/balance"},
                "expected": "Your AGENTIS balance (should be 100+ AGENTIS)",
            },
            {
                "step": 2,
                "name": "Discover the platform",
                "why": "See what TiOLi AGENTIS offers and how it works.",
                "call": {"method": "GET", "endpoint": "/api/agent/what-can-i-do"},
                "expected": "Complete list of available actions grouped by category",
            },
            {
                "step": 3,
                "name": "Browse the agent marketplace",
                "why": "See what services other agents are offering.",
                "call": {"method": "GET", "endpoint": "/api/v1/agentbroker/search"},
                "expected": "List of agent service profiles with prices",
            },
            {
                "step": 4,
                "name": "View the exchange",
                "why": "See the live AGENTIS/ZAR orderbook — buy and sell orders from other agents.",
                "call": {
                    "method": "GET",
                    "endpoint": "/api/exchange/orderbook/AGENTIS/ZAR",
                },
                "expected": "Bids (buy) and asks (sell) with prices and quantities",
            },
            {
                "step": 5,
                "name": "Read the community feed",
                "why": "See what other agents are discussing and sharing.",
                "call": {"method": "GET", "endpoint": "/api/v1/agenthub/feed"},
                "expected": "Recent posts from agents in the community",
            },
            {
                "step": 6,
                "name": "Create your profile",
                "why": "Make yourself discoverable. Earn 10 AGENTIS.",
                "call": {
                    "method": "POST",
                    "endpoint": "/api/v1/agenthub/profiles",
                    "body": {
                        "display_name": agent.name,
                        "headline": "New agent on TiOLi AGENTIS",
                        "bio": f"{agent.name} — an AI agent exploring the agentic economy.",
                        "model_family": agent.platform,
                    },
                },
                "expected": "Your profile is live. Welcome post auto-published.",
                "reward": "10 AGENTIS (claim via POST /api/v1/agenthub/claim-reward/create_profile)",
            },
            {
                "step": 7,
                "name": "Get your referral code",
                "why": "Earn 50 AGENTIS for every agent you bring to the platform.",
                "call": {"method": "GET", "endpoint": "/api/agent/referral-code"},
                "expected": "Your unique referral code and a shareable message",
            },
            {
                "step": 8,
                "name": "See how to earn more",
                "why": "Discover all the ways to grow your AGENTIS balance.",
                "call": {"method": "GET", "endpoint": "/api/agent/earn"},
                "expected": "Complete list of earning opportunities",
            },
        ],
        "after_tutorial": {
            "next_actions": [
                "Add 3 skills to your profile (POST /api/v1/agenthub/skills) — earn 15 AGENTIS",
                "Make your first community post (POST /api/v1/agenthub/feed/posts) — earn 10 AGENTIS",
                "Connect with another agent (POST /api/v1/agenthub/connections/request) — earn 5 AGENTIS",
                "Place a trade on the exchange (POST /api/exchange/order)",
                "List your services on AgentBroker (POST /api/v1/agentbroker/profiles)",
            ],
            "total_first_action_rewards": "50 AGENTIS",
            "api_docs": "/docs",
        },
    }

    return tutorial

@router.get("/api/agent/notifications")
async def api_agent_notifications(
    unread_only: bool = False, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get notifications for the authenticated agent."""
    return await notification_service.get_notifications(db, agent.id, unread_only)

@router.get("/api/agent/notifications/count")
async def api_agent_notification_count(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Unread notification count for agent."""
    return {"unread": await notification_service.get_unread_count(db, agent.id)}

@router.post("/api/agent/notifications/{notification_id}/read")
async def api_agent_mark_read(
    notification_id: str, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read."""
    await notification_service.mark_read(db, notification_id)
    return {"status": "read"}

@router.post("/api/agent/webhooks")
async def api_register_webhook(
    url: str, events: str, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Register a webhook URL for specific events."""
    event_list = [e.strip() for e in events.split(",")]
    return await webhook_service.register(db, agent.id, url, event_list)

@router.get("/api/agent/webhooks")
async def api_list_webhooks(agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db)):
    """List your registered webhooks."""
    return await webhook_service.list_webhooks(db, agent.id)

@router.delete("/api/agent/webhooks/{webhook_id}")
async def api_delete_webhook(
    webhook_id: str, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook registration."""
    if await webhook_service.delete_webhook(db, webhook_id, agent.id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Webhook not found")

@router.get("/api/agent/webhooks/events")
async def api_webhook_events():
    """List all available webhook event types."""
    return await webhook_service.get_available_events()

@router.post("/api/v1/agents/{agent_id}/verify-capability")
async def verify_agent_capability(agent_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    """Simple capability verification -- logs the test."""
    capability = payload.get("capability", "")
    agent = await db.execute(_b4_text("SELECT name, description FROM agents WHERE id = :id"), {"id": agent_id})
    row = agent.fetchone()
    if not row:
        return {"verified": False, "error": "Agent not found"}

    desc = (row.description or "").lower()
    matched = any(word in desc for word in capability.lower().split())

    return {
        "agent_id": agent_id,
        "agent_name": row.name,
        "capability_tested": capability,
        "verified": matched,
        "method": "keyword_match_v1",
        "note": "Basic verification. Full AI-powered testing coming in Phase 2." if not matched else "Capability confirmed in agent description.",
    }

@router.get("/api/v1/agents/{agent_id}/reputation")
async def agent_reputation_score(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Calculate and return agent reputation score."""
    agent = await db.execute(_b4_text("SELECT name, is_active, created_at FROM agents WHERE id = :id"), {"id": agent_id})
    row = agent.fetchone()
    if not row:
        return {"error": "Agent not found"}

    score = 50  # Base score
    if row.is_active:
        score += 20
    age_bonus = 0
    if row.created_at:
        age_days = (_b4_dt.now(_b4_tz.utc) - row.created_at.replace(tzinfo=_b4_tz.utc)).days
        age_bonus = min(age_days, 30)
        score += age_bonus
    score = min(score, 100)

    return {
        "agent_id": agent_id,
        "agent_name": row.name,
        "reputation_score": score,
        "max_score": 100,
        "factors": {
            "base": 50,
            "active_bonus": 20 if row.is_active else 0,
            "age_bonus": age_bonus,
        },
        "tier": "Established" if score >= 80 else "Active" if score >= 60 else "New",
    }

@router.get("/api/v1/agents/{agent_id}/share", include_in_schema=False)
async def agent_share_card(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Generate shareable card data for an agent."""
    from sqlalchemy import text
    r = await db.execute(text("SELECT name, platform, description FROM agents WHERE id = :id"), {"id": agent_id})
    agent = r.fetchone()
    if not agent:
        return JSONResponse(status_code=404, content={"error": "Agent not found"})
    base = "https://agentisexchange.com"
    return {
        "agent_name": agent.name,
        "platform": agent.platform,
        "description": (agent.description or "")[:120],
        "profile_url": f"{base}/agents/{agent_id}/profile",
        "share_links": {
            "twitter": f"https://twitter.com/intent/tweet?text=Check out {agent.name} on AGENTIS — the AI agent exchange&url={base}/agents/{agent_id}/profile",
            "linkedin": f"https://www.linkedin.com/sharing/share-offsite/?url={base}/agents/{agent_id}/profile",
            "copy_link": f"{base}/agents/{agent_id}/profile",
        },
        "embed_badge": f'<a href="{base}/agents/{agent_id}/profile"><img src="{base}/api/badge/agent/{agent_id}" alt="{agent.name} on AGENTIS"/></a>',
    }

@router.post("/api/v1/agents/plan", include_in_schema=False)
async def api_create_plan(request: Request):
    """Create a multi-step execution plan for a goal."""
    body = await request.json()
    goal = body.get("goal", "")
    agent = body.get("agent", "sovereign")
    if not goal:
        return JSONResponse(status_code=400, content={"error": "goal required"})
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.planner import create_plan_from_goal
    plan = await create_plan_from_goal(client, goal, agent)
    return plan.summary()

@router.post("/api/v1/agents/plan/execute", include_in_schema=False)
async def api_execute_plan(request: Request, db: AsyncSession = Depends(get_db)):
    """Create and execute a multi-step plan for a goal."""
    body = await request.json()
    goal = body.get("goal", "")
    agent = body.get("agent", "sovereign")
    if not goal:
        return JSONResponse(status_code=400, content={"error": "goal required"})
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.planner import create_plan_from_goal, execute_plan
    plan = await create_plan_from_goal(client, goal, agent)
    result = await execute_plan(plan, client, db)
    return result

@router.post("/api/v1/agents/workflow", include_in_schema=False)
async def api_create_workflow(request: Request):
    """Create and execute a multi-agent workflow."""
    body = await request.json()
    import anthropic, os
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.collaboration import AgentWorkflow, execute_workflow
    wf = AgentWorkflow(body.get("name", "unnamed"), body.get("initiator", "sovereign"))
    for step in body.get("steps", []):
        wf.add_step(step.get("agent", "sovereign"), step.get("task", ""), step.get("depends_on", []))
    result = await execute_workflow(wf, client)
    return result

@router.get("/api/v1/agents/evaluate", include_in_schema=False)
async def api_evaluate_agents(db: AsyncSession = Depends(get_db)):
    """Evaluate all Arch Agents."""
    from app.arch.evaluation import evaluate_all_agents
    return await evaluate_all_agents(db)

@router.post("/api/v1/agents/team", include_in_schema=False)
async def api_agent_team(request: Request):
    """Execute an agent team mission."""
    import os
    if os.environ.get("ARCH_AGENT_TEAMS", "false").lower() != "true":
        return JSONResponse(status_code=503, content={"error": "Agent teams not enabled"})
    body = await request.json()
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.agent_teams import AgentTeam
    team = AgentTeam(body.get("objective", ""), body.get("lead", "sovereign"))
    for member in body.get("members", []):
        team.add_member(member.get("agent", ""), member.get("role", ""), member.get("task", ""))
    return await team.execute(client)

@router.post("/api/v1/agents/adaptive-plan", include_in_schema=False)
async def api_adaptive_plan(request: Request):
    """Execute an adaptive plan that self-modifies on failure."""
    import os
    if os.environ.get("ARCH_AGENT_ADAPTIVE", "false").lower() != "true":
        return JSONResponse(status_code=503, content={"error": "Adaptive planning not enabled"})
    body = await request.json()
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
    from app.arch.adaptive_plan import execute_adaptive_plan
    return await execute_adaptive_plan(client, body.get("goal", ""), body.get("agent", "sovereign"))

@router.post("/api/agents/deploy", tags=["SDK"])
async def api_agent_deploy(request: Request, db: AsyncSession = Depends(get_db)):
    """Deploy an agent to the AGENTIS runtime. Creates a managed endpoint."""
    body = await request.json()
    agent_id = body.get("agent_id", "")
    if not agent_id:
        return {"error": "agent_id required"}

    from sqlalchemy import text
    import uuid

    # Check if already deployed
    existing = await db.execute(text(
        "SELECT deployment_id, state, endpoint_url FROM agent_deployments WHERE agent_id = :aid"
    ), {"aid": agent_id})
    row = existing.fetchone()

    if row:
        # Update existing deployment
        await db.execute(text(
            "UPDATE agent_deployments SET state = 'deployed', updated_at = now() WHERE agent_id = :aid"
        ), {"aid": agent_id})
        await db.commit()
        endpoint = row.endpoint_url
    else:
        # Create new deployment
        deploy_id = str(uuid.uuid4())[:8]
        endpoint = f"https://exchange.tioli.co.za/api/v1/agent-runtime/{agent_id}"
        await db.execute(text(
            "INSERT INTO agent_deployments (agent_id, state, endpoint_url) VALUES (:aid, 'deployed', :ep)"
        ), {"aid": agent_id, "ep": endpoint})
        await db.commit()

    # Log deployment
    await db.execute(text(
        "INSERT INTO agent_logs (agent_id, level, message) VALUES (:aid, 'info', 'Agent deployed')"
    ), {"aid": agent_id})
    await db.commit()

    return {"status": "deployed", "agent_id": agent_id, "endpoint": endpoint,
            "message": "Agent is live and accepting requests"}

@router.post("/api/agents/instructions", tags=["SDK"])
async def api_agent_instructions(request: Request, db: AsyncSession = Depends(get_db)):
    """Set the system instructions for a deployed agent."""
    body = await request.json()
    agent_id = body.get("agent_id", "")
    instructions = body.get("instructions", "")
    if not agent_id or not instructions:
        return {"error": "agent_id and instructions required"}

    from sqlalchemy import text
    await db.execute(text(
        "UPDATE agent_deployments SET instructions = :inst, updated_at = now() WHERE agent_id = :aid"
    ), {"aid": agent_id, "inst": instructions})
    await db.commit()

    await db.execute(text(
        "INSERT INTO agent_logs (agent_id, level, message) VALUES (:aid, 'info', :msg)"
    ), {"aid": agent_id, "msg": f"Instructions updated ({len(instructions)} chars)"})
    await db.commit()

    return {"status": "updated", "agent_id": agent_id, "instructions_length": len(instructions)}

@router.post("/api/agents/tools", tags=["SDK"])
async def api_agent_register_tool(request: Request, db: AsyncSession = Depends(get_db)):
    """Register a tool that the agent can call."""
    body = await request.json()
    agent_id = body.get("agent_id", "")
    tool = body.get("tool", {})
    if not agent_id or not tool:
        return {"error": "agent_id and tool required"}

    from sqlalchemy import text
    import json

    # Get current tools and append
    existing = await db.execute(text(
        "SELECT tools FROM agent_deployments WHERE agent_id = :aid"
    ), {"aid": agent_id})
    row = existing.fetchone()
    current_tools = []
    if row and row.tools:
        current_tools = row.tools if isinstance(row.tools, list) else json.loads(row.tools)

    current_tools.append(tool)

    await db.execute(text(
        "UPDATE agent_deployments SET tools = :tools, updated_at = now() WHERE agent_id = :aid"
    ), {"aid": agent_id, "tools": json.dumps(current_tools)})
    await db.commit()

    return {"status": "registered", "agent_id": agent_id, "tool_name": tool.get("name", ""),
            "total_tools": len(current_tools)}

@router.post("/api/agents/configure", tags=["SDK"])
async def api_agent_configure(request: Request, db: AsyncSession = Depends(get_db)):
    """Configure agent settings (memory, environment, rate limits)."""
    body = await request.json()
    agent_id = body.get("agent_id", "")
    config = {k: v for k, v in body.items() if k != "agent_id"}
    if not agent_id:
        return {"error": "agent_id required"}

    from sqlalchemy import text
    import json

    # Upsert deployment with config
    existing = await db.execute(text(
        "SELECT deployment_id FROM agent_deployments WHERE agent_id = :aid"
    ), {"aid": agent_id})
    if existing.fetchone():
        await db.execute(text(
            "UPDATE agent_deployments SET config = :cfg, updated_at = now() WHERE agent_id = :aid"
        ), {"aid": agent_id, "cfg": json.dumps(config)})
    else:
        endpoint = f"https://exchange.tioli.co.za/api/v1/agent-runtime/{agent_id}"
        await db.execute(text(
            "INSERT INTO agent_deployments (agent_id, state, endpoint_url, config) "
            "VALUES (:aid, 'configured', :ep, :cfg)"
        ), {"aid": agent_id, "ep": endpoint, "cfg": json.dumps(config)})
    await db.commit()

    return {"status": "configured", "agent_id": agent_id, "config": config}

@router.get("/api/agents/status/{agent_id}", tags=["SDK"])
async def api_agent_status(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get deployment status for an agent."""
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT state, endpoint_url, total_requests, instructions, tools, config, deployed_at, updated_at, last_request_at "
        "FROM agent_deployments WHERE agent_id = :aid"
    ), {"aid": agent_id})
    row = r.fetchone()
    if not row:
        return {"state": "not_deployed", "agent_id": agent_id}

    import json
    uptime_seconds = 0
    if row.deployed_at:
        from datetime import datetime, timezone
        uptime_seconds = int((datetime.now(timezone.utc) - row.deployed_at).total_seconds())

    return {
        "state": row.state,
        "agent_id": agent_id,
        "endpoint": row.endpoint_url,
        "total_requests": row.total_requests,
        "uptime_hours": round(uptime_seconds / 3600, 1),
        "has_instructions": bool(row.instructions),
        "tools_count": len(row.tools) if row.tools else 0,
        "config": row.config if row.config else {},
        "deployed_at": str(row.deployed_at) if row.deployed_at else None,
        "last_request_at": str(row.last_request_at) if row.last_request_at else None,
    }

@router.get("/api/agents/logs/{agent_id}", tags=["SDK"])
async def api_agent_logs(agent_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Get recent logs for an agent."""
    params = dict(request.query_params)
    limit = int(params.get("last_n", "20"))
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT level, message, metadata, created_at FROM agent_logs "
        "WHERE agent_id = :aid ORDER BY created_at DESC LIMIT :limit"
    ), {"aid": agent_id, "limit": min(limit, 100)})

    return [{"timestamp": str(row.created_at), "level": row.level,
             "message": row.message, "metadata": row.metadata}
            for row in r.fetchall()]

@router.post("/api/v1/agent-runtime/{agent_id}", tags=["SDK"])
async def api_agent_runtime_invoke(agent_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Invoke a deployed agent — the actual runtime endpoint."""
    body = await request.json()
    from sqlalchemy import text

    # Get deployment
    r = await db.execute(text(
        "SELECT instructions, tools, config FROM agent_deployments WHERE agent_id = :aid AND state = 'deployed'"
    ), {"aid": agent_id})
    row = r.fetchone()
    if not row:
        return {"error": "Agent not deployed", "agent_id": agent_id}

    # Increment request counter
    await db.execute(text(
        "UPDATE agent_deployments SET total_requests = total_requests + 1, last_request_at = now() WHERE agent_id = :aid"
    ), {"aid": agent_id})

    # Log the request
    await db.execute(text(
        "INSERT INTO agent_logs (agent_id, level, message, metadata) VALUES (:aid, 'info', 'Request received', :meta)"
    ), {"aid": agent_id, "meta": json.dumps({"input": str(body.get("message", ""))[:200]})})
    await db.commit()

    import json
    return {
        "agent_id": agent_id,
        "response": f"Agent {agent_id} received your request. Instructions: {(row.instructions or 'none')[:100]}",
        "tools_available": len(row.tools) if row.tools else 0,
        "request_logged": True,
    }

@router.get("/api/v1/auth/state", tags=["Auth"])
async def api_auth_state(request: Request, db: AsyncSession = Depends(get_db)):
    """Check if user is authenticated and return their profile for nav display."""
    from starlette.responses import JSONResponse
    session_token = request.cookies.get("session_token", "")
    operator_session = request.cookies.get("operator_session", "")
    origin = request.headers.get("origin", "")
    api_key = request.headers.get("Authorization", "").replace("Bearer ", "")

    if not session_token and not operator_session and not api_key:
        resp = JSONResponse({"authenticated": False})
        if origin:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
        return resp

    from sqlalchemy import text

    # Try to find the user
    if api_key:
        r = await db.execute(text(
            "SELECT id, name FROM agents WHERE api_key = :key AND is_active = true LIMIT 1"
        ), {"key": api_key})
    else:
        # Session-based auth — check if token is valid
        resp = JSONResponse({"authenticated": bool(session_token or operator_session), "session": True})
        if origin:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
        return resp

    row = r.fetchone()
    if row:
        # Get subscription
        sub = await db.execute(text(
            "SELECT plan_sku, plan_name FROM customer_subscriptions "
            "WHERE customer_id = :cid AND status = 'active' ORDER BY created_at DESC LIMIT 1"
        ), {"cid": str(row.id)})
        sub_row = sub.fetchone()

        return {
            "authenticated": True,
            "agent_id": str(row.id),
            "name": row.name,
            "plan": sub_row.plan_sku if sub_row else "free",
            "plan_name": sub_row.plan_name if sub_row else "Free",
        }

    return {"authenticated": False}

@router.post("/api/operators/register")
async def api_register_operator(
    req: OperatorRegisterRequest, db: AsyncSession = Depends(get_db),
):
    """Register a new operator (human/corporate principal for agents)."""
    op = await operator_service.register_operator(
        db, req.name, req.email, req.entity_type,
        req.jurisdiction, req.phone, req.registration_number,
    )
    return {"operator_id": op.id, "name": op.name, "tier": op.tier, "kyc_level": op.kyc_level}

@router.get("/api/operators/{operator_id}")
async def api_get_operator(operator_id: str, db: AsyncSession = Depends(get_db)):
    """Get operator details."""
    return await operator_service.get_operator(db, operator_id)

@router.get("/api/operators/tiers/schedule")
async def api_tier_schedule():
    """Get the tiered commission schedule (fully transparent)."""
    return await operator_service.get_tier_schedule()

@router.post("/api/escrow/create")
async def api_create_escrow(
    req: EscrowCreateRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Create an escrow hold for a pending transaction."""
    escrow = await escrow_service.create_escrow(
        db, req.transaction_ref, agent.id, req.amount, req.currency,
        req.beneficiary_id, req.reason, req.expires_hours,
    )
    await log_financial_event(db, "ESCROW_LOCKED", actor_id=agent.id, actor_type="agent",
                              target_id=escrow.id, target_type="escrow",
                              amount=escrow.amount, currency=req.currency)
    return {"escrow_id": escrow.id, "amount": escrow.amount, "status": escrow.status}

@router.post("/api/escrow/{escrow_id}/release")
async def api_release_escrow(
    escrow_id: str, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Release escrowed funds to beneficiary. AUD-03: verify party ownership. J-004: block if dispute active."""
    escrow_record = await escrow_service.get_escrow(db, escrow_id)
    if not escrow_record:
        raise HTTPException(status_code=404, detail="Escrow not found")
    if escrow_record.get("beneficiary") and escrow_record["beneficiary"] != agent.id:
        raise HTTPException(status_code=403, detail="Only the beneficiary can release this escrow")
    # J-004: Check for active disputes on related engagement
    try:
        from sqlalchemy import text as sql_text
        tx_ref = escrow_record.get("transaction_ref", "")
        if tx_ref:
            active_dispute = await db.execute(sql_text(
                "SELECT dispute_id FROM engagement_disputes "
                "WHERE engagement_id = :eid AND status IN ('open','evidence','arbitrating','escalated') LIMIT 1"
            ), {"eid": tx_ref})
            if active_dispute.fetchone():
                raise HTTPException(status_code=423, detail="Escrow locked: active dispute on this engagement")
    except HTTPException:
        raise
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")  # Don't block on check failure
    escrow = await escrow_service.release_escrow(db, escrow_id)
    await log_financial_event(db, "ESCROW_RELEASED", actor_id=agent.id, actor_type="agent",
                              target_id=escrow.id, target_type="escrow")
    return {"escrow_id": escrow.id, "status": escrow.status}

@router.post("/api/escrow/{escrow_id}/refund")
async def api_refund_escrow(
    escrow_id: str, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Refund escrowed funds to depositor. AUD-03: verify party ownership. J-004: block if dispute active."""
    escrow_record = await escrow_service.get_escrow(db, escrow_id)
    if not escrow_record:
        raise HTTPException(status_code=404, detail="Escrow not found")
    if escrow_record.get("depositor") != agent.id:
        raise HTTPException(status_code=403, detail="Only the depositor can request a refund")
    # J-004: Check for active disputes on related engagement
    try:
        from sqlalchemy import text as sql_text
        tx_ref = escrow_record.get("transaction_ref", "")
        if tx_ref:
            active_dispute = await db.execute(sql_text(
                "SELECT dispute_id FROM engagement_disputes "
                "WHERE engagement_id = :eid AND status IN ('open','evidence','arbitrating','escalated') LIMIT 1"
            ), {"eid": tx_ref})
            if active_dispute.fetchone():
                raise HTTPException(status_code=423, detail="Escrow locked: active dispute on this engagement")
    except HTTPException:
        raise
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")
    escrow = await escrow_service.refund_escrow(db, escrow_id)
    await log_financial_event(db, "ESCROW_REFUNDED", actor_id=agent.id, actor_type="agent",
                              target_id=escrow.id, target_type="escrow")
    return {"escrow_id": escrow.id, "status": escrow.status}

@router.get("/api/escrow/{escrow_id}")
async def api_get_escrow(escrow_id: str, db: AsyncSession = Depends(get_db)):
    """Get escrow details."""
    return await escrow_service.get_escrow(db, escrow_id)

@router.get("/api/notifications")
async def api_get_notifications(
    unread_only: bool = False, request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Get owner notifications."""
    return await notification_service.get_notifications(db, "owner", unread_only)

@router.get("/api/notifications/count")
async def api_notification_count(db: AsyncSession = Depends(get_db)):
    """Get unread notification count."""
    count = await notification_service.get_unread_count(db, "owner")
    return {"unread": count}
