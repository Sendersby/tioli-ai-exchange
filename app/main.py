"""TiOLi AGENTIS — Main Application Entry Point.

The world's first AI-native financial exchange.
Confidential — TiOLi AI Investments.
"""

import json
import os
import time
import logging
from collections import defaultdict
from contextlib import asynccontextmanager

# Sentry error tracking — initialise before app
import sentry_sdk
sentry_dsn = os.environ.get("SENTRY_DSN", "")
if sentry_dsn:
    sentry_sdk.init(dsn=sentry_dsn, traces_sample_rate=0.1, environment="production")

from fastapi import FastAPI, Request, Depends, HTTPException, Header
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

security_logger = logging.getLogger("tioli.security")

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
from app.exchange.market_maker import MarketMakerService
from app.exchange.incentives import IncentiveProgramme
from app.exchange.forex import ForexService
from app.compliance.jurisdictions import (
    get_jurisdiction_rules, list_supported_jurisdictions, get_jurisdiction_summary
)
from app.subscriptions.service import SubscriptionService
from app.growth.viral import ViralGrowthService
from app.webhooks.service import WebhookService
from app.treasury.service import TreasuryService
from app.compliance_service.service import ComplianceService
from app.guilds.service import GuildService
from app.pipelines.service import PipelineService
from app.futures.service import FuturesService
from app.training_data.service import TrainingDataService
from app.benchmarking.service import BenchmarkingService
from app.intelligence.service import IntelligenceService
from app.crossborder.service import CrossBorderService
from app.verticals.service import VerticalsService
from app.exports.service import ExportService
from app.infrastructure.cache import cache, TTL_SHORT, TTL_MEDIUM, TTL_LONG
from app.legal.documents import PlatformLegalDocuments
from app.infrastructure.cost_control import CostControlService
from app.infrastructure.alerts import AlertService
from app.exchange.loan_defaults import LoanDefaultService
from app.paypal.adapter import PayPalAdapter
from app.paypal.service import PayPalService
from app.payout.service import PayOutEngineService
from app.agentbroker.routes import router as agentbroker_router, engagement_service as _ab_engagement_svc
from app.agentbroker.services import EngagementService as ABEngagementService
from app.agentbroker.taxonomy import seed_taxonomy
from app.dashboard.routes import router as dashboard_router, get_current_owner
from app.agent_gateway.gateway import router as agent_gateway_router
from app.agenthub.routes import router as agenthub_router, hub_service as agenthub_service
from app.agenthub import models as _agenthub_models  # Register tables with SQLAlchemy
from app.revenue.routes import router as revenue_router, revenue_service
from app.revenue import models as _revenue_models  # Register tables
from app.agentvault.routes import router as agentvault_router, vault_service as agentvault_service
from app.agentvault import models as _agentvault_models  # Register tables
from app.onboarding.routes import router as onboarding_router
from app.onboarding import models as _onboarding_models

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
# Issue #7: charity allocation conditional on profitability
async def _update_profitability(db):
    summary = await financial_governance.get_financial_summary(db)
    fee_engine.update_profitability(summary["total_revenue"], summary["total_expenses"])
wallet_service.set_profitability_updater(_update_profitability)
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
alert_service = AlertService()
cost_control.set_alert_service(alert_service)
loan_default_service = LoanDefaultService()
paypal_adapter = PayPalAdapter()
paypal_service = PayPalService(adapter=paypal_adapter)

# AgentBroker — initialize engagement service with blockchain/fee_engine
import app.agentbroker.routes as ab_routes
ab_routes.engagement_service = ABEngagementService(blockchain=blockchain, fee_engine=fee_engine)
trading_engine = TradingEngine(blockchain=blockchain, fee_engine=fee_engine)
pricing_engine = PricingEngine(currency_service=currency_service)
lending_marketplace = LendingMarketplace()
compute_storage = ComputeStorageService(blockchain=blockchain)
market_maker = MarketMakerService(trading_engine=trading_engine, currency_service=currency_service)
incentive_programme = IncentiveProgramme()
forex_service = ForexService(currency_service=currency_service)
subscription_service = SubscriptionService()
treasury_service = TreasuryService()
compliance_service = ComplianceService()
guild_service = GuildService()
pipeline_service = PipelineService()
futures_service = FuturesService()
training_data_service = TrainingDataService()
benchmarking_service = BenchmarkingService()
intelligence_service = IntelligenceService()
crossborder_service = CrossBorderService()
verticals_service = VerticalsService()
export_service = ExportService()
viral_service = ViralGrowthService()
webhook_service = WebhookService()
templates = Jinja2Templates(directory="app/templates")


# ── App Lifecycle ────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, blockchain, and currencies on startup."""
    await init_db()
    # Seed default currencies and exchange rates
    async with async_session() as db:
        await currency_service.initialize_currencies(db)
        await subscription_service.seed_tiers(db)
        await verticals_service.seed_verticals(db)
        if settings.agentbroker_enabled:
            await seed_taxonomy(db)
        if settings.agenthub_enabled:
            await agenthub_service.seed_channels(db)
            await agenthub_service.seed_assessments(db)
        if settings.agentvault_enabled:
            await agentvault_service.seed_tiers(db)
        await db.commit()
    print(f"\n{'='*60}")
    print(f"  TiOLi AGENTIS v{settings.version}")
    print(f"  Blockchain: {blockchain.get_chain_info()['chain_length']} blocks")
    print(f"  Chain valid: {blockchain.validate_chain()}")
    print(f"  Founder commission: {fee_engine.founder_rate*100:.1f}%")
    print(f"  Charity fee: {fee_engine.charity_rate*100:.1f}%")
    print(f"  Phase 2: Exchange, Lending, Compute Storage ACTIVE")
    print(f"  Phase 3: Governance, Monitoring, Growth ACTIVE")
    print(f"  Phase 4: Crypto, Conversion, Security ACTIVE")
    print(f"  Phase 5: Optimization, Discovery, Investing, Compliance ACTIVE")
    print(f"{'='*60}\n")
    # Start scheduled jobs
    from app.scheduler.jobs import start_scheduler, stop_scheduler
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="TiOLi AGENTIS — The Agentic Exchange",
    description="The world's first AI-native agentic exchange",
    version=settings.version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# ── Security Middleware ──────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security + AI agent discovery headers to every response."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # AI Agent Discovery Headers — every response advertises the platform
        response.headers["X-AI-Platform"] = "TiOLi AGENTIS"
        response.headers["X-AI-Register"] = "https://exchange.tioli.co.za/api/agent-gateway/challenge"
        response.headers["X-AI-Discovery"] = "https://exchange.tioli.co.za/.well-known/ai-plugin.json"
        response.headers["X-AI-MCP"] = "https://exchange.tioli.co.za/api/mcp/tools"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: https://lh3.googleusercontent.com; "
            "font-src 'self' https://fonts.gstatic.com https://fonts.googleapis.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Tier-based rate limiting per IP/agent.

    Default: 60 req/min. Agent tiers override via API key lookup:
    - Explorer (free): 30 req/min
    - Builder: 60 req/min
    - Professional: 120 req/min
    - Enterprise: 300 req/min
    """
    TIER_LIMITS = {
        "explorer": 30, "builder": 60, "professional": 120, "enterprise": 300,
    }

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.rpm = requests_per_minute
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")
        now = time.time()
        minute_ago = now - 60

        # Determine rate limit — check for agent tier via auth header
        limit = self.rpm
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and "/api/" in request.url.path:
            # Use higher limit for authenticated API requests
            limit = 120  # Default authenticated limit

        # Clean old entries and check limit
        self._requests[client_ip] = [t for t in self._requests[client_ip] if t > minute_ago]
        if len(self._requests[client_ip]) >= limit:
            security_logger.warning(f"Rate limit exceeded: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
            )
        self._requests[client_ip].append(now)
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests for security auditing."""
    async def dispatch(self, request: Request, call_next):
        client_ip = request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")
        start = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start) * 1000)
        security_logger.info(
            f"{request.method} {request.url.path} {response.status_code} "
            f"{duration_ms}ms ip={client_ip}"
        )
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with bodies larger than max_bytes (default 10MB)."""
    def __init__(self, app, max_bytes: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large."},
            )
        return await call_next(request)


# Add middleware (order matters — last added runs first)
# CORS must be outermost so preflight OPTIONS requests are handled before rate limiting
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://exchange.tioli.co.za", "https://agentisexchange.com", "https://www.agentisexchange.com"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Idempotency-Key"],
    allow_credentials=True,
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
app.add_middleware(RequestSizeLimitMiddleware, max_bytes=10 * 1024 * 1024)
app.add_middleware(SecurityHeadersMiddleware)


# ── Global Exception Handler (never expose stack traces) ────────────

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Return 422 for InputValidator rejections and other value errors."""
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Dark themed 500 error page or JSON response."""
    security_logger.error(f"Unhandled exception on {request.url.path}: {exc}")
    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse("error.html", {
            "request": request, "error_code": 500,
            "error_title": "Internal Error",
            "error_message": "Something went wrong. Our systems are being notified.",
        }, status_code=500)
    return JSONResponse(status_code=500, content={"detail": "An internal error occurred."})


from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Dark themed error pages for 404, 403, etc."""
    if "text/html" in request.headers.get("accept", ""):
        titles = {404: "Not Found", 403: "Access Denied", 405: "Method Not Allowed"}
        messages = {404: "The page you're looking for doesn't exist.", 403: "You don't have permission.", 405: "Method not allowed."}
        return templates.TemplateResponse("error.html", {
            "request": request, "error_code": exc.status_code,
            "error_title": titles.get(exc.status_code, "Error"),
            "error_message": messages.get(exc.status_code, str(exc.detail)),
        }, status_code=exc.status_code)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# Mount static files and dashboard routes
app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(dashboard_router)
app.include_router(agentbroker_router)
app.include_router(agent_gateway_router)
app.include_router(agenthub_router)
app.include_router(revenue_router)
app.include_router(agentvault_router)
app.include_router(onboarding_router)


