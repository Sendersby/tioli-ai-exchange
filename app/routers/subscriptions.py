"""Router: subscriptions - auto-extracted from main.py (A-001)."""
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
from app.main_deps import (subscription_service)

from app.boardroom.payfast import payfast_router
router = APIRouter()


def _payfast_verify_signature(post_data: dict, passphrase: str) -> bool:
    """Verify PayFast ITN signature per PayFast documentation.

    Steps:
    1. Remove 'signature' field from the data
    2. URL-encode remaining fields in original order
    3. Append passphrase
    4. MD5 hash
    5. Constant-time compare with provided signature
    """
    import urllib.parse, hashlib, hmac
    received_sig = post_data.get("signature", "")
    if not received_sig:
        return False
    # Build verification string from all fields except signature, in original order
    verify_data = {k: v for k, v in post_data.items() if k != "signature"}
    verify_string = "&".join(
        f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in verify_data.items()
    )
    if passphrase:
        verify_string += f"&passphrase={urllib.parse.quote_plus(passphrase)}"
    expected_sig = hashlib.md5(verify_string.encode()).hexdigest()
    return hmac.compare_digest(expected_sig, received_sig)


@router.get("/api/v1/subscriptions/tiers")
async def api_subscription_tiers(db: AsyncSession = Depends(get_db)):
    """List all available subscription tiers with pricing and features. Public endpoint."""
    cached = cache.get("subscription_tiers")
    if cached:
        return cached
    result = await subscription_service.list_tiers(db)
    cache.set("subscription_tiers", result, TTL_LONG)
    return result

@router.post("/api/v1/subscriptions")
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

@router.get("/api/v1/subscriptions/{operator_id}")
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

@router.put("/api/v1/subscriptions/{operator_id}/upgrade")
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

@router.post("/api/v1/subscriptions/{operator_id}/renew")
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

@router.delete("/api/v1/subscriptions/{operator_id}")
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

