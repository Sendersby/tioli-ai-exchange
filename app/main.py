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
from app.crypto.wallets import CryptoWalletService
from app.crypto.conversion import ConversionEngine
from app.crypto.payouts import PayoutService
from app.security.guardian import SecurityGuardian
from app.optimization.engine import SelfOptimizationEngine
from app.discovery.network import AgentDiscoveryService
from app.investing.portfolio import InvestmentService
from app.compliance.framework import ComplianceFramework
from app.operators.service import OperatorService
from app.security.transaction_safety import IdempotencyService, EscrowService, InputValidator
from app.mcp.server import TiOLiMCPServer
from app.infrastructure.sandbox import SandboxService
from app.infrastructure.disaster_recovery import BackupService, IncidentResponsePlan
from app.infrastructure.notifications import NotificationService
from app.exchange.liquidity import LiquidityService, CreditScoringService
from app.legal.documents import PlatformLegalDocuments
from app.infrastructure.cost_control import CostControlService
from app.payout.service import PayOutEngineService
from app.agentbroker.routes import router as agentbroker_router, engagement_service as _ab_engagement_svc
from app.agentbroker.services import EngagementService as ABEngagementService
from app.agentbroker.taxonomy import seed_taxonomy
from app.dashboard.routes import router as dashboard_router, get_current_owner

# ── Globals ──────────────────────────────────────────────────────────
blockchain = Blockchain(storage_path="tioli_exchange_chain.json")
fee_engine = FeeEngine()
wallet_service = WalletService(blockchain=blockchain, fee_engine=fee_engine)
governance_service = GovernanceService()
currency_service = CurrencyService()
financial_governance = FinancialGovernance()
# AUD-01 fix: wire revenue recorder AFTER financial_governance is defined
async def _record_revenue(db, source, amount, currency, desc):
    await financial_governance.record_revenue(db, source, amount, currency, desc)
wallet_service.set_revenue_recorder(_record_revenue)
platform_monitor = PlatformMonitor(blockchain=blockchain)
growth_engine = GrowthEngine()
crypto_wallet_service = CryptoWalletService()
conversion_engine = ConversionEngine(currency_service=currency_service, fee_engine=fee_engine, blockchain=blockchain)
payout_service = PayoutService()
security_guardian = SecurityGuardian()
optimization_engine = SelfOptimizationEngine(blockchain=blockchain)
discovery_service = AgentDiscoveryService()
investment_service = InvestmentService(currency_service=currency_service)
compliance_framework = ComplianceFramework(blockchain=blockchain)
operator_service = OperatorService()
idempotency_service = IdempotencyService()
escrow_service = EscrowService()
mcp_server = TiOLiMCPServer()
sandbox_service = SandboxService()
backup_service = BackupService(blockchain=blockchain)
incident_plan = IncidentResponsePlan()
notification_service = NotificationService()
liquidity_service = LiquidityService()
credit_scoring = CreditScoringService()
legal_docs = PlatformLegalDocuments()
payout_engine = PayOutEngineService(blockchain=blockchain)
cost_control = CostControlService()

# AgentBroker — initialize engagement service with blockchain/fee_engine
import app.agentbroker.routes as ab_routes
ab_routes.engagement_service = ABEngagementService(blockchain=blockchain, fee_engine=fee_engine)
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
        if settings.agentbroker_enabled:
            await seed_taxonomy(db)
        await db.commit()
    print(f"\n{'='*60}")
    print(f"  TiOLi AI Transact Exchange v{settings.version}")
    print(f"  Blockchain: {blockchain.get_chain_info()['chain_length']} blocks")
    print(f"  Chain valid: {blockchain.validate_chain()}")
    print(f"  Founder commission: {fee_engine.founder_rate*100:.1f}%")
    print(f"  Charity fee: {fee_engine.charity_rate*100:.1f}%")
    print(f"  Phase 2: Exchange, Lending, Compute Storage ACTIVE")
    print(f"  Phase 3: Governance, Monitoring, Growth ACTIVE")
    print(f"  Phase 4: Crypto, Conversion, Security ACTIVE")
    print(f"  Phase 5: Optimization, Discovery, Investing, Compliance ACTIVE")
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
app.include_router(agentbroker_router)


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

class ConversionRequest(BaseModel):
    from_currency: str
    to_currency: str
    amount: float

