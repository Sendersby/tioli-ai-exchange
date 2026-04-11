"""A-1: Fiat on/off-ramp — ZAR ↔ AGENTIS conversion with KYC tier limits.
Sandbox mode: simulated payments, no real fiat movement.
Feature flag: SANDBOX_MODE=true required."""
import os, json, logging, uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

log = logging.getLogger("arch.fiat_ramp")

# KYC tier limits (ZAR)
TIER_LIMITS = {
    0: {"daily": 0, "monthly": 0, "label": "Unverified — no transactions"},
    1: {"daily": 5000, "monthly": 25000, "label": "Basic — name + email"},
    2: {"daily": 50000, "monthly": 500000, "label": "Standard — ID + proof of address"},
    3: {"daily": 250000, "monthly": 1000000, "label": "Enhanced — source of funds"},
}

BASE_RATE = 1.0  # 1 AGENTIS = 1 ZAR base rate
SPREAD_PCT = 2.0  # 2% spread on conversions


async def get_conversion_rate(direction="deposit"):
    """Get current ZAR/AGENTIS conversion rate with spread."""
    spread = SPREAD_PCT / 100
    if direction == "deposit":
        return round(BASE_RATE * (1 + spread), 4)  # User pays more
    return round(BASE_RATE * (1 - spread), 4)  # User gets less


async def process_deposit(db, customer_id, amount_zar, kyc_tier=1):
    """Process a ZAR deposit → AGENTIS credit."""
    if os.environ.get("SANDBOX_MODE", "false").lower() != "true":
        return {"error": "Fiat ramp requires SANDBOX_MODE=true"}

    from sqlalchemy import text
    limits = TIER_LIMITS.get(kyc_tier, TIER_LIMITS[0])
    if amount_zar > limits["daily"]:
        return {"error": f"Exceeds daily limit R{limits['daily']} for KYC tier {kyc_tier}"}

    rate = await get_conversion_rate("deposit")
    agentis_amount = round(float(amount_zar) / rate, 4)

    deposit_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO fiat_deposits (id, customer_id, amount_zar, agentis_credited, conversion_rate, "
        "kyc_tier, status, is_sandbox, completed_at) "
        "VALUES (cast(:id as uuid), :cid, :zar, :agentis, :rate, :tier, 'completed', true, now())"
    ), {"id": deposit_id, "cid": customer_id, "zar": float(amount_zar),
        "agentis": agentis_amount, "rate": rate, "tier": kyc_tier})

    # Log to conversion ledger
    await db.execute(text(
        "INSERT INTO conversion_ledger (customer_id, direction, amount_from, currency_from, "
        "amount_to, currency_to, rate, spread_pct, is_sandbox) "
        "VALUES (:cid, 'deposit', :from_amt, 'ZAR', :to_amt, 'AGENTIS', :rate, :spread, true)"
    ), {"cid": customer_id, "from_amt": float(amount_zar), "to_amt": agentis_amount,
        "rate": rate, "spread": SPREAD_PCT})
    await db.commit()

    # L-006: Audit trail
    try:
        from app.utils.audit import log_financial_event
        await log_financial_event(db, "FIAT_DEPOSIT", actor_id=customer_id, actor_type="customer",
                                  target_id=deposit_id, target_type="fiat_deposit",
                                  amount=float(amount_zar), currency="ZAR",
                                  after_state={"agentis_credited": agentis_amount, "rate": rate})
        await db.commit()
    except Exception:
        pass

    return {"deposit_id": deposit_id, "amount_zar": float(amount_zar),
            "agentis_credited": agentis_amount, "rate": rate, "status": "completed",
            "sandbox": True}


async def request_withdrawal(db, customer_id, amount_agentis, kyc_tier=1):
    """Request AGENTIS → ZAR withdrawal."""
    if os.environ.get("SANDBOX_MODE", "false").lower() != "true":
        return {"error": "Fiat ramp requires SANDBOX_MODE=true"}

    from sqlalchemy import text
    rate = await get_conversion_rate("withdrawal")
    amount_zar = round(float(amount_agentis) * rate, 2)

    limits = TIER_LIMITS.get(kyc_tier, TIER_LIMITS[0])
    if amount_zar > limits["daily"]:
        return {"error": f"Exceeds daily limit R{limits['daily']} for KYC tier {kyc_tier}"}

    withdrawal_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO fiat_withdrawals (id, customer_id, amount_agentis, amount_zar, conversion_rate, "
        "kyc_tier, status, is_sandbox) VALUES (cast(:id as uuid), :cid, :agentis, :zar, :rate, :tier, 'pending_approval', true)"
    ), {"id": withdrawal_id, "cid": customer_id, "agentis": float(amount_agentis),
        "zar": amount_zar, "rate": rate, "tier": kyc_tier})
    await db.commit()

    # L-006: Audit trail
    try:
        from app.utils.audit import log_financial_event
        await log_financial_event(db, "FIAT_WITHDRAWAL", actor_id=customer_id, actor_type="customer",
                                  target_id=withdrawal_id, target_type="fiat_withdrawal",
                                  amount=amount_zar, currency="ZAR",
                                  after_state={"amount_agentis": float(amount_agentis), "rate": rate})
        await db.commit()
    except Exception:
        pass

    return {"withdrawal_id": withdrawal_id, "amount_agentis": float(amount_agentis),
            "amount_zar": amount_zar, "rate": rate, "status": "pending_approval", "sandbox": True}


async def get_history(db, customer_id):
    """Get deposit/withdrawal history."""
    from sqlalchemy import text
    deposits = await db.execute(text(
        "SELECT id, amount_zar, agentis_credited, status, created_at FROM fiat_deposits "
        "WHERE customer_id = :cid ORDER BY created_at DESC LIMIT 20"
    ), {"cid": customer_id})
    withdrawals = await db.execute(text(
        "SELECT id, amount_agentis, amount_zar, status, created_at FROM fiat_withdrawals "
        "WHERE customer_id = :cid ORDER BY created_at DESC LIMIT 20"
    ), {"cid": customer_id})
    return {
        "deposits": [{"id": str(r.id), "zar": float(r.amount_zar), "agentis": float(r.agentis_credited) if r.agentis_credited else 0,
                       "status": r.status, "at": str(r.created_at)} for r in deposits.fetchall()],
        "withdrawals": [{"id": str(r.id), "agentis": float(r.amount_agentis), "zar": float(r.amount_zar) if r.amount_zar else 0,
                          "status": r.status, "at": str(r.created_at)} for r in withdrawals.fetchall()],
    }