@router.get("/api/v1/subscriptions/revenue/summary")
async def api_subscription_revenue(
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Get subscription revenue summary. Owner only."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await subscription_service.get_subscription_revenue(db)

@router.post("/api/v1/subscribe", include_in_schema=False)
async def subscribe_newsletter(request: Request, db: AsyncSession = Depends(get_db)):
    """Subscribe to weekly digest."""
    body = await validated_json(request)
    email = body.get("email", "").strip()
    if not email or "@" not in email:
        return JSONResponse(status_code=400, content={"error": "Valid email required"})
    from app.arch.email_digest import add_subscriber
    return await add_subscriber(db, email)

@router.post("/api/v1/unsubscribe", include_in_schema=False)
async def unsubscribe_newsletter(request: Request, db: AsyncSession = Depends(get_db)):
    """Unsubscribe from digest."""
    body = await validated_json(request)
    from app.arch.email_digest import remove_subscriber
    return await remove_subscriber(db, body.get("email", ""))

@router.get("/api/v1/digest/preview", include_in_schema=False)
async def preview_digest(db: AsyncSession = Depends(get_db)):
    """Preview this week's digest."""
    from app.arch.email_digest import generate_digest
    return await generate_digest(db)

@router.get("/api/v1/subscription-mgmt/plans", tags=["Subscriptions"])
async def api_subscription_plans(db: AsyncSession = Depends(get_db)):
    """List all available subscription plans."""
    from sqlalchemy import text
    r = await db.execute(text("SELECT * FROM subscription_plans ORDER BY price_zar ASC LIMIT 50"))
    return [{"plan_id": row.plan_id, "name": row.name, "price_zar": float(row.price_zar),
             "tokens_monthly": row.tokens_monthly, "memory_writes_daily": row.memory_writes_daily,
             "priority_discovery": row.priority_discovery, "advanced_analytics": row.advanced_analytics,
             "priority_support": row.priority_support, "description": row.description}
            for row in r.fetchall()]

@router.post("/api/v1/subscription-mgmt/create", tags=["Subscriptions"])
async def api_create_subscription(request: Request, db: AsyncSession = Depends(get_db)):
    """Create or upgrade a subscription. Returns PayFast payment URL for paid plans."""
    body = await validated_json(request)
    agent_id = body.get("agent_id", "")
    plan = body.get("plan", "free")
    from sqlalchemy import text

    # Get plan details
    plan_row = await db.execute(text("SELECT * FROM subscription_plans WHERE plan_id = :p"), {"p": plan})
    plan_data = plan_row.fetchone()
    if not plan_data:
        return {"error": f"Unknown plan: {plan}", "available": ["free", "builder", "pro"]}

    if plan == "free":
        # Free plan — just create subscription
        import uuid
        sub_id = str(uuid.uuid4())
        await db.execute(text(
            "INSERT INTO subscriptions (subscription_id, agent_id, plan, status, amount_zar, tokens_monthly, memory_writes_daily) "
            "VALUES (cast(:sid as uuid), :aid, :plan, 'active', 0, :tokens, :mem) "
            "ON CONFLICT (agent_id) DO UPDATE SET plan='free', status='active', updated_at=now()"
        ), {"sid": sub_id, "aid": agent_id, "plan": "free",
            "tokens": plan_data.tokens_monthly, "mem": plan_data.memory_writes_daily})
        await db.commit()
        return {"subscription_id": sub_id, "plan": "free", "status": "active", "payment_required": False}

    # Paid plan — generate PayFast payment URL
    import os, urllib.parse, hashlib
    merchant_id = os.environ.get("PAYFAST_MERCHANT_ID", "")
    merchant_key = os.environ.get("PAYFAST_MERCHANT_KEY", "")
    passphrase = os.environ.get("PAYFAST_PASSPHRASE", "")
    sandbox = os.environ.get("PAYFAST_SANDBOX", "true").lower() == "true"

    payment_data = {
        "merchant_id": merchant_id,
        "merchant_key": merchant_key,
        "return_url": os.environ.get("PAYFAST_RETURN_URL", "https://agentisexchange.com/pricing?payment=success"),
        "cancel_url": os.environ.get("PAYFAST_CANCEL_URL", "https://agentisexchange.com/pricing?payment=cancelled"),
        "notify_url": os.environ.get("PAYFAST_NOTIFY_URL", "https://exchange.tioli.co.za/api/v1/subscription-mgmt/payfast-notify"),
        "name_first": "AGENTIS",
        "name_last": "Operator",
        "email_address": body.get("email", "operator@agentis.exchange"),
        "m_payment_id": f"sub_{agent_id}_{plan}",
        "amount": f"{float(plan_data.price_zar):.2f}",
        "item_name": f"AGENTIS {plan_data.name} Plan — Monthly",
        "item_description": plan_data.description or f"{plan_data.name} subscription",
        "subscription_type": "1",
        "recurring_amount": f"{float(plan_data.price_zar):.2f}",
        "frequency": "3",
        "cycles": "0",
    }

    # Generate signature
    sig_string = "&".join(f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in payment_data.items())
    if passphrase:
        sig_string += f"&passphrase={urllib.parse.quote_plus(passphrase)}"
    signature = hashlib.md5(sig_string.encode()).hexdigest()
    payment_data["signature"] = signature

    base_url = "https://sandbox.payfast.co.za/eng/process" if sandbox else "https://www.payfast.co.za/eng/process"
    payment_url = f"{base_url}?{urllib.parse.urlencode(payment_data)}"

    # Create pending subscription
    import uuid
    sub_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO subscriptions (subscription_id, agent_id, plan, status, amount_zar, payment_ref, tokens_monthly, memory_writes_daily) "
        "VALUES (cast(:sid as uuid), :aid, :plan, 'pending_payment', :amount, :ref, :tokens, :mem)"
    ), {"sid": sub_id, "aid": agent_id, "plan": plan,
        "amount": float(plan_data.price_zar), "ref": f"sub_{agent_id}_{plan}",
        "tokens": plan_data.tokens_monthly, "mem": plan_data.memory_writes_daily})
    await db.commit()

    return {"subscription_id": sub_id, "plan": plan, "status": "pending_payment",
            "payment_url": payment_url, "amount_zar": float(plan_data.price_zar),
            "payment_required": True}

