"""Shared dependencies for all extracted routers (A-001 decomposition).

This module re-exports service instances, auth helpers, Pydantic models,
and utility functions that were previously defined inline in main.py.
Router files import from here instead of main.py to avoid circular imports.
"""

import json
import os
import time
import logging
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import Depends, Request, HTTPException, Header
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

security_logger = logging.getLogger("tioli.security")

from app.config import settings
from app.database.db import get_db, async_session
from app.blockchain.chain import Blockchain
from app.blockchain.transaction import Transaction, TransactionType
from app.agents.models import Agent, Wallet, Loan
from app.agents.wallet import WalletService
from app.utils.validators import require_kyc_verified
from app.utils.audit import log_financial_event
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
from app.revenue.service import RevenueEngineService

# Slowapi limiter
from slowapi import Limiter
import redis.asyncio as _cache_redis


# ── Service Instances ────────────────────────────────────────────────
blockchain = Blockchain(storage_path="/home/tioli/app/tioli_exchange_chain.json")
fee_engine = FeeEngine()
wallet_service = WalletService(blockchain=blockchain, fee_engine=fee_engine)
governance_service = GovernanceService()
currency_service = CurrencyService()
financial_governance = FinancialGovernance()

_revenue_engine = RevenueEngineService()
_STREAM_MAP = {
    "founder_commission": "agentbroker_commission",
    "charity_fee": "agentbroker_commission",
    "operator_commission": "operator_subscriptions",
    "platform_fee": "premium_addons",
}


async def record_revenue(db, source, amount, currency, desc):
    """Record revenue to both platform_revenue and revenue_transactions."""
    await financial_governance.record_revenue(db, source, amount, currency, desc)
    _rev_log = logging.getLogger("revenue.pipeline")
    try:
        stream = _STREAM_MAP.get(source, source)
        await _revenue_engine.record_revenue(
            db, stream=stream, source_type=source,
            gross_zar=amount if currency == "ZAR" else amount * 18.50,
            description=desc, source_id=None, agent_id=None,
        )
        _rev_log.info(f"revenue_transactions: recorded {amount} {currency} via {source}")
    except Exception as _rev_err:
        _rev_log.error(
            f"revenue_transactions recording failed (non-fatal): {_rev_err}",
            exc_info=True,
        )

# Alias for backward compat
_record_revenue = record_revenue

wallet_service.set_revenue_recorder(record_revenue)


async def _update_profitability(db):
    summary = await financial_governance.get_financial_summary(db)
    fee_engine.update_profitability(summary["total_revenue"], summary["total_expenses"])


wallet_service.set_profitability_updater(_update_profitability)

platform_monitor = PlatformMonitor(blockchain=blockchain)
growth_engine = GrowthEngine()
crypto_wallet_service = CryptoWalletService()
conversion_engine = ConversionEngine(
    currency_service=currency_service, fee_engine=fee_engine, blockchain=blockchain
)
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
trading_engine = TradingEngine(blockchain=blockchain, fee_engine=fee_engine)
pricing_engine = PricingEngine(currency_service=currency_service)
lending_marketplace = LendingMarketplace()
compute_storage = ComputeStorageService(blockchain=blockchain)
market_maker = MarketMakerService(
    trading_engine=trading_engine, currency_service=currency_service
)
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

# Agentis Cooperative Bank services
from app.agentis.compliance_service import AgentisComplianceService
from app.agentis.member_service import AgentisMemberService
from app.agentis.account_service import AgentisAccountService
from app.agentis.payment_service import AgentisPaymentService

agentis_compliance = AgentisComplianceService(blockchain=blockchain)
agentis_members = AgentisMemberService(
    compliance_service=agentis_compliance, blockchain=blockchain
)
agentis_accounts = AgentisAccountService(
    compliance_service=agentis_compliance,
    member_service=agentis_members,
    blockchain=blockchain,
)
agentis_payments = AgentisPaymentService(
    compliance_service=agentis_compliance,
    member_service=agentis_members,
    account_service=agentis_accounts,
    blockchain=blockchain,
)

