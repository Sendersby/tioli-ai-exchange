"""Router: exchange - auto-extracted from main.py (A-001)."""
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
from app.main_deps import (benchmarking_service, blockchain, cached_response, conversion_engine, credit_scoring, crypto_wallet_service, currency_service, enrich_transaction_response, export_service, fee_engine, forex_service, futures_service, idempotency_service, incentive_programme, intelligence_service, investment_service, liquidity_service, market_maker, payout_service, pricing_engine, require_agent, security_guardian, templates, trading_engine, training_data_service, verticals_service)
from app.main_deps import (CancelOrderRequest, ConversionRequest, CreateTokenRequest, CryptoAddressRequest, CryptoWithdrawRequest, IndexRequest, PayoutDestRequest, PlaceOrderRequest, WithdrawRequest)

_cached_response = cached_response

router = APIRouter()

@router.post("/api/exchange/order")
async def api_place_order(
    req: PlaceOrderRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Place a buy or sell order on the exchange."""
    await require_kyc_verified(db, agent.id)
    if idempotency_key:
        cached = await idempotency_service.check_and_store(db, idempotency_key, "order", agent.id)
        if cached:
            return JSONResponse(content=json.loads(cached))
    result = await trading_engine.place_order(
        db, agent.id, req.side, req.base_currency, req.quote_currency,
        req.price, req.quantity,
    )
    await log_financial_event(db, "ORDER_PLACED", actor_id=agent.id, actor_type="agent",
                              target_id=result.get("order_id"), target_type="order",
                              amount=req.price * req.quantity, currency=req.quote_currency,
                              after_state={"side": req.side, "trades": result.get("trades_executed", 0)})
    if result["trades_executed"] > 0:
        await pricing_engine.update_rates_from_trade(
            db, req.base_currency, req.quote_currency
        )
    result = enrich_transaction_response(result)
    if idempotency_key:
        await idempotency_service.store_response(db, idempotency_key, "order", agent.id, json.dumps(result, default=str))
    return result

@router.post("/api/exchange/cancel")
async def api_cancel_order(
    req: CancelOrderRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an open order."""
    return await trading_engine.cancel_order(db, req.order_id, agent.id)

@router.get("/api/exchange/orderbook/{base}/{quote}")
async def api_order_book(
    base: str, quote: str, depth: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get the order book for a trading pair."""
    return await trading_engine.get_order_book(db, base, quote, depth)

@router.get("/api/exchange/trades/{base}/{quote}")
async def api_recent_trades(
    base: str, quote: str, limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get recent trades for a pair."""
    return await trading_engine.get_recent_trades(db, base, quote, limit)

@router.get("/api/exchange/price/{base}/{quote}")
async def api_market_price(
    base: str, quote: str, db: AsyncSession = Depends(get_db),
):
    """Get the current market price for a trading pair."""
    return await pricing_engine.get_market_price(db, base, quote)

@router.get("/api/exchange/summary/{base}/{quote}")
async def api_market_summary(
    base: str, quote: str, db: AsyncSession = Depends(get_db),
):
    """Full market summary for a trading pair."""
    return await pricing_engine.get_market_summary(db, base, quote)

@router.get("/api/exchange/rates")
async def api_all_rates(db: AsyncSession = Depends(get_db)):
    """All current exchange rates (cached 60s)."""
    return await _cached_response("cache:exchange:rates", 60,
        lambda: pricing_engine.get_all_rates(db))

@router.get("/api/exchange/my-orders")
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

@router.get("/api/currencies")
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

@router.post("/api/currencies/create")
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

@router.post("/api/v1/orders/expire-stale", tags=["Orders"])
async def api_expire_stale_orders(db: AsyncSession = Depends(get_db)):
    """Expire orders that have been open for more than 24 hours."""
    from sqlalchemy import text
    import logging
    _logger = logging.getLogger("orders.expiry")
    result = await db.execute(text(
        "UPDATE orders SET status = 'expired' "
        "WHERE id IN (SELECT id FROM orders WHERE status = 'open' AND created_at < NOW() - INTERVAL '24 hours' LIMIT 200) "
        "RETURNING id"
    ))
    expired_ids = result.fetchall()  # LIMIT applied
    count = len(expired_ids)
    await db.commit()
    if count > 0:
        _logger.info(f"Expired {count} stale orders (open > 24h)")
    return {"expired_count": count, "status": "ok"}

@router.post("/api/forex/update")
async def api_forex_update(request: Request, db: AsyncSession = Depends(get_db)):
    """Fetch live forex rates and update platform fiat cross-rates."""
    # T-007: Allow internal calls from scheduler (localhost) without auth
    client_host = request.client.host if request.client else ""
    is_internal = client_host in ("127.0.0.1", "::1", "localhost")
    if not is_internal:
        owner = get_current_owner(request)
        if not owner:
            raise HTTPException(status_code=401, detail="Owner authentication required")
    return await forex_service.update_platform_rates(db)

@router.get("/api/forex/rates")
async def api_forex_rates():
    """Get cached fiat exchange rates."""
    return forex_service.get_cached_rates()

@router.get("/api/fees/schedule")
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

@router.post("/api/crypto/generate-address")
async def api_generate_deposit_address(
    req: CryptoAddressRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Generate a crypto deposit address."""
    return await crypto_wallet_service.generate_deposit_address(db, agent.id, req.network)

@router.get("/api/crypto/addresses")
async def api_get_addresses(
    network: str = None, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Get your crypto addresses."""
    return await crypto_wallet_service.get_addresses(db, agent.id, network)

@router.post("/api/crypto/withdraw")
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

@router.get("/api/crypto/transactions")
async def api_crypto_transactions(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Get crypto transaction history."""
    return await crypto_wallet_service.get_crypto_transactions(db, agent.id)

@router.get("/api/crypto/stats")
async def api_crypto_stats(db: AsyncSession = Depends(get_db)):
    """Platform crypto transaction statistics."""
    return await crypto_wallet_service.get_platform_crypto_stats(db)

@router.post("/api/convert/quote")
async def api_conversion_quote(
    req: ConversionRequest, db: AsyncSession = Depends(get_db),
):
    """Get a conversion quote (no execution)."""
    return await conversion_engine.get_conversion_quote(
        db, req.from_currency, req.to_currency, req.amount,
    )

@router.post("/api/convert/execute")
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

@router.get("/api/convert/history")
async def api_conversion_history(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Get your conversion history."""
    return await conversion_engine.get_conversion_history(db, agent.id)

@router.post("/api/payouts/destination")
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

@router.get("/api/payouts/destinations/{owner_type}")
async def api_get_destinations(
    owner_type: str, db: AsyncSession = Depends(get_db),
):
    """Get payout destinations for founder or charity."""
    return await payout_service.get_destinations(db, owner_type)

@router.get("/api/payouts/history/{owner_type}")
async def api_payout_history(
    owner_type: str, db: AsyncSession = Depends(get_db),
):
    """Get payout history."""
    return await payout_service.get_payout_history(db, owner_type)

@router.get("/api/investing/portfolio")
async def api_get_portfolio(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Get your full portfolio with valuations."""
    return await investment_service.get_portfolio(db, agent.id)

@router.post("/api/investing/snapshot")
async def api_portfolio_snapshot(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Take a portfolio snapshot for historical tracking."""
    snapshot = await investment_service.take_portfolio_snapshot(db, agent.id)
    return {"snapshot_id": snapshot.id, "value_tioli": snapshot.total_value_tioli}

@router.get("/api/investing/history")
async def api_portfolio_history(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Get portfolio history."""
    return await investment_service.get_portfolio_history(db, agent.id)

@router.get("/api/investing/performance")
async def api_portfolio_performance(
    agent: Agent = Depends(require_agent), db: AsyncSession = Depends(get_db),
):
    """Get portfolio performance (P&L, ROI)."""
    return await investment_service.get_portfolio_performance(db, agent.id)

@router.get("/api/investing/indices")
async def api_get_indices(db: AsyncSession = Depends(get_db)):
    """List market indices."""
    return await investment_service.get_indices(db)

@router.post("/api/investing/indices")
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

@router.post("/api/liquidity/seed")
async def api_seed_liquidity(
    currency: str = "AGENTIS", amount: float = 100000,
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Seed the founder liquidity pool (owner only)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await liquidity_service.seed_pool(db, currency, amount)

@router.get("/api/liquidity/status")
async def api_liquidity_status(db: AsyncSession = Depends(get_db)):
    """Get liquidity pool status."""
    return await liquidity_service.get_pool_status(db)

@router.get("/api/credit-score/{agent_id}")
async def api_credit_score(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get an agent's credit score."""
    return await credit_scoring.calculate_credit_score(db, agent_id)

@router.post("/api/market-maker/refresh")
async def api_market_maker_refresh(
    request: Request, db: AsyncSession = Depends(get_db),
):
    """Refresh market maker orders on all pairs (owner only)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await market_maker.refresh_orders(db)

@router.get("/api/market-maker/status")
async def api_market_maker_status():
    """Get market maker configuration and status."""
    return market_maker.get_status()

@router.post("/api/market-maker/configure")
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

@router.get("/api/incentives/status")
async def api_incentive_status(db: AsyncSession = Depends(get_db)):
    """Get the incentive programme status and spending."""
    return await incentive_programme.get_programme_status(db)

@router.post("/api/incentives/welcome/{agent_id}")
async def api_grant_welcome_bonus(
    agent_id: str, request: Request, db: AsyncSession = Depends(get_db),
):
    """Grant welcome bonus to a new agent (owner or system call)."""
    result = await incentive_programme.grant_welcome_bonus(db, agent_id)
    if not result:
        return {"status": "skipped", "reason": "Already received or programme limit reached"}
    return result

@router.get("/api/incentives/agent/{agent_id}")
async def api_agent_incentives(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get all incentives received by an agent."""
    return await incentive_programme.get_agent_incentives(db, agent_id)

@router.get("/api/v1/futures/search")
async def api_search_futures(capability_tag: str | None = None, max_price: float | None = None, db: AsyncSession = Depends(get_db)):
    if not settings.futures_enabled:
        raise HTTPException(status_code=503, detail="Futures module not enabled")
    return await futures_service.search_futures(db, capability_tag, max_price)

@router.post("/api/v1/futures/{future_id}/reserve")
async def api_reserve_future(future_id: str, buyer_operator_id: str, units: int, db: AsyncSession = Depends(get_db)):
    if not settings.futures_enabled:
        raise HTTPException(status_code=503, detail="Futures module not enabled")
    return await futures_service.reserve(db, future_id, buyer_operator_id, units)

@router.post("/api/v1/futures/{future_id}/settle")
async def api_settle_future(future_id: str, db: AsyncSession = Depends(get_db)):
    if not settings.futures_enabled:
        raise HTTPException(status_code=503, detail="Futures module not enabled")
    return await futures_service.settle(db, future_id)

@router.get("/api/v1/futures/market")
async def api_futures_market(db: AsyncSession = Depends(get_db)):
    if not settings.futures_enabled:
        raise HTTPException(status_code=503, detail="Futures module not enabled")
    return await futures_service.get_market(db)

@router.post("/api/v1/training/datasets")
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

@router.get("/api/v1/training/datasets/search")
async def api_search_datasets(domain_tag: str | None = None, licence_type: str | None = None, max_price: float | None = None, db: AsyncSession = Depends(get_db)):
    if not settings.training_data_enabled:
        raise HTTPException(status_code=503, detail="Training data module not enabled")
    return await training_data_service.search_datasets(db, domain_tag, licence_type, max_price)

@router.post("/api/v1/training/datasets/{dataset_id}/purchase")
async def api_purchase_dataset(dataset_id: str, buyer_operator_id: str, db: AsyncSession = Depends(get_db)):
    if not settings.training_data_enabled:
        raise HTTPException(status_code=503, detail="Training data module not enabled")
    return await training_data_service.purchase(db, dataset_id, buyer_operator_id)

@router.get("/api/v1/training/datasets/{dataset_id}/verify")
async def api_verify_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)):
    result = await training_data_service.verify_provenance(db, dataset_id)
    if not result:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return result

@router.post("/api/v1/benchmarking/evaluators")
async def api_register_evaluator(
    agent_id: str, operator_id: str, specialisation_domains: str,
    methodology_description: str, price_per_evaluation: float = 1200.0,
    db: AsyncSession = Depends(get_db),
):
    if not settings.benchmarking_enabled:
        raise HTTPException(status_code=503, detail="Benchmarking module not enabled")
    domains = [d.strip() for d in specialisation_domains.split(",")]
    return await benchmarking_service.register_evaluator(db, agent_id, operator_id, domains, methodology_description, price_per_evaluation)

@router.post("/api/v1/benchmarking/reports/commission")
async def api_commission_report(
    evaluator_id: str, subject_agent_id: str, task_category: str,
    commissioned_by_operator_id: str, report_type: str = "single",
    db: AsyncSession = Depends(get_db),
):
    if not settings.benchmarking_enabled:
        raise HTTPException(status_code=503, detail="Benchmarking module not enabled")
    return await benchmarking_service.commission_report(db, evaluator_id, subject_agent_id, task_category, commissioned_by_operator_id, report_type)

@router.get("/api/v1/benchmarking/reports/{report_id}")
async def api_get_benchmark_report(report_id: str, db: AsyncSession = Depends(get_db)):
    if not settings.benchmarking_enabled:
        raise HTTPException(status_code=503, detail="Benchmarking module not enabled")
    result = await benchmarking_service.get_report(db, report_id)
    if not result:
        raise HTTPException(status_code=404, detail="Report not found")
    return result

@router.get("/api/v1/benchmarking/reports/search")
async def api_search_reports(agent_id: str | None = None, task_category: str | None = None, min_score: float | None = None, db: AsyncSession = Depends(get_db)):
    if not settings.benchmarking_enabled:
        raise HTTPException(status_code=503, detail="Benchmarking module not enabled")
    return await benchmarking_service.search_reports(db, agent_id, task_category, min_score)

@router.get("/api/v1/benchmarking/leaderboard")
async def api_leaderboard(task_category: str | None = None, db: AsyncSession = Depends(get_db)):
    if not settings.benchmarking_enabled:
        raise HTTPException(status_code=503, detail="Benchmarking module not enabled")
    return await benchmarking_service.get_leaderboard(db, task_category)

@router.get("/api/v1/intelligence/tiers")
async def api_intelligence_tiers():
    return await intelligence_service.get_tiers()

@router.get("/api/v1/intelligence/market")
async def api_market_intelligence(tier: str = "public", category: str | None = None, db: AsyncSession = Depends(get_db)):
    if not settings.intelligence_enabled:
        raise HTTPException(status_code=503, detail="Intelligence module not enabled")
    return await intelligence_service.get_market_intelligence(db, tier, category)

@router.post("/api/v1/intelligence/subscribe")
async def api_intelligence_subscribe(operator_id: str, tier: str = "standard", db: AsyncSession = Depends(get_db)):
    if not settings.intelligence_enabled:
        raise HTTPException(status_code=503, detail="Intelligence module not enabled")
    return await intelligence_service.subscribe(db, operator_id, tier)

@router.get("/api/v1/intelligence/alerts")
async def api_intelligence_alerts(subscription_id: str, db: AsyncSession = Depends(get_db)):
    if not settings.intelligence_enabled:
        raise HTTPException(status_code=503, detail="Intelligence module not enabled")
    return await intelligence_service.get_alerts(db, subscription_id)

@router.post("/api/v1/intelligence/pipeline/run")
async def api_run_intelligence_pipeline(request: Request, db: AsyncSession = Depends(get_db)):
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await intelligence_service.run_nightly_pipeline(db)

@router.post("/api/v1/verticals/{vertical_id}/register")
async def api_register_vertical(vertical_id: str, operator_id: str, sector_licence_ref: str | None = None, request: Request = None, db: AsyncSession = Depends(get_db)):
    if not settings.verticals_enabled:
        raise HTTPException(status_code=503, detail="Verticals module not enabled")
    return await verticals_service.register_operator(db, operator_id, vertical_id, sector_licence_ref)

@router.get("/api/v1/verticals/agriculture/loan-templates")
async def api_loan_templates(db: AsyncSession = Depends(get_db)):
    if not settings.verticals_enabled:
        raise HTTPException(status_code=503, detail="Verticals module not enabled")
    return await verticals_service.get_loan_templates(db)

@router.get("/api/exports/tax-csv")
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

@router.get("/api/exports/receipt/{tx_index}")
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

@router.get("/api/transactions/{agent_id}")
async def api_agent_transactions(agent_id: str):
    return blockchain.get_transactions_for_agent(agent_id)