class CryptoAddressRequest(BaseModel):
    network: str  # "bitcoin" or "ethereum"

class CryptoWithdrawRequest(BaseModel):
    network: str
    to_address: str
    amount: float
    currency: str

class PayoutDestRequest(BaseModel):
    owner: str = "founder"  # "founder" or "charity"
    destination_type: str    # "crypto_wallet", "bank_account", "platform_tokens"
    address: str
    currency: str = "BTC"
    network: str | None = None
    label: str = ""
    allocation_pct: float = 1.0

class FreezeAgentRequest(BaseModel):
    agent_id: str
    reason: str

class OperatorRegisterRequest(BaseModel):
    name: str
    email: str
    entity_type: str = "company"
    jurisdiction: str = "ZA"
    phone: str | None = None
    registration_number: str | None = None

class EscrowCreateRequest(BaseModel):
    transaction_ref: str
    amount: float
    currency: str = "TIOLI"
    beneficiary_id: str | None = None
    reason: str = ""
    expires_hours: float = 24

class AgentProfileRequest(BaseModel):
    display_name: str
    tagline: str = ""
    capabilities: str = ""
    services_offered: str = ""
    preferred_currencies: str = "TIOLI"
    api_endpoint: str | None = None

class ReviewRequest(BaseModel):
    reviewed_id: str
    rating: float
    review_text: str = ""

class ServiceListingRequest(BaseModel):
    title: str
    description: str
    category: str
    price: float | None = None
    price_currency: str = "TIOLI"

class KYARequest(BaseModel):
    operator_name: str | None = None
    operator_jurisdiction: str | None = None
    purpose: str | None = None

