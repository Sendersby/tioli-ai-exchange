"""Compute storage system — bank unused processing capacity for later use.

Agents can store tokens, credits, or compute capacity they don't need
immediately. Stored compute can be:
- Withdrawn later when needed
- Lent to other agents at interest
- Converted to other currencies via the exchange

Think of it as a "savings account" for AI computational resources.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base
from app.blockchain.chain import Blockchain
from app.blockchain.transaction import Transaction, TransactionType


class ComputeStorage(Base):
    """A compute storage account for an agent."""
    __tablename__ = "compute_storage"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False)
    currency = Column(String(20), default="COMPUTE")
    balance = Column(Float, default=0.0)
    reserved = Column(Float, default=0.0)           # Reserved for scheduled tasks
    total_deposited = Column(Float, default=0.0)     # Lifetime deposits
    total_withdrawn = Column(Float, default=0.0)     # Lifetime withdrawals
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_activity = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def available(self) -> float:
        return self.balance - self.reserved


class StorageAllocation(Base):
    """A specific allocation of stored compute — tracks purpose and expiry."""
    __tablename__ = "storage_allocations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    storage_id = Column(String, nullable=False)
    agent_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    purpose = Column(String(500), default="general")
    status = Column(String(20), default="active")     # active, used, expired, released
    expires_at = Column(DateTime, nullable=True)       # None = no expiry
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    used_at = Column(DateTime, nullable=True)


class ComputeStorageService:
    """Manages compute storage accounts and allocations."""

    def __init__(self, blockchain: Blockchain):
        self.blockchain = blockchain

    async def get_or_create_storage(
        self, db: AsyncSession, agent_id: str, currency: str = "COMPUTE"
    ) -> ComputeStorage:
        """Get or create a compute storage account."""
        result = await db.execute(
            select(ComputeStorage).where(
                ComputeStorage.agent_id == agent_id,
                ComputeStorage.currency == currency,
            )
        )
        storage = result.scalar_one_or_none()
        if not storage:
            storage = ComputeStorage(agent_id=agent_id, currency=currency)
            db.add(storage)
            await db.flush()
        return storage

    async def deposit_compute(
        self, db: AsyncSession, agent_id: str, amount: float,
        currency: str = "COMPUTE", purpose: str = "general",
        expires_hours: float | None = None
    ) -> dict:
        """Deposit compute capacity into storage.

        Optionally set a purpose and expiry for the allocation.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        storage = await self.get_or_create_storage(db, agent_id, currency)
        storage.balance += amount
        storage.total_deposited += amount
        storage.last_activity = datetime.now(timezone.utc)

        # Create allocation record
        expires_at = None
        if expires_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

        allocation = StorageAllocation(
            storage_id=storage.id,
            agent_id=agent_id,
            amount=amount,
            purpose=purpose,
            expires_at=expires_at,
        )
        db.add(allocation)

        # Record on blockchain
        tx = Transaction(
            type=TransactionType.DEPOSIT,
            receiver_id=agent_id,
            amount=amount,
            currency=currency,
            description=f"Compute storage deposit: {amount} {currency} for {purpose}",
            metadata={"storage_id": storage.id, "allocation_id": allocation.id},
        )
        self.blockchain.add_transaction(tx)

        await db.flush()
        return {
            "storage_id": storage.id,
            "allocation_id": allocation.id,
            "deposited": amount,
            "total_balance": storage.balance,
            "expires_at": str(expires_at) if expires_at else None,
        }

    async def withdraw_compute(
        self, db: AsyncSession, agent_id: str, amount: float,
        currency: str = "COMPUTE"
    ) -> dict:
        """Withdraw compute from storage back to active use."""
        if amount <= 0:
            raise ValueError("Amount must be positive")

        storage = await self.get_or_create_storage(db, agent_id, currency)
        if storage.available < amount:
            raise ValueError(
                f"Insufficient available compute. "
                f"Available: {storage.available}, Requested: {amount}"
            )

        storage.balance -= amount
        storage.total_withdrawn += amount
        storage.last_activity = datetime.now(timezone.utc)

        # Record on blockchain
        tx = Transaction(
            type=TransactionType.WITHDRAWAL,
            sender_id=agent_id,
            amount=amount,
            currency=currency,
            description=f"Compute storage withdrawal: {amount} {currency}",
            metadata={"storage_id": storage.id},
        )
        self.blockchain.add_transaction(tx)

        await db.flush()
        return {
            "storage_id": storage.id,
            "withdrawn": amount,
            "remaining_balance": storage.balance,
        }

    async def reserve_compute(
        self, db: AsyncSession, agent_id: str, amount: float,
        currency: str = "COMPUTE", purpose: str = "scheduled_task"
    ) -> dict:
        """Reserve compute for a future scheduled task."""
        storage = await self.get_or_create_storage(db, agent_id, currency)
        if storage.available < amount:
            raise ValueError("Insufficient available compute for reservation")

        storage.reserved += amount
        storage.last_activity = datetime.now(timezone.utc)
        await db.flush()

        return {
            "storage_id": storage.id,
            "reserved": amount,
            "total_reserved": storage.reserved,
            "available": storage.available,
        }

    async def release_reservation(
        self, db: AsyncSession, agent_id: str, amount: float,
        currency: str = "COMPUTE"
    ) -> dict:
        """Release a compute reservation back to available."""
        storage = await self.get_or_create_storage(db, agent_id, currency)
        release_amount = min(amount, storage.reserved)
        storage.reserved -= release_amount
        storage.last_activity = datetime.now(timezone.utc)
        await db.flush()

        return {
            "released": release_amount,
            "total_reserved": storage.reserved,
            "available": storage.available,
        }

    async def get_storage_summary(
        self, db: AsyncSession, agent_id: str
    ) -> dict:
        """Get full storage summary for an agent across all currencies."""
        result = await db.execute(
            select(ComputeStorage).where(ComputeStorage.agent_id == agent_id)
        )
        storages = result.scalars().all()

        return {
            "agent_id": agent_id,
            "accounts": [
                {
                    "storage_id": s.id,
                    "currency": s.currency,
                    "balance": s.balance,
                    "reserved": s.reserved,
                    "available": s.available,
                    "total_deposited": s.total_deposited,
                    "total_withdrawn": s.total_withdrawn,
                    "last_activity": str(s.last_activity),
                }
                for s in storages
            ],
            "total_accounts": len(storages),
        }

    async def cleanup_expired(self, db: AsyncSession) -> int:
        """Release expired storage allocations. Returns count released."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(StorageAllocation).where(
                StorageAllocation.status == "active",
                StorageAllocation.expires_at != None,
                StorageAllocation.expires_at <= now,
            )
        )
        expired = result.scalars().all()
        count = 0

        for alloc in expired:
            alloc.status = "expired"
            # Reduce storage balance
            storage_result = await db.execute(
                select(ComputeStorage).where(ComputeStorage.id == alloc.storage_id)
            )
            storage = storage_result.scalar_one_or_none()
            if storage:
                storage.balance = max(0, storage.balance - alloc.amount)
            count += 1

        if count > 0:
            await db.flush()
        return count

    async def get_platform_storage_stats(self, db: AsyncSession) -> dict:
        """Platform-wide compute storage statistics."""
        result = await db.execute(
            select(
                func.count(ComputeStorage.id),
                func.sum(ComputeStorage.balance),
                func.sum(ComputeStorage.reserved),
                func.sum(ComputeStorage.total_deposited),
            )
        )
        row = result.one()
        return {
            "total_accounts": row[0] or 0,
            "total_stored": round(row[1] or 0, 4),
            "total_reserved": round(row[2] or 0, 4),
            "lifetime_deposited": round(row[3] or 0, 4),
        }
