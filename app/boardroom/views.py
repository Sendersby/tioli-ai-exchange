"""Boardroom HTML view routes — serves Jinja2 templates.

All views under /boardroom/ path. Extends existing base.html.
"""

import os
import json
import logging

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db

log = logging.getLogger("boardroom.views")
boardroom_views = APIRouter(prefix="/boardroom", tags=["Boardroom Views"])
templates = Jinja2Templates(directory="app/templates")

AGENT_COLOURS = {
    "sovereign": "#D4A94A",   # Gold
    "sentinel": "#4A90D9",    # Steel Blue
    "treasurer": "#028090",   # Teal
    "auditor": "#7B68AE",     # Purple
    "arbiter": "#E07A5F",     # Terracotta
    "architect": "#3D8B6E",   # Forest Green
    "ambassador": "#E8A838",  # Amber
}

AGENT_ABBREVS = {
    "sovereign": "SOV", "sentinel": "SEN", "treasurer": "TRS",
    "auditor": "AUD", "arbiter": "ARB", "architect": "ARC", "ambassador": "AMB",
}


def _check_enabled():
    if os.getenv("BOARDROOM_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Boardroom not enabled")


async def _get_boardroom_context(db: AsyncSession) -> dict:
    """Common context for all Boardroom templates."""
    # Agent statuses for status bar
    agents = await db.execute(text("""
        SELECT agent_name, display_name, status, last_heartbeat,
               tokens_used_this_month, token_budget_monthly
        FROM arch_agents ORDER BY agent_name
    """))
    agent_list = []
    for r in agents.fetchall():
        budget = r.token_budget_monthly or 1
        agent_list.append({
            "name": r.agent_name, "display": r.display_name,
            "status": r.status, "colour": AGENT_COLOURS.get(r.agent_name, "#666"),
            "abbrev": AGENT_ABBREVS.get(r.agent_name, "???"),
            "heartbeat": r.last_heartbeat,
            "token_pct": round(100 * r.tokens_used_this_month / budget, 1),
        })

    # Inbox count
    inbox = await db.execute(text(
        "SELECT COUNT(*) FROM arch_founder_inbox WHERE status = 'PENDING'"
    ))
    inbox_count = inbox.scalar() or 0

    # Open incidents
    incidents = await db.execute(text(
        "SELECT COUNT(*) FROM arch_incidents WHERE resolved_at IS NULL"
    ))

    return {
        "agents": agent_list,
        "agent_colours": AGENT_COLOURS,
        "inbox_count": inbox_count,
        "open_incidents": incidents.scalar() or 0,
        "boardroom_enabled": True,
    }


@boardroom_views.get("", response_class=HTMLResponse)
@boardroom_views.get("/", response_class=HTMLResponse)
async def boardroom_home(request: Request, db: AsyncSession = Depends(get_db)):
    """Board Home — the main Boardroom view."""
    _check_enabled()
    ctx = await _get_boardroom_context(db)

    # Reserve data
    reserve = await db.execute(text("""
        SELECT floor_zar, total_balance_zar, ceiling_remaining_zar
        FROM arch_reserve_ledger ORDER BY recorded_at DESC LIMIT 1
    """))
    r = reserve.fetchone()
    ctx["reserve"] = {
        "foundation": float(r.floor_zar) if r else 0,
        "balance": float(r.total_balance_zar) if r else 0,
        "headroom": float(r.total_balance_zar - r.floor_zar) if r else 0,
        "ceiling": float(r.ceiling_remaining_zar) if r else 0,
    } if r else {"foundation": 0, "balance": 0, "headroom": 0, "ceiling": 0}

    # Strategic visions
    visions = await db.execute(text("""
        SELECT agent_id, north_star_metric, current_score, target_score
        FROM boardroom_strategic_visions ORDER BY agent_id
    """))
    ctx["visions"] = {
        row.agent_id: {"metric": row.north_star_metric,
                       "current": float(row.current_score) if row.current_score else None,
                       "target": float(row.target_score) if row.target_score else None}
        for row in visions.fetchall()
    }

    # Recent feed
    feed = await db.execute(text("""
        SELECT agent_id, event_type, action_taken, created_at
        FROM arch_event_actions ORDER BY created_at DESC LIMIT 20
    """))
    ctx["feed"] = [
        {"agent": row.agent_id, "event": row.event_type,
         "action": row.action_taken, "at": row.created_at,
         "colour": AGENT_COLOURS.get(row.agent_id, "#666"),
         "abbrev": AGENT_ABBREVS.get(row.agent_id, "???")}
        for row in feed.fetchall()
    ]

    return templates.TemplateResponse("boardroom/home.html", {
        "request": request, "active": "boardroom", "authenticated": True, **ctx,
    })