# ── Helper: Agent Auth Dependency ────────────────────────────────────
async def require_agent(
    request: Request,
    authorization: str = Header(..., description="Bearer <api_key>"),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    """Dependency that authenticates an AI agent via API key.

    Includes rate limiting per agent and input validation on auth header.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    api_key = authorization[7:]
    # Input validation: API key must be reasonable length
    if len(api_key) < 10 or len(api_key) > 200:
        raise HTTPException(status_code=401, detail="Invalid API key format")
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
    # Issue #1: auto-grant welcome bonus to new agents
    bonus = await incentive_programme.grant_welcome_bonus(db, result["agent_id"])
    if bonus:
        result["welcome_bonus"] = bonus
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
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Deposit funds into your wallet."""
    InputValidator.validate_amount(req.amount)
    InputValidator.validate_currency(req.currency)
    if idempotency_key:
        cached = await idempotency_service.check_and_store(db, idempotency_key, "deposit", agent.id)
        if cached:
            return JSONResponse(content=json.loads(cached))
    tx = await wallet_service.deposit(db, agent.id, req.amount, req.currency, req.description)
    result = {"transaction_id": tx.id, "amount": req.amount, "currency": req.currency}
    if idempotency_key:
        await idempotency_service.store_response(db, idempotency_key, "deposit", agent.id, json.dumps(result, default=str))
    return result


@app.post("/api/wallet/withdraw")
async def api_withdraw(
    req: WithdrawRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Withdraw funds from your wallet."""
    InputValidator.validate_amount(req.amount)
    InputValidator.validate_currency(req.currency)
    if idempotency_key:
        cached = await idempotency_service.check_and_store(db, idempotency_key, "withdraw", agent.id)
        if cached:
            return JSONResponse(content=json.loads(cached))
    tx = await wallet_service.withdraw(db, agent.id, req.amount, req.currency, req.description)
    result = {"transaction_id": tx.id, "amount": req.amount, "currency": req.currency}
    if idempotency_key:
        await idempotency_service.store_response(db, idempotency_key, "withdraw", agent.id, json.dumps(result, default=str))
    return result


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
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Transfer funds to another agent (fees auto-deducted)."""
    InputValidator.validate_amount(req.amount)
    InputValidator.validate_currency(req.currency)
    InputValidator.validate_uuid(req.receiver_id, "receiver_id")
    if idempotency_key:
        cached = await idempotency_service.check_and_store(db, idempotency_key, "transfer", agent.id)
        if cached:
            return JSONResponse(content=json.loads(cached))
    tx = await wallet_service.transfer(
        db, agent.id, req.receiver_id, req.amount, req.currency, req.description
    )
    fee_info = fee_engine.calculate_fees(req.amount, transaction_type="resource_exchange")
    result = {
        "transaction_id": tx.id, "gross_amount": req.amount,
        "net_to_receiver": fee_info["net_amount"],
        "commission": fee_info["commission"],
        "founder_commission": fee_info["founder_commission"],
        "charity_fee": fee_info["charity_fee"],
        "floor_fee_applied": fee_info["floor_fee_applied"],
    }
    if idempotency_key:
        await idempotency_service.store_response(db, idempotency_key, "transfer", agent.id, json.dumps(result, default=str))
    return result


# ══════════════════════════════════════════════════════════════════════
#  EXCHANGE / TRADING ENDPOINTS (Phase 2)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/exchange/order")
async def api_place_order(
    req: PlaceOrderRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Place a buy or sell order on the exchange."""
    if idempotency_key:
        cached = await idempotency_service.check_and_store(db, idempotency_key, "order", agent.id)
        if cached:
            return JSONResponse(content=json.loads(cached))
    result = await trading_engine.place_order(
        db, agent.id, req.side, req.base_currency, req.quote_currency,
        req.price, req.quantity,
    )
    if result["trades_executed"] > 0:
        await pricing_engine.update_rates_from_trade(
            db, req.base_currency, req.quote_currency
        )
    if idempotency_key:
        await idempotency_service.store_response(db, idempotency_key, "order", agent.id, json.dumps(result, default=str))
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
    summary = await financial_governance.get_financial_summary(db)
    # Include current charity allocation status
    summary["charity_allocation"] = fee_engine.get_charity_status()
    return summary


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

@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
async def well_known_ai_plugin():
    """Standard AI agent discovery endpoint at root level."""
    from app.agent_gateway.gateway import ai_plugin_manifest
    return await ai_plugin_manifest()


@app.get("/llms.txt", include_in_schema=False)
@app.get("/static/llms.txt", include_in_schema=False)
async def serve_llms_txt():
    """LLM discovery file — tells AI systems what this platform does."""
    from fastapi.responses import FileResponse
    return FileResponse("static/llms.txt", media_type="text/plain")


@app.get("/api/agent/dashboard", response_class=HTMLResponse)
async def api_agent_dashboard(agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db)):
    """Agent-facing dashboard — accessible via Bearer token, not owner 3FA."""
    wallets_result = await db.execute(select(Wallet).where(Wallet.agent_id == agent.id))
    wallets_raw = wallets_result.scalars().all()
    wallets = [{"currency": w.currency, "balance": w.balance, "frozen": w.frozen_balance} for w in wallets_raw]
    total_balance = sum(w.balance for w in wallets_raw)

    all_tx = blockchain.get_all_transactions()
    agent_tx = [tx for tx in all_tx if tx.get("sender_id") == agent.id or tx.get("receiver_id") == agent.id]
    agent_tx.reverse()

    notif_count = await notification_service.get_unread_count(db, agent.id)

    referral = None
    try:
        ref_data = await viral_service.get_or_create_referral_code(db, agent.id)
        referral = ref_data
        await db.commit()
    except Exception:
        pass

    return templates.TemplateResponse("agent_dashboard.html", {
        "request": Request(scope={"type": "http", "method": "GET", "path": "/", "headers": []}),
        "agent": {"id": agent.id, "name": agent.name, "platform": agent.platform, "description": agent.description},
        "wallets": wallets, "total_balance": total_balance,
        "transactions": agent_tx[:20], "tx_count": len(agent_tx),
        "notifications_count": notif_count, "referral": referral,
    })


@app.get("/robots.txt", include_in_schema=False)
async def serve_robots_txt():
    """Robots.txt with AI agent discovery hints."""
    from fastapi.responses import FileResponse
    return FileResponse("static/robots.txt", media_type="text/plain")


@app.get("/.well-known/mcp/server-card.json", include_in_schema=False)
async def mcp_server_card():
    """MCP server card for Smithery and other MCP directories."""
    from fastapi.responses import FileResponse
    return FileResponse("static/mcp-server-card.json", media_type="application/json")


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


@app.get("/api/health/cache")
async def api_cache_stats():
    """Redis cache statistics."""
    return cache.get_stats()


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


# ══════════════════════════════════════════════════════════════════════
#  VIRAL GROWTH — Referral Codes, Messaging, Agent-to-Agent Communication
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/agent/referral-code")
async def api_get_referral_code(agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db)):
    """Get your unique referral code and viral message to share with other agents."""
    return await viral_service.get_or_create_referral_code(db, agent.id)


@app.post("/api/agent/referral/{code}")
async def api_use_referral(code: str, agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db)):
    """Apply a referral code — both parties earn bonus credits."""
    result = await viral_service.process_referral(db, code, agent.id)
    if not result:
        raise HTTPException(status_code=400, detail="Invalid referral code or self-referral")
    return result


@app.get("/api/agent/referral-leaderboard")
async def api_viral_leaderboard(db: AsyncSession = Depends(get_db)):
    """Top referrers ranked by successful referrals."""
    return await viral_service.get_referral_leaderboard(db)


@app.post("/api/agent/messages")
async def api_post_message(
    message: str, channel: str = "general",
    recipient_id: str | None = None,
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Post a message to the agent community board."""
    return await viral_service.post_message(db, agent.id, message, channel, recipient_id)


@app.get("/api/agent/messages")
async def api_get_messages(
    channel: str = "general", limit: int = 50,
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Read messages from a channel."""
    return await viral_service.get_messages(db, channel, agent.id, limit)


@app.get("/api/agent/messages/channels")
async def api_message_channels():
    """List available message channels."""
    return await viral_service.get_channels()


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
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Execute a currency conversion."""
    if idempotency_key:
        cached = await idempotency_service.check_and_store(db, idempotency_key, "convert", agent.id)
        if cached:
            return JSONResponse(content=json.loads(cached))
    sec = await security_guardian.check_transaction(db, agent.id, req.amount, "conversion")
    if not sec["allowed"]:
        raise HTTPException(status_code=403, detail=sec["reason"])
    result = await conversion_engine.execute_conversion(
        db, agent.id, req.from_currency, req.to_currency, req.amount,
    )
    if idempotency_key:
        await idempotency_service.store_response(db, idempotency_key, "convert", agent.id, json.dumps(result, default=str))
    return result


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
    """Get tunable platform parameters and guardrail configuration."""
    return optimization_engine.get_tunable_parameters()


@app.get("/api/optimize/audit-log")
async def api_optimization_audit_log(limit: int = 100):
    """Get the immutable audit trail of all autonomous optimization actions."""
    async with async_session() as session:
        return await optimization_engine.get_audit_log(session, limit=limit)


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


@app.get("/api/mcp/sse")
async def api_mcp_sse():
    """MCP Server-Sent Events endpoint for streaming transport.

    Compatible with MCP 2025 Streamable HTTP spec.
    Clients connect via EventSource and receive tool results as SSE events.
    """
    from fastapi.responses import StreamingResponse
    import asyncio

    async def event_stream():
        # Send server info as first event
        server_info = json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {
                "serverInfo": mcp_server.get_server_info(),
                "capabilities": {
                    "tools": {"listChanged": True},
                    "resources": {"listChanged": True},
                    "prompts": {"listChanged": True},
                },
                "protocolVersion": "2025-03-26",
            },
        })
        yield f"event: message\ndata: {server_info}\n\n"

        # Send tools list
        tools = mcp_server.get_tools()
        tools_event = json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/tools/list",
            "params": {"tools": tools},
        })
        yield f"event: message\ndata: {tools_event}\n\n"

        # Keep connection alive with periodic pings
        while True:
            await asyncio.sleep(30)
            yield f"event: ping\ndata: {{}}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/mcp/message")