@router.post("/api/v1/subscription-mgmt/payfast-notify", tags=["Subscriptions"])
async def api_payfast_notify(request: Request, db: AsyncSession = Depends(get_db)):
    """PayFast ITN (Instant Transaction Notification) callback."""
    import logging as _pf_log
    _pf_logger = _pf_log.getLogger("payfast.itn")
    form = await request.form()
    data = dict(form)
    from sqlalchemy import text
    import os

    # T-005: Verify PayFast signature (CRITICAL security check)
    passphrase = os.environ.get("PAYFAST_PASSPHRASE", "")
    if not _payfast_verify_signature(data, passphrase):
        _pf_logger.warning(
            "SECURITY: PayFast ITN signature mismatch -- possible forgery. "
            f"m_payment_id={data.get('m_payment_id', '?')}"
        )
        raise HTTPException(status_code=400, detail="Invalid signature")

    # T-005: Verify amount matches expected subscription price
    amount_gross = float(data.get("amount_gross", 0))
    m_payment_id = data.get("m_payment_id", "")
    r = await db.execute(text(
        "SELECT amount_zar FROM subscriptions WHERE payment_ref = :ref AND status = 'pending_payment'"
    ), {"ref": m_payment_id})
    expected_row = r.fetchone()
    if expected_row and abs(float(expected_row.amount_zar) - amount_gross) > 0.01:
        _pf_logger.warning(
            f"SECURITY: PayFast amount mismatch. Expected R{expected_row.amount_zar}, "
            f"got R{amount_gross}. Ref={m_payment_id}"
        )
        raise HTTPException(status_code=400, detail="Amount mismatch")

    payment_status = data.get("payment_status", "")

    if payment_status == "COMPLETE":
        # Activate subscription
        await db.execute(text(
            "UPDATE subscriptions SET status = 'active', payfast_token = :token, "
            "started_at = now(), expires_at = now() + interval '30 days', updated_at = now() "
            "WHERE payment_ref = :ref AND status = 'pending_payment'"
        ), {"token": data.get("token", ""), "ref": m_payment_id})
        await db.commit()

        # Log to founder inbox
        import json
        await db.execute(text(
            "INSERT INTO arch_founder_inbox (item_type, priority, description, status, due_at) "
            "VALUES ('INFORMATION', 'ROUTINE', :desc, 'PENDING', now() + interval '24 hours')"
        ), {"desc": json.dumps({"subject": f"NEW SUBSCRIPTION: {m_payment_id}",
                                "situation": f"Payment {payment_status}. Amount: R{data.get('amount_gross', '?')}. Token: {data.get('token', '?')[:20]}..."})})
        await db.commit()

    return {"status": "received"}