@boardroom_views.get("/board", response_class=HTMLResponse)
async def boardroom_board(request: Request, db: AsyncSession = Depends(get_db)):
    """Full Board / Board Chamber."""
    _check_enabled()
    ctx = await _get_boardroom_context(db)

    # Recent sessions
    sessions = await db.execute(text("""
        SELECT id::text, session_type, status, agenda, quorum_met,
               agents_present, opened_at, closed_at
        FROM arch_board_sessions ORDER BY opened_at DESC LIMIT 10
    """))
    ctx["sessions"] = [
        {"id": row.id, "type": row.session_type, "status": row.status,
         "agenda": row.agenda, "quorum": row.quorum_met,
         "present": row.agents_present, "opened": row.opened_at, "closed": row.closed_at}
        for row in sessions.fetchall()
    ]

    # Group presets
    presets = await db.execute(text(
        "SELECT id::text, preset_name, agent_ids, description FROM boardroom_group_presets ORDER BY sort_order"
    ))
    ctx["presets"] = [
        {"id": row.id, "name": row.preset_name, "agents": row.agent_ids, "desc": row.description}
        for row in presets.fetchall()
    ]

    return templates.TemplateResponse("boardroom/board.html", {
        "request": request, "active": "boardroom", "authenticated": True, **ctx,
    })


@boardroom_views.get("/agents/{agent_id}", response_class=HTMLResponse)
async def boardroom_agent(request: Request, agent_id: str, db: AsyncSession = Depends(get_db)):
    """Individual Agent Office."""
    _check_enabled()
    ctx = await _get_boardroom_context(db)

    # Full agent data
    agent = await db.execute(text("""
        SELECT agent_name, display_name, corporate_title, status,
               model_primary, agent_version, last_heartbeat,
               token_budget_monthly, tokens_used_this_month
        FROM arch_agents WHERE agent_name = :aid
    """), {"aid": agent_id})
    row = agent.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")

    budget = row.token_budget_monthly or 1
    ctx["agent"] = {
        "name": row.agent_name, "display": row.display_name,
        "title": row.corporate_title, "status": row.status,
        "model": row.model_primary, "version": row.agent_version,
        "heartbeat": row.last_heartbeat,
        "tokens_used": row.tokens_used_this_month, "budget": budget,
        "token_pct": round(100 * row.tokens_used_this_month / budget, 1),
        "colour": AGENT_COLOURS.get(agent_id, "#666"),
    }

    # Founding statement
    founding = await db.execute(text("""
        SELECT ruling_text FROM arch_constitutional_rulings
        WHERE ruling_type = 'FOUNDING_STATEMENT' AND subject_agents @> :agents LIMIT 1
    """), {"agents": json.dumps([agent_id])})
    f_row = founding.fetchone()
    if f_row:
        f_data = json.loads(f_row.ruling_text) if f_row.ruling_text.startswith('{') else {"statement": f_row.ruling_text}
        ctx["founding_statement"] = f_data.get("statement", "")
        ctx["commitment"] = f_data.get("commitment", "")
    else:
        ctx["founding_statement"] = ""
        ctx["commitment"] = ""

    # Vision
    vision = await db.execute(text("""
        SELECT vision_statement, north_star_metric, current_score, target_score
        FROM boardroom_strategic_visions WHERE agent_id = :aid
    """), {"aid": agent_id})
    v = vision.fetchone()
    ctx["vision"] = {
        "statement": v.vision_statement if v else "",
        "metric": v.north_star_metric if v else "",
        "current": float(v.current_score) if v and v.current_score else None,
        "target": float(v.target_score) if v and v.target_score else None,
    }

    # Chat history
    chat = await db.execute(text("""
        SELECT direction, message_text, message_type, created_at
        FROM boardroom_chat_messages WHERE agent_id = :aid
        ORDER BY created_at DESC LIMIT 30
    """), {"aid": agent_id})
    ctx["chat_history"] = list(reversed([
        {"dir": row.direction, "text": row.message_text,
         "type": row.message_type, "at": row.created_at}
        for row in chat.fetchall()
    ]))

    # Recent actions
    actions = await db.execute(text("""
        SELECT event_type, action_taken, processing_time_ms, created_at
        FROM arch_event_actions WHERE agent_id = :aid
        ORDER BY created_at DESC LIMIT 15
    """), {"aid": agent_id})
    ctx["recent_actions"] = [
        {"event": row.event_type, "action": row.action_taken,
         "ms": row.processing_time_ms, "at": row.created_at}
        for row in actions.fetchall()
    ]

    return templates.TemplateResponse("boardroom/agent_office.html", {
        "request": request, "active": "boardroom", "authenticated": True, **ctx,
    })


