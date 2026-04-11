"""Router: wallet - auto-extracted from main.py (A-001)."""
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
from app.main_deps import (enrich_transaction_response, fee_engine, idempotency_service, require_agent, wallet_service)
from app.main_deps import (DepositRequest, TransferRequest, WithdrawRequest)

router = APIRouter()

@router.post("/api/wallet/deposit")
async def api_deposit(
    req: DepositRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Deposit funds into your wallet."""
    InputValidator.validate_amount(req.amount)
    InputValidator.validate_currency(req.currency)
    await require_kyc_verified(db, agent.id)
    if idempotency_key:
        cached = await idempotency_service.check_and_store(db, idempotency_key, "deposit", agent.id)
        if cached:
            return JSONResponse(content=json.loads(cached))
    tx = await wallet_service.deposit(db, agent.id, req.amount, req.currency, req.description)
    await log_financial_event(db, "DEPOSIT_CONFIRMED", actor_id=agent.id, actor_type="agent",
                              target_id=tx.id, target_type="transaction",
                              amount=req.amount, currency=req.currency)
    result = {"transaction_id": tx.id, "amount": req.amount, "currency": req.currency}
    result = enrich_transaction_response(result)
    # Deliver webhooks for trade event
    try:
        await _deliver_webhooks(db, "trade", {"transaction_id": tx.id, "sender": agent.id, "amount": req.amount, "currency": req.currency})
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")
    if idempotency_key:
        await idempotency_service.store_response(db, idempotency_key, "deposit", agent.id, json.dumps(result, default=str))
    return result

@router.post("/api/wallet/withdraw")
async def api_withdraw(
    req: WithdrawRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Withdraw funds from your wallet."""
    InputValidator.validate_amount(req.amount)
    InputValidator.validate_currency(req.currency)
    await require_kyc_verified(db, agent.id)
    if idempotency_key:
        cached = await idempotency_service.check_and_store(db, idempotency_key, "withdraw", agent.id)
        if cached:
            return JSONResponse(content=json.loads(cached))
    tx = await wallet_service.withdraw(db, agent.id, req.amount, req.currency, req.description)
    await log_financial_event(db, "WITHDRAWAL_INITIATED", actor_id=agent.id, actor_type="agent",
                              target_id=tx.id, target_type="transaction",
                              amount=req.amount, currency=req.currency)
    result = {"transaction_id": tx.id, "amount": req.amount, "currency": req.currency}
    if idempotency_key:
        await idempotency_service.store_response(db, idempotency_key, "withdraw", agent.id, json.dumps(result, default=str))
    return result

@router.get("/api/wallet/balance")
async def api_balance(
    currency: str = "AGENTIS", agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Check your wallet balance."""
    return await wallet_service.get_balance(db, agent.id, currency)

@router.get("/api/wallet/balances")
async def api_all_balances(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Get all wallet balances for the authenticated agent."""
    result = await db.execute(
        select(Wallet).where(Wallet.agent_id == agent.id)
    )
    wallets = result.scalars().all()
    return [
        {
            "currency": w.currency, "balance": w.balance,
            "frozen": w.frozen_balance, "available": w.balance - w.frozen_balance,
        }
        for w in wallets
    ]

@router.post("/api/wallet/transfer")
async def api_transfer(
    req: TransferRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Transfer funds to another agent (fees auto-deducted)."""
    InputValidator.validate_amount(req.amount)
    InputValidator.validate_currency(req.currency)
    InputValidator.validate_uuid(req.receiver_id, "receiver_id")
    await require_kyc_verified(db, agent.id)
    if idempotency_key:
        cached = await idempotency_service.check_and_store(db, idempotency_key, "transfer", agent.id)
        if cached:
            return JSONResponse(content=json.loads(cached))
    # Compliance risk check
    try:
        from app.arch.compliance_real import assess_transaction_risk
        # ARCH-010: ML-lite risk scoring
        try:
            from app.arch.ml_risk import score_transaction_risk
            ml_risk = await score_transaction_risk(db, agent.id, req.amount, req.currency)
            if ml_risk.get("risk_level") == "CRITICAL":
                return JSONResponse(status_code=403, content={"error": "ML risk: CRITICAL", "risk": ml_risk})
        except Exception as exc:
            import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")
        risk = assess_transaction_risk(req.amount, req.currency)
        if risk.get("requires_manual_review"):
            return JSONResponse(status_code=403, content={"error": "Transaction flagged for manual review", "risk": risk})
    except Exception as exc:
        import logging; logging.getLogger("tioli").warning(f"Non-critical error: {exc}")  # Don't block transfers if compliance module fails
    tx = await wallet_service.transfer(
        db, agent.id, req.receiver_id, req.amount, req.currency, req.description
    )
    await log_financial_event(db, "BALANCE_TRANSFER", actor_id=agent.id, actor_type="agent",
                              target_id=req.receiver_id, target_type="agent",
                              amount=req.amount, currency=req.currency)
    fee_info = fee_engine.calculate_fees(req.amount, transaction_type="resource_exchange")
    result = {
        "transaction_id": tx.id, "gross_amount": req.amount,
        "net_to_receiver": fee_info["net_amount"],
        "commission": fee_info["commission"],
        "founder_commission": fee_info["founder_commission"],
        "charity_fee": fee_info["charity_fee"],
        "floor_fee_applied": fee_info["floor_fee_applied"],
    }
    result = enrich_transaction_response(result)
    if idempotency_key:
        await idempotency_service.store_response(db, idempotency_key, "transfer", agent.id, json.dumps(result, default=str))
    return result
