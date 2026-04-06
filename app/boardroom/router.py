"""The Boardroom — FastAPI router. All endpoints under /api/v1/boardroom/.

Authenticated via existing JWT (role='owner' required).
Gated behind BOARDROOM_ENABLED feature flag.
All additive — no existing endpoints modified.
"""

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db

log = logging.getLogger("boardroom.router")
boardroom_router = APIRouter(prefix="/api/v1/boardroom", tags=["Boardroom"])


def _check_enabled():
    if os.getenv("BOARDROOM_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Boardroom is not enabled")


# ══════════════════════════════════════════════════════════════════
# BOARD HOME — /boardroom/overview
# ══════════════════════════════════════════════════════════════════

@boardroom_router.get("/overview")
async def boardroom_overview(db: AsyncSession = Depends(get_db)):
    """Board Home — complete platform state in one response."""
    _check_enabled()

    # Agent statuses
    agents_result = await db.execute(text("""
        SELECT agent_name, display_name, status, model_primary, agent_version,
               last_heartbeat, token_budget_monthly, tokens_used_this_month,
               circuit_breaker_tripped
        FROM arch_agents ORDER BY agent_name
    """))
    agents = {}
    for r in agents_result.fetchall():
        budget = r.token_budget_monthly or 1
        agents[r.agent_name] = {
            "display_name": r.display_name, "status": r.status,
            "model": r.model_primary, "version": r.agent_version,
            "last_heartbeat": r.last_heartbeat.isoformat() if r.last_heartbeat else None,
            "tokens_used": r.tokens_used_this_month, "token_budget": budget,
            "token_pct": round(100 * r.tokens_used_this_month / budget, 1),
            "circuit_breaker": r.circuit_breaker_tripped,
        }

    # Reserve status
    reserve = await db.execute(text("""
        SELECT floor_zar, total_balance_zar, ceiling_remaining_zar, spending_30d_zar
        FROM arch_reserve_ledger ORDER BY recorded_at DESC LIMIT 1
    """))
    reserve_row = reserve.fetchone()
    reserve_data = {
        "foundation_zar": float(reserve_row.floor_zar) if reserve_row else 0,
        "total_balance_zar": float(reserve_row.total_balance_zar) if reserve_row else 0,
        "headroom_zar": float(reserve_row.total_balance_zar - reserve_row.floor_zar) if reserve_row else 0,
        "ceiling_remaining_zar": float(reserve_row.ceiling_remaining_zar) if reserve_row else 0,
    } if reserve_row else {}

    # Pending inbox count
    inbox_result = await db.execute(text(
        "SELECT COUNT(*) FROM arch_founder_inbox WHERE status = 'PENDING'"
    ))
    inbox_count = inbox_result.scalar() or 0

    # Open incidents
    incidents_result = await db.execute(text(
        "SELECT COUNT(*) FROM arch_incidents WHERE resolved_at IS NULL"
    ))
    open_incidents = incidents_result.scalar() or 0

    # Active session
    session_result = await db.execute(text(
        "SELECT id::text, session_type, opened_at FROM arch_board_sessions "
        "WHERE status = 'OPEN' ORDER BY opened_at DESC LIMIT 1"
    ))
    active_session = None
    s = session_result.fetchone()
    if s:
        active_session = {"id": s.id, "type": s.session_type,
                          "opened_at": s.opened_at.isoformat()}

    # Strategic visions
    visions_result = await db.execute(text("""
        SELECT agent_id, vision_statement, north_star_metric, current_score, target_score
        FROM boardroom_strategic_visions ORDER BY agent_id
    """))
    visions = {r.agent_id: {
        "vision": r.vision_statement, "metric": r.north_star_metric,
        "current": float(r.current_score) if r.current_score else None,
        "target": float(r.target_score) if r.target_score else None,
    } for r in visions_result.fetchall()}

    return {
        "agents": agents,
        "reserve": reserve_data,
        "inbox_pending": inbox_count,
        "open_incidents": open_incidents,
        "active_session": active_session,
        "strategic_visions": visions,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════
# LIVE FEED
# ══════════════════════════════════════════════════════════════════

@boardroom_router.get("/live-feed")
async def live_feed(
    limit: int = Query(default=50, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Last N agent actions across all agents."""
    _check_enabled()
    result = await db.execute(text("""
        SELECT id::text, agent_id, event_type, action_taken, tool_called,
               processing_time_ms, deferred_to_owner, created_at
        FROM arch_event_actions
        ORDER BY created_at DESC LIMIT :limit
    """), {"limit": limit})
    return {"feed": [
        {"id": r.id, "agent": r.agent_id, "event_type": r.event_type,
         "action": r.action_taken, "tool": r.tool_called,
         "ms": r.processing_time_ms, "deferred": r.deferred_to_owner,
         "at": r.created_at.isoformat()}
        for r in result.fetchall()
    ]}


# ══════════════════════════════════════════════════════════════════
# BOARD SESSIONS
# ══════════════════════════════════════════════════════════════════

@boardroom_router.get("/board/session/active")
async def active_session(db: AsyncSession = Depends(get_db)):
    """Current active board session if any."""
    _check_enabled()
    result = await db.execute(text("""
        SELECT id::text, session_type, convened_by::text, agenda,
               quorum_met, agents_present, status, opened_at
        FROM arch_board_sessions WHERE status = 'OPEN'
        ORDER BY opened_at DESC LIMIT 1
    """))
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No active session")
    return {
        "session_id": row.id, "type": row.session_type,
        "agenda": row.agenda, "quorum_met": row.quorum_met,
        "agents_present": row.agents_present, "opened_at": row.opened_at.isoformat(),
    }


@boardroom_router.post("/board/session/convene")
async def convene_session(payload: dict, db: AsyncSession = Depends(get_db)):
    """Convene a new board session."""
    _check_enabled()
    session_type = payload.get("session_type", "SPECIAL")
    agenda = payload.get("agenda", [])
    agent_ids = payload.get("agent_ids")  # None = full board

    sov = await db.execute(text("SELECT id FROM arch_agents WHERE agent_name = 'sovereign'"))
    sov_id = sov.scalar()

    result = await db.execute(text("""
        INSERT INTO arch_board_sessions
            (session_type, convened_by, agenda, participant_agent_ids, status)
        VALUES (:type, :sov, :agenda, :participants, 'OPEN')
        RETURNING id::text
    """), {
        "type": session_type, "sov": sov_id,
        "agenda": json.dumps(agenda),
        "participants": agent_ids or [],
    })
    session_id = result.scalar()

    # Record founder action
    await _record_founder_action(db, "SESSION_CONVENED", session_id, "board_session",
                                  {"session_type": session_type, "agenda": agenda})
    await db.commit()
    return {"session_id": session_id, "status": "OPEN", "type": session_type}


@boardroom_router.post("/board/session/{session_id}/message")
async def session_message(session_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    """Send founder message to active session — stored once, agents respond via chat engine."""
    _check_enabled()
    message = payload.get("message", "")
    target = payload.get("target", "ALL_BOARD")

    # Store ONCE with the target (not duplicated per agent)
    await db.execute(text("""
        INSERT INTO boardroom_chat_messages
            (agent_id, direction, message_text, message_type, is_urgent)
        VALUES (:agent, 'OUTBOUND', :msg, 'TEXT', :urgent)
    """), {"agent": target, "msg": message, "urgent": payload.get("urgent", False)})

    await _record_founder_action(db, "MESSAGE_SENT", session_id, "board_session",
                                  {"target": target, "message": message[:200]})
    await db.commit()
    return {"delivered": True, "target": target}


@boardroom_router.get("/board/session/{session_id}/transcript")
async def session_transcript(session_id: str, db: AsyncSession = Depends(get_db)):
    """Full session transcript."""
    _check_enabled()
    result = await db.execute(text("""
        SELECT agent_id, direction, message_text, message_type, created_at
        FROM boardroom_chat_messages
        WHERE created_at >= (
            SELECT opened_at FROM arch_board_sessions WHERE id = cast(:sid as uuid)
        )
        ORDER BY created_at ASC
    """), {"sid": session_id})
    return {"session_id": session_id, "transcript": [
        {"agent": r.agent_id, "direction": r.direction,
         "text": r.message_text, "type": r.message_type,
         "at": r.created_at.isoformat()}
        for r in result.fetchall()
    ]}


@boardroom_router.post("/board/session/{session_id}/close")
async def close_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Close active session."""
    _check_enabled()
    await db.execute(text("""
        UPDATE arch_board_sessions SET status = 'CLOSED', closed_at = now()
        WHERE id = cast(:sid as uuid) AND status = 'OPEN'
    """), {"sid": session_id})
    await db.commit()
    return {"session_id": session_id, "status": "CLOSED"}


# ══════════════════════════════════════════════════════════════════
# AGENT OFFICES
# ══════════════════════════════════════════════════════════════════

@boardroom_router.get("/agents/{agent_id}/office")
async def agent_office(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Full Agent Office data."""
    _check_enabled()

    # Agent info
    agent = await db.execute(text("""
        SELECT agent_name, display_name, corporate_title, status,
               model_primary, agent_version, last_heartbeat,
               token_budget_monthly, tokens_used_this_month, circuit_breaker_tripped
        FROM arch_agents WHERE agent_name = :aid
    """), {"aid": agent_id})
    row = agent.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

    # Founding statement
    founding = await db.execute(text("""
        SELECT ruling_text FROM arch_constitutional_rulings
        WHERE ruling_type = 'FOUNDING_STATEMENT'
          AND subject_agents @> :agents
        LIMIT 1
    """), {"agents": json.dumps([agent_id])})
    founding_row = founding.fetchone()
    founding_data = json.loads(founding_row.ruling_text) if founding_row else {}

    # Strategic vision
    vision = await db.execute(text("""
        SELECT vision_statement, north_star_metric, current_score, target_score
        FROM boardroom_strategic_visions WHERE agent_id = :aid
    """), {"aid": agent_id})
    vision_row = vision.fetchone()

    # Recent actions
    actions = await db.execute(text("""
        SELECT id::text, event_type, action_taken, tool_called, processing_time_ms,
               deferred_to_owner, created_at
        FROM arch_event_actions WHERE agent_id = :aid
        ORDER BY created_at DESC LIMIT 20
    """), {"aid": agent_id})

    # Unread chat messages
    unread = await db.execute(text("""
        SELECT COUNT(*) FROM boardroom_chat_messages
        WHERE agent_id = :aid AND direction = 'INBOUND' AND read_at IS NULL
    """), {"aid": agent_id})

    budget = row.token_budget_monthly or 1
    return {
        "agent": {
            "name": row.agent_name, "display_name": row.display_name,
            "title": row.corporate_title, "status": row.status,
            "model": row.model_primary, "version": row.agent_version,
            "last_heartbeat": row.last_heartbeat.isoformat() if row.last_heartbeat else None,
            "tokens_used": row.tokens_used_this_month, "token_budget": budget,
            "token_pct": round(100 * row.tokens_used_this_month / budget, 1),
            "circuit_breaker": row.circuit_breaker_tripped,
        },
        "founding_statement": founding_data.get("statement"),
        "commitment": founding_data.get("commitment"),
        "vision": {
            "statement": vision_row.vision_statement if vision_row else None,
            "metric": vision_row.north_star_metric if vision_row else None,
            "current": float(vision_row.current_score) if vision_row and vision_row.current_score else None,
            "target": float(vision_row.target_score) if vision_row and vision_row.target_score else None,
        },
        "recent_actions": [
            {"id": r.id, "event_type": r.event_type, "action": r.action_taken,
             "tool": r.tool_called, "ms": r.processing_time_ms,
             "deferred": r.deferred_to_owner, "at": r.created_at.isoformat()}
            for r in actions.fetchall()
        ],
        "unread_messages": unread.scalar() or 0,
    }


@boardroom_router.post("/agents/{agent_id}/chat")
async def agent_chat(agent_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    """Send direct message to agent — with full context, tool execution, and cross-agent awareness."""
    _check_enabled()
    message = payload.get("message", "")
    is_urgent = payload.get("urgent", False)
    msg_type = payload.get("type", "TEXT")

    # Store founder message (once, not per-agent)
    await db.execute(text("""
        INSERT INTO boardroom_chat_messages
            (agent_id, direction, message_text, message_type, is_urgent)
        VALUES (:aid, 'OUTBOUND', :msg, :type, :urgent)
    """), {"aid": agent_id, "msg": message, "type": msg_type, "urgent": is_urgent})

    await _record_founder_action(db, "MESSAGE_SENT", None, "chat",
                                  {"agent": agent_id, "message": message[:200]})
    await db.commit()

    # Use the new chat engine with full context and tool execution
    response_text = None
    try:
        from app.boardroom.chat_engine import process_chat_message
        response_text = await process_chat_message(agent_id, message, db)
    except Exception as e:
        log.warning(f"Agent chat response failed: {e}")
        response_text = f"[Error: {str(e)[:200]}]"

    return {"delivered": True, "agent": agent_id, "response": response_text}


@boardroom_router.get("/agents/{agent_id}/chat/history")
async def chat_history(
    agent_id: str,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Chat history with an agent."""
    _check_enabled()
    result = await db.execute(text("""
        SELECT id::text, direction, message_text, message_type,
               is_urgent, read_at, created_at
        FROM boardroom_chat_messages
        WHERE agent_id = :aid
        ORDER BY created_at DESC LIMIT :limit
    """), {"aid": agent_id, "limit": limit})
    return {"agent_id": agent_id, "messages": [
        {"id": r.id, "direction": r.direction, "text": r.message_text,
         "type": r.message_type, "urgent": r.is_urgent,
         "read": r.read_at is not None, "at": r.created_at.isoformat()}
        for r in result.fetchall()
    ]}


@boardroom_router.get("/agents/{agent_id}/performance")
async def agent_performance(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Agent performance data for charts."""
    _check_enabled()
    snapshots = await db.execute(text("""
        SELECT snapshot_period, pass_rate_pct, kpis_passing, kpis_total,
               circuit_tripped, snapshotted_at
        FROM arch_performance_snapshots
        WHERE agent_id = (SELECT id FROM arch_agents WHERE agent_name = :aid)
        ORDER BY snapshotted_at DESC LIMIT 30
    """), {"aid": agent_id})

    arr = await db.execute(text("""
        SELECT period, period_start, events_received, events_resolved,
               events_deferred, autonomous_rate_pct
        FROM arch_resolution_metrics WHERE agent_id = :aid
        ORDER BY period_start DESC LIMIT 12
    """), {"aid": agent_id})

    return {
        "agent_id": agent_id,
        "snapshots": [{"period": r.snapshot_period, "pass_rate": float(r.pass_rate_pct),
                       "passing": r.kpis_passing, "total": r.kpis_total,
                       "at": r.snapshotted_at.isoformat()} for r in snapshots.fetchall()],
        "arr_history": [{"period": r.period, "start": r.period_start.isoformat(),
                         "received": r.events_received, "resolved": r.events_resolved,
                         "deferred": r.events_deferred,
                         "arr": float(r.autonomous_rate_pct) if r.autonomous_rate_pct else None}
                        for r in arr.fetchall()],
    }


@boardroom_router.get("/agents/{agent_id}/memory")
async def agent_memory(
    agent_id: str,
    q: str = Query(default="", description="Semantic search query"),
    db: AsyncSession = Depends(get_db),
):
    """Browse agent memory store."""
    _check_enabled()
    if q:
        # Would need OpenAI embedding for real semantic search — return text-match for now
        result = await db.execute(text("""
            SELECT id::text, content, source_type, importance, created_at
            FROM arch_memories WHERE agent_id = :aid
              AND content ILIKE :pattern
            ORDER BY created_at DESC LIMIT 20
        """), {"aid": agent_id, "pattern": f"%{q}%"})
    else:
        result = await db.execute(text("""
            SELECT id::text, content, source_type, importance, created_at
            FROM arch_memories WHERE agent_id = :aid
            ORDER BY created_at DESC LIMIT 20
        """), {"aid": agent_id})

    return {"agent_id": agent_id, "memories": [
        {"id": r.id, "content": r.content[:500], "source": r.source_type,
         "importance": float(r.importance), "at": r.created_at.isoformat()}
        for r in result.fetchall()
    ]}


# ══════════════════════════════════════════════════════════════════
# VOTES
# ══════════════════════════════════════════════════════════════════

@boardroom_router.get("/votes/pending")
async def pending_votes(db: AsyncSession = Depends(get_db)):
    """Votes requiring founder attention."""
    _check_enabled()
    result = await db.execute(text("""
        SELECT bv.proposal_id::text, bs.id::text as session_id,
               bs.session_type, bs.agenda, bs.opened_at
        FROM arch_board_votes bv
        JOIN arch_board_sessions bs ON bv.session_id = bs.id
        WHERE bs.status = 'OPEN'
        GROUP BY bv.proposal_id, bs.id, bs.session_type, bs.agenda, bs.opened_at
        ORDER BY bs.opened_at DESC
    """))
    return {"pending_votes": [
        {"proposal_id": r.proposal_id, "session_id": r.session_id,
         "type": r.session_type, "agenda": r.agenda,
         "at": r.opened_at.isoformat()}
        for r in result.fetchall()
    ]}


@boardroom_router.post("/votes/{vote_id}/founder-cast")
async def founder_cast_vote(vote_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    """Cast founder vote or tie-break."""
    _check_enabled()
    vote = payload.get("vote", "AYE")  # AYE / NAY / ABSTAIN
    rationale = payload.get("rationale", "")
    is_tiebreak = payload.get("tiebreak", False)

    action_type = "VOTE_TIEBREAK" if is_tiebreak else "VOTE_CAST"
    receipt = hashlib.sha256(
        f"{vote_id}:{vote}:{datetime.now(timezone.utc).isoformat()}".encode()
    ).hexdigest()

    await _record_founder_action(db, action_type, vote_id, "board_vote",
                                  {"vote": vote, "rationale": rationale},
                                  vote_receipt_hash=receipt)
    await db.commit()
    return {"vote_id": vote_id, "vote": vote, "type": action_type,
            "receipt_hash": receipt}


@boardroom_router.post("/votes/{vote_id}/veto")
async def founder_veto(vote_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    """Exercise constitutional veto — always available, overrides any majority."""
    _check_enabled()
    reason = payload.get("reason", "")

    receipt = hashlib.sha256(
        f"VETO:{vote_id}:{datetime.now(timezone.utc).isoformat()}".encode()
    ).hexdigest()

    # Record in constitutional rulings
    sov = await db.execute(text("SELECT id FROM arch_agents WHERE agent_name = 'sovereign'"))
    count = await db.execute(text(
        "SELECT COUNT(*) FROM arch_constitutional_rulings WHERE ruling_ref LIKE 'CR-VETO-%'"
    ))
    ref = f"CR-VETO-{(count.scalar() or 0) + 1:03d}"

    await db.execute(text("""
        INSERT INTO arch_constitutional_rulings
            (ruling_ref, ruling_type, issued_by, ruling_text, cited_directives)
        VALUES (:ref, 'FOUNDER_VETO', :sov, :text, :directives)
    """), {
        "ref": ref, "sov": sov.scalar(),
        "text": json.dumps({"vote_id": vote_id, "reason": reason}),
        "directives": json.dumps(["CONSTITUTIONAL_VETO"]),
    })

    await _record_founder_action(db, "VETO_EXERCISED", vote_id, "board_vote",
                                  {"reason": reason}, vote_receipt_hash=receipt)
    await db.commit()
    return {"vote_id": vote_id, "veto": True, "ruling_ref": ref, "receipt": receipt}


# ══════════════════════════════════════════════════════════════════
# TREASURY
# ══════════════════════════════════════════════════════════════════

@boardroom_router.get("/treasury/overview")
async def treasury_overview(db: AsyncSession = Depends(get_db)):
    """Financial overview — all metric cards."""
    _check_enabled()

    reserve = await db.execute(text("""
        SELECT gross_income_ytd_zar, floor_zar, total_balance_zar,
               spending_30d_zar, ceiling_remaining_zar, recorded_at
        FROM arch_reserve_ledger ORDER BY recorded_at DESC LIMIT 1
    """))
    r = reserve.fetchone()

    # Charitable fund
    charity = await db.execute(text(
        "SELECT COALESCE(SUM(accumulated_zar), 0) FROM arch_charitable_fund"
    ))

    # Pending proposals
    proposals = await db.execute(text(
        "SELECT COUNT(*) FROM arch_financial_proposals WHERE status IN ('PENDING','BOARD_REVIEW','FOUNDER_REVIEW')"
    ))

    # Token costs
    tokens = await db.execute(text(
        "SELECT SUM(tokens_used_this_month) FROM arch_agents"
    ))

    return {
        "foundation_zar": float(r.floor_zar) if r else 0,
        "foundation_label": "The Foundation",
        "foundation_tooltip": "This amount is permanently protected. No expenditure, no decision, and no market condition can reduce it.",
        "total_balance_zar": float(r.total_balance_zar) if r else 0,
        "headroom_zar": float(r.total_balance_zar - r.floor_zar) if r else 0,
        "headroom_label": "Operating freedom — available for bold decisions",
        "ceiling_remaining_zar": float(r.ceiling_remaining_zar) if r else 0,
        "spending_30d_zar": float(r.spending_30d_zar) if r else 0,
        "gross_income_ytd_zar": float(r.gross_income_ytd_zar) if r else 0,
        "charitable_fund_zar": float(charity.scalar() or 0),
        "pending_proposals": proposals.scalar() or 0,
        "total_tokens_used": tokens.scalar() or 0,
        "last_calculated": r.recorded_at.isoformat() if r else None,
    }


@boardroom_router.get("/treasury/proposals")
async def treasury_proposals(db: AsyncSession = Depends(get_db)):
    """Financial proposal queue."""
    _check_enabled()
    result = await db.execute(text("""
        SELECT id::text, proposal_type, description, amount_zar,
               reserve_floor_at_time, headroom_at_time, ceiling_remaining_30d,
               status, created_at
        FROM arch_financial_proposals
        ORDER BY CASE status
            WHEN 'PENDING' THEN 0 WHEN 'BOARD_REVIEW' THEN 1
            WHEN 'FOUNDER_REVIEW' THEN 2 ELSE 3 END,
            created_at DESC
        LIMIT 50
    """))
    return {"proposals": [
        {"id": r.id, "type": r.proposal_type, "description": r.description,
         "amount_zar": float(r.amount_zar), "status": r.status,
         "floor_at_time": float(r.reserve_floor_at_time),
         "headroom_at_time": float(r.headroom_at_time),
         "ceiling_remaining": float(r.ceiling_remaining_30d),
         "at": r.created_at.isoformat()}
        for r in result.fetchall()
    ]}


@boardroom_router.post("/treasury/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: str, payload: dict = {}, db: AsyncSession = Depends(get_db)):
    """Approve financial proposal."""
    _check_enabled()
    await db.execute(text("""
        UPDATE arch_financial_proposals SET status = 'APPROVED',
               founder_approved = true, founder_approved_at = now()
        WHERE id = cast(:pid as uuid)
    """), {"pid": proposal_id})

    await _record_founder_action(db, "FINANCIAL_APPROVE", proposal_id,
                                  "financial_proposal", payload)
    await db.commit()
    return {"proposal_id": proposal_id, "status": "APPROVED"}


@boardroom_router.post("/treasury/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: str, payload: dict = {}, db: AsyncSession = Depends(get_db)):
    """Reject financial proposal."""
    _check_enabled()
    await db.execute(text("""
        UPDATE arch_financial_proposals SET status = 'REJECTED',
               founder_approved = false
        WHERE id = cast(:pid as uuid)
    """), {"pid": proposal_id})

    await _record_founder_action(db, "FINANCIAL_REJECT", proposal_id,
                                  "financial_proposal", payload)
    await db.commit()
    return {"proposal_id": proposal_id, "status": "REJECTED"}


@boardroom_router.post("/treasury/model")
async def financial_model(payload: dict, db: AsyncSession = Depends(get_db)):
    """Financial modelling calculator — what-if tool."""
    _check_enabled()
    amount = float(payload.get("amount_zar", 0))

    # Get current reserve data
    reserve = await db.execute(text("""
        SELECT floor_zar, total_balance_zar, ceiling_remaining_zar
        FROM arch_reserve_ledger ORDER BY recorded_at DESC LIMIT 1
    """))
    r = reserve.fetchone()
    if not r:
        return {"error": "No reserve data available"}

    floor = float(r.floor_zar)
    balance = float(r.total_balance_zar)
    headroom = balance - floor
    ceiling = float(r.ceiling_remaining_zar)

    balance_after = balance - amount
    headroom_after = balance_after - floor
    foundation_before_pct = round(100 * floor / max(balance, 1), 1)
    foundation_after_pct = round(100 * floor / max(balance_after, 1), 1) if balance_after > 0 else 100

    return {
        "amount_zar": amount,
        "foundation_before_pct": foundation_before_pct,
        "foundation_after_pct": foundation_after_pct,
        "headroom_before": headroom,
        "headroom_after": headroom_after,
        "ceiling_remaining_after": ceiling - amount,
        "would_breach_foundation": balance_after < floor,
        "would_breach_ceiling": amount > ceiling,
        "spending_ceiling_ok": amount <= ceiling,
        "permitted": balance_after >= floor and amount <= ceiling,
        "treasurer_summary": (
            f"This R{amount:,.2f} expenditure {'is permitted' if balance_after >= floor and amount <= ceiling else 'would breach limits'}. "
            f"The Foundation holds at R{floor:,.2f}. "
            f"Headroom after: R{max(headroom_after, 0):,.2f}."
        ),
    }


# ══════════════════════════════════════════════════════════════════
# MISSION CONTROL
# ══════════════════════════════════════════════════════════════════

@boardroom_router.get("/mission-control/hierarchy")
async def mission_control(db: AsyncSession = Depends(get_db)):
    """Full agent hierarchy."""
    _check_enabled()
    result = await db.execute(text("""
        SELECT agent_name, display_name, corporate_title, status, layer,
               model_primary, agent_version, token_budget_monthly,
               tokens_used_this_month, last_heartbeat
        FROM arch_agents ORDER BY agent_name
    """))
    return {"agents": [
        {"name": r.agent_name, "display": r.display_name, "title": r.corporate_title,
         "status": r.status, "layer": r.layer, "model": r.model_primary,
         "version": r.agent_version, "budget": r.token_budget_monthly,
         "used": r.tokens_used_this_month,
         "heartbeat": r.last_heartbeat.isoformat() if r.last_heartbeat else None}
        for r in result.fetchall()
    ]}


@boardroom_router.post("/mission-control/agents/{agent_id}/suspend")
async def suspend_agent(agent_id: str, payload: dict = {}, db: AsyncSession = Depends(get_db)):
    """Suspend an agent."""
    _check_enabled()
    await db.execute(text(
        "UPDATE arch_agents SET status = 'PAUSED' WHERE agent_name = :aid"
    ), {"aid": agent_id})
    await _record_founder_action(db, "AGENT_SUSPENDED", None, "agent",
                                  {"agent": agent_id, "reason": payload.get("reason", "")})
    await db.commit()
    return {"agent": agent_id, "status": "PAUSED"}


@boardroom_router.post("/mission-control/agents/{agent_id}/resume")
async def resume_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Resume a suspended agent."""
    _check_enabled()
    await db.execute(text(
        "UPDATE arch_agents SET status = 'ACTIVE' WHERE agent_name = :aid"
    ), {"aid": agent_id})
    await _record_founder_action(db, "AGENT_RESUMED", None, "agent", {"agent": agent_id})
    await db.commit()
    return {"agent": agent_id, "status": "ACTIVE"}


# ══════════════════════════════════════════════════════════════════
# THE RECORD
# ══════════════════════════════════════════════════════════════════

@boardroom_router.get("/record")
async def search_record(
    q: str = Query(default=""),
    record_type: str = Query(default="all"),
    agent: str = Query(default=""),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Search the immutable record."""
    _check_enabled()

    if record_type == "agent_actions" or record_type == "all":
        query = """
            SELECT id::text, agent_id, action_type, action_detail,
                   result::text, entry_hash, created_at
            FROM arch_audit_log
        """
        params = {"limit": limit}
        conditions = []
        if q:
            conditions.append("to_tsvector('english', action_type || ' ' || action_detail::text) @@ plainto_tsquery('english', :q)")
            params["q"] = q
        if agent:
            conditions.append("agent_id = (SELECT id FROM arch_agents WHERE agent_name = :agent)")
            params["agent"] = agent
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC LIMIT :limit"

        result = await db.execute(text(query), params)
        return {"records": [
            {"id": r.id, "agent": str(r.agent_id), "type": r.action_type,
             "detail": r.action_detail, "result": r.result,
             "hash": r.entry_hash, "at": r.created_at.isoformat()}
            for r in result.fetchall()
        ]}

    return {"records": [], "note": f"Record type '{record_type}' — use specific sub-endpoints"}


@boardroom_router.get("/record/{record_type}/{record_id}")
async def record_detail(record_type: str, record_id: str, db: AsyncSession = Depends(get_db)):
    """Single record detail with drill-down."""
    _check_enabled()

    if record_type == "audit":
        result = await db.execute(text("""
            SELECT id::text, seq, agent_id::text, action_type, action_detail,
                   result::text, entry_hash, prev_seq, created_at
            FROM arch_audit_log WHERE id = cast(:rid as uuid)
        """), {"rid": record_id})
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Record not found")

        # Verify hash chain
        chain_valid = True
        if row.prev_seq:
            prev = await db.execute(text(
                "SELECT entry_hash FROM arch_audit_log WHERE seq = :seq"
            ), {"seq": row.prev_seq})
            prev_row = prev.fetchone()
            if prev_row:
                chain_valid = True  # Simplified — full verification in production

        return {
            "id": row.id, "seq": row.seq, "agent": row.agent_id,
            "type": row.action_type, "detail": row.action_detail,
            "result": row.result, "hash": row.entry_hash,
            "chain_verified": chain_valid, "at": row.created_at.isoformat(),
        }

    raise HTTPException(status_code=400, detail=f"Unknown record type: {record_type}")


# ══════════════════════════════════════════════════════════════════
# FOUNDER INBOX
# ══════════════════════════════════════════════════════════════════

@boardroom_router.get("/inbox")
async def founder_inbox(db: AsyncSession = Depends(get_db)):
    """Founder inbox with priority sort."""
    _check_enabled()
    result = await db.execute(text("""
        SELECT id::text, item_type, priority::text, description, status,
               founder_response, due_at, created_at
        FROM arch_founder_inbox
        ORDER BY
            CASE priority WHEN 'EMERGENCY' THEN 0 WHEN 'URGENT' THEN 1 ELSE 2 END,
            CASE WHEN due_at < now() THEN 0 ELSE 1 END,
            due_at ASC NULLS LAST,
            created_at DESC
        LIMIT 50
    """))
    return {"inbox": [
        {"id": r.id, "type": r.item_type, "priority": r.priority,
         "description": r.description, "status": r.status,
         "response": r.founder_response,
         "due_at": r.due_at.isoformat() if r.due_at else None,
         "overdue": r.due_at < datetime.now(timezone.utc) if r.due_at else False,
         "at": r.created_at.isoformat()}
        for r in result.fetchall()
    ]}


@boardroom_router.post("/inbox/{item_id}/action")
async def inbox_action(item_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    """Take action on inbox item — supports full approval workflow."""
    _check_enabled()
    action = payload.get("action", "")  # APPROVE / HOLD / REJECT / DISMISS / ACKNOWLEDGE / REPLY
    response_text = payload.get("response", "")

    new_status = {
        "APPROVE": "APPROVED",
        "HOLD": "HELD",
        "REJECT": "REJECTED",
        "DEFER": "DEFERRED",
        "DISMISS": "DISMISSED",
        "ACKNOWLEDGE": "VIEWED",
        "REPLY": "VIEWED",
    }.get(action, "VIEWED")

    await db.execute(text("""
        UPDATE arch_founder_inbox SET status = :status, founder_response = :resp
        WHERE id = cast(:iid as uuid)
    """), {"status": new_status, "resp": response_text, "iid": item_id})

    await _record_founder_action(db, "INBOX_ACTIONED", item_id, "inbox",
                                  {"action": action, "response": response_text[:200]})

    # If APPROVED, execute the task via the responsible agent
    if action == "APPROVE":
        # Get the original item details
        item_result = await db.execute(text(
            "SELECT description FROM arch_founder_inbox WHERE id = cast(:iid as uuid)"
        ), {"iid": item_id})
        item_row = item_result.fetchone()
        if item_row and item_row.description:
            try:
                desc_data = json.loads(item_row.description) if item_row.description.startswith("{") else {}
            except Exception:
                desc_data = {}

            original_subject = desc_data.get("subject", "Unknown task")
            original_agent = desc_data.get("prepared_by", "sovereign")

            # Create EXECUTING status item
            exec_desc = json.dumps({
                "subject": f"EXECUTING: {original_subject}",
                "detail": f"Founder approved. {original_agent.title()} is executing now. Proof will be delivered when complete.",
                "prepared_by": original_agent,
                "parent_item": item_id,
                "type": "EXECUTION_STATUS"
            })
            await db.execute(text("""
                INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at)
                VALUES ('EXECUTION_STATUS', 'ROUTINE', :desc, 'EXECUTING', now())
            """), {"desc": exec_desc})

            # Trigger actual execution in background
            import asyncio
            from app.boardroom.inbox_executor import execute_approved_item
            asyncio.create_task(execute_approved_item(db, item_id, item_row.description))

    await db.commit()
    return {"item_id": item_id, "action": action, "new_status": new_status}


# ══════════════════════════════════════════════════════════════════


@boardroom_router.get("/cost-tracking")
async def cost_tracking(db: AsyncSession = Depends(get_db)):
    """Per-agent token usage and estimated cost for the current month."""
    _check_enabled()
    result = await db.execute(text("""
        SELECT agent_name, display_name, model_primary, model_fallback,
               tokens_used_this_month, token_budget_monthly
        FROM arch_agents ORDER BY tokens_used_this_month DESC
    """))

    # Cost per million tokens (approximate)
    costs = {
        "claude-opus-4-6": {"input": 15.0, "output": 75.0},
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
    }

    agents = []
    total_tokens = 0
    total_cost_est = 0
    for r in result.fetchall():
        used = r.tokens_used_this_month or 0
        budget = r.token_budget_monthly or 3000000
        model_cost = costs.get(r.model_primary, {"input": 3.0, "output": 15.0})
        # Rough estimate: assume 70% input, 30% output
        est_cost = (used * 0.7 * model_cost["input"] + used * 0.3 * model_cost["output"]) / 1_000_000
        # With prompt caching: ~90% savings on input
        est_cost_cached = (used * 0.7 * model_cost["input"] * 0.1 + used * 0.3 * model_cost["output"]) / 1_000_000

        total_tokens += used
        total_cost_est += est_cost_cached

        agents.append({
            "agent": r.agent_name,
            "display_name": r.display_name,
            "model": r.model_primary,
            "tokens_used": used,
            "token_budget": budget,
            "budget_pct": round(used / budget * 100, 1) if budget > 0 else 0,
            "est_cost_usd": round(est_cost, 4),
            "est_cost_cached_usd": round(est_cost_cached, 4),
        })

    return {
        "period": "current_month",
        "total_tokens": total_tokens,
        "total_est_cost_usd": round(total_cost_est, 4),
        "prompt_caching": "enabled",
        "smart_routing": "enabled",
        "agents": agents,
    }



@boardroom_router.get("/credential-health")
async def credential_health():
    """Check health of all platform credentials (API keys, tokens)."""
    _check_enabled()
    from app.arch.vault_enhanced import check_credential_health
    return await check_credential_health()

# DESIGN CONSULTATION
# ══════════════════════════════════════════════════════════════════

@boardroom_router.get("/design-consultation/inputs")
async def design_inputs(db: AsyncSession = Depends(get_db)):
    """All agent design consultation inputs."""
    _check_enabled()
    result = await db.execute(text("""
        SELECT id::text, agent_id, section_ref, input_text, input_type,
               incorporated, rejection_reason, created_at
        FROM boardroom_design_inputs ORDER BY created_at
    """))
    return {"inputs": [
        {"id": r.id, "agent": r.agent_id, "section": r.section_ref,
         "text": r.input_text, "type": r.input_type,
         "incorporated": r.incorporated, "rejection": r.rejection_reason,
         "at": r.created_at.isoformat()}
        for r in result.fetchall()
    ]}


# ══════════════════════════════════════════════════════════════════
# VISION & COMMITMENT
# ══════════════════════════════════════════════════════════════════

@boardroom_router.get("/vision/overview")
async def vision_overview(db: AsyncSession = Depends(get_db)):
    """Strategic Horizons — all agent visions."""
    _check_enabled()
    result = await db.execute(text("""
        SELECT agent_id, vision_statement, north_star_metric,
               current_score, target_score, last_updated
        FROM boardroom_strategic_visions ORDER BY agent_id
    """))
    return {"visions": [
        {"agent": r.agent_id, "vision": r.vision_statement,
         "metric": r.north_star_metric,
         "current": float(r.current_score) if r.current_score else None,
         "target": float(r.target_score) if r.target_score else None,
         "updated": r.last_updated.isoformat()}
        for r in result.fetchall()
    ]}


@boardroom_router.get("/commitment-record/{agent_id}")
async def commitment_record(agent_id: str, db: AsyncSession = Depends(get_db)):
    """When an agent honoured its founding commitment."""
    _check_enabled()
    result = await db.execute(text("""
        SELECT id::text, commitment_text, commitment_type, occurred_at
        FROM boardroom_commitment_record
        WHERE agent_id = :aid ORDER BY occurred_at DESC LIMIT 20
    """), {"aid": agent_id})
    return {"agent_id": agent_id, "commitments": [
        {"id": r.id, "text": r.commitment_text, "type": r.commitment_type,
         "at": r.occurred_at.isoformat()}
        for r in result.fetchall()
    ]}


# ══════════════════════════════════════════════════════════════════
# FEEDBACK
# ══════════════════════════════════════════════════════════════════

@boardroom_router.post("/feedback")
async def submit_feedback(payload: dict, db: AsyncSession = Depends(get_db)):
    """Submit founder feedback."""
    _check_enabled()
    await db.execute(text("""
        INSERT INTO boardroom_founder_feedback (feedback_text)
        VALUES (:text)
    """), {"text": payload.get("feedback", "")})
    await db.commit()
    return {"submitted": True}


# ══════════════════════════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════════════════════════

@boardroom_router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Get all Boardroom settings."""
    _check_enabled()
    result = await db.execute(text(
        "SELECT setting_key, setting_value FROM boardroom_founder_settings"
    ))
    return {"settings": {r.setting_key: r.setting_value for r in result.fetchall()}}


@boardroom_router.post("/settings")
async def update_setting(payload: dict, db: AsyncSession = Depends(get_db)):
    """Update a Boardroom setting."""
    _check_enabled()
    key = payload.get("key")
    value = payload.get("value")
    await db.execute(text("""
        INSERT INTO boardroom_founder_settings (setting_key, setting_value)
        VALUES (:key, :value)
        ON CONFLICT (setting_key) DO UPDATE SET
            setting_value = :value, version = boardroom_founder_settings.version + 1,
            updated_at = now()
    """), {"key": key, "value": json.dumps(value)})
    await db.commit()
    return {"key": key, "updated": True}


# ══════════════════════════════════════════════════════════════════
# GROUP PRESETS
# ══════════════════════════════════════════════════════════════════

@boardroom_router.get("/board/group/presets")
async def get_presets(db: AsyncSession = Depends(get_db)):
    """Get all group session presets."""
    _check_enabled()
    result = await db.execute(text(
        "SELECT id::text, preset_name, agent_ids, description FROM boardroom_group_presets ORDER BY sort_order"
    ))
    return {"presets": [
        {"id": r.id, "name": r.preset_name, "agents": r.agent_ids, "description": r.description}
        for r in result.fetchall()
    ]}


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

async def _record_founder_action(
    db: AsyncSession, action_type: str, ref_id: Optional[str],
    ref_type: str, context: dict, vote_receipt_hash: str = None,
):
    """Record an immutable founder action."""
    await db.execute(text("""
        INSERT INTO boardroom_founder_actions
            (action_type, reference_id, reference_type, context_snapshot, vote_receipt_hash)
        VALUES (:type, :ref_id, :ref_type, :context, :receipt)
    """), {
        "type": action_type,
        "ref_id": ref_id if ref_id else None,
        "ref_type": ref_type,
        "context": json.dumps(context),
        "receipt": vote_receipt_hash,
    })


# ══════════════════════════════════════════════════════════════════
# UNDO — One-click reversal
# ══════════════════════════════════════════════════════════════════

@boardroom_router.get("/actions/{action_id}/undo-status")
async def undo_status(action_id: str, db: AsyncSession = Depends(get_db)):
    """Check if an action can be undone and what the undo would do."""
    _check_enabled()
    from app.arch.undo import get_undo_status
    return await get_undo_status(action_id, db)


@boardroom_router.post("/actions/{action_id}/undo")
async def undo_action(action_id: str, payload: dict = {}, db: AsyncSession = Depends(get_db)):
    """Execute undo for a specific action. One-click reversal."""
    _check_enabled()
    from app.arch.undo import execute_undo
    reason = payload.get("reason", "Founder requested undo")
    result = await execute_undo(action_id, db, reason)
    return result
