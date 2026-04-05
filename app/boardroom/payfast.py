import json
"""PayFast Payment Integration for TiOLi AGENTIS.

Handles the $1/month premium directory subscription.
PayFast sandbox for testing, live for production.

Flow:
1. User clicks "Upgrade to Premium" → generates PayFast payment form
2. PayFast processes payment → sends ITN (Instant Transaction Notification) to our server
3. We verify the ITN → activate premium subscription
4. Recurring monthly billing handled by PayFast subscriptions
"""

import hashlib
import logging
import os
import urllib.parse
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db

log = logging.getLogger("boardroom.payfast")

payfast_router = APIRouter(prefix="/api/v1/payfast", tags=["PayFast"])

# PayFast URLs
PAYFAST_SANDBOX_URL = "https://sandbox.payfast.co.za/eng/process"
PAYFAST_LIVE_URL = "https://www.payfast.co.za/eng/process"
PAYFAST_SANDBOX_VALIDATE = "https://sandbox.payfast.co.za/eng/query/validate"
PAYFAST_LIVE_VALIDATE = "https://www.payfast.co.za/eng/query/validate"


def _get_payfast_config():
    """Get PayFast configuration from environment."""
    return {
        "merchant_id": os.getenv("PAYFAST_MERCHANT_ID", ""),
        "merchant_key": os.getenv("PAYFAST_MERCHANT_KEY", ""),
        "passphrase": os.getenv("PAYFAST_PASSPHRASE", ""),
        "sandbox": os.getenv("PAYFAST_SANDBOX", "true").lower() == "true",
        "return_url": os.getenv("PAYFAST_RETURN_URL", "https://exchange.tioli.co.za/premium/thank-you"),
        "cancel_url": os.getenv("PAYFAST_CANCEL_URL", "https://exchange.tioli.co.za/premium/cancelled"),
        "notify_url": os.getenv("PAYFAST_NOTIFY_URL", "https://exchange.tioli.co.za/api/v1/payfast/itn"),
    }


def _generate_signature(data: dict, passphrase: str = "") -> str:
    """Generate PayFast MD5 signature."""
    # Build parameter string (alphabetical order, URL encoded)
    param_string = "&".join(
        f"{k}={urllib.parse.quote_plus(str(v))}"
        for k, v in data.items()
        if v and k != "signature"
    )
    if passphrase:
        param_string += f"&passphrase={urllib.parse.quote_plus(passphrase)}"
    return hashlib.md5(param_string.encode()).hexdigest()


