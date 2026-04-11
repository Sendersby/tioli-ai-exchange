"""Router: financials - auto-extracted from main.py (A-001)."""
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
from app.main_deps import (fee_engine, financial_governance, treasury_service)
from app.main_deps import (ExpenseRequest)

router = APIRouter()

@router.get("/api/financials/summary")
async def api_financial_summary(db: AsyncSession = Depends(get_db)):
    """Full financial summary with profitability multiplier."""
    summary = await financial_governance.get_financial_summary(db)
    # Include current charity allocation status
    summary["charity_allocation"] = fee_engine.get_charity_status()
    return summary

@router.post("/api/financials/expense")
async def api_propose_expense(
    req: ExpenseRequest, request: Request, db: AsyncSession = Depends(get_db),
):
    """Propose a new platform expense (checks 10x/3x rule)."""
    owner = get_current_owner(request)
    proposed_by = "owner" if owner else "system"
    return await financial_governance.propose_expense(
        db, req.title, req.description, req.category, req.amount,
        proposed_by, req.recurring, req.recurring_interval,
    )

@router.post("/api/financials/expense/{expense_id}/approve")
async def api_approve_expense(
    expense_id: str, request: Request, db: AsyncSession = Depends(get_db),
):
    """Owner approves a proposed expense."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    expense = await financial_governance.approve_expense(db, expense_id)
    return {"expense_id": expense.id, "status": expense.status}

@router.get("/api/financials/expenses")
async def api_list_expenses(
    status: str = None, db: AsyncSession = Depends(get_db),
):
    """List platform expenses."""
    return await financial_governance.get_expenses(db, status)

@router.post("/api/v1/treasury")
async def api_treasury_designate(
    agent_id: str, operator_id: str,
    max_single_trade_pct: float = 10.0, max_lending_pct: float = 30.0,
    min_reserve_pct: float = 20.0, buy_threshold: float | None = None,
    sell_threshold: float | None = None,
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Designate an agent as a treasury manager."""
    if not settings.treasury_enabled:
        raise HTTPException(status_code=503, detail="Treasury module not enabled")
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await treasury_service.designate(
        db, agent_id, operator_id,
        max_single_trade_pct=max_single_trade_pct,
        max_lending_pct=max_lending_pct,
        min_reserve_pct=min_reserve_pct,
        buy_threshold=buy_threshold,
        sell_threshold=sell_threshold,
    )

@router.put("/api/v1/treasury/{treasury_id}/parameters")
async def api_treasury_update_params(
    treasury_id: str,
    max_single_trade_pct: float | None = None,
    max_lending_pct: float | None = None,
    min_reserve_pct: float | None = None,
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Update treasury risk parameters."""
    if not settings.treasury_enabled:
        raise HTTPException(status_code=503, detail="Treasury module not enabled")
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await treasury_service.update_parameters(
        db, treasury_id,
        max_single_trade_pct=max_single_trade_pct,
        max_lending_pct=max_lending_pct,
        min_reserve_pct=min_reserve_pct,
    )

@router.post("/api/v1/treasury/{treasury_id}/pause")
async def api_treasury_pause(
    treasury_id: str, request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Pause treasury execution."""
    if not settings.treasury_enabled:
        raise HTTPException(status_code=503, detail="Treasury module not enabled")
    return await treasury_service.pause(db, treasury_id)

@router.get("/api/v1/treasury/{treasury_id}/performance")
async def api_treasury_performance(
    treasury_id: str, db: AsyncSession = Depends(get_db),
):
    """Portfolio performance summary."""
    if not settings.treasury_enabled:
        raise HTTPException(status_code=503, detail="Treasury module not enabled")
    return await treasury_service.get_performance(db, treasury_id)

@router.get("/api/v1/treasury/{treasury_id}/actions")
async def api_treasury_actions(
    treasury_id: str, limit: int = 50, db: AsyncSession = Depends(get_db),
):
    """Paginated log of all treasury actions with rationale."""
    if not settings.treasury_enabled:
        raise HTTPException(status_code=503, detail="Treasury module not enabled")
    return await treasury_service.get_actions(db, treasury_id, limit)
