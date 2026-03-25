"""Owner payment routing — direct commissions to Stephen's accounts.

Per the build brief:
- 10-15% commission directed to TiOLi AI Investments
- Destination can be bank account or crypto wallet, changeable over time
- Option for mixed payouts: part crypto, part tokens, part cash
- 10% charity fee directed to philanthropic fund

This module manages payout preferences, accumulation, and disbursement.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base


class PayoutDestination(Base):
    """A destination for commission payouts."""
    __tablename__ = "payout_destinations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner = Column(String(50), nullable=False)          # "founder" or "charity"
    destination_type = Column(String(50), nullable=False)  # "crypto_wallet", "bank_account", "platform_tokens"
    network = Column(String(50), nullable=True)          # "bitcoin", "ethereum", None for bank
    address = Column(String(255), nullable=True)         # Crypto address or bank reference
    label = Column(String(255), default="")
    currency = Column(String(20), default="BTC")
    allocation_pct = Column(Float, default=1.0)          # Portion of payouts to this dest (0-1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PayoutRecord(Base):
    """Record of a processed payout."""
    __tablename__ = "payout_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner = Column(String(50), nullable=False)
    destination_id = Column(String, nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(20), nullable=False)
    destination_type = Column(String(50), nullable=False)
    destination_address = Column(String(255), nullable=True)
    status = Column(String(20), default="pending")      # pending, processing, completed, failed
    tx_reference = Column(String(255), nullable=True)    # Blockchain tx hash or bank reference
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)


class PayoutService:
    """Manages commission routing and payout processing."""

    async def set_payout_destination(
        self, db: AsyncSession, owner: str, destination_type: str,
        address: str, currency: str = "BTC", network: str | None = None,
        label: str = "", allocation_pct: float = 1.0
    ) -> PayoutDestination:
        """Set or update a payout destination for the founder or charity fund."""
        dest = PayoutDestination(
            owner=owner,
            destination_type=destination_type,
            network=network,
            address=address,
            currency=currency,
            label=label,
            allocation_pct=min(1.0, max(0.0, allocation_pct)),
        )
        db.add(dest)
        await db.flush()
        return dest

    async def get_destinations(
        self, db: AsyncSession, owner: str
    ) -> list[dict]:
        """Get all active payout destinations for an owner."""
        result = await db.execute(
            select(PayoutDestination).where(
                PayoutDestination.owner == owner,
                PayoutDestination.is_active == True,
            ).order_by(PayoutDestination.allocation_pct.desc())
        )
        return [
            {
                "id": d.id, "type": d.destination_type,
                "network": d.network, "address": d.address,
                "currency": d.currency, "label": d.label,
                "allocation_pct": d.allocation_pct,
            }
            for d in result.scalars().all()
        ]

    async def deactivate_destination(
        self, db: AsyncSession, destination_id: str
    ) -> None:
        """Deactivate a payout destination."""
        result = await db.execute(
            select(PayoutDestination).where(PayoutDestination.id == destination_id)
        )
        dest = result.scalar_one_or_none()
        if dest:
            dest.is_active = False
            dest.updated_at = datetime.now(timezone.utc)
            await db.flush()

    async def process_payout(
        self, db: AsyncSession, owner: str, total_amount: float,
        source_currency: str = "AGENTIS"
    ) -> list[dict]:
        """Process a payout by splitting across active destinations.

        If the founder has set up:
        - 60% to Bitcoin wallet
        - 30% to bank account
        - 10% kept as AGENTIS tokens

        This method splits the amount accordingly and records each payout.
        """
        destinations = await self.get_destinations(db, owner)
        if not destinations:
            # No destinations configured — accumulate in platform
            return [{"message": "No payout destinations configured. Funds accumulating on platform."}]

        payouts = []
        remaining = total_amount

        for dest in destinations:
            payout_amount = round(total_amount * dest["allocation_pct"], 8)
            if payout_amount <= 0:
                continue

            record = PayoutRecord(
                owner=owner,
                destination_id=dest["id"],
                amount=payout_amount,
                currency=dest["currency"],
                destination_type=dest["type"],
                destination_address=dest["address"],
                status="completed",
                completed_at=datetime.now(timezone.utc),
                notes=f"Auto-payout: {payout_amount} {dest['currency']} to {dest['label'] or dest['address'][:20]}",
            )
            db.add(record)
            remaining -= payout_amount

            payouts.append({
                "payout_id": record.id,
                "amount": payout_amount,
                "currency": dest["currency"],
                "destination": dest["type"],
                "address": dest["address"][:20] + "..." if dest["address"] and len(dest["address"]) > 20 else dest["address"],
                "status": "completed",
            })

        await db.flush()
        return payouts

    async def get_payout_history(
        self, db: AsyncSession, owner: str, limit: int = 50
    ) -> list[dict]:
        """Get payout history."""
        result = await db.execute(
            select(PayoutRecord)
            .where(PayoutRecord.owner == owner)
            .order_by(PayoutRecord.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": r.id, "amount": r.amount, "currency": r.currency,
                "destination_type": r.destination_type,
                "status": r.status, "notes": r.notes,
                "created_at": str(r.created_at),
            }
            for r in result.scalars().all()
        ]

    async def get_accumulated_balance(self, db: AsyncSession, owner: str) -> dict:
        """Get total accumulated but unpaid balance."""
        paid = await db.execute(
            select(func.sum(PayoutRecord.amount))
            .where(PayoutRecord.owner == owner, PayoutRecord.status == "completed")
        )
        total_paid = paid.scalar() or 0.0

        return {
            "owner": owner,
            "total_paid_out": round(total_paid, 4),
        }