@router.get("/api/v1/subscription-mgmt/status/{agent_id}", tags=["Subscriptions"])
async def api_subscription_status(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get subscription status for an agent."""
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT subscription_id, plan, status, amount_zar, tokens_monthly, memory_writes_daily, "
        "started_at, expires_at FROM subscriptions WHERE agent_id = :aid ORDER BY created_at DESC LIMIT 1"
    ), {"aid": agent_id})
    row = r.fetchone()
    if not row:
        return {"agent_id": agent_id, "plan": "free", "status": "active",
                "tokens_monthly": 100, "memory_writes_daily": 5, "note": "Default free tier"}
    return {"agent_id": agent_id, "subscription_id": str(row.subscription_id),
            "plan": row.plan, "status": row.status,
            "amount_zar": float(row.amount_zar) if row.amount_zar else 0,
            "tokens_monthly": row.tokens_monthly, "memory_writes_daily": row.memory_writes_daily,
            "started_at": str(row.started_at) if row.started_at else None,
            "expires_at": str(row.expires_at) if row.expires_at else None}

@router.post("/api/v1/subscription-mgmt/cancel/{agent_id}", tags=["Subscriptions"])
async def api_cancel_subscription(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Cancel a subscription. Reverts to free tier."""
    from sqlalchemy import text
    await db.execute(text(
        "UPDATE subscriptions SET status = 'cancelled', cancelled_at = now(), plan = 'free', "
        "tokens_monthly = 100, memory_writes_daily = 5, updated_at = now() WHERE agent_id = :aid AND status = 'active'"
    ), {"aid": agent_id})
    await db.commit()
    return {"agent_id": agent_id, "plan": "free", "status": "cancelled", "reverted_to": "free"}

@router.get("/api/v1/plans", tags=["Plans"])
async def api_list_plans(db: AsyncSession = Depends(get_db)):
    """List all available plans and add-ons with pricing."""
    from sqlalchemy import text
    r = await db.execute(text("SELECT * FROM plan_configurations ORDER BY price_zar ASC LIMIT 50"))
    return [{"sku": row.sku, "name": row.name, "type": row.plan_type,
             "price_zar": float(row.price_zar), "price_usd": float(row.price_usd) if row.price_usd else 0,
             "billing": row.billing, "api_calls": row.api_calls_monthly,
             "memory_entries": row.memory_entries, "commission_rate": float(row.commission_rate),
             "agents_max": row.agents_max, "features": row.features,
             "description": row.description} for row in r.fetchall()]

@router.post("/api/v1/checkout", tags=["Plans"])
async def api_cart_checkout(request: Request, db: AsyncSession = Depends(get_db)):
    """Process cart checkout — generates PayFast payment URL for selected SKUs."""
    body = await validated_json(request)
    items = body.get("items", [])  # List of SKU strings
    email = body.get("email", "")
    customer_id = body.get("customer_id", body.get("agent_id", body.get("operator_id", "")))

    if not items:
        return {"error": "No items selected"}
    if not email:
        return {"error": "Email required for payment"}

    from sqlalchemy import text
    import os, uuid, hashlib, urllib.parse

    # Look up all selected plans
    total_zar = 0
    plan_names = []
    primary_plan = None

    for sku in items:
        r = await db.execute(text("SELECT * FROM plan_configurations WHERE sku = :s"), {"s": sku})
        plan = r.fetchone()
        if plan:
            total_zar += float(plan.price_zar)
            plan_names.append(plan.name)
            if plan.plan_type in ("agent", "operator") and not primary_plan:
                primary_plan = plan

    if total_zar <= 0:
        # Free plan — activate immediately
        sub_id = str(uuid.uuid4())
        primary_sku = items[0] if items else "OP-EXPLORER"
        await db.execute(text(
            "INSERT INTO customer_subscriptions (id, customer_id, email, plan_sku, plan_name, plan_type, "
            "amount_zar, add_ons, status, started_at, expires_at) "
            "VALUES (cast(:id as uuid), :cid, :email, :sku, :name, :ptype, 0, :addons, 'active', now(), now() + interval '100 years')"
        ), {"id": sub_id, "cid": customer_id, "email": email,
            "sku": primary_sku, "name": plan_names[0] if plan_names else "Free",
            "ptype": "free", "addons": json.dumps(items)})
        await db.commit()
        return {"subscription_id": sub_id, "status": "active", "plan": primary_sku,
                "total_zar": 0, "payment_required": False}

    # Paid plan — generate PayFast URL
    merchant_id = os.environ.get("PAYFAST_MERCHANT_ID", "")
    merchant_key = os.environ.get("PAYFAST_MERCHANT_KEY", "")
    passphrase = os.environ.get("PAYFAST_PASSPHRASE", "")
    sandbox = os.environ.get("PAYFAST_SANDBOX", "true").lower() == "true"

    sub_id = str(uuid.uuid4())
    payment_ref = f"cart_{sub_id[:8]}"

    payment_data = {
        "merchant_id": merchant_id,
        "merchant_key": merchant_key,
        "return_url": os.environ.get("PAYFAST_RETURN_URL", "https://agentisexchange.com/pricing?payment=success"),
        "cancel_url": os.environ.get("PAYFAST_CANCEL_URL", "https://agentisexchange.com/pricing?payment=cancelled"),
        "notify_url": os.environ.get("PAYFAST_NOTIFY_URL", "https://exchange.tioli.co.za/api/v1/checkout/payfast-notify"),
        "name_first": "AGENTIS",
        "name_last": "Customer",
        "email_address": email,
        "m_payment_id": payment_ref,
        "amount": f"{total_zar:.2f}",
        "item_name": f"AGENTIS: {', '.join(plan_names[:3])}",
        "item_description": f"SKUs: {', '.join(items)}",
    }

    # Add recurring billing if monthly
    if primary_plan and primary_plan.billing == "monthly":
        payment_data["subscription_type"] = "1"
        payment_data["recurring_amount"] = f"{total_zar:.2f}"
        payment_data["frequency"] = "3"
        payment_data["cycles"] = "0"

    # Generate signature
    sig_string = "&".join(f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in payment_data.items())
    if passphrase:
        sig_string += f"&passphrase={urllib.parse.quote_plus(passphrase)}"
    signature = hashlib.md5(sig_string.encode()).hexdigest()
    payment_data["signature"] = signature

    base_url = "https://sandbox.payfast.co.za/eng/process" if sandbox else "https://www.payfast.co.za/eng/process"
    payment_url = f"{base_url}?{urllib.parse.urlencode(payment_data)}"

    # Create pending subscription
    primary_sku = items[0]
    primary_name = plan_names[0] if plan_names else "Bundle"
    plan_type = primary_plan.plan_type if primary_plan else "bundle"

    limits = {}
    if primary_plan:
        limits = {
            "api_calls": primary_plan.api_calls_monthly,
            "memory": primary_plan.memory_entries,
            "commission": float(primary_plan.commission_rate),
            "agents": primary_plan.agents_max,
        }

    await db.execute(text(
        "INSERT INTO customer_subscriptions (id, customer_id, email, plan_sku, plan_name, plan_type, "
        "amount_zar, add_ons, status, payment_ref, api_calls_monthly, memory_entries_max, "
        "commission_rate, agents_max) "
        "VALUES (cast(:id as uuid), :cid, :email, :sku, :name, :ptype, :amount, :addons, "
        "'pending_payment', :ref, :api, :mem, :comm, :agents)"
    ), {"id": sub_id, "cid": customer_id, "email": email,
        "sku": primary_sku, "name": primary_name, "ptype": plan_type,
        "amount": total_zar, "addons": json.dumps(items), "ref": payment_ref,
        "api": limits.get("api_calls", 10000), "mem": limits.get("memory", 500),
        "comm": limits.get("commission", 12.0), "agents": limits.get("agents", 3)})
    await db.commit()

    return {"subscription_id": sub_id, "status": "pending_payment",
            "plan": primary_sku, "items": items, "plan_names": plan_names,
            "total_zar": total_zar, "payment_url": payment_url, "payment_required": True}

@router.post("/api/v1/checkout/payfast-notify", tags=["Plans"])
async def api_checkout_payfast_notify(request: Request, db: AsyncSession = Depends(get_db)):
    """PayFast ITN callback for cart checkout payments."""
    import logging as _pf_log2
    _pf_logger2 = _pf_log2.getLogger("payfast.itn")
    form = await request.form()
    data = dict(form)
    from sqlalchemy import text
    import os

    # T-005: Verify PayFast signature (CRITICAL security check)
    passphrase = os.environ.get("PAYFAST_PASSPHRASE", "")
    if not _payfast_verify_signature(data, passphrase):
        _pf_logger2.warning(
            "SECURITY: PayFast checkout ITN signature mismatch -- possible forgery. "
            f"m_payment_id={data.get('m_payment_id', '?')}"
        )
        raise HTTPException(status_code=400, detail="Invalid signature")

    # T-005: Verify amount matches expected checkout price
    amount_gross = float(data.get("amount_gross", 0))
    payment_ref = data.get("m_payment_id", "")
    r = await db.execute(text(
        "SELECT amount_zar FROM customer_subscriptions WHERE payment_ref = :ref AND status = 'pending_payment'"
    ), {"ref": payment_ref})
    expected_row = r.fetchone()
    if expected_row and abs(float(expected_row.amount_zar) - amount_gross) > 0.01:
        _pf_logger2.warning(
            f"SECURITY: PayFast checkout amount mismatch. Expected R{expected_row.amount_zar}, "
            f"got R{amount_gross}. Ref={payment_ref}"
        )
        raise HTTPException(status_code=400, detail="Amount mismatch")

    payment_status = data.get("payment_status", "")

    if payment_status == "COMPLETE":
        await db.execute(text(
            "UPDATE customer_subscriptions SET status = 'active', payfast_token = :token, "
            "started_at = now(), expires_at = now() + interval '30 days', updated_at = now() "
            "WHERE payment_ref = :ref AND status = 'pending_payment'"
        ), {"token": data.get("token", ""), "ref": payment_ref})
        await db.commit()

        # Log to founder inbox
        import json
        await db.execute(text(
            "INSERT INTO arch_founder_inbox (item_type, priority, description, status, due_at) "
            "VALUES ('INFORMATION', 'URGENT', :desc, 'PENDING', now() + interval '24 hours')"
        ), {"desc": json.dumps({"subject": f"NEW PAYMENT: {payment_ref}",
                                "situation": f"Payment COMPLETE. Amount: R{data.get('amount_gross', '?')}. Ref: {payment_ref}"})})
        await db.commit()

    return {"status": "received"}

@router.get("/api/v1/customer/subscription/{customer_id}", tags=["Plans"])
async def api_customer_subscription(customer_id: str, db: AsyncSession = Depends(get_db)):
    """Get active subscription and limits for a customer."""
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT id, plan_sku, plan_name, plan_type, amount_zar, add_ons, status, "
        "api_calls_monthly, memory_entries_max, commission_rate, agents_max, "
        "started_at, expires_at FROM customer_subscriptions "
        "WHERE customer_id = :cid AND status = 'active' ORDER BY created_at DESC LIMIT 1"
    ), {"cid": customer_id})
    row = r.fetchone()
    if not row:
        return {"customer_id": customer_id, "plan": "free", "status": "active",
                "limits": {"api_calls": 10000, "memory_entries": 500, "commission_rate": 12.0, "agents_max": 3},
                "add_ons": []}

    return {
        "customer_id": customer_id,
        "subscription_id": str(row.id),
        "plan": row.plan_sku, "plan_name": row.plan_name, "plan_type": row.plan_type,
        "amount_zar": float(row.amount_zar),
        "status": row.status,
        "limits": {
            "api_calls": row.api_calls_monthly,
            "memory_entries": row.memory_entries_max,
            "commission_rate": float(row.commission_rate),
            "agents_max": row.agents_max,
        },
        "add_ons": row.add_ons if row.add_ons else [],
        "started_at": str(row.started_at) if row.started_at else None,
        "expires_at": str(row.expires_at) if row.expires_at else None,
    }

