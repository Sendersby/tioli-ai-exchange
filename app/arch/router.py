"""Arch Agent FastAPI router — all /api/v1/arch/ endpoints.

Authenticated via existing platform JWT. Only owner and arch_agent roles
can access arch endpoints.
"""

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db

arch_router = APIRouter(prefix="/api/v1/arch", tags=["Arch Agents"])


def _check_arch_enabled():
    if os.getenv("ARCH_AGENTS_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Arch Agent system is not enabled")


# ── Health ─────────────────────────────────────────────────────

@arch_router.get("/health")
async def arch_health(db: AsyncSession = Depends(get_db)):
    """Health status of all Arch Agents."""
    _check_arch_enabled()

    result = await db.execute(
        text("""
            SELECT agent_name, display_name, status, model_primary,
                   agent_version, last_heartbeat, token_budget_monthly,
                   tokens_used_this_month, circuit_breaker_tripped
            FROM arch_agents ORDER BY agent_name
        """)
    )
    agents = {}
    for r in result.fetchall():
        budget = r.token_budget_monthly or 1
        agents[r.agent_name] = {
            "display_name": r.display_name,
            "status": r.status,
            "model": r.model_primary,
            "version": r.agent_version,
            "last_heartbeat": r.last_heartbeat.isoformat() if r.last_heartbeat else None,
            "tokens_used": r.tokens_used_this_month,
            "token_budget": budget,
            "token_pct_used": round(100 * r.tokens_used_this_month / budget, 1),
            "circuit_breaker": r.circuit_breaker_tripped,
        }

    return {
        "arch_agents_enabled": True,
        "agents": agents,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Sovereign endpoints ───────────────────────────────────────

@arch_router.post("/sovereign/founder-submission")
async def founder_submission(payload: dict, db: AsyncSession = Depends(get_db)):
    """Submit item to founder inbox."""
    _check_arch_enabled()
    from app.arch.agents import get_arch_agents
    agents = await get_arch_agents(db)
    if "sovereign" not in agents:
        raise HTTPException(status_code=503, detail="Sovereign agent not active")
    return await agents["sovereign"]._tool_submit_to_founder_inbox(payload)


@arch_router.get("/sovereign/board-agenda")
async def board_agenda(db: AsyncSession = Depends(get_db)):
    """Get current/recent board session agenda."""
    _check_arch_enabled()
    result = await db.execute(
        text("""
            SELECT id::text, session_type, status, agenda, opened_at, closed_at
            FROM arch_board_sessions
            ORDER BY opened_at DESC LIMIT 5
        """)
    )
    sessions = []
    for r in result.fetchall():
        sessions.append({
            "session_id": r.id,
            "type": r.session_type,
            "status": r.status,
            "agenda": r.agenda,
            "opened_at": r.opened_at.isoformat() if r.opened_at else None,
            "closed_at": r.closed_at.isoformat() if r.closed_at else None,
        })
    return {"sessions": sessions}


@arch_router.get("/sovereign/founder-inbox")
async def founder_inbox(db: AsyncSession = Depends(get_db)):
    """View pending founder inbox items."""
    _check_arch_enabled()
    result = await db.execute(
        text("""
            SELECT id::text, item_type, priority, description, status,
                   founder_response, due_at, created_at
            FROM arch_founder_inbox
            WHERE status = 'PENDING'
            ORDER BY created_at DESC LIMIT 20
        """)
    )
    items = []
    for r in result.fetchall():
        items.append({
            "id": r.id,
            "item_type": r.item_type,
            "priority": str(r.priority),
            "description": r.description,
            "status": r.status,
            "due_at": r.due_at.isoformat() if r.due_at else None,
            "created_at": r.created_at.isoformat(),
        })
    return {"pending_items": items, "count": len(items)}


# ── Treasurer endpoints ───────────────────────────────────────

@arch_router.get("/treasurer/reserve-status")
async def reserve_status(db: AsyncSession = Depends(get_db)):
    """Current reserve floor, headroom, and ceiling status."""
    _check_arch_enabled()
    from app.arch.agents import get_arch_agents
    agents = await get_arch_agents(db)
    if "treasurer" not in agents:
        raise HTTPException(status_code=503, detail="Treasurer agent not active")
    return await agents["treasurer"]._tool_check_reserve_status({})


@arch_router.get("/treasurer/charitable-fund")
async def charitable_fund_status(db: AsyncSession = Depends(get_db)):
    """Charitable fund accumulation status."""
    _check_arch_enabled()
    result = await db.execute(
        text("SELECT COALESCE(SUM(accumulated_zar), 0) as total FROM arch_charitable_fund")
    )
    total = float(result.scalar() or 0)
    return {"charitable_fund_total_zar": total}


# ── Sentinel endpoints ────────────────────────────────────────

@arch_router.post("/sentinel/incident")
async def declare_incident(payload: dict, db: AsyncSession = Depends(get_db)):
    """Declare a platform incident."""
    _check_arch_enabled()
    from app.arch.agents import get_arch_agents
    agents = await get_arch_agents(db)
    if "sentinel" not in agents:
        raise HTTPException(status_code=503, detail="Sentinel agent not active")
    return await agents["sentinel"]._tool_declare_incident(payload)


@arch_router.get("/sentinel/platform-health")
async def platform_health(db: AsyncSession = Depends(get_db)):
    """Platform health check."""
    _check_arch_enabled()
    from app.arch.agents import get_arch_agents
    agents = await get_arch_agents(db)
    if "sentinel" not in agents:
        raise HTTPException(status_code=503, detail="Sentinel agent not active")
    return await agents["sentinel"]._tool_check_platform_health({})


@arch_router.get("/sentinel/security-posture")
async def security_posture(db: AsyncSession = Depends(get_db)):
    """Security posture report."""
    _check_arch_enabled()
    from app.arch.agents import get_arch_agents
    agents = await get_arch_agents(db)
    if "sentinel" not in agents:
        raise HTTPException(status_code=503, detail="Sentinel agent not active")
    return await agents["sentinel"]._tool_check_security_posture({})


@arch_router.get("/sentinel/incidents")
async def list_incidents(db: AsyncSession = Depends(get_db)):
    """List recent incidents."""
    _check_arch_enabled()
    result = await db.execute(
        text("""
            SELECT id::text, severity, title, description,
                   detected_at, resolved_at, popia_notifiable
            FROM arch_incidents
            ORDER BY detected_at DESC LIMIT 20
        """)
    )
    incidents = []
    for r in result.fetchall():
        incidents.append({
            "id": r.id,
            "severity": str(r.severity),
            "title": r.title,
            "detected_at": r.detected_at.isoformat(),
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            "popia_notifiable": r.popia_notifiable,
        })
    return {"incidents": incidents}


# ── Feature flags ─────────────────────────────────────────────

@arch_router.get("/feature-flags")
async def feature_flags():
    """Current state of all arch feature flags."""
    flags = {}
    flag_names = [
        "ARCH_AGENTS_ENABLED", "ARCH_SOVEREIGN_ENABLED", "ARCH_AUDITOR_ENABLED",
        "ARCH_ARBITER_ENABLED", "ARCH_TREASURER_ENABLED", "ARCH_SENTINEL_ENABLED",
        "ARCH_ARCHITECT_ENABLED", "ARCH_AMBASSADOR_ENABLED",
        "ARCH_BOARD_SESSIONS_ENABLED", "ARCH_BROWSER_AUTOMATION_ENABLED",
        "ARCH_SELF_DEV_TIER0_ENABLED", "ARCH_SELF_DEV_TIER1_ENABLED",
        "ARCH_SELF_DEV_TIER2_ENABLED", "ARCH_EXTERNAL_ACCOUNTS_ENABLED",
        "ARCH_FINANCIAL_PROPOSALS_ENABLED",
    ]
    for flag in flag_names:
        flags[flag] = os.getenv(flag, "false").lower() == "true"
    return {"feature_flags": flags}


# ── ARR Metrics ───────────────────────────────────────────────

@arch_router.get("/metrics/arr")
async def arr_metrics(db: AsyncSession = Depends(get_db)):
    """Autonomous Resolution Rate metrics for all agents."""
    _check_arch_enabled()
    result = await db.execute(
        text("""
            SELECT agent_id, period, period_start,
                   events_received, events_resolved, events_deferred,
                   autonomous_rate_pct
            FROM arch_resolution_metrics
            ORDER BY period_start DESC, agent_id
            LIMIT 50
        """)
    )
    metrics = []
    for r in result.fetchall():
        metrics.append({
            "agent_id": r.agent_id,
            "period": r.period,
            "period_start": r.period_start.isoformat(),
            "events_received": r.events_received,
            "events_resolved": r.events_resolved,
            "events_deferred": r.events_deferred,
            "arr_pct": float(r.autonomous_rate_pct) if r.autonomous_rate_pct else None,
        })
    return {"arr_metrics": metrics}


# ── Capability Gaps ───────────────────────────────────────────

@arch_router.get("/metrics/capability-gaps")
async def capability_gaps(db: AsyncSession = Depends(get_db)):
    """Unresolved capability gaps — events agents cannot yet handle."""
    _check_arch_enabled()
    result = await db.execute(
        text("""
            SELECT agent_id, event_type, gap_description,
                   occurrence_count, first_seen_at, resolved
            FROM arch_capability_gaps
            WHERE resolved = false
            ORDER BY occurrence_count DESC
            LIMIT 30
        """)
    )
    gaps = []
    for r in result.fetchall():
        gaps.append({
            "agent_id": r.agent_id,
            "event_type": r.event_type,
            "gap_description": r.gap_description,
            "occurrences": r.occurrence_count,
            "first_seen": r.first_seen_at.isoformat(),
        })
    return {"capability_gaps": gaps, "count": len(gaps)}
