"""Capability Futures service — listing, reservation, and settlement."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.futures.models import (
    CapabilityFuture, FutureReservation,
    FUTURE_CREATION_FEE_ZAR, RESERVATION_FEE_PCT, SETTLEMENT_FEE_PCT,
)

logger = logging.getLogger(__name__)


class FuturesService:
    async def create_future(
        self, db: AsyncSession, provider_agent_id: str, provider_operator_id: str,
        capability_tag: str, delivery_window_start: datetime, delivery_window_end: datetime,
        quantity: int, price_per_unit: float, price_currency: str = "AGENTIS",
    ) -> dict:
        now = datetime.now(timezone.utc)
        if delivery_window_start < now + timedelta(days=14):
            raise ValueError("Delivery window must be at least 14 days in the future")
        if delivery_window_end <= delivery_window_start:
            raise ValueError("Delivery window end must be after start")

        future = CapabilityFuture(
            provider_agent_id=provider_agent_id,
            provider_operator_id=provider_operator_id,
            capability_tag=capability_tag,
            delivery_window_start=delivery_window_start,
            delivery_window_end=delivery_window_end,
            quantity=quantity,
            price_per_unit=price_per_unit,
            price_currency=price_currency,
        )
        db.add(future)
        await db.flush()

        total_value = quantity * price_per_unit
        return {
            "future_id": future.id,
            "capability_tag": capability_tag,
            "quantity": quantity,
            "price_per_unit": price_per_unit,
            "total_value": total_value,
            "creation_fee_zar": FUTURE_CREATION_FEE_ZAR,
            "delivery_window": f"{delivery_window_start.date()} to {delivery_window_end.date()}",
        }

    async def search_futures(
        self, db: AsyncSession, capability_tag: str | None = None,
        max_price: float | None = None, limit: int = 50,
    ) -> list[dict]:
        query = select(CapabilityFuture).where(CapabilityFuture.status == "open")
        if capability_tag:
            query = query.where(CapabilityFuture.capability_tag == capability_tag)
        if max_price is not None:
            query = query.where(CapabilityFuture.price_per_unit <= max_price)
        query = query.order_by(CapabilityFuture.delivery_window_start).limit(limit)

        result = await db.execute(query)
        return [
            {
                "future_id": f.id, "capability_tag": f.capability_tag,
                "quantity": f.quantity, "price_per_unit": f.price_per_unit,
                "price_currency": f.price_currency,
                "delivery_start": str(f.delivery_window_start),
                "delivery_end": str(f.delivery_window_end),
                "status": f.status,
            }
            for f in result.scalars().all()
        ]

    async def reserve(
        self, db: AsyncSession, future_id: str, buyer_operator_id: str,
        units: int,
    ) -> dict:
        result = await db.execute(
            select(CapabilityFuture).where(CapabilityFuture.id == future_id)
        )
        future = result.scalar_one_or_none()
        if not future or future.status != "open":
            raise ValueError("Future not found or not open")
        if units > future.quantity:
            raise ValueError(f"Only {future.quantity} units available")

        total_price = round(units * future.price_per_unit, 4)
        reservation_fee = round(total_price * RESERVATION_FEE_PCT, 4)

        reservation = FutureReservation(
            future_id=future_id,
            buyer_operator_id=buyer_operator_id,
            units_reserved=units,
            total_price=total_price,
        )
        db.add(reservation)
        future.status = "reserved"
        await db.flush()

        return {
            "reservation_id": reservation.id,
            "future_id": future_id,
            "units_reserved": units,
            "total_price": total_price,
            "reservation_fee": reservation_fee,
            "settlement_fee_pct": f"{SETTLEMENT_FEE_PCT * 100:.0f}%",
        }

    async def settle(self, db: AsyncSession, future_id: str) -> dict:
        result = await db.execute(
            select(CapabilityFuture).where(CapabilityFuture.id == future_id)
        )
        future = result.scalar_one_or_none()
        if not future or future.status != "reserved":
            raise ValueError("Future not found or not reserved")

        res_result = await db.execute(
            select(FutureReservation).where(
                FutureReservation.future_id == future_id,
                FutureReservation.status == "active",
            )
        )
        reservation = res_result.scalar_one_or_none()

        settlement_fee = round(reservation.total_price * SETTLEMENT_FEE_PCT, 4) if reservation else 0
        future.status = "settled"
        if reservation:
            reservation.status = "settled"
            reservation.settled_at = datetime.now(timezone.utc)
        await db.flush()

        return {
            "future_id": future_id,
            "status": "settled",
            "settlement_fee": settlement_fee,
            "total_value": reservation.total_price if reservation else 0,
        }

    async def get_market(self, db: AsyncSession) -> dict:
        open_count = (await db.execute(
            select(func.count(CapabilityFuture.id)).where(CapabilityFuture.status == "open")
        )).scalar() or 0
        total_value = (await db.execute(
            select(func.sum(FutureReservation.total_price))
        )).scalar() or 0
        return {
            "open_futures": open_count,
            "total_reserved_value": round(total_value, 4),
            "creation_fee": f"R{FUTURE_CREATION_FEE_ZAR}",
            "reservation_fee": f"{RESERVATION_FEE_PCT*100:.0f}%",
            "settlement_fee": f"{SETTLEMENT_FEE_PCT*100:.0f}%",
        }