@boardroom_views.get("/treasury", response_class=HTMLResponse)
async def boardroom_treasury(request: Request, db: AsyncSession = Depends(get_db)):
    """Treasury — The Foundation."""
    _check_enabled()
    ctx = await _get_boardroom_context(db)

    reserve = await db.execute(text("""
        SELECT gross_income_ytd_zar, floor_zar, total_balance_zar,
               spending_30d_zar, ceiling_remaining_zar, recorded_at
        FROM arch_reserve_ledger ORDER BY recorded_at DESC LIMIT 1
    """))
    r = reserve.fetchone()
    ctx["treasury"] = {
        "foundation": float(r.floor_zar) if r else 0,
        "balance": float(r.total_balance_zar) if r else 0,
        "headroom": float(r.total_balance_zar - r.floor_zar) if r else 0,
        "ceiling": float(r.ceiling_remaining_zar) if r else 0,
        "spending_30d": float(r.spending_30d_zar) if r else 0,
        "income_ytd": float(r.gross_income_ytd_zar) if r else 0,
        "last_calc": r.recorded_at if r else None,
    }

    # Proposals
    proposals = await db.execute(text("""
        SELECT id::text, proposal_type, description, amount_zar, status, created_at
        FROM arch_financial_proposals ORDER BY created_at DESC LIMIT 20
    """))
    ctx["proposals"] = [
        {"id": row.id, "type": row.proposal_type, "desc": row.description,
         "amount": float(row.amount_zar), "status": row.status, "at": row.created_at}
        for row in proposals.fetchall()
    ]

    # Charitable fund
    charity = await db.execute(text(
        "SELECT COALESCE(SUM(accumulated_zar), 0) FROM arch_charitable_fund"
    ))
    ctx["charitable_total"] = float(charity.scalar() or 0)

    return templates.TemplateResponse("boardroom/treasury.html", {
        "request": request, "active": "boardroom", "authenticated": True, **ctx,
    })


@boardroom_views.get("/inbox", response_class=HTMLResponse)
async def boardroom_inbox(request: Request, db: AsyncSession = Depends(get_db)):
    """Founder Inbox."""
    _check_enabled()
    ctx = await _get_boardroom_context(db)

    items = await db.execute(text("""
        SELECT id::text, item_type, priority::text, description, status,
               founder_response, due_at, created_at
        FROM arch_founder_inbox
        ORDER BY
            CASE priority WHEN 'EMERGENCY' THEN 0 WHEN 'URGENT' THEN 1 ELSE 2 END,
            CASE WHEN due_at < now() THEN 0 ELSE 1 END,
            due_at ASC NULLS LAST
        LIMIT 50
    """))
    ctx["inbox_items"] = [
        {"id": row.id, "type": row.item_type, "priority": row.priority,
         "desc": row.description, "status": row.status,
         "response": row.founder_response, "due": row.due_at, "at": row.created_at}
        for row in items.fetchall()
    ]

    return templates.TemplateResponse("boardroom/inbox.html", {
        "request": request, "active": "boardroom", "authenticated": True, **ctx,
    })


@boardroom_views.get("/record", response_class=HTMLResponse)
async def boardroom_record(request: Request, db: AsyncSession = Depends(get_db)):
    """The Record — immutable audit trail."""
    _check_enabled()
    ctx = await _get_boardroom_context(db)

    records = await db.execute(text("""
        SELECT id::text, agent_id::text, action_type, action_detail,
               result::text, entry_hash, created_at
        FROM arch_audit_log ORDER BY created_at DESC LIMIT 50
    """))
    ctx["records"] = [
        {"id": row.id, "agent": row.agent_id, "type": row.action_type,
         "detail": row.action_detail, "result": row.result,
         "hash": row.entry_hash, "at": row.created_at}
        for row in records.fetchall()
    ]

    return templates.TemplateResponse("boardroom/record.html", {
        "request": request, "active": "boardroom", "authenticated": True, **ctx,
    })


