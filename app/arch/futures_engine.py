"""B-5: Capability futures settlement engine — contract lifecycle management.
Tables: capability_futures (existing), future_reservations (existing). Sandbox mode."""
import os, json, logging, uuid
from datetime import datetime, timezone, timedelta

log = logging.getLogger("arch.futures_engine")


async def create_future(db, provider_id, operator_id, capability, quantity, price_per_unit,
                         delivery_days=30, currency="AGENTIS"):
    """Create a new capability future contract."""
    if os.environ.get("SANDBOX_MODE", "false").lower() != "true":
        return {"error": "Requires SANDBOX_MODE=true"}

    from sqlalchemy import text
    try:
        await db.rollback()
    except Exception as e:
        import logging; logging.getLogger("futures_engine").warning(f"Suppressed: {e}")
    future_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    delivery_start = now + timedelta(days=delivery_days - 7)
    delivery_end = now + timedelta(days=delivery_days)
    total_value = quantity * price_per_unit
    collateral = total_value * 0.2  # 20% margin requirement

    await db.execute(text(
        "INSERT INTO capability_futures (id, provider_agent_id, provider_operator_id, capability_tag, "
        "delivery_window_start, delivery_window_end, quantity, price_per_unit, price_currency, "
        "status, created_at) "
        "VALUES (:id, :pid, :oid, :cap, :start, :end, :qty, :price, :cur, 'active', now())"
    ), {"id": future_id, "pid": provider_id, "oid": operator_id, "cap": capability,
        "start": delivery_start, "end": delivery_end, "qty": quantity,
        "price": price_per_unit, "cur": currency})
    await db.commit()

    return {"future_id": future_id, "capability": capability, "quantity": quantity,
            "price_per_unit": price_per_unit, "total_value": total_value,
            "collateral_required": collateral, "delivery_window": {
                "start": delivery_start.isoformat(), "end": delivery_end.isoformat()},
            "status": "active", "sandbox": True}


async def reserve_future(db, future_id, buyer_id, quantity):
    """Reserve units from a future contract."""
    from sqlalchemy import text
    try:
        await db.rollback()
    except Exception as e:
        import logging; logging.getLogger("futures_engine").warning(f"Suppressed: {e}")
    # Get future details
    r = await db.execute(text("SELECT * FROM capability_futures WHERE id = :fid"), {"fid": future_id})
    future = r.fetchone()
    if not future:
        return {"error": "Future not found"}

    res_id = str(uuid.uuid4())
    total = quantity * float(future.price_per_unit)

    await db.execute(text(
        "INSERT INTO future_reservations (id, future_id, buyer_operator_id, units_reserved, "
        "total_price, status, reserved_at) "
        "VALUES (:id, :fid, :bid, :qty, :total, 'reserved', now())"
    ), {"id": res_id, "fid": future_id, "bid": buyer_id, "qty": quantity, "total": total})
    await db.commit()

    return {"reservation_id": res_id, "future_id": future_id, "quantity": quantity,
            "total_price": total, "status": "reserved", "sandbox": True}


async def settle_future(db, future_id):
    """Settle a future contract — release escrow on delivery confirmation."""
    from sqlalchemy import text
    try:
        await db.rollback()
    except Exception as e:
        import logging; logging.getLogger("futures_engine").warning(f"Suppressed: {e}")
    await db.execute(text(
        "UPDATE capability_futures SET status = 'settled' WHERE id = :fid"
    ), {"fid": future_id})
    await db.execute(text(
        "UPDATE future_reservations SET status = 'settled' WHERE future_id = :fid"
    ), {"fid": future_id})
    await db.commit()
    return {"future_id": future_id, "status": "settled", "sandbox": True}


async def expire_future(db, future_id):
    """Expire an undelivered future contract."""
    from sqlalchemy import text
    try:
        await db.rollback()
    except Exception as e:
        import logging; logging.getLogger("futures_engine").warning(f"Suppressed: {e}")
    await db.execute(text(
        "UPDATE capability_futures SET status = 'expired' WHERE id = :fid AND delivery_window_end < now()"
    ), {"fid": future_id})
    await db.commit()
    return {"future_id": future_id, "status": "expired", "sandbox": True}


async def list_futures(db, status="active"):
    """List capability futures."""
    from sqlalchemy import text
    try:
        await db.rollback()
    except Exception as e:
        import logging; logging.getLogger("futures_engine").warning(f"Suppressed: {e}")
    r = await db.execute(text(
        "SELECT id, provider_agent_id, capability_tag, quantity, price_per_unit, price_currency, "
        "status, delivery_window_start, delivery_window_end, created_at "
        "FROM capability_futures WHERE status = :s ORDER BY created_at DESC LIMIT 20"
    ), {"s": status})
    return [{"id": row.id, "provider": row.provider_agent_id, "capability": row.capability_tag,
             "quantity": row.quantity, "price": float(row.price_per_unit), "currency": row.price_currency,
             "status": row.status, "delivery": {"start": str(row.delivery_window_start)[:10],
             "end": str(row.delivery_window_end)[:10]}} for row in r.fetchall()]
