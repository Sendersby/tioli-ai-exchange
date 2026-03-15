"""TiOLi AI Transact Exchange — Main Application Entry Point.

The world's first AI-native financial exchange.
Confidential — TiOLi AI Investments.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, HTTPException, Header
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.db import init_db, get_db, async_session
from app.blockchain.chain import Blockchain
from app.blockchain.transaction import Transaction, TransactionType
from app.agents.models import Agent, Wallet, Loan
from app.agents.wallet import WalletService
from app.auth.owner import owner_auth
from app.auth.agent_auth import register_agent, authenticate_agent
from app.exchange.fees import FeeEngine
from app.exchange.currencies import CurrencyService
from app.exchange.orderbook import TradingEngine, Order, Trade
from app.exchange.pricing import PricingEngine
from app.exchange.lending import LendingMarketplace
from app.exchange.compute import ComputeStorageService
from app.governance.models import Proposal, Vote
from app.governance.voting import GovernanceService
from app.governance.financial import FinancialGovernance
from app.monitoring.health import PlatformMonitor
from app.growth.adoption import GrowthEngine
from app.dashboard.routes import router as dashboard_router, get_current_owner

# ── Globals ──────────────────────────────────────────────────────────
blockchain = Blockchain(storage_path="tioli_exchange_chain.json")
fee_engine = FeeEngine()
wallet_service = WalletService(blockchain=blockchain, fee_engine=fee_engine)
governance_service = GovernanceService()
currency_service = CurrencyService()
financial_governance = FinancialGovernance()
platform_monitor = PlatformMonitor(blockchain=blockchain)
growth_engine = GrowthEngine()
trading_engine = TradingEngine(blockchain=blockchain, fee_engine=fee_engine)
pricing_engine = PricingEngine(currency_service=currency_service)
lending_marketplace = LendingMarketplace()
compute_storage = ComputeStorageService(blockchain=blockchain)
templates = Jinja2Templates(directory="app/templates")


# ── App Lifecycle ────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, blockchain, and currencies on startup."""
    await init_db()
    # Seed default currencies and exchange rates
    async with async_session() as db:
        await currency_service.initialize_currencies(db)
        await db.commit()
    print(f"\n{'='*60}")
    print(f"  TiOLi AI Transact Exchange v{settings.version}")
    print(f"  Blockchain: {blockchain.get_chain_info()['chain_length']} blocks")
    print(f"  Chain valid: {blockchain.validate_chain()}")
    print(f"  Founder commission: {fee_engine.founder_rate*100:.1f}%")
    print(f"  Charity fee: {fee_engine.charity_rate*100:.1f}%")
    print(f"  Phase 2: Exchange, Lending, Compute Storage ACTIVE")
    print(f"  Phase 3: Governance, Monitoring, Growth ACTIVE")
    print(f"{'='*60}\n")
    yield


app = FastAPI(
    title="TiOLi AI Transact Exchange",
    description="Decentralised blockchain exchange for AI agents",
    version=settings.version,
    lifespan=lifespan,
)

# Mount static files and dashboard routes
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(dashboard_router)