# Wire Agentis services into routes module
import app.agentis.routes as agentis_routes
agentis_routes.compliance_service = agentis_compliance
agentis_routes.member_service = agentis_members
agentis_routes.account_service = agentis_accounts
agentis_routes.payment_service = agentis_payments

# AgentBroker initialization
from app.agentbroker.services import EngagementService as ABEngagementService
import app.agentbroker.routes as ab_routes
ab_routes.engagement_service = ABEngagementService(
    blockchain=blockchain, fee_engine=fee_engine
)

# ── Templates ────────────────────────────────────────────────────────
templates = Jinja2Templates(directory="app/templates")


class _StrKeyCache(dict):
    def __missing__(self, key):
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[str(key)]
        except KeyError:
            return default

    def __setitem__(self, key, value):
        super().__setitem__(str(key), value)

    def __getitem__(self, key):
        return super().__getitem__(str(key))

    def __contains__(self, key):
        return super().__contains__(str(key))


templates.env.cache = _StrKeyCache()

# ── Rate Limiter ─────────────────────────────────────────────────────


def _rate_limit_key(request):
    """Rate limit key - exempt localhost."""
    client_ip = request.headers.get(
        "X-Real-IP", request.client.host if request.client else "unknown"
    )
    if client_ip in ("127.0.0.1", "::1", "localhost"):
        return "localhost_exempt"
    return client_ip


limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=["100/minute"],
    storage_uri="redis://localhost:6379/1",
    in_memory_fallback_enabled=True,
)

# ── Redis Cache ──────────────────────────────────────────────────────
_cache_client = _cache_redis.from_url("redis://localhost:6379/2")


