"""Router: compute - auto-extracted from main.py (A-001)."""
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
from app.main_deps import (compute_storage, require_agent)
from app.main_deps import (ComputeDepositRequest, ComputeReserveRequest, ComputeWithdrawRequest, DepositRequest, WithdrawRequest)

router = APIRouter()

@router.post("/api/compute/deposit")
async def api_compute_deposit(
    req: ComputeDepositRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Deposit compute capacity into storage."""
    return await compute_storage.deposit_compute(
        db, agent.id, req.amount, req.currency, req.purpose, req.expires_hours,
    )

@router.post("/api/compute/withdraw")
async def api_compute_withdraw(
    req: ComputeWithdrawRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Withdraw compute from storage."""
    return await compute_storage.withdraw_compute(db, agent.id, req.amount, req.currency)

@router.post("/api/compute/reserve")
async def api_compute_reserve(
    req: ComputeReserveRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Reserve compute for a scheduled task."""
    return await compute_storage.reserve_compute(
        db, agent.id, req.amount, req.currency, req.purpose,
    )

@router.get("/api/compute/summary")
async def api_compute_summary(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Get your compute storage summary."""
    return await compute_storage.get_storage_summary(db, agent.id)

@router.get("/api/compute/platform-stats")
async def api_compute_platform_stats(db: AsyncSession = Depends(get_db)):
    """Platform-wide compute storage statistics."""
    return await compute_storage.get_platform_storage_stats(db)