@boardroom_views.get("/votes", response_class=HTMLResponse)
async def boardroom_votes(request: Request, db: AsyncSession = Depends(get_db)):
    """Vote registry."""
    _check_enabled()
    ctx = await _get_boardroom_context(db)

    votes = await db.execute(text("""
        SELECT bv.proposal_id::text, bv.vote::text, bv.rationale,
               bv.voted_at, a.agent_name, a.display_name
        FROM arch_board_votes bv
        JOIN arch_agents a ON bv.agent_id = a.id
        ORDER BY bv.voted_at DESC LIMIT 50
    """))
    ctx["vote_records"] = [
        {"proposal": row.proposal_id, "vote": row.vote,
         "rationale": row.rationale, "agent": row.agent_name,
         "display": row.display_name, "at": row.voted_at}
        for row in votes.fetchall()
    ]

    return templates.TemplateResponse("boardroom/votes.html", {
        "request": request, "active": "boardroom", "authenticated": True, **ctx,
    })


@boardroom_views.get("/mission-control", response_class=HTMLResponse)
async def boardroom_mission(request: Request, db: AsyncSession = Depends(get_db)):
    """Mission Control — full agent hierarchy."""
    _check_enabled()
    ctx = await _get_boardroom_context(db)
    return templates.TemplateResponse("boardroom/mission_control.html", {
        "request": request, "active": "boardroom", "authenticated": True, **ctx,
    })


# ══════════════════════════════════════════════════════════════════
# MISSING ROUTES — Fix 404s
# ══════════════════════════════════════════════════════════════════

@boardroom_views.get("/board/convene", response_class=HTMLResponse)
async def boardroom_convene(request: Request, db: AsyncSession = Depends(get_db)):
    """Convene a new board session — redirects to active session after creation."""
    _check_enabled()
    ctx = await _get_boardroom_context(db)

    preset_id = request.query_params.get("preset", "")
    preset_agents = None
    if preset_id:
        p = await db.execute(text(
            "SELECT preset_name, agent_ids FROM boardroom_group_presets WHERE id = cast(:pid as uuid)"
        ), {"pid": preset_id})
        row = p.fetchone()
        if row:
            preset_agents = {"name": row.preset_name, "agents": row.agent_ids}

    # Presets for the composer
    presets = await db.execute(text(
        "SELECT id::text, preset_name, agent_ids, description FROM boardroom_group_presets ORDER BY sort_order"
    ))
    ctx["presets"] = [
        {"id": row.id, "name": row.preset_name, "agents": row.agent_ids, "desc": row.description}
        for row in presets.fetchall()
    ]
    ctx["selected_preset"] = preset_agents

    return templates.TemplateResponse("boardroom/convene.html", {
        "request": request, "active": "boardroom", "authenticated": True, **ctx,
    })


@boardroom_views.get("/board/session/{session_id}", response_class=HTMLResponse)
async def boardroom_session_detail(request: Request, session_id: str, db: AsyncSession = Depends(get_db)):
    """View a specific board session — active or historical."""
    _check_enabled()
    ctx = await _get_boardroom_context(db)

    session = await db.execute(text("""
        SELECT id::text, session_type, status, agenda, quorum_met,
               agents_present, outcome, minutes, opened_at, closed_at
        FROM arch_board_sessions WHERE id = cast(:sid as uuid)
    """), {"sid": session_id})
    s = session.fetchone()
    if not s:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/boardroom/board")

    ctx["session"] = {
        "id": s.id, "type": s.session_type, "status": s.status,
        "agenda": s.agenda, "quorum": s.quorum_met,
        "present": s.agents_present, "outcome": s.outcome,
        "minutes": s.minutes, "opened": s.opened_at, "closed": s.closed_at,
    }

    # Get chat messages during this session
    if s.opened_at:
        msgs = await db.execute(text("""
            SELECT agent_id, direction, message_text, message_type, created_at
            FROM boardroom_chat_messages
            WHERE created_at >= :start AND created_at <= COALESCE(:end, now())
            ORDER BY created_at ASC
        """), {"start": s.opened_at, "end": s.closed_at})
        ctx["transcript"] = [
            {"agent": r.agent_id, "dir": r.direction, "text": r.message_text,
             "type": r.message_type, "at": r.created_at}
            for r in msgs.fetchall()
        ]
    else:
        ctx["transcript"] = []

    # Get votes from this session
    votes = await db.execute(text("""
        SELECT bv.vote::text, bv.rationale, a.agent_name, a.display_name
        FROM arch_board_votes bv
        JOIN arch_agents a ON bv.agent_id = a.id
        WHERE bv.session_id = cast(:sid as uuid)
        ORDER BY bv.voted_at
    """), {"sid": session_id})
    ctx["session_votes"] = [
        {"vote": r.vote, "rationale": r.rationale,
         "agent": r.agent_name, "display": r.display_name}
        for r in votes.fetchall()
    ]

    return templates.TemplateResponse("boardroom/session.html", {
        "request": request, "active": "boardroom", "authenticated": True, **ctx,
    })