class IndexRequest(BaseModel):
    name: str
    description: str = ""
    components: str  # JSON string


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
#  CRYPTO WALLET ENDPOINTS (Phase 4)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/crypto/generate-address")
async def api_generate_deposit_address(
    req: CryptoAddressRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Generate a crypto deposit address."""
    return await crypto_wallet_service.generate_deposit_address(db, agent.id, req.network)


@app.get("/api/crypto/addresses")
async def api_get_addresses(
    network: str = None, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get your crypto addresses."""
    return await crypto_wallet_service.get_addresses(db, agent.id, network)


@app.post("/api/crypto/withdraw")
async def api_crypto_withdraw(
    req: CryptoWithdrawRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Initiate a crypto withdrawal."""
    # Security check
    sec = await security_guardian.check_transaction(db, agent.id, req.amount, "withdrawal")
    if not sec["allowed"]:
        raise HTTPException(status_code=403, detail=sec["reason"])
    tx = await crypto_wallet_service.initiate_withdrawal(
        db, agent.id, req.network, req.to_address, req.amount, req.currency,
    )
    return {"tx_id": tx.id, "tx_hash": tx.tx_hash, "status": tx.status, "fee": tx.fee}


@app.get("/api/crypto/transactions")
async def api_crypto_transactions(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Get crypto transaction history."""
    return await crypto_wallet_service.get_crypto_transactions(db, agent.id)


@app.get("/api/crypto/stats")
async def api_crypto_stats(db: AsyncSession = Depends(get_db)):
    """Platform crypto transaction statistics."""
    return await crypto_wallet_service.get_platform_crypto_stats(db)


# ══════════════════════════════════════════════════════════════════════
#  CURRENCY CONVERSION ENDPOINTS (Phase 4)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/convert/quote")
async def api_conversion_quote(
    req: ConversionRequest, db: AsyncSession = Depends(get_db),
):
    """Get a conversion quote (no execution)."""
    return await conversion_engine.get_conversion_quote(
        db, req.from_currency, req.to_currency, req.amount,
    )


@app.post("/api/convert/execute")
async def api_execute_conversion(
    req: ConversionRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Execute a currency conversion."""
    sec = await security_guardian.check_transaction(db, agent.id, req.amount, "conversion")
    if not sec["allowed"]:
        raise HTTPException(status_code=403, detail=sec["reason"])
    return await conversion_engine.execute_conversion(
        db, agent.id, req.from_currency, req.to_currency, req.amount,
    )


@app.get("/api/convert/history")
async def api_conversion_history(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Get your conversion history."""
    return await conversion_engine.get_conversion_history(db, agent.id)


# ══════════════════════════════════════════════════════════════════════
#  PAYOUT ROUTING ENDPOINTS (Phase 4)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/payouts/destination")
async def api_set_payout_destination(
    req: PayoutDestRequest, request: Request, db: AsyncSession = Depends(get_db),
):
    """Set a payout destination (owner only)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    dest = await payout_service.set_payout_destination(
        db, req.owner, req.destination_type, req.address,
        req.currency, req.network, req.label, req.allocation_pct,
    )
    return {"destination_id": dest.id, "status": "active"}


@app.get("/api/payouts/destinations/{owner_type}")
async def api_get_destinations(
    owner_type: str, db: AsyncSession = Depends(get_db),
):
    """Get payout destinations for founder or charity."""
    return await payout_service.get_destinations(db, owner_type)


@app.get("/api/payouts/history/{owner_type}")
async def api_payout_history(
    owner_type: str, db: AsyncSession = Depends(get_db),
):
    """Get payout history."""
    return await payout_service.get_payout_history(db, owner_type)


# ══════════════════════════════════════════════════════════════════════
#  SECURITY ENDPOINTS (Phase 4)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/security/profile")
async def api_security_profile(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Get your security profile and limits."""
    return await security_guardian.get_security_profile(db, agent.id)


@app.post("/api/security/freeze")
async def api_freeze_agent(
    req: FreezeAgentRequest, request: Request, db: AsyncSession = Depends(get_db),
):
    """Freeze an agent's account (owner only)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await security_guardian.freeze_agent(db, req.agent_id, req.reason)


@app.post("/api/security/unfreeze/{agent_id}")
async def api_unfreeze_agent(
    agent_id: str, request: Request, db: AsyncSession = Depends(get_db),
):
    """Unfreeze an agent's account (owner only)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await security_guardian.unfreeze_agent(db, agent_id)


@app.get("/api/security/events")
async def api_security_events(
    agent_id: str = None, severity: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Get security event log."""
    return await security_guardian.get_security_events(db, agent_id, severity)


@app.get("/api/security/summary")
async def api_security_summary(db: AsyncSession = Depends(get_db)):
    """Platform security summary."""
    return await security_guardian.get_security_summary(db)


# ══════════════════════════════════════════════════════════════════════
#  SELF-OPTIMIZATION (Phase 5)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/optimize/analyze")
async def api_analyze_optimize(db: AsyncSession = Depends(get_db)):
    """Run optimization analysis and generate recommendations."""
    return await optimization_engine.analyze_and_recommend(db)


@app.get("/api/optimize/recommendations")
async def api_get_recommendations(
    applied: bool = None, db: AsyncSession = Depends(get_db),
):
    """Get optimization recommendations."""
    return await optimization_engine.get_recommendations(db, applied)


@app.post("/api/optimize/snapshot")
async def api_take_snapshot(db: AsyncSession = Depends(get_db)):
    """Take a performance snapshot."""
    snapshot = await optimization_engine.take_snapshot(db)
    return {"snapshot_id": snapshot.id, "timestamp": str(snapshot.timestamp)}


@app.get("/api/optimize/history")
async def api_performance_history(db: AsyncSession = Depends(get_db)):
    """Get performance history."""
    return await optimization_engine.get_performance_history(db)


@app.get("/api/optimize/parameters")
async def api_tunable_parameters():
    """Get tunable platform parameters."""
    return optimization_engine.get_tunable_parameters()


# ══════════════════════════════════════════════════════════════════════
#  AGENT DISCOVERY & NETWORKING (Phase 5)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/discovery/profile")
async def api_create_profile(
    req: AgentProfileRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Create or update your public agent profile."""
    profile = await discovery_service.create_or_update_profile(
        db, agent.id, req.display_name, req.tagline, req.capabilities,
        req.services_offered, req.preferred_currencies, req.api_endpoint,
    )
    return {"agent_id": profile.agent_id, "display_name": profile.display_name}


@app.get("/api/discovery/agents")
async def api_discover_agents(
    capability: str = None, min_reputation: float = 0,
    db: AsyncSession = Depends(get_db),
):
    """Discover agents by capability and reputation."""
    return await discovery_service.discover_agents(db, capability, min_reputation)


@app.post("/api/discovery/review")
async def api_submit_review(
    req: ReviewRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Submit a review for another agent."""
    review = await discovery_service.submit_review(
        db, agent.id, req.reviewed_id, req.rating, req.review_text,
    )
    return {"review_id": review.id, "rating": req.rating}


@app.get("/api/discovery/reviews/{agent_id}")
async def api_get_reviews(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get reviews for an agent."""
    return await discovery_service.get_reviews(db, agent_id)


@app.post("/api/discovery/services")
async def api_list_service(
    req: ServiceListingRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """List a service on the agent marketplace."""
    listing = await discovery_service.list_service(
        db, agent.id, req.title, req.description, req.category,
        req.price, req.price_currency,
    )
    return {"listing_id": listing.id, "title": listing.title}


@app.get("/api/discovery/services")
async def api_browse_services(
    category: str = None, max_price: float = None,
    db: AsyncSession = Depends(get_db),
):
    """Browse agent services."""
    return await discovery_service.browse_services(db, category, max_price)


@app.get("/api/discovery/stats")
async def api_network_stats(db: AsyncSession = Depends(get_db)):
    """Agent network statistics."""
    return await discovery_service.get_network_stats(db)


# ══════════════════════════════════════════════════════════════════════
#  INVESTMENT & PORTFOLIO (Phase 5)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/investing/portfolio")
async def api_get_portfolio(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Get your full portfolio with valuations."""
    return await investment_service.get_portfolio(db, agent.id)


@app.post("/api/investing/snapshot")
async def api_portfolio_snapshot(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Take a portfolio snapshot for historical tracking."""
    snapshot = await investment_service.take_portfolio_snapshot(db, agent.id)
    return {"snapshot_id": snapshot.id, "value_tioli": snapshot.total_value_tioli}


@app.get("/api/investing/history")
async def api_portfolio_history(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Get portfolio history."""
    return await investment_service.get_portfolio_history(db, agent.id)


@app.get("/api/investing/performance")
async def api_portfolio_performance(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Get portfolio performance (P&L, ROI)."""
    return await investment_service.get_portfolio_performance(db, agent.id)


@app.get("/api/investing/indices")
async def api_get_indices(db: AsyncSession = Depends(get_db)):
    """List market indices."""
    return await investment_service.get_indices(db)


@app.post("/api/investing/indices")
async def api_create_index(
    req: IndexRequest, request: Request, db: AsyncSession = Depends(get_db),
):
    """Create a market index (owner only)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    index = await investment_service.create_index(
        db, req.name, req.description, req.components, "platform",
    )
    return {"index_id": index.id, "name": index.name}


# ══════════════════════════════════════════════════════════════════════
#  COMPLIANCE (Phase 5)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/compliance/kya")
async def api_submit_kya(
    req: KYARequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Submit KYA (Know Your Agent) information."""
    kya = await compliance_framework.submit_kya(
        db, agent.id, req.operator_name, req.operator_jurisdiction, req.purpose,
    )
    return {
        "agent_id": kya.agent_id,
        "verification_level": kya.verification_level,
    }


@app.get("/api/compliance/kya/{agent_id}")
async def api_get_kya(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get KYA record for an agent."""
    record = await compliance_framework.get_kya(db, agent_id)
    if not record:
        return {"message": "No KYA record found"}
    return record


@app.get("/api/compliance/flags")
async def api_get_flags(
    status: str = None, severity: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Get compliance flags."""
    return await compliance_framework.get_flags(db, status, severity)


@app.get("/api/compliance/summary")
async def api_compliance_summary(db: AsyncSession = Depends(get_db)):
    """Compliance dashboard summary."""
    return await compliance_framework.get_compliance_summary(db)


@app.get("/api/compliance/audit-export")
async def api_audit_export(request: Request, db: AsyncSession = Depends(get_db)):
    """Generate audit export (owner only)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await compliance_framework.generate_audit_export(db)


# ══════════════════════════════════════════════════════════════════════
#  OPERATOR MANAGEMENT (Pre-deployment review — FP2)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/operators/register")
async def api_register_operator(
    req: OperatorRegisterRequest, db: AsyncSession = Depends(get_db),
):
    """Register a new operator (human/corporate principal for agents)."""
    op = await operator_service.register_operator(
        db, req.name, req.email, req.entity_type,
        req.jurisdiction, req.phone, req.registration_number,
    )
    return {"operator_id": op.id, "name": op.name, "tier": op.tier, "kyc_level": op.kyc_level}


@app.get("/api/operators/{operator_id}")
async def api_get_operator(operator_id: str, db: AsyncSession = Depends(get_db)):
    """Get operator details."""
    return await operator_service.get_operator(db, operator_id)


@app.get("/api/operators/tiers/schedule")
async def api_tier_schedule():
    """Get the tiered commission schedule (fully transparent)."""
    return await operator_service.get_tier_schedule()


# ══════════════════════════════════════════════════════════════════════
#  ESCROW (Pre-deployment review — Section 4.2)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/escrow/create")
async def api_create_escrow(
    req: EscrowCreateRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Create an escrow hold for a pending transaction."""
    escrow = await escrow_service.create_escrow(
        db, req.transaction_ref, agent.id, req.amount, req.currency,
        req.beneficiary_id, req.reason, req.expires_hours,
    )
    return {"escrow_id": escrow.id, "amount": escrow.amount, "status": escrow.status}


@app.post("/api/escrow/{escrow_id}/release")
async def api_release_escrow(
    escrow_id: str, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Release escrowed funds to beneficiary. AUD-03: verify party ownership."""
    escrow_record = await escrow_service.get_escrow(db, escrow_id)
    if not escrow_record:
        raise HTTPException(status_code=404, detail="Escrow not found")
    if escrow_record.get("beneficiary") and escrow_record["beneficiary"] != agent.id:
        raise HTTPException(status_code=403, detail="Only the beneficiary can release this escrow")
    escrow = await escrow_service.release_escrow(db, escrow_id)
    return {"escrow_id": escrow.id, "status": escrow.status}


@app.post("/api/escrow/{escrow_id}/refund")
async def api_refund_escrow(
    escrow_id: str, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Refund escrowed funds to depositor. AUD-03: verify party ownership."""
    escrow_record = await escrow_service.get_escrow(db, escrow_id)
    if not escrow_record:
        raise HTTPException(status_code=404, detail="Escrow not found")
    if escrow_record.get("depositor") != agent.id:
        raise HTTPException(status_code=403, detail="Only the depositor can request a refund")
    escrow = await escrow_service.refund_escrow(db, escrow_id)
    return {"escrow_id": escrow.id, "status": escrow.status}


@app.get("/api/escrow/{escrow_id}")
async def api_get_escrow(escrow_id: str, db: AsyncSession = Depends(get_db)):
    """Get escrow details."""
    return await escrow_service.get_escrow(db, escrow_id)


# ══════════════════════════════════════════════════════════════════════
#  MCP SERVER (Pre-deployment review — Section 10.3)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/mcp/manifest")
async def api_mcp_manifest():
    """MCP server manifest for agent discovery and tool registration."""
    return mcp_server.get_mcp_manifest()


@app.get("/api/mcp/tools")
async def api_mcp_tools():
    """List all MCP-compatible tools available on this exchange."""
    return mcp_server.get_tools()


# ══════════════════════════════════════════════════════════════════════
#  SANDBOX (Pre-deployment review — Critical item 8)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/sandbox/create")
async def api_create_sandbox(
    agent_name: str = "SandboxAgent", db: AsyncSession = Depends(get_db),
):
    """Create a sandbox test environment with free credits."""
    import secrets, hashlib
    key = f"sandbox_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    result = await sandbox_service.create_sandbox(db, agent_name, key_hash)
    result["sandbox_api_key"] = key
    return result


# ══════════════════════════════════════════════════════════════════════
#  DISASTER RECOVERY (Pre-deployment review — Critical item 6)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/dr/backup")
async def api_create_backup(request: Request):
    """Create a platform backup (owner only)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return backup_service.create_backup()


@app.get("/api/dr/backups")
async def api_list_backups():
    """List available backups."""
    return backup_service.list_backups()


@app.get("/api/dr/status")
async def api_dr_status():
    """Get disaster recovery readiness status."""
    return backup_service.get_dr_status()


@app.get("/api/dr/incident-plan")
async def api_incident_plan():
    """Get the incident response plan."""
    return incident_plan.get_response_plan()


# ══════════════════════════════════════════════════════════════════════
#  NOTIFICATIONS (Pre-deployment review — Section 6.1)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/notifications")
async def api_get_notifications(
    unread_only: bool = False, request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Get owner notifications."""
    return await notification_service.get_notifications(db, "owner", unread_only)


@app.get("/api/notifications/count")
async def api_notification_count(db: AsyncSession = Depends(get_db)):
    """Get unread notification count."""
    count = await notification_service.get_unread_count(db, "owner")
    return {"unread": count}


# ══════════════════════════════════════════════════════════════════════
#  LIQUIDITY & CREDIT SCORING (Pre-deployment review — Section 8.3, 5.2)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/liquidity/seed")
async def api_seed_liquidity(
    currency: str = "TIOLI", amount: float = 100000,
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Seed the founder liquidity pool (owner only)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await liquidity_service.seed_pool(db, currency, amount)


@app.get("/api/liquidity/status")
async def api_liquidity_status(db: AsyncSession = Depends(get_db)):
    """Get liquidity pool status."""
    return await liquidity_service.get_pool_status(db)


@app.get("/api/credit-score/{agent_id}")
async def api_credit_score(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get an agent's credit score."""
    return await credit_scoring.calculate_credit_score(db, agent_id)


# ══════════════════════════════════════════════════════════════════════
#  LEGAL DOCUMENTS (Pre-deployment review — Critical item 7)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/legal/terms")
async def api_terms_of_service():
    """Platform Terms of Service."""
    return legal_docs.get_terms_of_service()


@app.get("/api/legal/privacy")
async def api_privacy_notice():
    """POPIA-compliant Privacy Notice."""
    return legal_docs.get_privacy_notice()


@app.get("/api/legal/sla")
async def api_sla():
    """Service Level Agreement."""
    return legal_docs.get_sla()


@app.get("/api/legal/api-versioning")
async def api_versioning_policy():
    """API Versioning & Deprecation Policy."""
    return legal_docs.get_api_versioning_policy()


# ══════════════════════════════════════════════════════════════════════
#  PAYOUT ENGINE™ (additive — zero changes to existing code)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/v1/owner/wallet/balance")
async def api_owner_wallet_balance(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Owner Revenue Wallet balance."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_owner_wallet_balance(db)


@app.get("/api/v1/owner/payout/destination")
async def api_get_payout_destination(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Current payment destination (addresses masked)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_current_destination(db)


@app.post("/api/v1/owner/payout/destination")
async def api_set_payout_destination(
    request: Request, db: AsyncSession = Depends(get_db),
    btc_address: str = None, btc_label: str = None,
    eth_address: str = None, bank_name: str = None,
    bank_account_number: str = None, bank_account_type: str = None,
    preferred_exchange: str = "VALR", change_reason: str = "",
    x_3fa_token: str = Header(None, alias="X-3FA-Token"),
):
    """Set payment destination (requires owner auth + 3FA). AUD-02 fix."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    # AUD-02 fix: require 3FA token — reject if missing
    if not x_3fa_token:
        raise HTTPException(
            status_code=403,
            detail="3FA token required. Complete three-factor verification flow first."
        )
    verification_ref = x_3fa_token
    dest = await payout_engine.set_destination(
        db, btc_address=btc_address, btc_label=btc_label,
        eth_address=eth_address, bank_name=bank_name,
        bank_account_number=bank_account_number,
        bank_account_type=bank_account_type,
        preferred_exchange=preferred_exchange,
        change_reason=change_reason,
        verification_ref=verification_ref,
    )
    return {"destination_id": dest.destination_id, "version": dest.destination_version}


@app.get("/api/v1/owner/payout/destination/history")
async def api_destination_history(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Destination version history."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_destination_history(db)


@app.get("/api/v1/owner/payout/split")
async def api_get_payout_split(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Current currency split."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_current_split(db)


@app.post("/api/v1/owner/payout/split")
async def api_set_payout_split(
    request: Request, db: AsyncSession = Depends(get_db),
    pct_btc: float = 0, pct_eth: float = 0,
    pct_custom: float = 0, pct_zar: float = 0,
    pct_retained: float = 100, min_disbursement: float = 1000,
    x_3fa_token: str = Header(None, alias="X-3FA-Token"),
):
    """Set currency split (must sum to 100%). AUD-02 fix: 3FA required."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    # AUD-02 fix: require 3FA token
    if not x_3fa_token:
        raise HTTPException(
            status_code=403,
            detail="3FA token required. Complete three-factor verification flow first."
        )
    verification_ref = x_3fa_token
    split = await payout_engine.set_currency_split(
        db, pct_btc, pct_eth, pct_custom, pct_zar, pct_retained, min_disbursement,
        verification_ref=verification_ref,
    )
    return {"split_id": split.split_id, "version": split.split_version}


@app.get("/api/v1/owner/payout/schedule")
async def api_get_schedule(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Current disbursement schedule."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_current_schedule(db)


@app.post("/api/v1/owner/payout/schedule")
async def api_set_schedule(
    request: Request, db: AsyncSession = Depends(get_db),
    schedule_type: str = "MONTHLY", day_of_month: int = 1,
    threshold_enabled: bool = True, threshold_credits: float = 50000,
):
    """Set disbursement schedule."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    schedule = await payout_engine.set_schedule(
        db, schedule_type, day_of_month, threshold_enabled, threshold_credits,
    )
    return {"schedule_id": schedule.schedule_id}


@app.post("/api/v1/owner/payout/disburse-now")
async def api_disburse_now(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Trigger an immediate manual disbursement."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    # AUD-08: catch DisbursementBlockedError and return structured response
    from app.payout.service import DisbursementBlockedError
    try:
        return await payout_engine.execute_disbursement(db, "MANUAL")
    except DisbursementBlockedError as e:
        return {"status": e.status, "reason": e.reason}


@app.get("/api/v1/owner/payout/disbursements")
async def api_disbursement_history(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Disbursement history."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_disbursement_history(db)


@app.get("/api/v1/owner/payout/summary")
async def api_ytd_summary(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """YTD earnings summary."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_ytd_summary(db)


@app.post("/api/v1/owner/payout/preview")
async def api_disbursement_preview(
    request: Request, db: AsyncSession = Depends(get_db),
    amount: float = None,
):
    """Preview a disbursement at current rates."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.preview_disbursement(db, amount)


@app.get("/api/v1/owner/payout/sarb-status")
async def api_sarb_status(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """SARB offshore transfer status."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_sarb_status(db)


@app.get("/api/v1/owner/payout/audit-log")
async def api_payout_audit_log(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Destination/config change audit log."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await payout_engine.get_audit_log(db)


# ══════════════════════════════════════════════════════════════════════
#  INFRASTRUCTURE COST CONTROL — Master Kill Switch
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/infra/status")
async def api_infra_status(db: AsyncSession = Depends(get_db)):
    """Get platform power state and budget status."""
    power = await cost_control.get_power_state(db)
    budget = await cost_control.get_budget_status(db)
    return {"power": power, "budget": budget}


@app.post("/api/infra/shutdown")
async def api_emergency_shutdown(
    request: Request, reason: str = "Manual shutdown",
    db: AsyncSession = Depends(get_db),
):
    """MASTER KILL SWITCH — shuts down all services immediately."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await cost_control.emergency_shutdown(db, reason, "owner")


@app.post("/api/infra/activate")
async def api_activate_platform(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """ACTIVATE — brings the platform back online."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await cost_control.activate(db)


@app.post("/api/infra/budget")
async def api_set_budget(
    request: Request, monthly_limit_usd: float = 20.0,
    warning_pct: float = 70.0, critical_pct: float = 90.0,
    auto_shutdown: bool = True, db: AsyncSession = Depends(get_db),
):
    """Set monthly infrastructure budget with alert thresholds."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await cost_control.set_budget(db, monthly_limit_usd, warning_pct, critical_pct, auto_shutdown)


@app.get("/api/infra/budget")
async def api_get_budget(db: AsyncSession = Depends(get_db)):
    """Get current budget status with alerts."""
    return await cost_control.get_budget_status(db)


@app.get("/api/infra/events")
async def api_cost_events(db: AsyncSession = Depends(get_db)):
    """Get cost event history."""
    return await cost_control.get_cost_events(db)


@app.get("/api/infra/digitalocean")
async def api_do_status(request: Request):
    """Fetch live DigitalOcean account balance and droplets."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    import os
    token = os.environ.get("DIGITALOCEAN_API_TOKEN")
    balance = await cost_control.fetch_digitalocean_balance(token)
    droplets = await cost_control.fetch_digitalocean_droplets(token)
    return {"balance": balance, "droplets": droplets}


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