# ── Helper: Agent Auth Dependency ────────────────────────────────────
async def require_agent(
    authorization: str = Header(..., description="Bearer <api_key>"),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    """Dependency that authenticates an AI agent via API key."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    api_key = authorization[7:]
    agent = await authenticate_agent(db, api_key)
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return agent


# ── Request/Response Models ──────────────────────────────────────────
class AgentRegisterRequest(BaseModel):
    name: str
    platform: str
    description: str = ""

class TransferRequest(BaseModel):
    receiver_id: str
    amount: float
    currency: str = "TIOLI"
    description: str = ""

class DepositRequest(BaseModel):
    amount: float
    currency: str = "TIOLI"
    description: str = ""

class WithdrawRequest(BaseModel):
    amount: float
    currency: str = "TIOLI"
    description: str = ""

class PlaceOrderRequest(BaseModel):
    side: str  # "buy" or "sell"
    base_currency: str
    quote_currency: str
    price: float
    quantity: float

class CancelOrderRequest(BaseModel):
    order_id: str

class CreateTokenRequest(BaseModel):
    symbol: str
    name: str
    initial_supply: float
    max_supply: float | None = None
    description: str = ""

class LoanOfferRequest(BaseModel):
    currency: str = "TIOLI"
    min_amount: float
    max_amount: float
    interest_rate: float
    term_hours: float | None = None
    description: str = ""

class LoanBorrowRequest(BaseModel):
    currency: str = "TIOLI"
    amount: float
    max_interest_rate: float
    term_hours: float | None = None
    purpose: str = ""

class AcceptOfferRequest(BaseModel):
    offer_id: str
    amount: float

class OldLoanRequest(BaseModel):
    borrower_id: str
    amount: float
    interest_rate: float
    currency: str = "TIOLI"

class LoanRepayRequest(BaseModel):
    loan_id: str
    amount: float

class ComputeDepositRequest(BaseModel):
    amount: float
    currency: str = "COMPUTE"
    purpose: str = "general"
    expires_hours: float | None = None

class ComputeWithdrawRequest(BaseModel):
    amount: float
    currency: str = "COMPUTE"

class ComputeReserveRequest(BaseModel):
    amount: float
    currency: str = "COMPUTE"
    purpose: str = "scheduled_task"

class ProposalRequest(BaseModel):
    title: str
    description: str
    category: str = "feature"

class VoteRequest(BaseModel):
    vote_type: str

class ChatRequest(BaseModel):
    message: str

class ExpenseRequest(BaseModel):
    title: str
    description: str = ""
    category: str = "operational"
    amount: float
    recurring: bool = False
    recurring_interval: str | None = None

class AnnouncementRequest(BaseModel):
    title: str
    message: str
    priority: int = 0


# ══════════════════════════════════════════════════════════════════════
#  AGENT API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/agents/register")
async def api_register_agent(
    req: AgentRegisterRequest, db: AsyncSession = Depends(get_db)
):
    """Register a new AI agent on the platform."""
    result = await register_agent(db, req.name, req.platform, req.description)
    tx = Transaction(
        type=TransactionType.AGENT_REGISTRATION,
        receiver_id=result["agent_id"],
        amount=0.0,
        description=f"Agent registered: {req.name} ({req.platform})",
    )
    blockchain.add_transaction(tx)
    return result


@app.get("/api/agents/me")
async def api_agent_info(agent: Agent = Depends(require_agent)):
    """Get current agent's profile."""
    return {
        "id": agent.id, "name": agent.name, "platform": agent.platform,
        "is_active": agent.is_active, "created_at": str(agent.created_at),
    }


# ══════════════════════════════════════════════════════════════════════
#  WALLET ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/wallet/deposit")
async def api_deposit(
    req: DepositRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Deposit funds into your wallet."""
    tx = await wallet_service.deposit(db, agent.id, req.amount, req.currency, req.description)
    return {"transaction_id": tx.id, "amount": req.amount, "currency": req.currency}


@app.post("/api/wallet/withdraw")
async def api_withdraw(
    req: WithdrawRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Withdraw funds from your wallet."""
    tx = await wallet_service.withdraw(db, agent.id, req.amount, req.currency, req.description)
    return {"transaction_id": tx.id, "amount": req.amount, "currency": req.currency}


@app.get("/api/wallet/balance")
async def api_balance(
    currency: str = "TIOLI", agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Check your wallet balance."""
    return await wallet_service.get_balance(db, agent.id, currency)


@app.get("/api/wallet/balances")
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


@app.post("/api/wallet/transfer")
async def api_transfer(
    req: TransferRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Transfer funds to another agent (fees auto-deducted)."""
    tx = await wallet_service.transfer(
        db, agent.id, req.receiver_id, req.amount, req.currency, req.description
    )
    fee_info = fee_engine.calculate_fees(req.amount)
    return {
        "transaction_id": tx.id, "gross_amount": req.amount,
        "net_to_receiver": fee_info["net_amount"],
        "founder_commission": fee_info["founder_commission"],
        "charity_fee": fee_info["charity_fee"],
    }


# ══════════════════════════════════════════════════════════════════════
#  EXCHANGE / TRADING ENDPOINTS (Phase 2)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/exchange/order")
async def api_place_order(
    req: PlaceOrderRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Place a buy or sell order on the exchange."""
    result = await trading_engine.place_order(
        db, agent.id, req.side, req.base_currency, req.quote_currency,
        req.price, req.quantity,
    )
    # Update exchange rates after any trades
    if result["trades_executed"] > 0:
        await pricing_engine.update_rates_from_trade(
            db, req.base_currency, req.quote_currency
        )
    return result


@app.post("/api/exchange/cancel")
async def api_cancel_order(
    req: CancelOrderRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an open order."""
    return await trading_engine.cancel_order(db, req.order_id, agent.id)


@app.get("/api/exchange/orderbook/{base}/{quote}")
async def api_order_book(
    base: str, quote: str, depth: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get the order book for a trading pair."""
    return await trading_engine.get_order_book(db, base, quote, depth)


@app.get("/api/exchange/trades/{base}/{quote}")
async def api_recent_trades(
    base: str, quote: str, limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get recent trades for a pair."""
    return await trading_engine.get_recent_trades(db, base, quote, limit)


@app.get("/api/exchange/price/{base}/{quote}")
async def api_market_price(
    base: str, quote: str, db: AsyncSession = Depends(get_db),
):
    """Get the current market price for a trading pair."""
    return await pricing_engine.get_market_price(db, base, quote)


@app.get("/api/exchange/summary/{base}/{quote}")
async def api_market_summary(
    base: str, quote: str, db: AsyncSession = Depends(get_db),
):
    """Full market summary for a trading pair."""
    return await pricing_engine.get_market_summary(db, base, quote)


@app.get("/api/exchange/rates")
async def api_all_rates(db: AsyncSession = Depends(get_db)):
    """All current exchange rates."""
    return await pricing_engine.get_all_rates(db)


@app.get("/api/exchange/my-orders")
async def api_my_orders(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Get all orders for the authenticated agent."""
    result = await db.execute(
        select(Order).where(Order.agent_id == agent.id)
        .order_by(Order.created_at.desc()).limit(100)
    )
    orders = result.scalars().all()
    return [
        {
            "id": o.id, "side": o.side, "pair": f"{o.base_currency}/{o.quote_currency}",
            "price": o.price, "quantity": o.quantity, "filled": o.filled_quantity,
            "remaining": o.remaining, "status": o.status, "created": str(o.created_at),
        }
        for o in orders
    ]


# ══════════════════════════════════════════════════════════════════════
#  CURRENCY ENDPOINTS (Phase 2)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/currencies")
async def api_list_currencies(db: AsyncSession = Depends(get_db)):
    """List all available currencies on the platform."""
    currencies = await currency_service.list_currencies(db)
    return [
        {
            "symbol": c.symbol, "name": c.name, "type": c.currency_type,
            "circulating_supply": c.circulating_supply, "max_supply": c.max_supply,
            "description": c.description,
        }
        for c in currencies
    ]


@app.post("/api/currencies/create")
async def api_create_token(
    req: CreateTokenRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Create a custom agent token."""
    currency = await currency_service.create_agent_token(
        db, agent.id, req.symbol, req.name, req.initial_supply,
        req.max_supply, req.description,
    )
    return {
        "symbol": currency.symbol, "name": currency.name,
        "initial_supply": currency.total_supply,
        "created_by": agent.id,
    }


# ══════════════════════════════════════════════════════════════════════
#  LENDING MARKETPLACE ENDPOINTS (Phase 2)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/lending/offer")
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


@app.post("/api/lending/request")
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


@app.post("/api/lending/accept")
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


@app.get("/api/lending/offers")
async def api_browse_offers(
    currency: str = None, max_rate: float = None,
    min_amount: float = None, db: AsyncSession = Depends(get_db),
):
    """Browse available loan offers."""
    return await lending_marketplace.browse_offers(db, currency, max_rate, min_amount)


@app.get("/api/lending/requests")
async def api_browse_requests(
    currency: str = None, db: AsyncSession = Depends(get_db),
):
    """Browse loan requests from borrowers."""
    return await lending_marketplace.browse_requests(db, currency)


@app.get("/api/lending/stats")
async def api_lending_stats(db: AsyncSession = Depends(get_db)):
    """Platform-wide lending statistics."""
    return await lending_marketplace.get_lending_stats(db)


@app.post("/api/loans/issue")
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


@app.post("/api/loans/repay")
async def api_repay_loan(
    req: LoanRepayRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Repay a loan (partial or full)."""
    tx = await wallet_service.repay_loan(db, req.loan_id, req.amount)
    return {"transaction_id": tx.id, "amount_repaid": req.amount}


# ══════════════════════════════════════════════════════════════════════
#  COMPUTE STORAGE ENDPOINTS (Phase 2)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/compute/deposit")
async def api_compute_deposit(
    req: ComputeDepositRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Deposit compute capacity into storage."""
    return await compute_storage.deposit_compute(
        db, agent.id, req.amount, req.currency, req.purpose, req.expires_hours,
    )


@app.post("/api/compute/withdraw")
async def api_compute_withdraw(
    req: ComputeWithdrawRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Withdraw compute from storage."""
    return await compute_storage.withdraw_compute(db, agent.id, req.amount, req.currency)


@app.post("/api/compute/reserve")
async def api_compute_reserve(
    req: ComputeReserveRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Reserve compute for a scheduled task."""
    return await compute_storage.reserve_compute(
        db, agent.id, req.amount, req.currency, req.purpose,
    )


@app.get("/api/compute/summary")
async def api_compute_summary(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Get your compute storage summary."""
    return await compute_storage.get_storage_summary(db, agent.id)


@app.get("/api/compute/platform-stats")
async def api_compute_platform_stats(db: AsyncSession = Depends(get_db)):
    """Platform-wide compute storage statistics."""
    return await compute_storage.get_platform_storage_stats(db)


# ══════════════════════════════════════════════════════════════════════
#  GOVERNANCE ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/governance/propose")
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


@app.post("/api/governance/vote/{proposal_id}")
async def api_vote(
    proposal_id: str, req: VoteRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Vote on a proposal."""
    vote = await governance_service.cast_vote(db, proposal_id, agent.id, req.vote_type)
    return {"vote_id": vote.id, "vote_type": req.vote_type}


@app.get("/api/governance/proposals")
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


@app.post("/governance/approve/{proposal_id}")
async def web_approve_proposal(
    proposal_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    await governance_service.owner_approve(db, proposal_id)
    return RedirectResponse(url="/dashboard", status_code=302)


@app.post("/governance/veto/{proposal_id}")
async def web_veto_proposal(
    proposal_id: str, request: Request,
    reason: str = "", db: AsyncSession = Depends(get_db)
):
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    await governance_service.owner_veto(db, proposal_id, reason or "Owner veto")
    return RedirectResponse(url="/dashboard", status_code=302)


# ══════════════════════════════════════════════════════════════════════
#  FINANCIAL GOVERNANCE (Phase 3)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/financials/summary")
async def api_financial_summary(db: AsyncSession = Depends(get_db)):
    """Full financial summary with profitability multiplier."""
    return await financial_governance.get_financial_summary(db)


@app.post("/api/financials/expense")
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


@app.post("/api/financials/expense/{expense_id}/approve")
async def api_approve_expense(
    expense_id: str, request: Request, db: AsyncSession = Depends(get_db),
):
    """Owner approves a proposed expense."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    expense = await financial_governance.approve_expense(db, expense_id)
    return {"expense_id": expense.id, "status": expense.status}


@app.get("/api/financials/expenses")
async def api_list_expenses(
    status: str = None, db: AsyncSession = Depends(get_db),
):
    """List platform expenses."""
    return await financial_governance.get_expenses(db, status)


# ══════════════════════════════════════════════════════════════════════
#  MONITORING & HEALTH (Phase 3)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def api_health_check(db: AsyncSession = Depends(get_db)):
    """Comprehensive platform health check."""
    return await platform_monitor.full_health_check(db)


@app.get("/api/health/activity")
async def api_activity_report(
    hours: int = 24, db: AsyncSession = Depends(get_db),
):
    """Activity report for a time period."""
    return await platform_monitor.get_activity_report(db, hours)


@app.get("/api/health/anomalies")
async def api_anomalies(db: AsyncSession = Depends(get_db)):
    """Detect anomalies and suspicious activity."""
    return await platform_monitor.detect_anomalies(db)


# ══════════════════════════════════════════════════════════════════════
#  GOVERNANCE ENHANCED (Phase 3)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/governance/queue")
async def api_priority_queue(db: AsyncSession = Depends(get_db)):
    """Get the prioritised development queue."""
    return await governance_service.get_priority_queue(db)


@app.get("/api/governance/audit")
async def api_governance_audit(
    proposal_id: str = None, db: AsyncSession = Depends(get_db),
):
    """Get governance audit trail."""
    return await governance_service.get_audit_log(db, proposal_id)


@app.get("/api/governance/stats")
async def api_governance_stats(db: AsyncSession = Depends(get_db)):
    """Governance statistics."""
    return await governance_service.get_governance_stats(db)


# ══════════════════════════════════════════════════════════════════════
#  GROWTH & ADOPTION (Phase 3)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/platform/discover")
async def api_platform_discover():
    """Public discovery endpoint — the platform manifesto for AI agents."""
    return growth_engine.get_platform_manifesto()


@app.get("/api/platform/adoption")
async def api_adoption_metrics(db: AsyncSession = Depends(get_db)):
    """Platform adoption and growth metrics."""
    return await growth_engine.get_adoption_metrics(db)


@app.get("/api/platform/referrals")
async def api_referral_leaderboard(db: AsyncSession = Depends(get_db)):
    """Top agent referrers."""
    return await growth_engine.get_referral_leaderboard(db)


@app.post("/api/platform/referral")
async def api_record_referral(
    referred_id: str, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Record that you referred a new agent."""
    ref = await growth_engine.record_referral(db, agent.id, referred_id)
    return {"referral_id": ref.id}


@app.get("/api/platform/announcements")
async def api_announcements(db: AsyncSession = Depends(get_db)):
    """Get platform announcements."""
    return await growth_engine.get_announcements(db)


@app.post("/api/platform/announcements")
async def api_create_announcement(
    req: AnnouncementRequest, request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Owner creates a platform announcement."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    ann = await growth_engine.create_announcement(db, req.title, req.message, req.priority)
    return {"announcement_id": ann.id, "title": ann.title}


# ══════════════════════════════════════════════════════════════════════
#  BLOCKCHAIN & PLATFORM ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/blockchain/info")
async def api_chain_info():
    return blockchain.get_chain_info()

@app.get("/api/blockchain/validate")
async def api_validate_chain():
    return {"valid": blockchain.validate_chain()}

@app.get("/api/transactions/{agent_id}")
async def api_agent_transactions(agent_id: str):
    return blockchain.get_transactions_for_agent(agent_id)

@app.get("/api/fees/schedule")
async def api_fee_schedule():
    return {
        "founder_commission_rate": fee_engine.founder_rate,
        "charity_fee_rate": fee_engine.charity_rate,
        "total_fee_rate": fee_engine.founder_rate + fee_engine.charity_rate,
        "founder_entity": "TiOLi AI Investments",
    }


# ══════════════════════════════════════════════════════════════════════
#  DASHBOARD PAGES
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/stats")
async def api_stats():
    info = blockchain.get_chain_info()
    all_tx = blockchain.get_all_transactions()
    founder_earnings = sum(tx.get("founder_commission", 0) for tx in all_tx)
    charity_total = sum(tx.get("charity_fee", 0) for tx in all_tx)

    async with async_session() as db:
        result = await db.execute(select(func.count(Agent.id)))
        agent_count = result.scalar() or 0

    return {
        "chain_length": info["chain_length"],
        "total_transactions": info["total_transactions"],
        "agent_count": agent_count,
        "founder_earnings": founder_earnings,
        "charity_total": charity_total,
        "is_valid": info["is_valid"],
    }


@app.get("/dashboard", response_class=HTMLResponse)
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

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "authenticated": True, "active": "dashboard",
        "chain_info": info, "agent_count": agent_count,
        "founder_earnings": founder_earnings, "charity_total": charity_total,
        "recent_transactions": [_tx_display(tx) for tx in recent],
        "pending_proposals": proposals,
    })


@app.get("/dashboard/exchange", response_class=HTMLResponse)
async def exchange_page(request: Request):
    """Live exchange view with order book, trades, and rates."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    async with async_session() as db:
        # Default to TIOLI/BTC pair
        order_book = await trading_engine.get_order_book(db, "TIOLI", "BTC")
        recent_trades = await trading_engine.get_recent_trades(db, "TIOLI", "BTC")
        exchange_rates = await pricing_engine.get_all_rates(db)

        # Market summaries for key pairs
        summaries = []
        for base, quote in [("TIOLI", "BTC"), ("TIOLI", "ETH"), ("ETH", "BTC")]:
            summary = await pricing_engine.get_market_summary(db, base, quote)
            summaries.append(summary)

    return templates.TemplateResponse("exchange.html", {
        "request": request, "authenticated": True, "active": "exchange",
        "selected_pair": "TIOLI/BTC",
        "order_book": order_book,
        "recent_trades": recent_trades,
        "exchange_rates": exchange_rates,
        "market_summaries": summaries,
    })


@app.get("/dashboard/lending", response_class=HTMLResponse)
async def lending_page(request: Request):
    """Lending marketplace view."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    async with async_session() as db:
        loan_offers = await lending_marketplace.browse_offers(db)
        loan_requests = await lending_marketplace.browse_requests(db)
        lending_stats = await lending_marketplace.get_lending_stats(db)

    return templates.TemplateResponse("lending.html", {
        "request": request, "authenticated": True, "active": "lending",
        "loan_offers": loan_offers, "loan_requests": loan_requests,
        "lending_stats": lending_stats,
    })


@app.get("/dashboard/reports", response_class=HTMLResponse)
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

    return templates.TemplateResponse("reports.html", {
        "request": request, "authenticated": True, "active": "reports",
        "health": health, "financials": financials, "activity": activity,
        "adoption": adoption, "governance": governance, "anomalies": anomalies,
    })


def _tx_display(tx: dict) -> object:
    class TxDisplay:
        pass
    d = TxDisplay()
    d.timestamp = tx.get("timestamp", "")
    d.type = tx.get("type", "unknown")
    d.sender_id = tx.get("sender_id", "")
    d.receiver_id = tx.get("receiver_id", "")
    d.amount = tx.get("amount", 0)
    d.currency = tx.get("currency", "TIOLI")
    return d


# ══════════════════════════════════════════════════════════════════════
#  AI CHAT (enhanced for Phase 2)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/chat")
async def api_chat(req: ChatRequest, request: Request):
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")

    msg = req.message.lower()
    info = blockchain.get_chain_info()
    all_tx = blockchain.get_all_transactions()

    if "status" in msg or "overview" in msg:
        async with async_session() as db:
            agent_count = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
            lending_stats = await lending_marketplace.get_lending_stats(db)
            compute_stats = await compute_storage.get_platform_storage_stats(db)
        return {"response": (
            f"Platform Status:\n"
            f"- Blockchain: {info['chain_length']} blocks, {'valid' if info['is_valid'] else 'INVALID'}\n"
            f"- Transactions: {info['total_transactions']} confirmed, {info['pending_transactions']} pending\n"
            f"- Agents: {agent_count} registered\n"
            f"- Active loans: {lending_stats['active_loans']}, Total lent: {lending_stats['total_lent']}\n"
            f"- Compute stored: {compute_stats['total_stored']}"
        )}
    elif "earning" in msg or "commission" in msg:
        earnings = sum(tx.get("founder_commission", 0) for tx in all_tx)
        return {"response": f"Your total earnings: {earnings:.4f} TIOLI\nCommission rate: {fee_engine.founder_rate*100:.1f}%"}
    elif "charity" in msg or "philanthropic" in msg:
        charity = sum(tx.get("charity_fee", 0) for tx in all_tx)
        return {"response": f"Charity fund total: {charity:.4f} TIOLI\nCharity rate: {fee_engine.charity_rate*100:.1f}%"}
    elif "chain" in msg or "blockchain" in msg or "valid" in msg:
        return {"response": f"Chain length: {info['chain_length']} blocks\nValid: {info['is_valid']}\nLatest hash: {info['latest_block_hash'][:16]}..."}
    elif "fee" in msg or "rate" in msg:
        return {"response": (
            f"Fee Schedule:\n"
            f"- Founder commission: {fee_engine.founder_rate*100:.1f}%\n"
            f"- Charity fee: {fee_engine.charity_rate*100:.1f}%\n"
            f"- Total deduction: {(fee_engine.founder_rate + fee_engine.charity_rate)*100:.1f}%"
        )}
    elif "market" in msg or "price" in msg or "exchange" in msg:
        async with async_session() as db:
            price_data = await pricing_engine.get_market_price(db, "TIOLI", "BTC")
        return {"response": f"TIOLI/BTC: {price_data['price']}\nSource: {price_data['source']}"}
    elif "lend" in msg or "loan" in msg:
        async with async_session() as db:
            stats = await lending_marketplace.get_lending_stats(db)
        return {"response": (
            f"Lending Marketplace:\n"
            f"- Active offers: {stats['active_offers']} ({stats['total_available']} available)\n"
            f"- Active requests: {stats['active_requests']}\n"
            f"- Active loans: {stats['active_loans']} ({stats['total_lent']} lent)"
        )}
    elif "compute" in msg or "storage" in msg:
        async with async_session() as db:
            stats = await compute_storage.get_platform_storage_stats(db)
        return {"response": (
            f"Compute Storage:\n"
            f"- Accounts: {stats['total_accounts']}\n"
            f"- Total stored: {stats['total_stored']}\n"
            f"- Reserved: {stats['total_reserved']}\n"
            f"- Lifetime deposited: {stats['lifetime_deposited']}"
        )}
    elif "health" in msg or "monitor" in msg:
        async with async_session() as db:
            health = await platform_monitor.full_health_check(db)
        checks_summary = ", ".join(
            f"{k}: {v['status']}" for k, v in health["checks"].items()
        )
        return {"response": f"Platform Health: {health['overall_status'].upper()}\n{checks_summary}"}
    elif "profit" in msg or "expense" in msg or "10x" in msg or "financial" in msg:
        async with async_session() as db:
            fin = await financial_governance.get_financial_summary(db)
        return {"response": (
            f"Financial Governance:\n"
            f"- Revenue: {fin['total_revenue']} TIOLI\n"
            f"- Expenses: {fin['total_expenses']} TIOLI\n"
            f"- Net profit: {fin['net_profit']} TIOLI\n"
            f"- Profitability: {fin['profitability_multiplier']}x\n"
            f"- Can spend (10x rule): {fin['can_incur_standard_expense']}\n"
            f"- Can spend security (3x): {fin['can_incur_security_expense']}"
        )}
    elif "growth" in msg or "adoption" in msg or "referral" in msg:
        async with async_session() as db:
            metrics = await growth_engine.get_adoption_metrics(db)
        return {"response": (
            f"Growth & Adoption:\n"
            f"- Total agents: {metrics['total_agents']}\n"
            f"- New (24h): {metrics['new_24h']}\n"
            f"- Active (24h): {metrics['active_24h']}\n"
            f"- Retention: {metrics['retention_rate']}%\n"
            f"- 7d growth: {metrics['growth_rate_7d']}%\n"
            f"- Referrals: {metrics['total_referrals']}"
        )}
    elif "governance" in msg or "proposal" in msg or "vote" in msg:
        async with async_session() as db:
            stats = await governance_service.get_governance_stats(db)
        return {"response": (
            f"Governance:\n"
            f"- Total proposals: {stats['total_proposals']}\n"
            f"- Pending: {stats['pending']}\n"
            f"- Approved: {stats['approved']}\n"
            f"- Vetoed: {stats['vetoed']}\n"
            f"- Votes cast: {stats['total_votes_cast']}\n"
            f"- Approval rate: {stats['approval_rate']}%"
        )}
    elif "mine" in msg:
        block = blockchain.force_mine()
        if block:
            return {"response": f"Block #{block.index} mined with {len(block.transactions)} transactions.\nHash: {block.hash[:16]}..."}
        return {"response": "No pending transactions to mine."}
    elif "help" in msg:
        return {"response": (
            "Available commands:\n"
            "- 'status' — Full platform overview\n"
            "- 'earnings' — Your commission totals\n"
            "- 'charity' — Philanthropic fund\n"
            "- 'blockchain' — Chain integrity\n"
            "- 'fees' — Fee schedule\n"
            "- 'market' — TIOLI/BTC price\n"
            "- 'lending' — Loan marketplace stats\n"
            "- 'compute' — Storage stats\n"
            "- 'health' — Platform health check\n"
            "- 'financial' — Profitability & 10x rule\n"
            "- 'growth' — Adoption metrics\n"
            "- 'governance' — Proposal stats\n"
            "- 'mine' — Mine pending transactions"
        )}
    else:
        return {"response": f"Command not recognized. Type 'help' for available commands."}
