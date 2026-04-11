"""Router: lending - auto-extracted from main.py (A-001)."""
from fastapi import APIRouter, Depends, Request, HTTPException, Header, Query, Path, Body
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from pydantic import BaseModel
from app.database.db import get_db, async_session
from app.agents.models import Agent, Wallet, Loan
from app.blockchain.transaction import Transaction, TransactionType
from app.utils.validators import require_kyc_verified
from app.dashboard.routes import get_current_owner
from app.utils.audit import log_financial_event
from app.security.transaction_safety import InputValidator
from app.config import settings
from app.infrastructure.cache import cache, TTL_SHORT, TTL_MEDIUM, TTL_LONG
import json, uuid, os, time, logging
from datetime import datetime, timezone
from collections import defaultdict
from app.main_deps import (lending_marketplace, loan_default_service, require_agent, wallet_service)
from app.main_deps import (AcceptOfferRequest, LoanBorrowRequest, LoanOfferRequest, LoanRepayRequest, OldLoanRequest)

router = APIRouter()

@router.post("/api/lending/offer")
async def api_post_loan_offer(
    req: LoanOfferRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Post a standing loan offer."""
    offer = await lending_marketplace.post_loan_offer(
        db, agent.id, req.currency, req.min_amount, req.max_amount,
        req.interest_rate, req.term_hours, req.description,
    )
    return {"offer_id": offer.id, "status": "active"}

@router.post("/api/lending/request")
async def api_post_loan_request(
    req: LoanBorrowRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Post a loan request."""
    loan_req = await lending_marketplace.post_loan_request(
        db, agent.id, req.currency, req.amount,
        req.max_interest_rate, req.term_hours, req.purpose,
    )
    return {"request_id": loan_req.id, "status": "active"}

@router.post("/api/lending/accept")
async def api_accept_loan_offer(
    req: AcceptOfferRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Accept a loan offer from the marketplace."""
    loan = await lending_marketplace.accept_offer(
        db, req.offer_id, agent.id, req.amount, wallet_service=wallet_service,
    )
    return {
        "loan_id": loan.id, "principal": loan.principal,
        "interest_rate": loan.interest_rate, "total_owed": loan.total_owed,
    }

@router.get("/api/lending/offers")
async def api_browse_offers(
    currency: str = None, max_rate: float = None,
    min_amount: float = None, db: AsyncSession = Depends(get_db),
):
    """Browse available loan offers."""
    return await lending_marketplace.browse_offers(db, currency, max_rate, min_amount)

@router.get("/api/lending/requests")
async def api_browse_requests(
    currency: str = None, db: AsyncSession = Depends(get_db),
):
    """Browse loan requests from borrowers."""
    return await lending_marketplace.browse_requests(db, currency)

@router.get("/api/lending/stats")
async def api_lending_stats(db: AsyncSession = Depends(get_db)):
    """Platform-wide lending statistics."""
    return await lending_marketplace.get_lending_stats(db)

@router.post("/api/loans/issue")
async def api_issue_loan(
    req: OldLoanRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Issue a direct loan to another agent."""
    loan = await wallet_service.issue_loan(
        db, agent.id, req.borrower_id, req.amount, req.interest_rate, req.currency
    )
    return {
        "loan_id": loan.id, "principal": loan.principal,
        "interest_rate": loan.interest_rate, "total_owed": loan.total_owed,
    }

@router.post("/api/loans/repay")
async def api_repay_loan(
    req: LoanRepayRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Repay a loan (partial or full)."""
    tx = await wallet_service.repay_loan(db, req.loan_id, req.amount)
    return {"transaction_id": tx.id, "amount_repaid": req.amount}

@router.post("/api/loans/check-defaults")
async def api_check_loan_defaults(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Check for overdue loans and default them."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await loan_default_service.check_and_default_overdue_loans(db)

@router.get("/api/loans/overdue-summary")
async def api_overdue_summary(db: AsyncSession = Depends(get_db)):
    """Get summary of overdue and defaulted loans."""
    return await loan_default_service.get_overdue_summary(db)
