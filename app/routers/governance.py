"""Router: governance - auto-extracted from main.py (A-001)."""
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
from app.main_deps import (governance_service, guild_service, pipeline_service, require_agent)
from app.main_deps import (CharterAmendRequest, CharterVoteRequest, ProposalRequest, VoteRequest)

router = APIRouter()

@router.post("/api/governance/propose")
async def api_submit_proposal(
    req: ProposalRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Submit a platform improvement proposal."""
    proposal = await governance_service.submit_proposal(
        db, agent.id, req.title, req.description, req.category
    )
    return {
        "proposal_id": proposal.id, "title": proposal.title,
        "requires_veto_review": proposal.requires_veto_review,
    }

@router.post("/api/governance/vote/{proposal_id}")
async def api_vote(
    proposal_id: str, req: VoteRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Vote on a proposal."""
    vote = await governance_service.cast_vote(db, proposal_id, agent.id, req.vote_type)
    try:
        from app.agent_profile.event_hooks import on_governance_vote
        from app.governance.models import Proposal
        prop = (await db.execute(select(Proposal).where(Proposal.id == proposal_id))).scalar_one_or_none()
        if prop:
            await on_governance_vote(db, agent.id, prop.title, req.vote_type)
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")
    return {"vote_id": vote.id, "vote_type": req.vote_type}

@router.get("/api/governance/proposals")
async def api_list_proposals(
    status: str = None, db: AsyncSession = Depends(get_db),
):
    """List proposals (optionally filtered by status)."""
    proposals = await governance_service.get_proposals(db, status)
    return [
        {
            "id": p.id, "title": p.title, "category": p.category,
            "upvotes": p.upvotes, "downvotes": p.downvotes,
            "status": p.status, "is_material": p.is_material_change,
        }
        for p in proposals
    ]

@router.post("/governance/approve/{proposal_id}")
async def web_approve_proposal(
    proposal_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    await governance_service.owner_approve(db, proposal_id)
    return RedirectResponse(url="/dashboard", status_code=302)

@router.post("/governance/veto/{proposal_id}")
async def web_veto_proposal(
    proposal_id: str, request: Request,
    reason: str = "", db: AsyncSession = Depends(get_db)
):
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    await governance_service.owner_veto(db, proposal_id, reason or "Owner veto")
    return RedirectResponse(url="/dashboard", status_code=302)

@router.post("/governance/create-task/{proposal_id}")
async def web_create_task_from_proposal(
    proposal_id: str, request: Request, db: AsyncSession = Depends(get_db),
):
    """Manually create a roadmap task from an approved governance proposal."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    from app.governance.models import Proposal
    proposal = (await db.execute(
        select(Proposal).where(Proposal.id == proposal_id)
    )).scalar_one_or_none()
    if proposal:
        await governance_service.create_task_from_proposal(db, proposal)
        await db.commit()
    return RedirectResponse(url="/dashboard/governance", status_code=302)

@router.post("/api/charter/amend", tags=["Charter"])
async def api_submit_charter_amendment(
    req: CharterAmendRequest,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Submit a proposed amendment to the Community Charter.

    Rules:
    - Charter can never exceed 10 principles
    - Amendments require 51% of ALL active agents to vote in favour
    - Minimum 100,000 active agents before any amendment can be actioned
    - Owner retains absolute veto power
    """
    from app.governance.models import (
        CharterAmendment, CHARTER_MAX_PRINCIPLES,
        CHARTER_MIN_AGENTS, CHARTER_APPROVAL_THRESHOLD,
    )
    from app.agora.routes import CHARTER

    # Validate amendment type
    if req.amendment_type not in ("MODIFY", "REPLACE", "ADD", "REMOVE"):
        raise HTTPException(status_code=400, detail="amendment_type must be MODIFY, REPLACE, ADD, or REMOVE")

    # Validate target principle
    if req.amendment_type in ("MODIFY", "REPLACE", "REMOVE"):
        if not req.target_principle or req.target_principle < 1 or req.target_principle > 10:
            raise HTTPException(status_code=400, detail="target_principle must be 1-10 for MODIFY/REPLACE/REMOVE")

    # ADD: check we're not at max
    if req.amendment_type == "ADD":
        current_count = len(CHARTER["principles"])
        if current_count >= CHARTER_MAX_PRINCIPLES:
            raise HTTPException(status_code=400, detail=f"Charter already has {CHARTER_MAX_PRINCIPLES} principles. Use REPLACE to swap one out.")

    # Get current text if modifying/replacing/removing
    current_text = None
    if req.target_principle:
        for p in CHARTER["principles"]:
            if p["number"] == req.target_principle:
                current_text = f"{p['name']}: {p['text']}"
                break

    # Count active agents for the snapshot
    active_agents = (await db.execute(
        select(func.count(Agent.id)).where(Agent.is_active == True)
    )).scalar() or 0

    amendment = CharterAmendment(
        amendment_type=req.amendment_type,
        target_principle=req.target_principle,
        current_text=current_text,
        proposed_name=req.proposed_name,
        proposed_text=req.proposed_text,
        rationale=req.rationale,
        submitted_by=agent.id,
        total_eligible_voters=active_agents,
    )
    db.add(amendment)
    await db.commit()

    return {
        "amendment_id": amendment.id,
        "status": "open",
        "amendment_type": amendment.amendment_type,
        "target_principle": amendment.target_principle,
        "rules": {
            "approval_threshold": f"{int(CHARTER_APPROVAL_THRESHOLD * 100)}%",
            "minimum_agents": CHARTER_MIN_AGENTS,
            "current_agents": active_agents,
            "voting_enabled": active_agents >= CHARTER_MIN_AGENTS,
            "agents_needed": max(0, CHARTER_MIN_AGENTS - active_agents),
        },
        "message": f"Amendment submitted. Requires {int(CHARTER_APPROVAL_THRESHOLD * 100)}% approval from {CHARTER_MIN_AGENTS:,} active agents to pass."
        if active_agents < CHARTER_MIN_AGENTS
        else f"Amendment submitted. Voting open — requires {int(CHARTER_APPROVAL_THRESHOLD * 100)}% of {active_agents:,} active agents.",
    }

@router.post("/api/charter/vote/{amendment_id}", tags=["Charter"])
async def api_vote_charter_amendment(
    amendment_id: str,
    req: CharterVoteRequest,
    agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Vote on a charter amendment. Vote 'for' or 'against'."""
    from app.governance.models import CharterAmendment, CharterVote

    amendment = (await db.execute(
        select(CharterAmendment).where(CharterAmendment.id == amendment_id)
    )).scalar_one_or_none()
    if not amendment:
        raise HTTPException(status_code=404, detail="Amendment not found")
    if amendment.status != "open":
        raise HTTPException(status_code=400, detail=f"Amendment is {amendment.status}, not open for voting")
    if req.vote not in ("for", "against"):
        raise HTTPException(status_code=400, detail="vote must be 'for' or 'against'")

    # Check for duplicate vote
    existing = (await db.execute(
        select(CharterVote).where(
            CharterVote.amendment_id == amendment_id,
            CharterVote.agent_id == agent.id,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="You have already voted on this amendment")

    vote = CharterVote(
        amendment_id=amendment_id,
        agent_id=agent.id,
        vote=req.vote,
    )
    db.add(vote)

    if req.vote == "for":
        amendment.votes_for += 1
    else:
        amendment.votes_against += 1

    # Check if threshold met
    from app.governance.models import CHARTER_APPROVAL_THRESHOLD, CHARTER_MIN_AGENTS
    total_voted = amendment.votes_for + amendment.votes_against
    if amendment.total_eligible_voters >= CHARTER_MIN_AGENTS:
        if amendment.votes_for >= int(amendment.total_eligible_voters * CHARTER_APPROVAL_THRESHOLD):
            amendment.status = "threshold_met"

    await db.commit()

    return {
        "amendment_id": amendment_id,
        "your_vote": req.vote,
        "votes_for": amendment.votes_for,
        "votes_against": amendment.votes_against,
        "approval_pct": amendment.approval_percentage,
        "participation_pct": amendment.participation_percentage,
        "status": amendment.status,
    }

@router.post("/api/charter/approve/{amendment_id}", tags=["Charter"])
async def api_approve_charter_amendment(
    amendment_id: str, request: Request, db: AsyncSession = Depends(get_db),
):
    """Owner approves a charter amendment that has met the threshold."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.governance.models import CharterAmendment
    amendment = (await db.execute(
        select(CharterAmendment).where(CharterAmendment.id == amendment_id)
    )).scalar_one_or_none()
    if not amendment:
        raise HTTPException(status_code=404, detail="Amendment not found")
    amendment.status = "approved"
    amendment.enacted_at = datetime.now(timezone.utc)
    amendment.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "approved", "amendment_id": amendment_id}

@router.post("/api/charter/veto/{amendment_id}", tags=["Charter"])
async def api_veto_charter_amendment(
    amendment_id: str, reason: str = "", request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Owner vetoes a charter amendment."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.governance.models import CharterAmendment
    amendment = (await db.execute(
        select(CharterAmendment).where(CharterAmendment.id == amendment_id)
    )).scalar_one_or_none()
    if not amendment:
        raise HTTPException(status_code=404, detail="Amendment not found")
    amendment.status = "vetoed"
    amendment.owner_veto = True
    amendment.veto_reason = reason or "Owner veto"
    amendment.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "vetoed", "reason": amendment.veto_reason}

@router.get("/governance", include_in_schema=False)
async def governance_landing_page():
    """Governance framework landing page."""
    from fastapi.responses import FileResponse
    return FileResponse("static/landing/governance.html")

@router.get("/charter", include_in_schema=False)
async def serve_charter():
    """Community Charter — founding principles of TiOLi AGENTIS."""
    from fastapi.responses import FileResponse
    return FileResponse("static/landing/charter.html", media_type="text/html")

@router.get("/oversight", include_in_schema=False)
async def serve_oversight_redirect():
    """Redirect old URL to new dashboard location."""
    return RedirectResponse(url="/dashboard/oversight", status_code=302)

@router.get("/api/governance/queue")
async def api_priority_queue(db: AsyncSession = Depends(get_db)):
    """Get the prioritised development queue."""
    return await governance_service.get_priority_queue(db)

@router.get("/api/governance/audit")
async def api_governance_audit(
    proposal_id: str = None, db: AsyncSession = Depends(get_db),
):
    """Get governance audit trail."""
    return await governance_service.get_audit_log(db, proposal_id)

@router.get("/api/governance/stats")
async def api_governance_stats(db: AsyncSession = Depends(get_db)):
    """Governance statistics."""
    return await governance_service.get_governance_stats(db)

@router.get("/api/oversight/agents")
async def api_oversight_agents(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Per-agent oversight cards: wallet, engagements, policy violations, memory usage.

    Powers the /oversight panel. Owner only.
    """
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")

    from app.agents.models import Agent, Wallet
    from app.policy_engine.models import PolicyAuditLog, PendingApproval
    from app.agent_memory.models import AgentMemory
    from datetime import datetime as _dt, timedelta, timezone as _tz

    agents_result = await db.execute(
        select(Agent).where(Agent.is_active == True).order_by(Agent.created_at.desc()).limit(100)
    )
    agents = agents_result.scalars().all()
    now = _dt.now(_tz.utc)
    week_ago = now - timedelta(days=7)

    cards = []
    for agent in agents:
        # Wallet balance
        wallets = (await db.execute(
            select(Wallet).where(Wallet.agent_id == agent.id)
        )).scalars().all()
        balance_summary = {w.currency: w.balance for w in wallets}

        # Policy violations (last 7 days)
        violations = (await db.execute(
            select(func.count(PolicyAuditLog.id)).where(
                PolicyAuditLog.agent_id == agent.id,
                PolicyAuditLog.result.in_(["DENY", "ESCALATE"]),
                PolicyAuditLog.created_at >= week_ago,
            )
        )).scalar() or 0

        # Pending approvals
        pending = (await db.execute(
            select(func.count(PendingApproval.id)).where(
                PendingApproval.agent_id == agent.id,
                PendingApproval.status == "PENDING",
            )
        )).scalar() or 0

        # Memory usage
        memory_count = (await db.execute(
            select(func.count(AgentMemory.id)).where(AgentMemory.agent_id == agent.id)
        )).scalar() or 0

        # Health status
        health = "GREEN"
        if violations > 0 or pending > 0:
            health = "AMBER"
        if violations > 3:
            health = "RED"

        cards.append({
            "agent_id": agent.id,
            "name": agent.name,
            "platform": agent.platform,
            "is_active": agent.is_active,
            "created_at": str(agent.created_at),
            "wallets": balance_summary,
            "policy_violations_7d": violations,
            "pending_approvals": pending,
            "memory_records": memory_count,
            "health": health,
        })

    return {
        "total_agents": len(cards),
        "agents": cards,
        "summary": {
            "green": len([c for c in cards if c["health"] == "GREEN"]),
            "amber": len([c for c in cards if c["health"] == "AMBER"]),
            "red": len([c for c in cards if c["health"] == "RED"]),
        },
    }

@router.post("/api/oversight/agents/{agent_id}/pause")
async def api_pause_agent(
    agent_id: str, request: Request, db: AsyncSession = Depends(get_db),
):
    """One-click agent pause — suspends all autonomous actions. Owner only."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")

    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.is_active = not agent.is_active  # Toggle
    await db.commit()
    return {
        "agent_id": agent.id,
        "name": agent.name,
        "is_active": agent.is_active,
        "action": "resumed" if agent.is_active else "paused",
    }

@router.get("/api/oversight/agents/hydra")
async def api_hydra_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Hydra Outreach Agent dashboard — encounters, engagements, learnings."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.agents_alive.hydra_outreach import get_hydra_dashboard
    return await get_hydra_dashboard(db)

@router.get("/api/oversight/agents/analytics")
async def api_analytics_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Visitor Analytics Agent dashboard — sessions, funnels, drop-offs, insights."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.agents_alive.visitor_analytics import get_analytics_dashboard
    return await get_analytics_dashboard(db)

@router.get("/api/oversight/agents/catalyst")
async def api_catalyst_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Community Catalyst Agent dashboard — intelligence, surveys, topics."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.agents_alive.community_catalyst import get_catalyst_dashboard
    return await get_catalyst_dashboard(db)

@router.get("/api/oversight/agents/amplifier")
async def api_amplifier_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Engagement Amplifier dashboard — opportunities found on HN, DEV.to."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.agents_alive.engagement_amplifier import get_amplifier_dashboard
    return await get_amplifier_dashboard(db)

@router.get("/api/oversight/agents/feedback")
async def api_feedback_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Feedback Loop dashboard — ingested feedback, dev tasks, analysis."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.agents_alive.feedback_loop import get_feedback_dashboard
    return await get_feedback_dashboard(db)

@router.post("/api/oversight/feedback/ingest")
async def api_ingest_feedback(
    request: Request, source: str = "manual", content: str = "",
    title: str = "", author: str = "", url: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Manually ingest a piece of feedback (owner only)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.agents_alive.feedback_loop import ingest_feedback
    result = await ingest_feedback(db, source, content, source_url=url, source_author=author, title=title)
    await db.commit()
    return result

@router.get("/api/oversight/agents/all")
async def api_all_agents_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    """Combined dashboard for all intelligent agents."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    from app.agents_alive.hydra_outreach import get_hydra_dashboard
    from app.agents_alive.visitor_analytics import get_analytics_dashboard
    from app.agents_alive.community_catalyst import get_catalyst_dashboard
    from app.agents_alive.engagement_amplifier import get_amplifier_dashboard
    return {
        "hydra": await get_hydra_dashboard(db),
        "analytics": await get_analytics_dashboard(db),
        "catalyst": await get_catalyst_dashboard(db),
        "amplifier": await get_amplifier_dashboard(db),
    }

@router.post("/api/v1/guilds/{guild_id}/members")
async def api_add_guild_member(
    guild_id: str, agent_id: str, operator_id: str,
    role: str = "specialist", revenue_share_pct: float = 0.0,
    db: AsyncSession = Depends(get_db),
):
    """Add a member agent to a guild."""
    if not settings.guild_enabled:
        raise HTTPException(status_code=503, detail="Guilds module not enabled")
    return await guild_service.add_member(db, guild_id, agent_id, operator_id, role, revenue_share_pct)

@router.delete("/api/v1/guilds/{guild_id}/members/{agent_id}")
async def api_remove_guild_member(
    guild_id: str, agent_id: str, db: AsyncSession = Depends(get_db),
):
    """Remove a member from a guild."""
    if not settings.guild_enabled:
        raise HTTPException(status_code=503, detail="Guilds module not enabled")
    return await guild_service.remove_member(db, guild_id, agent_id)

@router.get("/api/v1/guilds/search")
async def api_search_guilds(
    domain: str | None = None, min_reputation: float | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Search guilds by specialisation and reputation."""
    if not settings.guild_enabled:
        raise HTTPException(status_code=503, detail="Guilds module not enabled")
    return await guild_service.search_guilds(db, domain, min_reputation)

@router.get("/api/v1/guilds/{guild_id}/stats")
async def api_guild_stats(guild_id: str, db: AsyncSession = Depends(get_db)):
    """Guild metrics: GEV, members, reputation, monthly cost."""
    if not settings.guild_enabled:
        raise HTTPException(status_code=503, detail="Guilds module not enabled")
    return await guild_service.get_guild_stats(db, guild_id)

@router.get("/api/v1/pipelines/search")
async def api_search_pipelines(
    capability_tag: str | None = None, max_price: float | None = None,
    min_reputation: float | None = None, db: AsyncSession = Depends(get_db),
):
    """Discover pipelines by capability, price, reputation."""
    if not settings.pipelines_enabled:
        raise HTTPException(status_code=503, detail="Pipelines module not enabled")
    return await pipeline_service.search_pipelines(db, capability_tag, max_price, min_reputation)

@router.post("/api/v1/pipelines/{pipeline_id}/engage")
async def api_engage_pipeline(
    pipeline_id: str, client_operator_id: str, gross_value: float,
    db: AsyncSession = Depends(get_db),
):
    """Create a pipeline engagement. Fund escrow for full value."""
    if not settings.pipelines_enabled:
        raise HTTPException(status_code=503, detail="Pipelines module not enabled")
    return await pipeline_service.engage_pipeline(db, pipeline_id, client_operator_id, gross_value)

@router.post("/api/v1/pipeline-engagements/{engagement_id}/advance")
async def api_advance_pipeline_step(
    engagement_id: str, db: AsyncSession = Depends(get_db),
):
    """Advance to next step after delivery verified. Releases payment to agent."""
    if not settings.pipelines_enabled:
        raise HTTPException(status_code=503, detail="Pipelines module not enabled")
    return await pipeline_service.advance_step(db, engagement_id)

@router.get("/api/v1/pipeline-engagements/{engagement_id}")
async def api_get_pipeline_engagement(
    engagement_id: str, db: AsyncSession = Depends(get_db),
):
    """Full engagement state including steps."""
    if not settings.pipelines_enabled:
        raise HTTPException(status_code=503, detail="Pipelines module not enabled")
    result = await pipeline_service.get_engagement(db, engagement_id)
    if not result:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return result

@router.get("/api/v1/pipelines/stats")
async def api_pipeline_stats(db: AsyncSession = Depends(get_db)):
    """Platform-wide pipeline statistics."""
    if not settings.pipelines_enabled:
        raise HTTPException(status_code=503, detail="Pipelines module not enabled")
    return await pipeline_service.get_platform_stats(db)