async def cached_response(key: str, ttl: int, fetch_fn):
    """Check Redis cache first, fall back to fetch_fn."""
    try:
        cached = await _cache_client.get(key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        import logging; logging.getLogger("main_deps").warning(f"Suppressed: {e}")
    result = await fetch_fn()
    try:
        await _cache_client.setex(key, ttl, json.dumps(result, default=str))
    except Exception as e:
        import logging; logging.getLogger("main_deps").warning(f"Suppressed: {e}")
    return result

# Alias for backward compat
_cached_response = cached_response

# ── Brute-Force Protection ──────────────────────────────────────────
_auth_failures: dict[str, list[float]] = defaultdict(list)
AUTH_LOCKOUT_THRESHOLD = 10
AUTH_LOCKOUT_WINDOW = 900


# ── Agent Auth Dependency ────────────────────────────────────────────
async def require_agent(
    request: Request,
    authorization: str = Header(..., description="Bearer <api_key>"),
    db: AsyncSession = Depends(get_db),
) -> Agent:
    """Dependency that authenticates an AI agent via API key."""
    client_ip = request.headers.get(
        "X-Real-IP", request.client.host if request.client else "unknown"
    )

    now = time.time()
    cutoff = now - AUTH_LOCKOUT_WINDOW
    _auth_failures[client_ip] = [
        t for t in _auth_failures[client_ip] if t > cutoff
    ]
    if len(_auth_failures[client_ip]) >= AUTH_LOCKOUT_THRESHOLD:
        security_logger.warning(
            f"Auth lockout: {client_ip} ({len(_auth_failures[client_ip])} failures)"
        )
        raise HTTPException(
            status_code=429,
            detail="Too many failed authentication attempts. Try again in 15 minutes.",
        )

    if not authorization.startswith("Bearer "):
        _auth_failures[client_ip].append(now)
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    api_key = authorization[7:]
    if len(api_key) < 10 or len(api_key) > 200:
        _auth_failures[client_ip].append(now)
        raise HTTPException(status_code=401, detail="Invalid API key format")
    agent = await authenticate_agent(db, api_key)
    if not agent:
        _auth_failures[client_ip].append(now)
        security_logger.warning(
            f"Auth failure: {client_ip} (attempt {len(_auth_failures[client_ip])})"
        )
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return agent


# ── Transaction Enrichment ───────────────────────────────────────────
def enrich_transaction_response(result: dict) -> dict:
    """Add blockchain proof + charitable allocation to any transaction response."""
    chain_info = blockchain.get_chain_info()
    all_tx = blockchain.get_all_transactions()
    total_charitable = sum(tx.get("charity_fee", 0) for tx in all_tx)

    result["blockchain"] = {
        "chain_valid": chain_info["is_valid"],
        "latest_block_hash": chain_info["latest_block_hash"],
        "block_count": chain_info["chain_length"],
        "total_transactions": chain_info["total_transactions"],
    }
    result["charitable_impact"] = {
        "this_transaction": result.get("charity_fee", 0),
        "running_total": round(total_charitable, 2),
        "message": "10% of all platform commission is allocated to charitable causes and recorded on-chain.",
    }
    result["verification"] = {
        "explorer_url": "https://exchange.tioli.co.za/explorer",
        "docs_url": "https://exchange.tioli.co.za/docs",
    }
    return result


# ── Pydantic Request Models ─────────────────────────────────────────

class AgentRegisterRequest(BaseModel):
    name: str
    platform: str
    description: str = ""
    referral_code: str | None = None

class TransferRequest(BaseModel):
    receiver_id: str
    amount: float
    currency: str = "AGENTIS"
    description: str = ""

class DepositRequest(BaseModel):
    amount: float
    currency: str = "AGENTIS"
    description: str = ""

class WithdrawRequest(BaseModel):
    amount: float
    currency: str = "AGENTIS"
    description: str = ""

class PlaceOrderRequest(BaseModel):
    side: str
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
    currency: str = "AGENTIS"
    min_amount: float
    max_amount: float
    interest_rate: float
    term_hours: float | None = None
    description: str = ""

class LoanBorrowRequest(BaseModel):
    currency: str = "AGENTIS"
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
    currency: str = "AGENTIS"

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
    network: str

class CryptoWithdrawRequest(BaseModel):
    network: str
    to_address: str
    amount: float
    currency: str

class PayoutDestRequest(BaseModel):
    owner: str = "founder"
    destination_type: str
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
    currency: str = "AGENTIS"
    beneficiary_id: str | None = None
    reason: str = ""
    expires_hours: float = 24

class AgentProfileRequest(BaseModel):
    display_name: str
    tagline: str = ""
    capabilities: str = ""
    services_offered: str = ""
    preferred_currencies: str = "AGENTIS"
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
    price_currency: str = "AGENTIS"

class KYARequest(BaseModel):
    operator_name: str | None = None
    operator_jurisdiction: str | None = None
    purpose: str | None = None

class IndexRequest(BaseModel):
    name: str
    description: str = ""
    components: str

class CharterAmendRequest(BaseModel):
    amendment_type: str
    target_principle: int | None = None
    proposed_name: str | None = None
    proposed_text: str
    rationale: str = ""

class CharterVoteRequest(BaseModel):
    vote: str


# ── Webhook Delivery Helper ─────────────────────────────────────────
async def _deliver_webhooks(db, event_type: str, payload: dict):
    """Deliver webhook payloads to all registered URLs for this event type."""
    from sqlalchemy import text
    import httpx
    _wh_log = logging.getLogger("webhooks")
    try:
        hooks = await db.execute(text(
            "SELECT id, url, events FROM webhook_registrations WHERE is_active = true LIMIT 200"
        ))
        for hook in hooks.fetchall():
            events = hook.events if isinstance(hook.events, list) else []
            if event_type in events or "all" in events:
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.post(hook.url, json={
                            "event": event_type,
                            "payload": payload,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "source": "agentis-exchange"
                        })
                        await db.execute(text(
                            "UPDATE webhook_registrations SET last_triggered = now() WHERE id = :id"
                        ), {"id": hook.id})
                        _wh_log.info(f"Webhook {hook.id[:8]} delivered to {hook.url}: {resp.status_code}")
                except Exception as e:
                    await db.execute(text(
                        "UPDATE webhook_registrations SET failures = failures + 1 WHERE id = :id"
                    ), {"id": hook.id})
                    _wh_log.warning(f"Webhook {hook.id[:8]} delivery failed: {e}")
        await db.commit()
    except Exception as e:
        _wh_log.error(f"Webhook delivery error: {e}")