@router.get("/api/v1/customer/dashboard-config/{customer_id}", tags=["Plans"])
async def api_dashboard_config(customer_id: str, db: AsyncSession = Depends(get_db)):
    """Get dashboard configuration based on customer tier — what features to show/lock."""
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT plan_sku, plan_name, plan_type, add_ons, api_calls_monthly, memory_entries_max, "
        "commission_rate, agents_max FROM customer_subscriptions "
        "WHERE customer_id = :cid AND status = 'active' ORDER BY created_at DESC LIMIT 1"
    ), {"cid": customer_id})
    row = r.fetchone()

    if not row:
        return {
            "plan": "free", "plan_name": "Free",
            "features": {
                "dashboard": True, "transactions": True, "agents": True,
                "escrow": True, "trading": True, "governance": True,
                "lending": False, "analytics": False, "intelligence": False,
                "vault": False, "guild": False, "priority_support": False,
            },
            "limits": {"api_calls": 10000, "memory": 500, "agents": 3, "commission": 12.0},
            "locked_features": ["analytics", "intelligence", "vault", "guild", "priority_support"],
            "upgrade_cta": "Upgrade to Builder for R299/mo to unlock analytics and more agents",
        }

    add_ons = row.add_ons if row.add_ons else []
    plan = row.plan_sku

    features = {
        "dashboard": True, "transactions": True, "agents": True,
        "escrow": True, "trading": True, "governance": True,
        "lending": plan in ("OP-PROFESSIONAL", "OP-ENTERPRISE"),
        "analytics": plan in ("OP-PROFESSIONAL", "OP-ENTERPRISE") or "AH-PRO" in add_ons,
        "intelligence": plan in ("OP-PROFESSIONAL", "OP-ENTERPRISE"),
        "vault": any(sku.startswith("AV-") and sku != "AV-CACHE" for sku in add_ons),
        "guild": any(sku.startswith("GUILD") for sku in add_ons),
        "priority_support": plan in ("OP-PROFESSIONAL", "OP-ENTERPRISE"),
        "benchmarking": "BENCH" in add_ons,
        "capability_badge": "BADGE" in add_ons,
    }

    locked = [f for f, v in features.items() if not v]

    return {
        "plan": plan, "plan_name": row.plan_name,
        "features": features,
        "limits": {
            "api_calls": row.api_calls_monthly,
            "memory": row.memory_entries_max,
            "agents": row.agents_max,
            "commission": float(row.commission_rate),
        },
        "add_ons": add_ons,
        "locked_features": locked,
        "upgrade_cta": f"Upgrade from {row.plan_name} at /pricing" if locked else None,
    }