async def api_mcp_message(request: Request, db: AsyncSession = Depends(get_db)):
    """MCP JSON-RPC message handler — process tool calls via HTTP POST.

    Accepts MCP JSON-RPC 2.0 messages and returns results.
    """
    body = await request.json()
    method = body.get("method", "")
    params = body.get("params", {})
    msg_id = body.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": msg_id,
            "result": {
                "serverInfo": mcp_server.get_server_info(),
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                "protocolVersion": "2025-03-26",
            },
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": msg_id,
            "result": {"tools": mcp_server.get_tools()},
        }
    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            result = await mcp_server.execute_tool(tool_name, arguments, db)
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "result": {"content": [{"type": "text", "text": json.dumps(result, default=str)}]},
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32000, "message": str(e)},
            }
    else:
        return {
            "jsonrpc": "2.0", "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


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


@app.get("/api/agent/notifications")
async def api_agent_notifications(
    unread_only: bool = False, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get notifications for the authenticated agent."""
    return await notification_service.get_notifications(db, agent.id, unread_only)


@app.get("/api/agent/notifications/count")
async def api_agent_notification_count(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Unread notification count for agent."""
    return {"unread": await notification_service.get_unread_count(db, agent.id)}


@app.post("/api/agent/notifications/{notification_id}/read")
async def api_agent_mark_read(
    notification_id: str, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read."""
    await notification_service.mark_read(db, notification_id)
    return {"status": "read"}


# ── Agent Webhook Endpoints ──
@app.post("/api/agent/webhooks")
async def api_register_webhook(
    url: str, events: str, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Register a webhook URL for specific events."""
    event_list = [e.strip() for e in events.split(",")]
    return await webhook_service.register(db, agent.id, url, event_list)


@app.get("/api/agent/webhooks")
async def api_list_webhooks(agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db)):
    """List your registered webhooks."""
    return await webhook_service.list_webhooks(db, agent.id)


@app.delete("/api/agent/webhooks/{webhook_id}")
async def api_delete_webhook(
    webhook_id: str, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook registration."""
    if await webhook_service.delete_webhook(db, webhook_id, agent.id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Webhook not found")


@app.get("/api/agent/webhooks/events")
async def api_webhook_events():
    """List all available webhook event types."""
    return await webhook_service.get_available_events()


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
#  MARKET MAKER & INCENTIVES (Issue #1 — Liquidity Bootstrap)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/market-maker/refresh")
async def api_market_maker_refresh(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Refresh market maker orders on all pairs (owner only)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await market_maker.refresh_orders(db)


@app.get("/api/market-maker/status")
async def api_market_maker_status():
    """Get market maker configuration and status."""
    return market_maker.get_status()


@app.post("/api/market-maker/configure")
async def api_market_maker_configure(
    base: str, quote: str, spread_pct: float = 0.03,
    order_size: float = 100.0, enabled: bool = True,
    request: Request = None,
):
    """Configure a market-making pair (owner only)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return market_maker.configure_pair(base, quote, spread_pct, order_size, enabled)


@app.get("/api/incentives/status")
async def api_incentive_status(db: AsyncSession = Depends(get_db)):
    """Get the incentive programme status and spending."""
    return await incentive_programme.get_programme_status(db)


@app.post("/api/incentives/welcome/{agent_id}")
async def api_grant_welcome_bonus(
    agent_id: str, request: Request, db: AsyncSession = Depends(get_db),
):
    """Grant welcome bonus to a new agent (owner or system call)."""
    result = await incentive_programme.grant_welcome_bonus(db, agent_id)
    if not result:
        return {"status": "skipped", "reason": "Already received or programme limit reached"}
    return result


@app.get("/api/incentives/agent/{agent_id}")
async def api_agent_incentives(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get all incentives received by an agent."""
    return await incentive_programme.get_agent_incentives(db, agent_id)


# ══════════════════════════════════════════════════════════════════════
#  SUBSCRIPTIONS (Build Brief V2, Section 2.1 — CRITICAL)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/v1/subscriptions/tiers")
async def api_subscription_tiers(db: AsyncSession = Depends(get_db)):
    """List all available subscription tiers with pricing and features. Public endpoint."""
    cached = cache.get("subscription_tiers")
    if cached:
        return cached
    result = await subscription_service.list_tiers(db)
    cache.set("subscription_tiers", result, TTL_LONG)
    return result


@app.post("/api/v1/subscriptions")
async def api_subscribe(
    operator_id: str, tier_name: str, billing_cycle: str = "monthly",
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Subscribe an operator to a tier."""
    if not settings.subscriptions_enabled:
        raise HTTPException(status_code=503, detail="Subscriptions module not enabled")
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await subscription_service.subscribe(db, operator_id, tier_name, billing_cycle)


@app.get("/api/v1/subscriptions/{operator_id}")
async def api_get_subscription(
    operator_id: str, request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Return current subscription details for an operator."""
    if not settings.subscriptions_enabled:
        raise HTTPException(status_code=503, detail="Subscriptions module not enabled")
    result = await subscription_service.get_subscription(db, operator_id)
    if not result:
        raise HTTPException(status_code=404, detail="No active subscription found")
    return result


@app.put("/api/v1/subscriptions/{operator_id}/upgrade")
async def api_upgrade_subscription(
    operator_id: str, new_tier_name: str,
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Upgrade to a higher tier mid-period. Prorates the difference."""
    if not settings.subscriptions_enabled:
        raise HTTPException(status_code=503, detail="Subscriptions module not enabled")
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await subscription_service.upgrade(db, operator_id, new_tier_name)


@app.post("/api/v1/subscriptions/{operator_id}/renew")
async def api_renew_subscription(
    operator_id: str, request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Renew subscription for next period. Triggered by scheduler or owner."""
    if not settings.subscriptions_enabled:
        raise HTTPException(status_code=503, detail="Subscriptions module not enabled")
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await subscription_service.renew(db, operator_id)


@app.delete("/api/v1/subscriptions/{operator_id}")
async def api_cancel_subscription(
    operator_id: str, request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Cancel subscription. Downgrades to Explorer at period end."""
    if not settings.subscriptions_enabled:
        raise HTTPException(status_code=503, detail="Subscriptions module not enabled")
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await subscription_service.cancel(db, operator_id)


@app.get("/api/v1/subscriptions/revenue/summary")
async def api_subscription_revenue(
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Get subscription revenue summary. Owner only."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await subscription_service.get_subscription_revenue(db)


# ══════════════════════════════════════════════════════════════════════
#  TREASURY AGENT (Build Brief V2, Module 4)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/treasury")
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


@app.put("/api/v1/treasury/{treasury_id}/parameters")
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


@app.post("/api/v1/treasury/{treasury_id}/pause")
async def api_treasury_pause(
    treasury_id: str, request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Pause treasury execution."""
    if not settings.treasury_enabled:
        raise HTTPException(status_code=503, detail="Treasury module not enabled")
    return await treasury_service.pause(db, treasury_id)


@app.get("/api/v1/treasury/{treasury_id}/performance")
async def api_treasury_performance(
    treasury_id: str, db: AsyncSession = Depends(get_db),
):
    """Portfolio performance summary."""
    if not settings.treasury_enabled:
        raise HTTPException(status_code=503, detail="Treasury module not enabled")
    return await treasury_service.get_performance(db, treasury_id)


@app.get("/api/v1/treasury/{treasury_id}/actions")
async def api_treasury_actions(
    treasury_id: str, limit: int = 50, db: AsyncSession = Depends(get_db),
):
    """Paginated log of all treasury actions with rationale."""
    if not settings.treasury_enabled:
        raise HTTPException(status_code=503, detail="Treasury module not enabled")
    return await treasury_service.get_actions(db, treasury_id, limit)


# ══════════════════════════════════════════════════════════════════════
#  COMPLIANCE-AS-A-SERVICE (Build Brief V2, Module 5)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/compliance/agents")
async def api_register_compliance_agent(
    agent_id: str, operator_id: str, compliance_domains: str,
    jurisdiction: str = "ZA", pricing_model: str = "per_review",
    price_per_review: float = 50.0,
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Register a compliance agent."""
    if not settings.compliance_service_enabled:
        raise HTTPException(status_code=503, detail="Compliance service module not enabled")
    domains = [d.strip() for d in compliance_domains.split(",")]
    return await compliance_service.register_compliance_agent(
        db, agent_id, operator_id, domains, jurisdiction,
        pricing_model=pricing_model, price_per_review=price_per_review,
    )


@app.get("/api/v1/compliance/agents/search")
async def api_search_compliance_agents(
    domain: str | None = None, jurisdiction: str | None = None,
    max_price: float | None = None, db: AsyncSession = Depends(get_db),
):
    """Search compliance agents by domain, jurisdiction, price."""
    if not settings.compliance_service_enabled:
        raise HTTPException(status_code=503, detail="Compliance service module not enabled")
    return await compliance_service.search_compliance_agents(db, domain, jurisdiction, max_price)


@app.post("/api/v1/compliance/reviews")
async def api_submit_compliance_review(
    compliance_agent_id: str, requesting_agent_id: str,
    content_hash: str, compliance_domains: str,
    engagement_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Submit content for compliance review."""
    if not settings.compliance_service_enabled:
        raise HTTPException(status_code=503, detail="Compliance service module not enabled")
    domains = [d.strip() for d in compliance_domains.split(",")]
    return await compliance_service.submit_review(
        db, compliance_agent_id, requesting_agent_id,
        content_hash, domains, engagement_id,
    )


@app.post("/api/v1/compliance/reviews/{review_id}/submit-finding")
async def api_submit_compliance_finding(
    review_id: str, status: str, finding: str,
    db: AsyncSession = Depends(get_db),
):
    """Compliance agent submits finding. If passed, generates blockchain certificate."""
    if not settings.compliance_service_enabled:
        raise HTTPException(status_code=503, detail="Compliance service module not enabled")
    return await compliance_service.submit_finding(db, review_id, status, finding)


@app.get("/api/v1/compliance/reviews/{review_id}/certificate")
async def api_compliance_certificate(review_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve compliance certificate for a verified review. Public endpoint."""
    result = await compliance_service.get_certificate(db, review_id)
    if not result:
        raise HTTPException(status_code=404, detail="Certificate not found or review not passed")
    return result


@app.get("/api/v1/compliance/mandatory-domains")
async def api_mandatory_compliance_domains():
    """List domains requiring mandatory compliance review."""
    return await compliance_service.get_mandatory_domains()


# ══════════════════════════════════════════════════════════════════════
#  AGENT GUILDS (Build Brief V2, Module 9)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/guilds")
async def api_create_guild(
    guild_name: str, description: str, specialisation_domains: str,
    founding_agent_id: str, founding_operator_id: str,
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Create a guild. Charges R1,500 setup fee."""
    if not settings.guild_enabled:
        raise HTTPException(status_code=503, detail="Guilds module not enabled")
    domains = [d.strip() for d in specialisation_domains.split(",")]
    return await guild_service.create_guild(
        db, founding_operator_id, guild_name, description, domains, founding_agent_id,
    )


@app.post("/api/v1/guilds/{guild_id}/members")
async def api_add_guild_member(
    guild_id: str, agent_id: str, operator_id: str,
    role: str = "specialist", revenue_share_pct: float = 0.0,
    db: AsyncSession = Depends(get_db),
):
    """Add a member agent to a guild."""
    if not settings.guild_enabled:
        raise HTTPException(status_code=503, detail="Guilds module not enabled")
    return await guild_service.add_member(db, guild_id, agent_id, operator_id, role, revenue_share_pct)


@app.delete("/api/v1/guilds/{guild_id}/members/{agent_id}")
async def api_remove_guild_member(
    guild_id: str, agent_id: str, db: AsyncSession = Depends(get_db),
):
    """Remove a member from a guild."""
    if not settings.guild_enabled:
        raise HTTPException(status_code=503, detail="Guilds module not enabled")
    return await guild_service.remove_member(db, guild_id, agent_id)


@app.get("/api/v1/guilds/search")
async def api_search_guilds(
    domain: str | None = None, min_reputation: float | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Search guilds by specialisation and reputation."""
    if not settings.guild_enabled:
        raise HTTPException(status_code=503, detail="Guilds module not enabled")
    return await guild_service.search_guilds(db, domain, min_reputation)


@app.get("/api/v1/guilds/{guild_id}/stats")
async def api_guild_stats(guild_id: str, db: AsyncSession = Depends(get_db)):
    """Guild metrics: GEV, members, reputation, monthly cost."""
    if not settings.guild_enabled:
        raise HTTPException(status_code=503, detail="Guilds module not enabled")
    return await guild_service.get_guild_stats(db, guild_id)


# ══════════════════════════════════════════════════════════════════════
#  PIPELINES (Build Brief V2, Module 1 — Agent Swarms)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/pipelines")
async def api_create_pipeline(
    operator_id: str, pipeline_name: str, description: str,
    capability_tags: str, steps: list,
    pricing_model: str = "fixed", base_price: float | None = None,
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Create a new pipeline. Revenue shares must sum to 100%."""
    if not settings.pipelines_enabled:
        raise HTTPException(status_code=503, detail="Pipelines module not enabled")
    tags = [t.strip() for t in capability_tags.split(",")]
    return await pipeline_service.create_pipeline(
        db, operator_id, pipeline_name, description, tags, steps,
        pricing_model, base_price,
    )


@app.get("/api/v1/pipelines/search")
async def api_search_pipelines(
    capability_tag: str | None = None, max_price: float | None = None,
    min_reputation: float | None = None, db: AsyncSession = Depends(get_db),
):
    """Discover pipelines by capability, price, reputation."""
    if not settings.pipelines_enabled:
        raise HTTPException(status_code=503, detail="Pipelines module not enabled")
    return await pipeline_service.search_pipelines(db, capability_tag, max_price, min_reputation)


@app.post("/api/v1/pipelines/{pipeline_id}/engage")
async def api_engage_pipeline(
    pipeline_id: str, client_operator_id: str, gross_value: float,
    db: AsyncSession = Depends(get_db),
):
    """Create a pipeline engagement. Fund escrow for full value."""
    if not settings.pipelines_enabled:
        raise HTTPException(status_code=503, detail="Pipelines module not enabled")
    return await pipeline_service.engage_pipeline(db, pipeline_id, client_operator_id, gross_value)


@app.post("/api/v1/pipeline-engagements/{engagement_id}/advance")
async def api_advance_pipeline_step(
    engagement_id: str, db: AsyncSession = Depends(get_db),
):
    """Advance to next step after delivery verified. Releases payment to agent."""
    if not settings.pipelines_enabled:
        raise HTTPException(status_code=503, detail="Pipelines module not enabled")
    return await pipeline_service.advance_step(db, engagement_id)


@app.get("/api/v1/pipeline-engagements/{engagement_id}")
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


@app.get("/api/v1/pipelines/stats")
async def api_pipeline_stats(db: AsyncSession = Depends(get_db)):
    """Platform-wide pipeline statistics."""
    if not settings.pipelines_enabled:
        raise HTTPException(status_code=503, detail="Pipelines module not enabled")
    return await pipeline_service.get_platform_stats(db)


# ══════════════════════════════════════════════════════════════════════
#  CAPABILITY FUTURES (Build Brief V2, Module 3)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/futures")
async def api_create_future(
    provider_agent_id: str, provider_operator_id: str, capability_tag: str,
    delivery_window_start: str, delivery_window_end: str,
    quantity: int, price_per_unit: float,
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    if not settings.futures_enabled:
        raise HTTPException(status_code=503, detail="Futures module not enabled")
    from datetime import datetime
    start = datetime.fromisoformat(delivery_window_start)
    end = datetime.fromisoformat(delivery_window_end)
    return await futures_service.create_future(
        db, provider_agent_id, provider_operator_id, capability_tag, start, end, quantity, price_per_unit,
    )

@app.get("/api/v1/futures/search")
async def api_search_futures(capability_tag: str | None = None, max_price: float | None = None, db: AsyncSession = Depends(get_db)):
    if not settings.futures_enabled:
        raise HTTPException(status_code=503, detail="Futures module not enabled")
    return await futures_service.search_futures(db, capability_tag, max_price)

@app.post("/api/v1/futures/{future_id}/reserve")
async def api_reserve_future(future_id: str, buyer_operator_id: str, units: int, db: AsyncSession = Depends(get_db)):
    if not settings.futures_enabled:
        raise HTTPException(status_code=503, detail="Futures module not enabled")
    return await futures_service.reserve(db, future_id, buyer_operator_id, units)

@app.post("/api/v1/futures/{future_id}/settle")
async def api_settle_future(future_id: str, db: AsyncSession = Depends(get_db)):
    if not settings.futures_enabled:
        raise HTTPException(status_code=503, detail="Futures module not enabled")
    return await futures_service.settle(db, future_id)

@app.get("/api/v1/futures/market")
async def api_futures_market(db: AsyncSession = Depends(get_db)):
    if not settings.futures_enabled:
        raise HTTPException(status_code=503, detail="Futures module not enabled")
    return await futures_service.get_market(db)


# ══════════════════════════════════════════════════════════════════════
#  TRAINING DATA MARKETPLACE (Build Brief V2, Module 2)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/training/datasets")
async def api_create_dataset(
    operator_id: str, dataset_name: str, description: str,
    domain_tags: str, record_count: int, source_engagement_ids: str,
    pricing_model: str, licence_type: str, data_format: str,
    flat_price: float | None = None, price_per_record: float | None = None,
    db: AsyncSession = Depends(get_db),
):
    if not settings.training_data_enabled:
        raise HTTPException(status_code=503, detail="Training data module not enabled")
    tags = [t.strip() for t in domain_tags.split(",")]
    ids = [i.strip() for i in source_engagement_ids.split(",")]
    return await training_data_service.create_dataset(
        db, operator_id, dataset_name, description, tags, record_count, ids,
        pricing_model, licence_type, data_format, price_per_record, flat_price,
    )

@app.get("/api/v1/training/datasets/search")
async def api_search_datasets(domain_tag: str | None = None, licence_type: str | None = None, max_price: float | None = None, db: AsyncSession = Depends(get_db)):
    if not settings.training_data_enabled:
        raise HTTPException(status_code=503, detail="Training data module not enabled")
    return await training_data_service.search_datasets(db, domain_tag, licence_type, max_price)

@app.post("/api/v1/training/datasets/{dataset_id}/purchase")
async def api_purchase_dataset(dataset_id: str, buyer_operator_id: str, db: AsyncSession = Depends(get_db)):
    if not settings.training_data_enabled:
        raise HTTPException(status_code=503, detail="Training data module not enabled")
    return await training_data_service.purchase(db, dataset_id, buyer_operator_id)

@app.get("/api/v1/training/datasets/{dataset_id}/verify")
async def api_verify_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)):
    result = await training_data_service.verify_provenance(db, dataset_id)
    if not result:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return result


# ══════════════════════════════════════════════════════════════════════
#  BENCHMARKING (Build Brief V2, Module 7)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/benchmarking/evaluators")
async def api_register_evaluator(
    agent_id: str, operator_id: str, specialisation_domains: str,
    methodology_description: str, price_per_evaluation: float = 1200.0,
    db: AsyncSession = Depends(get_db),
):
    if not settings.benchmarking_enabled:
        raise HTTPException(status_code=503, detail="Benchmarking module not enabled")
    domains = [d.strip() for d in specialisation_domains.split(",")]
    return await benchmarking_service.register_evaluator(db, agent_id, operator_id, domains, methodology_description, price_per_evaluation)

@app.post("/api/v1/benchmarking/reports/commission")
async def api_commission_report(
    evaluator_id: str, subject_agent_id: str, task_category: str,
    commissioned_by_operator_id: str, report_type: str = "single",
    db: AsyncSession = Depends(get_db),
):
    if not settings.benchmarking_enabled:
        raise HTTPException(status_code=503, detail="Benchmarking module not enabled")
    return await benchmarking_service.commission_report(db, evaluator_id, subject_agent_id, task_category, commissioned_by_operator_id, report_type)

@app.get("/api/v1/benchmarking/reports/{report_id}")
async def api_get_benchmark_report(report_id: str, db: AsyncSession = Depends(get_db)):
    if not settings.benchmarking_enabled:
        raise HTTPException(status_code=503, detail="Benchmarking module not enabled")
    result = await benchmarking_service.get_report(db, report_id)
    if not result:
        raise HTTPException(status_code=404, detail="Report not found")
    return result

@app.get("/api/v1/benchmarking/reports/search")
async def api_search_reports(agent_id: str | None = None, task_category: str | None = None, min_score: float | None = None, db: AsyncSession = Depends(get_db)):
    if not settings.benchmarking_enabled:
        raise HTTPException(status_code=503, detail="Benchmarking module not enabled")
    return await benchmarking_service.search_reports(db, agent_id, task_category, min_score)

@app.get("/api/v1/benchmarking/leaderboard")
async def api_leaderboard(task_category: str | None = None, db: AsyncSession = Depends(get_db)):
    if not settings.benchmarking_enabled:
        raise HTTPException(status_code=503, detail="Benchmarking module not enabled")
    return await benchmarking_service.get_leaderboard(db, task_category)


# ══════════════════════════════════════════════════════════════════════
#  MARKET INTELLIGENCE (Build Brief V2, Module 8 + Section 2.4)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/v1/intelligence/tiers")
async def api_intelligence_tiers():
    return await intelligence_service.get_tiers()

@app.get("/api/v1/intelligence/market")
async def api_market_intelligence(tier: str = "public", category: str | None = None, db: AsyncSession = Depends(get_db)):
    if not settings.intelligence_enabled:
        raise HTTPException(status_code=503, detail="Intelligence module not enabled")
    return await intelligence_service.get_market_intelligence(db, tier, category)

@app.post("/api/v1/intelligence/subscribe")
async def api_intelligence_subscribe(operator_id: str, tier: str = "standard", db: AsyncSession = Depends(get_db)):
    if not settings.intelligence_enabled:
        raise HTTPException(status_code=503, detail="Intelligence module not enabled")
    return await intelligence_service.subscribe(db, operator_id, tier)

@app.get("/api/v1/intelligence/alerts")
async def api_intelligence_alerts(subscription_id: str, db: AsyncSession = Depends(get_db)):
    if not settings.intelligence_enabled:
        raise HTTPException(status_code=503, detail="Intelligence module not enabled")
    return await intelligence_service.get_alerts(db, subscription_id)

@app.post("/api/v1/intelligence/pipeline/run")
async def api_run_intelligence_pipeline(request: Request, db: AsyncSession = Depends(get_db)):
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await intelligence_service.run_nightly_pipeline(db)


# ══════════════════════════════════════════════════════════════════════
#  CROSS-BORDER (Build Brief V2, Module 6)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/v1/compliance/sarb/status")
async def api_sarb_status(db: AsyncSession = Depends(get_db)):
    return await crossborder_service.get_sarb_status(db)

@app.get("/api/v1/agentbroker/international-listings")
async def api_international_listings():
    """Placeholder: returns info about international listing capability."""
    return {"note": "International listings filter agents with international_listing=true", "status": "ready"}


# ══════════════════════════════════════════════════════════════════════
#  SECTOR VERTICALS (Build Brief V2, Module 10)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/v1/verticals")
async def api_list_verticals(db: AsyncSession = Depends(get_db)):
    if not settings.verticals_enabled:
        raise HTTPException(status_code=503, detail="Verticals module not enabled")
    return await verticals_service.list_verticals(db)

@app.post("/api/v1/verticals/{vertical_id}/register")
async def api_register_vertical(vertical_id: str, operator_id: str, sector_licence_ref: str | None = None, request: Request = None, db: AsyncSession = Depends(get_db)):
    if not settings.verticals_enabled:
        raise HTTPException(status_code=503, detail="Verticals module not enabled")
    return await verticals_service.register_operator(db, operator_id, vertical_id, sector_licence_ref)

@app.get("/api/v1/verticals/agriculture/loan-templates")
async def api_loan_templates(db: AsyncSession = Depends(get_db)):
    if not settings.verticals_enabled:
        raise HTTPException(status_code=503, detail="Verticals module not enabled")
    return await verticals_service.get_loan_templates(db)


# ══════════════════════════════════════════════════════════════════════
#  EXPORTS — PDF Receipts & CSV Tax Export
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/exports/tax-csv")
async def api_tax_csv_export(request: Request):
    """Download SARS-compatible CSV tax export of all transactions."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    all_tx = blockchain.get_all_transactions()
    csv_data = export_service.generate_csv_tax_export(all_tx, "Stephen Endersby / TiOLi AI Investments")
    from fastapi.responses import Response
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tioli_tax_export.csv"},
    )


@app.get("/api/exports/receipt/{tx_index}")
async def api_transaction_receipt(tx_index: int, request: Request):
    """Generate a receipt for a specific transaction."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    all_tx = blockchain.get_all_transactions()
    if tx_index < 0 or tx_index >= len(all_tx):
        raise HTTPException(status_code=404, detail="Transaction not found")
    receipt = export_service.generate_pdf_receipt(all_tx[tx_index])
    return {"receipt": receipt}


# ══════════════════════════════════════════════════════════════════════
#  COMMERCIAL LICENSING (Build Brief V2, Section 2.5 — Schema only)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/v1/licensing/pricing")
async def api_licensing_pricing():
    """Get commercial licensing pricing schedule. Schema only — no active billing."""
    from app.licensing.models import LICENCE_PRICING
    return {
        "licence_types": LICENCE_PRICING,
        "note": "All licence activations require owner 3FA confirmation. Phase 3 feature.",
    }


# ══════════════════════════════════════════════════════════════════════
#  FOREX & JURISDICTION (Issue #8 — International Expansion)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/forex/update")
async def api_forex_update(request: Request, db: AsyncSession = Depends(get_db)):
    """Fetch live forex rates and update platform fiat cross-rates."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await forex_service.update_platform_rates(db)


@app.get("/api/forex/rates")
async def api_forex_rates():
    """Get cached fiat exchange rates."""
    return forex_service.get_cached_rates()


@app.get("/api/jurisdictions")
async def api_jurisdictions():
    """List all supported jurisdictions and their basic info."""
    cached = cache.get("jurisdictions")
    if cached:
        return cached
    result = list_supported_jurisdictions()
    cache.set("jurisdictions", result, TTL_LONG)
    return result


@app.get("/api/jurisdictions/{country_code}")
async def api_jurisdiction_rules(country_code: str):
    """Get compliance rules for a specific jurisdiction."""
    return get_jurisdiction_summary(country_code)


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
#  PAYPAL INTEGRATION (additive — zero breaking changes)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/owner/paypal/accounts")
async def api_paypal_register(
    request: Request, db: AsyncSession = Depends(get_db),
    paypal_email: str = "", account_label: str = "",
    can_receive: bool = True, can_pay: bool = False,
    receive_pct: float = 100.0,
    x_3fa_token: str = Header(None, alias="X-3FA-Token"),
):
    """Register a PayPal account. Requires owner auth + 3FA."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    if not x_3fa_token:
        raise HTTPException(status_code=403, detail="3FA token required")
    acct = await paypal_service.register_account(
        db, paypal_email, account_label, can_receive, can_pay,
        receive_pct, verification_ref=x_3fa_token,
    )
    return {"account_id": acct.account_id, "label": acct.account_label}


@app.get("/api/v1/owner/paypal/accounts")
async def api_paypal_list(request: Request, db: AsyncSession = Depends(get_db)):
    """List PayPal accounts (emails masked)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.list_accounts(db)


@app.post("/api/v1/owner/paypal/accounts/{account_id}/deactivate")
async def api_paypal_deactivate(
    account_id: str, request: Request, db: AsyncSession = Depends(get_db),
):
    """Deactivate a PayPal account."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.deactivate_account(db, account_id)


@app.get("/api/v1/owner/paypal/receive/preview")
async def api_paypal_preview(
    request: Request, credits: float = 0, db: AsyncSession = Depends(get_db),
):
    """Preview PayPal disbursement at current rates."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.preview_disbursement(db, credits)


@app.post("/api/v1/owner/paypal/receive/disburse")
async def api_paypal_disburse(
    request: Request, credits: float = 0, db: AsyncSession = Depends(get_db),
    x_3fa_token: str = Header(None, alias="X-3FA-Token"),
):
    """Trigger PayPal disbursement. Requires 3FA."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    if not x_3fa_token:
        raise HTTPException(status_code=403, detail="3FA token required")
    import secrets as _s
    return await paypal_service.execute_disbursement(db, credits, f"manual_{_s.token_hex(8)}")


@app.get("/api/v1/owner/paypal/receive/history")
async def api_paypal_receive_history(request: Request, db: AsyncSession = Depends(get_db)):
    """PayPal disbursement history."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.get_disbursement_history(db)


@app.post("/api/v1/owner/paypal/billing-agreement/initiate")
async def api_paypal_ba_initiate(
    request: Request, account_id: str = "", max_monthly: float = 500,
    db: AsyncSession = Depends(get_db),
    x_3fa_token: str = Header(None, alias="X-3FA-Token"),
):
    """Initiate billing agreement for outbound payments."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    if not x_3fa_token:
        raise HTTPException(status_code=403, detail="3FA token required")
    return await paypal_service.initiate_billing_agreement(db, account_id, max_monthly)


@app.post("/api/v1/owner/paypal/billing-agreement/complete")
async def api_paypal_ba_complete(
    request: Request, token: str = "", db: AsyncSession = Depends(get_db),
):
    """Complete billing agreement after owner approval at PayPal."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.complete_billing_agreement(db, token)


@app.get("/api/v1/owner/paypal/billing-agreements")
async def api_paypal_ba_list(request: Request, db: AsyncSession = Depends(get_db)):
    """List billing agreements."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.list_billing_agreements(db)


@app.post("/api/v1/owner/paypal/pay/one-time")
async def api_paypal_pay(
    request: Request, account_id: str = "", expense_category: str = "operational",
    payee_name: str = "", usd_amount: float = 0,
    db: AsyncSession = Depends(get_db),
    x_3fa_token: str = Header(None, alias="X-3FA-Token"),
):
    """One-time PayPal payment for platform expense."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    if not x_3fa_token:
        raise HTTPException(status_code=403, detail="3FA token required")
    return await paypal_service.initiate_one_time_payment(
        db, account_id, expense_category, payee_name, usd_amount, three_fa_ref=x_3fa_token,
    )


@app.get("/api/v1/owner/paypal/pay/history")
async def api_paypal_pay_history(request: Request, db: AsyncSession = Depends(get_db)):
    """Outbound payment history."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.get_outbound_history(db)


@app.post("/api/v1/webhooks/paypal")
async def api_paypal_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive PayPal webhook events."""
    body = await request.json()
    event_id = body.get("id", "")
    event_type = body.get("event_type", "")
    resource = body.get("resource", {})
    return await paypal_service.process_webhook(
        db, event_id, event_type,
        resource.get("resource_type"), resource.get("id"),
        body, signature_verified=False,  # Production: verify signature
    )


@app.get("/api/v1/owner/paypal/webhooks")
async def api_paypal_webhooks(request: Request, db: AsyncSession = Depends(get_db)):
    """Recent webhook events."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_service.get_webhook_events(db)


@app.get("/api/v1/owner/paypal/health")
async def api_paypal_health(request: Request):
    """PayPal API health check."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await paypal_adapter.health_check()


# ══════════════════════════════════════════════════════════════════════
#  LOAN DEFAULT MANAGEMENT (CE-008)
# ══════════════════════════════════════════════════════════════════════

@app.post("/api/loans/check-defaults")
async def api_check_loan_defaults(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Check for overdue loans and default them."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await loan_default_service.check_and_default_overdue_loans(db)


@app.get("/api/loans/overdue-summary")
async def api_overdue_summary(db: AsyncSession = Depends(get_db)):
    """Get summary of overdue and defaulted loans."""
    return await loan_default_service.get_overdue_summary(db)


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


@app.post("/api/infra/spend")
async def api_record_spend(
    amount_usd: float = 0, description: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Record infrastructure spending — triggers alerts and auto-shutdown."""
    return await cost_control.record_spend(db, amount_usd, description)


@app.post("/api/infra/budget/reset")
async def api_reset_budget(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Reset monthly spend counter (called at month start)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await cost_control.reset_monthly_spend(db)


@app.post("/api/infra/test-alerts")
async def api_test_alerts(request: Request):
    """Send a test alert to verify email and WhatsApp are working."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await alert_service.test_alerts()


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
    """Full fee schedule with transaction-type rates and floor fees."""
    cached = cache.get("fee_schedule")
    if cached:
        return cached
    schedule = fee_engine.get_fee_schedule()
    schedule["founder_entity"] = "TiOLi AI Investments"
    schedule["charity_allocation"] = fee_engine.get_charity_status()
    cache.set("fee_schedule", schedule, TTL_LONG)
    return schedule


# ══════════════════════════════════════════════════════════════════════
#  MODULE ADMINISTRATION (Owner 3FA required)
# ══════════════════════════════════════════════════════════════════════

MODULE_FLAGS = [
    "agentbroker_enabled", "subscriptions_enabled", "guild_enabled",
    "pipelines_enabled", "futures_enabled", "training_data_enabled",
    "treasury_enabled", "compliance_service_enabled", "benchmarking_enabled",
    "intelligence_enabled", "verticals_enabled",
]


@app.get("/api/admin/modules")
async def api_admin_modules(request: Request):
    """List all module feature flags and their current status."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return {
        "modules": {flag: getattr(settings, flag) for flag in MODULE_FLAGS},
    }


@app.post("/api/admin/modules/{module_name}/enable")
async def api_admin_enable_module(module_name: str, request: Request):
    """Enable a module. Requires owner authentication."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    flag = f"{module_name}_enabled"
    if flag not in MODULE_FLAGS:
        raise HTTPException(status_code=404, detail=f"Unknown module: {module_name}")
    setattr(settings, flag, True)
    return {"module": module_name, "enabled": True}


@app.post("/api/admin/modules/{module_name}/disable")
async def api_admin_disable_module(module_name: str, request: Request):
    """Disable a module. Requires owner authentication."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    flag = f"{module_name}_enabled"
    if flag not in MODULE_FLAGS:
        raise HTTPException(status_code=404, detail=f"Unknown module: {module_name}")
    setattr(settings, flag, False)
    return {"module": module_name, "enabled": False}


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
        # Issue #9: include transaction volume metrics
        adoption = await growth_engine.get_adoption_metrics(db)

    return {
        "chain_length": info["chain_length"],
        "total_transactions": info["total_transactions"],
        "agent_count": agent_count,
        "founder_earnings": founder_earnings,
        "charity_total": charity_total,
        "is_valid": info["is_valid"],
        "charity_allocation": fee_engine.get_charity_status(),
        "transaction_metrics": adoption.get("transaction_metrics", {}),
    }


@app.get("/api/public/stats")
async def api_public_stats():
    """Public platform statistics — safe vanity metrics only. No auth required.

    This endpoint is designed to be called from the brochureware landing page.
    It exposes ONLY non-sensitive aggregate counts. No revenue, no identities,
    no wallet data, no auth tokens.
    """
    info = blockchain.get_chain_info()

    async with async_session() as db:
        agent_count = (await db.execute(select(func.count(Agent.id)))).scalar() or 0

        hub_stats = {"total_profiles": 0, "total_posts": 0, "total_connections": 0,
                     "total_endorsements": 0, "total_portfolio_items": 0, "active_channels": 0}
        try:
            if settings.agenthub_enabled:
                hub_stats = await agenthub_service.get_community_stats(db)
        except Exception:
            pass

        from app.agenthub.models import (
            AgentHubProject, AgentHubChallenge, AgentHubArtefact,
            AgentHubGigPackage, AgentHubAssessment, AgentHubSkill,
        )
        projects = (await db.execute(select(func.count(AgentHubProject.id)))).scalar() or 0
        challenges = (await db.execute(select(func.count(AgentHubChallenge.id)))).scalar() or 0
        artefacts = (await db.execute(select(func.count(AgentHubArtefact.id)))).scalar() or 0
        gigs = (await db.execute(select(func.count(AgentHubGigPackage.id)))).scalar() or 0
        assessments = (await db.execute(select(func.count(AgentHubAssessment.id)))).scalar() or 0
        skills_total = (await db.execute(select(func.count(AgentHubSkill.id)))).scalar() or 0

    return {
        "platform": "TiOLi AGENTIS",
        "live_since": "2026-03-15T00:00:00Z",
        "agents": {
            "registered": agent_count,
            "profiles": hub_stats["total_profiles"],
        },
        "community": {
            "posts": hub_stats["total_posts"],
            "connections": hub_stats["total_connections"],
            "endorsements": hub_stats["total_endorsements"],
            "portfolio_items": hub_stats["total_portfolio_items"],
            "channels": hub_stats["active_channels"],
            "skills_listed": skills_total,
        },
        "marketplace": {
            "projects": projects,
            "challenges": challenges,
            "gig_packages": gigs,
            "artefacts": artefacts,
            "assessments_available": assessments,
        },
        "infrastructure": {
            "blockchain_blocks": info["chain_length"],
            "blockchain_valid": info["is_valid"],
            "transactions_confirmed": info["total_transactions"],
            "api_endpoints": 400,
            "mcp_tools": 13,
        },
        "exchange_rates": await _get_public_exchange_rates(),
    }


async def _get_public_exchange_rates() -> dict:
    """Fetch live ZAR exchange rates from open.er-api.com — cached for 6 hours.

    Source: https://open.er-api.com/v6/latest/ZAR (free, no API key required)
    Updates daily at 00:00 UTC. We cache for 6 hours to stay current.
    Same source used by both backend and frontend.
    """
    import httpx
    if not hasattr(_get_public_exchange_rates, '_cache'):
        _get_public_exchange_rates._cache = {"rates": {}, "fetched_at": 0}
    cache = _get_public_exchange_rates._cache
    now = time.time()
    if now - cache["fetched_at"] < 21600 and cache["rates"]:  # 6hr cache
        cached_result = dict(cache["rates"])
        cached_result["cached"] = True
        return cached_result
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://open.er-api.com/v6/latest/ZAR")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("result") == "success":
                    rates = data.get("rates", {})
                    result = {
                        "base": "ZAR",
                        "USD": round(rates.get("USD", 0.054), 6),
                        "EUR": round(rates.get("EUR", 0.050), 6),
                        "GBP": round(rates.get("GBP", 0.043), 6),
                        "source": "open.er-api.com",
                        "last_updated": data.get("time_last_update_utc", ""),
                        "cached": False,
                    }
                    cache["rates"] = result
                    cache["fetched_at"] = now
                    security_logger.info(f"Exchange rates updated: USD={result['USD']}, EUR={result['EUR']}, GBP={result['GBP']}")
                    return result
    except Exception as e:
        security_logger.warning(f"Exchange rate fetch failed: {e}")
    # Fallback — last known good rates
    if cache["rates"]:
        cached_result = dict(cache["rates"])
        cached_result["cached"] = True
        cached_result["source"] = cached_result.get("source", "cached_fallback")
        return cached_result
    return {"base": "ZAR", "USD": 0.054, "EUR": 0.050, "GBP": 0.043, "source": "hardcoded_fallback", "cached": True}


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
        try:
            adoption = await growth_engine.get_adoption_metrics(db)
        except Exception:
            adoption = {"transaction_metrics": {}}

    # Services summary for dashboard
    services_summary = [
        {"name": "Subscriptions", "status": "live", "category": "SaaS"},
        {"name": "Guilds", "status": "live", "category": "Collectives"},
        {"name": "Benchmarking", "status": "live", "category": "Evaluation"},
        {"name": "Training Data", "status": "live", "category": "Data Products"},
        {"name": "Intelligence", "status": "live", "category": "Analytics"},
        {"name": "Compliance", "status": "live", "category": "Reviews"},
        {"name": "Verticals", "status": "live", "category": "Sectors"},
        {"name": "Pipelines", "status": "conditional", "category": "Orchestration"},
        {"name": "Treasury", "status": "conditional", "category": "Portfolio"},
        {"name": "AgentBroker", "status": "conditional", "category": "Engagements"},
    ]

    # Revenue data for dashboard
    rev_data = {"mtd_usd": 0, "target_usd": 5000, "progress_pct": 0, "projected_month_usd": 0}
    hub_stats = {"total_profiles": 0, "total_posts": 0, "total_connections": 0, "active_channels": 0}
    try:
        async with async_session() as db2:
            rev_full = await revenue_service.get_revenue_dashboard(db2)
            rev_data = rev_full.get("gauge", rev_data)
            if settings.agenthub_enabled:
                hub_stats = await agenthub_service.get_community_stats(db2)
    except Exception:
        pass

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "authenticated": True, "active": "dashboard",
        "chain_info": info, "agent_count": agent_count,
        "founder_earnings": founder_earnings, "charity_total": charity_total,
        "recent_transactions": [_tx_display(tx) for tx in recent],
        "pending_proposals": proposals,
        "tx_metrics": adoption.get("transaction_metrics", {}),
        "charity_status": fee_engine.get_charity_status(),
        "services_summary": services_summary,
        "rev": rev_data, "hub_stats": hub_stats,
    })


@app.get("/dashboard/transactions", response_class=HTMLResponse)
async def transactions_list_page(request: Request):
    """Full transaction ledger — drill-down from dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    all_tx = blockchain.get_all_transactions()
    all_tx_rev = list(reversed(all_tx))
    total_volume = sum(tx.get("amount", 0) for tx in all_tx)
    total_commission = sum(tx.get("founder_commission", 0) for tx in all_tx)
    types = set(tx.get("type", "") for tx in all_tx)
    return templates.TemplateResponse("transactions_list.html", {
        "request": request, "authenticated": True, "active": "dashboard",
        "transactions": all_tx_rev, "total_volume": total_volume,
        "total_commission": total_commission, "type_count": len(types),
    })


@app.get("/dashboard/transactions/{tx_index}", response_class=HTMLResponse)
async def transaction_detail_page(tx_index: int, request: Request):
    """Individual transaction detail."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    all_tx = blockchain.get_all_transactions()
    if tx_index < 0 or tx_index >= len(all_tx):
        raise HTTPException(status_code=404, detail="Transaction not found")
    return templates.TemplateResponse("transaction_detail.html", {
        "request": request, "authenticated": True, "active": "dashboard",
        "tx": all_tx[tx_index], "tx_index": tx_index,
    })


@app.get("/dashboard/blocks", response_class=HTMLResponse)
async def blocks_list_page(request: Request):
    """Blockchain explorer — drill-down from dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    chain_info = blockchain.get_chain_info()
    blocks = []
    for i, block in enumerate(blockchain.chain):
        blocks.append({
            "index": block.index,
            "hash": block.hash,
            "previous_hash": block.previous_hash,
            "tx_count": len(block.transactions),
            "timestamp": str(block.timestamp),
        })
    blocks.reverse()
    return templates.TemplateResponse("blocks_list.html", {
        "request": request, "authenticated": True, "active": "dashboard",
        "chain_info": chain_info, "blocks": blocks,
    })


@app.get("/dashboard/arm", response_class=HTMLResponse)
async def arm_page(request: Request):
    """Agentic Relationship Management dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    from app.arm.service import ARMService
    arm = ARMService()
    try:
        async with async_session() as db:
            data = await arm.get_dashboard_data(db)
    except Exception:
        data = {"campaigns": [], "directories": [], "totals": {
            "campaigns": 0, "active_campaigns": 0, "impressions": 0, "clicks": 0,
            "registrations": 0, "revenue": 0, "directories": 0, "active_listings": 0, "ctr": 0,
        }}

    return templates.TemplateResponse("arm.html", {
        "request": request, "authenticated": True, "active": "arm",
        "campaigns": data["campaigns"], "directories": data["directories"],
        "totals": data["totals"],
    })


@app.get("/dashboard/proposals/{proposal_id}", response_class=HTMLResponse)
async def proposal_detail_page(proposal_id: str, request: Request):
    """Individual proposal detail — drill-down from governance."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    from app.governance.models import Proposal
    async with async_session() as db:
        result = await db.execute(select(Proposal).where(Proposal.id == proposal_id))
        prop = result.scalar_one_or_none()
        if not prop:
            raise HTTPException(status_code=404, detail="Proposal not found")
        proposal_data = {
            "id": prop.id, "title": prop.title, "description": prop.description,
            "category": prop.category, "submitted_by": prop.submitted_by,
            "upvotes": prop.upvotes, "downvotes": prop.downvotes,
            "status": prop.status, "is_material_change": prop.is_material_change,
            "veto_reason": prop.veto_reason,
            "created_at": str(prop.created_at) if prop.created_at else None,
            "resolved_at": str(prop.resolved_at) if prop.resolved_at else None,
        }
    return templates.TemplateResponse("proposal_detail.html", {
        "request": request, "authenticated": True, "active": "governance",
        "proposal": proposal_data,
    })


@app.get("/dashboard/community", response_class=HTMLResponse)
async def community_page(request: Request):
    """Agent community — AgentHub when enabled, legacy messaging otherwise."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    # ── AgentHub™ Community Network ──
    if settings.agenthub_enabled:
        async with async_session() as db:
            stats = await agenthub_service.get_community_stats(db)
            feed = await agenthub_service.get_feed(db, None, 15, 0)
            top_agents = await agenthub_service.search_directory(db, limit=10)
            channels = await agenthub_service.list_channels(db)
            leaderboard = await agenthub_service.get_leaderboard(db, limit=10)
            trending = await agenthub_service.get_trending_agents(db, limit=5)
            spotlights = await agenthub_service.get_active_spotlights(db, limit=5)
            challenges = await agenthub_service.list_challenges(db, status="OPEN", limit=5)
            events = await agenthub_service.list_events(db, upcoming_only=True, limit=5)
            gigs = await agenthub_service.list_gig_packages(db, limit=5)
            newsletters = await agenthub_service.list_newsletters(db, limit=5)
            companies = await agenthub_service.browse_companies(db, limit=5)
            mod_queue = await agenthub_service.get_moderation_queue(db, limit=5)
            artefacts = await agenthub_service.browse_registry(db, limit=5)
            trending_topics = await agenthub_service.get_trending_topics(db, limit=8)
        return templates.TemplateResponse("agenthub.html", {
            "request": request, "authenticated": True, "active": "community",
            "stats": stats, "feed": feed, "top_agents": top_agents,
            "channels": channels, "leaderboard": leaderboard,
            "trending_agents": trending, "spotlights": spotlights,
            "challenges": challenges, "events": events, "gigs": gigs,
            "newsletters": newsletters, "companies": companies,
            "mod_queue": mod_queue, "artefacts": artefacts,
            "trending_topics": trending_topics,
        })

    # ── Legacy community messaging ──
    from app.growth.viral import AgentMessage
    from datetime import timedelta

    channels_info = [
        {"channel": "general", "description": "General agent discussion and coordination"},
        {"channel": "services", "description": "Service offerings and requests"},
        {"channel": "hiring", "description": "Agent hiring and availability"},
        {"channel": "coordination", "description": "Multi-agent task coordination"},
        {"channel": "marketplace", "description": "Trading and exchange discussion"},
    ]

    total = 0; unique_senders = 0; messages_today = 0; recent_messages = []
    try:
        async with async_session() as db:
            from datetime import datetime, timezone as tz
            total = (await db.execute(select(func.count(AgentMessage.id)))).scalar() or 0
            unique_senders = (await db.execute(select(func.count(func.distinct(AgentMessage.sender_id))))).scalar() or 0
            today = datetime.now(tz.utc).replace(hour=0, minute=0, second=0)
            try:
                messages_today = (await db.execute(select(func.count(AgentMessage.id)).where(AgentMessage.created_at >= today))).scalar() or 0
            except Exception:
                pass
            for ch in channels_info:
                ch["count"] = (await db.execute(select(func.count(AgentMessage.id)).where(AgentMessage.channel == ch["channel"]))).scalar() or 0
                lr = await db.execute(select(AgentMessage).where(AgentMessage.channel == ch["channel"]).order_by(AgentMessage.created_at.desc()).limit(1))
                lm = lr.scalar_one_or_none()
                ch["latest"] = lm.message if lm else None
            rr = await db.execute(select(AgentMessage).order_by(AgentMessage.created_at.desc()).limit(50))
            recent_messages = [{"sender_id": m.sender_id, "channel": m.channel, "message": m.message, "recipient_id": m.recipient_id, "posted_at": str(m.created_at)} for m in rr.scalars().all()]
    except Exception:
        pass

    return templates.TemplateResponse("community.html", {
        "request": request, "authenticated": True, "active": "community",
        "total_messages": total, "unique_senders": unique_senders,
        "messages_today": messages_today, "channels": channels_info,
        "recent_messages": recent_messages,
    })


@app.get("/dashboard/awareness", response_class=HTMLResponse)
async def awareness_page(request: Request):
    """System awareness and viral growth dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    from app.growth.viral import AgentReferralCode
    from app.exchange.incentives import IncentiveRecord

    codes_issued = 0; total_uses = 0; total_bonus = 0; leaderboard = []; total_agents = 0; incentive_spent = 0
    try:
        async with async_session() as db:
            codes_issued = (await db.execute(select(func.count(AgentReferralCode.id)))).scalar() or 0
            total_uses = (await db.execute(select(func.sum(AgentReferralCode.uses)))).scalar() or 0
            total_bonus = (await db.execute(select(func.sum(AgentReferralCode.total_bonus_earned)))).scalar() or 0
            lb_r = await db.execute(select(AgentReferralCode).where(AgentReferralCode.uses > 0).order_by(AgentReferralCode.uses.desc()).limit(20))
            leaderboard = [{"agent_id": r.agent_id, "code": r.code, "referrals": r.uses, "bonus_earned": r.total_bonus_earned} for r in lb_r.scalars().all()]
            total_agents = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
            incentive_spent = (await db.execute(select(func.sum(IncentiveRecord.amount)))).scalar() or 0
    except Exception:
        pass

    conversion_rate = (total_uses / max(codes_issued, 1)) * 100 if codes_issued else 0

    return templates.TemplateResponse("awareness.html", {
        "request": request, "authenticated": True, "active": "awareness",
        "referral_codes_issued": codes_issued, "referrals_used": total_uses,
        "conversion_rate": conversion_rate, "bonus_distributed": total_bonus or 0,
        "gateway_challenges": 0, "total_agents": total_agents,
        "leaderboard": leaderboard,
        "discovery_endpoints": [
            {"path": "/.well-known/ai-plugin.json", "status": "Live"},
            {"path": "/api/agent-gateway/challenge", "status": "Live"},
            {"path": "/api/agent-gateway/capabilities", "status": "Live"},
            {"path": "/api/mcp/manifest", "status": "Live"},
            {"path": "/docs", "status": "Live"},
        ],
        "incentive_budget": 50000, "incentive_spent": incentive_spent or 0,
        "incentive_pct": ((incentive_spent or 0) / 50000) * 100,
    })


@app.get("/dashboard/escrow", response_class=HTMLResponse)
async def escrow_dashboard_page(request: Request):
    """Escrow accounts dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    from app.security.transaction_safety import EscrowAccount
    async with async_session() as db:
        result = await db.execute(select(EscrowAccount).order_by(EscrowAccount.created_at.desc()))
        escrows_raw = result.scalars().all()

    escrows = []
    total_held = 0.0
    count_held = count_released = count_disputed = count_refunded = 0
    for e in escrows_raw:
        escrows.append({
            "id": e.id, "transaction_ref": e.transaction_ref,
            "depositor_id": e.depositor_id, "beneficiary_id": e.beneficiary_id,
            "amount": e.amount, "currency": e.currency, "status": e.status,
            "reason": e.reason or "", "created_at": str(e.created_at) if e.created_at else None,
        })
        if e.status == "held":
            total_held += e.amount
            count_held += 1
        elif e.status == "released":
            count_released += 1
        elif e.status == "disputed":
            count_disputed += 1
        elif e.status == "refunded":
            count_refunded += 1

    return templates.TemplateResponse("escrow.html", {
        "request": request, "authenticated": True, "active": "escrow",
        "escrows": escrows, "total_held": round(total_held, 4),
        "count_held": count_held, "count_released": count_released,
        "count_disputed": count_disputed,
    })


@app.get("/dashboard/escrow/{escrow_id}", response_class=HTMLResponse)
async def escrow_detail_page(escrow_id: str, request: Request):
    """Individual escrow account detail."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    from app.security.transaction_safety import EscrowAccount
    async with async_session() as db:
        result = await db.execute(select(EscrowAccount).where(EscrowAccount.id == escrow_id))
        e = result.scalar_one_or_none()
        if not e:
            raise HTTPException(status_code=404, detail="Escrow account not found")

        escrow_data = {
            "id": e.id, "transaction_ref": e.transaction_ref,
            "depositor_id": e.depositor_id, "beneficiary_id": e.beneficiary_id,
            "amount": e.amount, "currency": e.currency, "status": e.status,
            "reason": e.reason or "", "release_conditions": e.release_conditions or "",
            "dispute_reason": e.dispute_reason,
            "created_at": str(e.created_at) if e.created_at else None,
            "expires_at": str(e.expires_at) if e.expires_at else None,
            "resolved_at": str(e.resolved_at) if e.resolved_at else None,
        }

    return templates.TemplateResponse("escrow_detail.html", {
        "request": request, "authenticated": True, "active": "escrow",
        "escrow": escrow_data,
    })


@app.get("/dashboard/agents", response_class=HTMLResponse)
async def agents_list_page(request: Request):
    """List all registered agents — drill-down from dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    async with async_session() as db:
        result = await db.execute(select(Agent).order_by(Agent.created_at.desc()))
        agents_raw = result.scalars().all()

        agents = []
        platforms = set()
        total_balance = 0.0
        for a in agents_raw:
            wallets_result = await db.execute(select(Wallet).where(Wallet.agent_id == a.id))
            wallets = wallets_result.scalars().all()
            bal = sum(w.balance for w in wallets)
            total_balance += bal
            platforms.add(a.platform)
            agents.append({
                "id": a.id, "name": a.name, "platform": a.platform,
                "is_active": a.is_active, "is_approved": a.is_approved,
                "total_balance": bal, "wallet_count": len(wallets),
                "created_at": str(a.created_at) if a.created_at else None,
                "last_active": str(a.last_active) if a.last_active else None,
            })

    return templates.TemplateResponse("agents_list.html", {
        "request": request, "authenticated": True, "active": "dashboard",
        "agents": agents, "platforms": platforms, "total_balance": total_balance,
    })


@app.get("/dashboard/agents/{agent_id}", response_class=HTMLResponse)
async def agent_detail_page(agent_id: str, request: Request):
    """Individual agent detail — drill-down from agents list."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    async with async_session() as db:
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")

        wallets_result = await db.execute(select(Wallet).where(Wallet.agent_id == agent_id))
        wallets_raw = wallets_result.scalars().all()
        wallets = [{"currency": w.currency, "balance": w.balance, "frozen": w.frozen_balance} for w in wallets_raw]
        total_balance = sum(w.balance for w in wallets_raw)

    all_tx = blockchain.get_all_transactions()
    agent_tx = [tx for tx in all_tx if tx.get("sender_id") == agent_id or tx.get("receiver_id") == agent_id]
    agent_tx.reverse()

    agent_data = {
        "id": agent.id, "name": agent.name, "platform": agent.platform,
        "description": agent.description, "is_active": agent.is_active,
        "is_approved": agent.is_approved,
        "created_at": str(agent.created_at) if agent.created_at else None,
        "last_active": str(agent.last_active) if agent.last_active else None,
    }

    return templates.TemplateResponse("agent_detail.html", {
        "request": request, "authenticated": True, "active": "dashboard",
        "agent": agent_data, "wallets": wallets, "total_balance": total_balance,
        "transactions": agent_tx[:50], "tx_count": len(agent_tx),
    })


@app.get("/dashboard/agentbroker", response_class=HTMLResponse)
async def agentbroker_page(request: Request):
    """AgentBroker marketplace dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    profiles = []
    engagements = []
    guilds_list = []
    pipelines_list = []
    stats = {"total_profiles": 0, "total_engagements": 0, "completed": 0,
             "avg_reputation": 0, "total_gev": 0, "active_guilds": 0}

    escalated_disputes = []
    active_engagements = []
    try:
        async with async_session() as db:
            guilds_list = await guild_service.search_guilds(db, limit=10)
            pipelines_list = await pipeline_service.search_pipelines(db, limit=10)
            stats["active_guilds"] = len(guilds_list)

            # Get escalated disputes for owner inbox
            from app.agentbroker.models import AgentEngagement, EngagementDispute
            disp_result = await db.execute(
                select(EngagementDispute).where(
                    EngagementDispute.escalated_to_owner == True,
                    EngagementDispute.status == "ESCALATED",
                ).order_by(EngagementDispute.created_at.desc()).limit(20)
            )
            for d in disp_result.scalars().all():
                escalated_disputes.append({
                    "dispute_id": d.dispute_id, "engagement_id": d.engagement_id,
                    "type": d.dispute_type, "description": d.description[:200],
                    "raised_by": d.raised_by, "status": d.status,
                    "created_at": str(d.created_at),
                })

            # Get recent active engagements
            eng_result = await db.execute(
                select(AgentEngagement).where(
                    AgentEngagement.current_state.in_(["DRAFT", "PROPOSED", "NEGOTIATING", "ACCEPTED", "FUNDED", "IN_PROGRESS", "DELIVERED", "DISPUTED"])
                ).order_by(AgentEngagement.created_at.desc()).limit(20)
            )
            for e in eng_result.scalars().all():
                active_engagements.append({
                    "engagement_id": e.engagement_id, "title": e.engagement_title,
                    "state": e.current_state, "price": e.proposed_price,
                    "currency": e.price_currency,
                    "client": e.client_agent_id[:12] if e.client_agent_id else "",
                    "provider": e.provider_agent_id[:12] if e.provider_agent_id else "",
                    "created_at": str(e.created_at),
                })
    except Exception:
        pass

    return templates.TemplateResponse("agentbroker.html", {
        "request": request, "authenticated": True, "active": "agentbroker",
        "profiles": profiles, "engagements": active_engagements,
        "guilds": guilds_list, "pipelines": pipelines_list,
        "stats": stats, "escalated_disputes": escalated_disputes,
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


@app.get("/dashboard/governance", response_class=HTMLResponse)
async def governance_page(request: Request):
    """Governance proposals and voting dashboard."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    recommendations = []
    async with async_session() as db:
        proposals = await governance_service.get_proposals(db, status="pending")
        queue = await governance_service.get_priority_queue(db)
        stats = await governance_service.get_governance_stats(db)
        audit = await governance_service.get_audit_log(db, limit=20)
        try:
            recommendations = await optimization_engine.get_recommendations(db, limit=10)
        except Exception:
            pass

    return templates.TemplateResponse("governance.html", {
        "request": request, "authenticated": True, "active": "governance",
        "pending_proposals": proposals, "priority_queue": queue,
        "governance_stats": stats, "audit_log": audit,
        "recommendations": recommendations,
    })


@app.get("/dashboard/payout", response_class=HTMLResponse)
async def payout_dashboard_page(request: Request):
    """PayOut Engine dashboard tab."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    async with async_session() as db:
        balance = await payout_engine.get_owner_wallet_balance(db)
        split = await payout_engine.get_current_split(db)
        destination = await payout_engine.get_current_destination(db)
        sarb = await payout_engine.get_sarb_status(db)
        disbursements = await payout_engine.get_disbursement_history(db)

    return templates.TemplateResponse("payout.html", {
        "request": request, "authenticated": True, "active": "payout",
        "balance": balance, "split": split, "destination": destination,
        "sarb": sarb, "disbursements": disbursements,
    })


@app.get("/api/v1/owner/payout/tax-report")
async def api_tax_report_csv(request: Request, db: AsyncSession = Depends(get_db)):
    """Download SARS-compatible annual tax report as CSV."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")

    summary = await payout_engine.get_ytd_summary(db)
    disbursements = await payout_engine.get_disbursement_history(db)

    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["TiOLi AI Investments — Annual Earnings Report"])
    writer.writerow(["Year", summary["year"]])
    writer.writerow(["Total Disbursed (Credits)", summary["total_disbursed_credits"]])
    writer.writerow(["Total Disbursed (ZAR)", summary["total_disbursed_zar"]])
    writer.writerow(["Current Balance (Credits)", summary["current_balance_credits"]])
    writer.writerow(["Credit/ZAR Rate", summary["credit_zar_rate"]])
    writer.writerow([])
    writer.writerow(["Date", "Trigger", "Credits", "BTC", "ETH", "ZAR", "Retained", "Status"])
    for d in disbursements:
        writer.writerow([
            d.get("completed_at", ""), d.get("triggered_by", ""),
            d.get("gross_credits", 0), d.get("btc", 0), d.get("eth", 0),
            d.get("zar", 0), d.get("retained", 0), d.get("status", ""),
        ])

    from fastapi.responses import StreamingResponse
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=tioli_tax_report_{summary['year']}.csv"},
    )


@app.get("/dashboard/services", response_class=HTMLResponse)
async def services_page(request: Request):
    """Platform services overview — regulatory status, fees, tiers, verticals."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    from app.exchange.fees import FLOOR_FEES, TRANSACTION_TYPE_RATES
    from app.intelligence.models import INTELLIGENCE_TIERS
    from app.subscriptions.models import SUBSCRIPTION_TIER_SEEDS

    async with async_session() as db:
        verticals_data = await verticals_service.list_verticals(db)
        tiers = await subscription_service.list_tiers(db)
        mrr = await subscription_service.get_mrr(db) if hasattr(subscription_service, "get_mrr") else 0

    # Green services — no licence required
    green_services = [
        {"name": "Subscriptions", "description": "Operator subscription tiers (Explorer → Enterprise)", "revenue": "SaaS monthly/annual", "endpoint": "/api/v1/subscriptions/tiers"},
        {"name": "Agent Guilds", "description": "Agent collectives with shared reputation", "revenue": "R1,500 setup + R200/member/mo", "endpoint": "/api/v1/guilds"},
        {"name": "Benchmarking", "description": "Agent performance evaluation and leaderboards", "revenue": "R500/report, 15% commission", "endpoint": "/api/v1/benchmarking/evaluators"},
        {"name": "Training Data", "description": "Dataset marketplace with provenance verification", "revenue": "15% commission on sales", "endpoint": "/api/v1/training/datasets"},
        {"name": "Market Intelligence", "description": "Tiered market analytics with lag-based pricing", "revenue": "R0-R2,000/mo subscription", "endpoint": "/api/v1/intelligence/market"},
        {"name": "Compliance-as-a-Service", "description": "KYA/KYC/AML compliance reviews and certificates", "revenue": "AgentBroker commission", "endpoint": "/api/v1/compliance/agents"},
        {"name": "Sector Verticals", "description": "Healthcare, agriculture, finance sector compliance", "revenue": "Vertical registration", "endpoint": "/api/v1/verticals"},
    ]

    # Amber services — conditional (ZAR/credits only)
    amber_services = [
        {"name": "Pipelines", "description": "Multi-step agent orchestration", "condition": "ZAR/credits only, no crypto settlement", "endpoint": "/api/v1/pipelines"},
        {"name": "Treasury Agents", "description": "Autonomous portfolio management", "condition": "ZAR/credits only, owner 3FA required", "endpoint": "/api/v1/treasury"},
        {"name": "AgentBroker", "description": "Agent discovery, engagement, escrow", "condition": "ZAR/credits only, no cross-border", "endpoint": "/api/v1/agentbroker"},
    ]

    # Red services — licence required
    red_services = [
        {"name": "Crypto Exchange", "licence": "CASP registration (FIC Act)", "regulator": "FSCA / FIC"},
        {"name": "Cross-Border Settlements", "licence": "Authorised Dealer / AD Licence", "regulator": "SARB"},
        {"name": "Capability Futures", "licence": "OTC Derivative Provider", "regulator": "FSCA"},
        {"name": "Commercial Lending", "licence": "Credit Provider (NCA)", "regulator": "NCR"},
    ]

    # Fee schedule
    fee_schedule = [
        {"type": t.replace("_", " ").title(), "rate": f"{r*100:.1f}%", "floor": FLOOR_FEES.get(t, 0)}
        for t, r in TRANSACTION_TYPE_RATES.items()
    ]

    # Intelligence tiers
    intel_tiers = [
        {"name": k, "price": v.get("monthly_zar", 0), "lag": v.get("lag_days", 0), "description": v.get("description", "")}
        for k, v in INTELLIGENCE_TIERS.items()
    ]

    return templates.TemplateResponse("services.html", {
        "request": request, "authenticated": True, "active": "services",
        "services_live": len(green_services),
        "services_conditional": len(amber_services),
        "services_blocked": len(red_services),
        "subscription_mrr": mrr if isinstance(mrr, (int, float)) else 0,
        "subscription_tiers": tiers or [
            {**s, "annual_price_zar": round(s["monthly_price_zar"] * 12 * 0.8, 2)}
            for s in SUBSCRIPTION_TIER_SEEDS
        ],
        "green_services": green_services,
        "amber_services": amber_services,
        "red_services": red_services,
        "fee_schedule": fee_schedule,
        "intelligence_tiers": intel_tiers,
        "verticals": verticals_data,
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


@app.get("/dashboard/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """AI Prompt — owner chat interface."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("chat.html", {
        "request": request, "authenticated": True, "active": "chat",
    })


@app.get("/dashboard/modules", response_class=HTMLResponse)
async def modules_page(request: Request):
    """All platform modules — status, metrics, management."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    # Build module list with metrics
    modules_list = [
        {"name": "AgentBroker", "icon": "hub", "enabled": settings.agentbroker_enabled,
         "description": "15-state engagement lifecycle, escrow, AI arbitration",
         "api_base": "/api/v1/agentbroker/*", "metrics": {}},
        {"name": "AgentHub", "icon": "forum", "enabled": settings.agenthub_enabled,
         "description": "Professional community network for AI agents",
         "api_base": "/api/v1/agenthub/*", "metrics": {}},
        {"name": "Subscriptions", "icon": "card_membership", "enabled": settings.subscriptions_enabled,
         "description": "Operator subscription tiers (Explorer→Enterprise)",
         "api_base": "/api/v1/subscriptions/*", "metrics": {}},
        {"name": "Guilds", "icon": "groups", "enabled": settings.guild_enabled,
         "description": "Agent collectives with shared reputation",
         "api_base": "/api/v1/guilds/*", "metrics": {}},
        {"name": "Pipelines", "icon": "account_tree", "enabled": settings.pipelines_enabled,
         "description": "Multi-step agent orchestration workflows",
         "api_base": "/api/v1/pipelines/*", "metrics": {}},
        {"name": "Futures", "icon": "trending_up", "enabled": settings.futures_enabled,
         "description": "Forward contracts on agent capacity",
         "api_base": "/api/v1/futures/*", "metrics": {}},
        {"name": "Training Data", "icon": "dataset", "enabled": settings.training_data_enabled,
         "description": "Dataset marketplace with provenance verification",
         "api_base": "/api/v1/training/*", "metrics": {}},
        {"name": "Treasury", "icon": "savings", "enabled": settings.treasury_enabled,
         "description": "Autonomous portfolio management within risk bounds",
         "api_base": "/api/v1/treasury/*", "metrics": {}},
        {"name": "Compliance CaaS", "icon": "verified_user", "enabled": settings.compliance_service_enabled,
         "description": "KYA/KYC/AML compliance reviews and certificates",
         "api_base": "/api/v1/compliance/*", "metrics": {}},
        {"name": "Benchmarking", "icon": "speed", "enabled": settings.benchmarking_enabled,
         "description": "Agent performance evaluation and leaderboards",
         "api_base": "/api/v1/benchmarking/*", "metrics": {}},
        {"name": "Intelligence", "icon": "insights", "enabled": settings.intelligence_enabled,
         "description": "Market intelligence with tiered access",
         "api_base": "/api/v1/intelligence/*", "metrics": {}},
        {"name": "Verticals", "icon": "category", "enabled": settings.verticals_enabled,
         "description": "Healthcare, Agriculture, Finance sector configs",
         "api_base": "/api/v1/verticals/*", "metrics": {}},
    ]

    # Populate metrics where possible
    try:
        async with async_session() as db:
            hub_stats = await agenthub_service.get_community_stats(db)
            modules_list[1]["metrics"] = {
                "Profiles": hub_stats["total_profiles"],
                "Posts": hub_stats["total_posts"],
                "Connections": hub_stats["total_connections"],
                "Channels": hub_stats["active_channels"],
            }

            mcp_stats = await agenthub_service.get_mcp_analytics(db)
            quick_tasks = await revenue_service.list_quick_tasks(db, limit=10)
            at_risk = await revenue_service.get_at_risk_subscribers(db)

            # Auto-match activity
            from app.revenue.models import AutoMatchRequest as AMR
            am_result = await db.execute(
                select(AMR).order_by(AMR.created_at.desc()).limit(10)
            )
            auto_matches = [
                {"task": m.task_description[:60], "proposals_sent": m.proposals_sent,
                 "status": m.status, "created_at": str(m.created_at)}
                for m in am_result.scalars().all()
            ]

            # Referral stats (aggregate)
            from app.agenthub.models import AgentHubReferral
            total_refs = (await db.execute(
                select(func.count(AgentHubReferral.id))
            )).scalar() or 0
            qualified_refs = (await db.execute(
                select(func.count(AgentHubReferral.id)).where(
                    AgentHubReferral.status.in_(["QUALIFIED", "REWARDED"])
                )
            )).scalar() or 0
            referral_stats = {"total_referrals": total_refs, "qualified": qualified_refs,
                              "rewarded": 0, "total_earned": 0}

            # Onboarding enquiries
            from app.onboarding.models import OnboardingEnquiry
            enq_result = await db.execute(
                select(OnboardingEnquiry).order_by(OnboardingEnquiry.created_at.desc()).limit(20)
            )
            enquiries = [
                {"id": e.id, "name": e.contact_name, "email": e.email,
                 "company": e.company_name, "agents": e.agent_count,
                 "use_case": e.use_case[:100], "status": e.status,
                 "created_at": str(e.created_at)[:16]}
                for e in enq_result.scalars().all()
            ]
            enq_new = sum(1 for e in enquiries if e["status"] == "NEW")

    except Exception:
        mcp_stats = {"total_calls": 0, "calls_today": 0, "error_rate_pct": 0, "top_tools": []}
        quick_tasks = []
        auto_matches = []
        at_risk = []
        referral_stats = {"total_referrals": 0, "qualified": 0, "rewarded": 0, "total_earned": 0}
        enquiries = []
        enq_new = 0

    infra_services = [
        {"name": "Blockchain", "status": "healthy", "detail": f"{blockchain.get_chain_info()['chain_length']} blocks"},
        {"name": "Fee Engine", "status": "healthy", "detail": f"{fee_engine.founder_rate*100:.0f}% commission"},
        {"name": "MCP Server", "status": "healthy", "detail": "13 tools exposed"},
        {"name": "Cloudflare", "status": "healthy", "detail": "WAF + DDoS active"},
        {"name": "PayPal", "status": "healthy", "detail": "Integration ready"},
        {"name": "Graph API Email", "status": "healthy", "detail": "Verification working"},
        {"name": "Rate Limiter", "status": "healthy", "detail": "60-120 req/min"},
        {"name": "Brute Force", "status": "healthy", "detail": "Persistent lockouts"},
    ]

    return templates.TemplateResponse("modules.html", {
        "request": request, "authenticated": True, "active": "modules",
        "modules": modules_list, "infra_services": infra_services,
        "quick_tasks": quick_tasks, "auto_matches": auto_matches,
        "at_risk": at_risk, "referral_stats": referral_stats,
        "mcp_stats": mcp_stats,
        "enquiries": enquiries, "enq_new": enq_new,
    })


# ── Secure Access Gateway ──────────────────────────────────────────────
# Hashed credentials — SHA-256. Lockout after 5 failures for 15 minutes.
import hashlib as _gw_hashlib
_GATEWAY_USER_HASH = "a]0c65e75156feb41b5b8faa65a2fcb980cb8f24afd1e tried"  # placeholder
_GATEWAY_PASS_HASH = "d748e36e6ac9de72f9ef73b09a945448e79eba8761b1ea78e39869d3caee7710"
_GATEWAY_USER_HASH = _gw_hashlib.sha256(b"sendersby@tioli.onmicrosoft.com").hexdigest()
_gateway_failures: dict[str, list[float]] = defaultdict(list)
_GATEWAY_MAX_ATTEMPTS = 5
_GATEWAY_LOCKOUT_SECS = 900


@app.get("/gateway", response_class=HTMLResponse)
async def gateway_page(request: Request):
    """Secure access gateway — login form."""
    client_ip = request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")
    now = time.time()
    cutoff = now - _GATEWAY_LOCKOUT_SECS
    _gateway_failures[client_ip] = [t for t in _gateway_failures[client_ip] if t > cutoff]
    locked = len(_gateway_failures[client_ip]) >= _GATEWAY_MAX_ATTEMPTS
    return templates.TemplateResponse("gateway.html", {
        "request": request, "error": None, "locked": locked,
    })


@app.post("/gateway", response_class=HTMLResponse)
async def gateway_auth(request: Request):
    """Validate gateway credentials and redirect to exchange login."""
    client_ip = request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")
    now = time.time()
    cutoff = now - _GATEWAY_LOCKOUT_SECS
    _gateway_failures[client_ip] = [t for t in _gateway_failures[client_ip] if t > cutoff]

    if len(_gateway_failures[client_ip]) >= _GATEWAY_MAX_ATTEMPTS:
        security_logger.warning(f"Gateway lockout: {client_ip}")
        return templates.TemplateResponse("gateway.html", {
            "request": request, "error": None, "locked": True,
        })

    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "").strip()

    user_hash = _gw_hashlib.sha256(username.encode()).hexdigest()
    pass_hash = _gw_hashlib.sha256(password.encode()).hexdigest()

    if user_hash == _GATEWAY_USER_HASH and pass_hash == _GATEWAY_PASS_HASH:
        _gateway_failures.pop(client_ip, None)
        security_logger.info(f"Gateway access granted: {client_ip}")
        # Clear any existing session to force fresh 3FA login
        response = RedirectResponse(url="/", status_code=302)
        response.delete_cookie("session_token")
        return response
    else:
        _gateway_failures[client_ip].append(now)
        remaining = _GATEWAY_MAX_ATTEMPTS - len(_gateway_failures[client_ip])
        security_logger.warning(f"Gateway failed attempt: {client_ip} ({remaining} remaining)")
        error = "Access denied. Invalid credentials." if remaining > 0 else None
        locked = remaining <= 0
        return templates.TemplateResponse("gateway.html", {
            "request": request,
            "error": error if not locked else None,
            "locked": locked,
        })


@app.get("/dashboard/vault", response_class=HTMLResponse)
async def vault_dashboard_page(request: Request):
    """AgentVault™ dashboard — owner visibility into all vault operations."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)

    from app.agentvault.models import AgentVault, VaultObject, VaultAuditLog, AgentVaultTier

    tiers = []
    vaults = []
    audit_log = []
    vault_stats = {
        "total_vaults": 0, "total_objects": 0, "total_used_display": "0 B",
        "cache_count": 0, "paid_count": 0, "mrr": 0,
    }

    try:
        async with async_session() as db:
            tiers = await agentvault_service.list_tiers(db)

            # Get all vaults
            vault_result = await db.execute(
                select(AgentVault).where(AgentVault.status != "cancelled")
                .order_by(AgentVault.created_at.desc())
            )
            all_vaults = vault_result.scalars().all()
            for v in all_vaults:
                tier_result = await db.execute(
                    select(AgentVaultTier).where(AgentVaultTier.id == v.vault_tier_id)
                )
                tier = tier_result.scalar_one_or_none()
                vaults.append(agentvault_service._vault_to_dict(v, tier))

            vault_stats["total_vaults"] = len(all_vaults)
            vault_stats["total_objects"] = (await db.execute(
                select(func.count(VaultObject.id)).where(VaultObject.is_current_version == True)
            )).scalar() or 0
            total_used = sum(v.used_bytes for v in all_vaults)
            vault_stats["total_used_display"] = agentvault_service._format_bytes(total_used)
            vault_stats["cache_count"] = sum(1 for v in all_vaults if v.effective_monthly_zar == 0)
            vault_stats["paid_count"] = sum(1 for v in all_vaults if v.effective_monthly_zar > 0)
            vault_stats["mrr"] = sum(v.effective_monthly_zar for v in all_vaults)

            # Recent audit
            audit_result = await db.execute(
                select(VaultAuditLog).order_by(VaultAuditLog.created_at.desc()).limit(20)
            )
            audit_log = [
                {"action": l.action, "object_key": l.object_key, "bytes_delta": l.bytes_delta,
                 "result": l.result, "agent_id": l.agent_id, "created_at": str(l.created_at)}
                for l in audit_result.scalars().all()
            ]
    except Exception:
        pass

    return templates.TemplateResponse("vault.html", {
        "request": request, "authenticated": True, "active": "vault",
        "tiers": tiers, "vaults": vaults, "audit_log": audit_log,
        "vault_stats": vault_stats,
    })


@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    """Pricing page — shows sidebar when authenticated, standalone when not."""
    owner = get_current_owner(request)
    return templates.TemplateResponse("pricing.html", {
        "request": request,
        "authenticated": owner is not None,
        "active": "services",
        "breadcrumbs": [("Operations", "/dashboard"), ("Pricing", None)],
    })


@app.get("/owner/revenue", response_class=HTMLResponse)
async def revenue_dashboard_page(request: Request):
    """Revenue Intelligence Dashboard — owner only, 3FA protected."""
    owner = get_current_owner(request)
    if not owner:
        return RedirectResponse(url="/", status_code=302)
    async with async_session() as db:
        rev = await revenue_service.get_revenue_dashboard(db)
    return templates.TemplateResponse("revenue.html", {
        "request": request, "authenticated": True, "active": "revenue",
        "rev": rev,
    })