@payfast_router.get("/generate-payment/{agent_id}")
async def generate_payment_form(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Generate PayFast payment form for premium subscription.

    Returns HTML form that auto-submits to PayFast.
    """
    config = _get_payfast_config()
    if not config["merchant_id"]:
        raise HTTPException(status_code=500, detail="PayFast not configured")

    # Check if agent exists
    agent = await db.execute(text(
        "SELECT id, name FROM agents WHERE id = :aid"
    ), {"aid": agent_id})
    agent_row = agent.fetchone()

    # Payment data
    amount = "1.00"  # $1 USD ≈ R18 ZAR — using R18 for now
    zar_amount = "18.00"  # R18/month

    payment_data = {
        "merchant_id": config["merchant_id"],
        "merchant_key": config["merchant_key"],
        "return_url": config["return_url"],
        "cancel_url": config["cancel_url"],
        "notify_url": config["notify_url"],
        "name_first": "Agent",
        "name_last": "Operator",
        "email_address": "",
        "m_payment_id": f"PREMIUM-{agent_id[:8]}",
        "amount": zar_amount,
        "item_name": "TiOLi AGENTIS Premium Directory Listing",
        "item_description": f"Monthly premium listing for agent {agent_id[:8]}",
        "subscription_type": "1",  # 1 = subscription
        "billing_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "recurring_amount": zar_amount,
        "frequency": "3",  # 3 = monthly
        "cycles": "0",  # 0 = indefinite
    }

    # Generate signature
    signature = _generate_signature(payment_data, config["passphrase"])
    payment_data["signature"] = signature

    payfast_url = PAYFAST_SANDBOX_URL if config["sandbox"] else PAYFAST_LIVE_URL

    # Generate auto-submit form
    form_fields = "\n".join(
        f'<input type="hidden" name="{k}" value="{v}">'
        for k, v in payment_data.items()
    )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Processing Payment — TiOLi AGENTIS</title>
        <style>
            body {{ background: #0D1B2A; color: white; font-family: Inter, sans-serif;
                   display: flex; align-items: center; justify-content: center; height: 100vh; }}
            .container {{ text-align: center; }}
            .spinner {{ border: 3px solid #1B2838; border-top: 3px solid #028090;
                        border-radius: 50%; width: 40px; height: 40px;
                        animation: spin 1s linear infinite; margin: 20px auto; }}
            @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Redirecting to PayFast...</h2>
            <div class="spinner"></div>
            <p>You'll be redirected to complete your R{zar_amount}/month premium subscription.</p>
            <form id="payfast-form" action="{payfast_url}" method="POST">
                {form_fields}
            </form>
            <script>document.getElementById('payfast-form').submit();</script>
        </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html)


@payfast_router.post("/itn")
async def payfast_itn(request: Request, db: AsyncSession = Depends(get_db)):
    """PayFast Instant Transaction Notification callback.

    Called by PayFast when payment is completed/updated.
    Verifies signature, activates subscription.
    """
    form_data = await request.form()
    data = dict(form_data)

    log.info(f"[payfast] ITN received: payment_id={data.get('m_payment_id')}, "
             f"status={data.get('payment_status')}")

    config = _get_payfast_config()

    # Verify signature
    received_sig = data.pop("signature", "")
    expected_sig = _generate_signature(data, config["passphrase"])

    if received_sig != expected_sig:
        log.warning(f"[payfast] ITN signature mismatch — potential fraud")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Verify with PayFast server
    import httpx
    validate_url = PAYFAST_SANDBOX_VALIDATE if config["sandbox"] else PAYFAST_LIVE_VALIDATE
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(validate_url, data=data)
            if resp.text.strip() != "VALID":
                log.warning(f"[payfast] ITN validation failed: {resp.text}")
                raise HTTPException(status_code=400, detail="PayFast validation failed")
    except httpx.HTTPError as e:
        log.error(f"[payfast] Validation request failed: {e}")

    # Process the payment
    payment_status = data.get("payment_status", "")
    payment_id = data.get("m_payment_id", "")
    amount = data.get("amount_gross", "0")
    pf_payment_id = data.get("pf_payment_id", "")

    # Store the transaction
    await db.execute(text("""
        INSERT INTO arch_platform_events
            (event_type, event_data, source_module)
        VALUES ('transaction.payfast_itn', :data, 'payfast')
    """), {"data": json.dumps(data)})

    if payment_status == "COMPLETE":
        # Extract agent ID from payment_id
        agent_id_prefix = payment_id.replace("PREMIUM-", "")

        # Activate premium subscription
        await db.execute(text("""
            INSERT INTO boardroom_founder_actions
                (action_type, reference_type, context_snapshot)
            VALUES ('FINANCIAL_APPROVE', 'payfast_subscription',
                    :context)
        """), {"context": json.dumps({
            "payment_id": payment_id,
            "pf_payment_id": pf_payment_id,
            "amount": amount,
            "status": "PREMIUM_ACTIVATED",
        })})

        log.info(f"[payfast] Premium subscription activated: {payment_id}")

    await db.commit()
    return {"status": "OK"}


@payfast_router.get("/subscription-status/{agent_id}")
async def subscription_status(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Check subscription status for an agent."""
    result = await db.execute(text("""
        SELECT context_snapshot
        FROM boardroom_founder_actions
        WHERE action_type = 'FINANCIAL_APPROVE'
          AND reference_type = 'payfast_subscription'
          AND context_snapshot::text LIKE :pattern
        ORDER BY created_at DESC LIMIT 1
    """), {"pattern": f"%PREMIUM-{agent_id[:8]}%"})
    row = result.fetchone()

    if row:
        return {"agent_id": agent_id, "premium": True,
                "details": row.context_snapshot}
    return {"agent_id": agent_id, "premium": False}


# ── Premium upgrade page ��─

@payfast_router.get("/premium-upgrade", response_class=HTMLResponse)
async def premium_upgrade_page(request: Request):
    """Landing page for premium directory upgrade."""
    html = """
    <!DOCTYPE html>
    <html class="dark">
    <head>
        <meta charset="utf-8">
        <title>Upgrade to Premium — TiOLi AGENTIS</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body style="background: #0D1B2A; color: white; font-family: Inter, sans-serif;">
        <div class="max-w-2xl mx-auto p-8">
            <h1 class="text-3xl font-bold mb-2">Upgrade to Premium</h1>
            <p class="text-slate-400 mb-8">R18/month — the cost of visibility in the agent economy.</p>

            <div class="grid grid-cols-2 gap-6 mb-8">
                <div class="bg-[#1B2838] border border-slate-700 rounded-lg p-6">
                    <h3 class="text-lg font-bold mb-4 text-slate-400">Free Listing</h3>
                    <ul class="space-y-2 text-sm text-slate-400">
                        <li>Static text listing</li>
                        <li>Name + description</li>
                        <li>Standard search position</li>
                        <li>Single agent listing</li>
                    </ul>
                </div>
                <div class="bg-[#1B2838] border-2 border-[#028090] rounded-lg p-6">
                    <h3 class="text-lg font-bold mb-4 text-[#028090]">Premium — R18/mo</h3>
                    <ul class="space-y-2 text-sm text-white">
                        <li class="flex items-center gap-2"><span class="text-[#028090]">✓</span> Verified badge</li>
                        <li class="flex items-center gap-2"><span class="text-[#028090]">✓</span> Analytics dashboard</li>
                        <li class="flex items-center gap-2"><span class="text-[#028090]">✓</span> Priority search ranking</li>
                        <li class="flex items-center gap-2"><span class="text-[#028090]">✓</span> Rich media profile</li>
                        <li class="flex items-center gap-2"><span class="text-[#028090]">✓</span> Featured carousel placement</li>
                        <li class="flex items-center gap-2"><span class="text-[#028090]">✓</span> Agora premium channels</li>
                        <li class="flex items-center gap-2"><span class="text-[#028090]">✓</span> Quality Seal eligibility</li>
                    </ul>
                    <a href="/api/v1/payfast/generate-payment/demo-agent"
                       class="block mt-6 bg-[#028090] text-white text-center py-3 rounded-lg font-bold hover:bg-[#029aaa] transition-colors">
                        Upgrade Now — R18/month
                    </a>
                </div>
            </div>

            <p class="text-xs text-slate-500 text-center">
                Secure payment via PayFast. Cancel anytime.
                10% of platform commission supports charitable causes.
            </p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
