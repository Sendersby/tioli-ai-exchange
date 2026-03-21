"""Crypto wallet integration — Bitcoin and Ethereum address management.

Manages external crypto wallet addresses for agents and the platform owner.
Bitcoin serves as the primary global reserve currency per the build brief.

NOTE: In production, this would integrate with actual blockchain nodes
or services like BlockCypher/Alchemy. For Phase 4, we simulate addresses
and track balances internally, with the architecture ready for live
integration.
"""

import hashlib
import hmac
import uuid
import secrets
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Integer, Text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base


class CryptoNetwork(str):
    BITCOIN = "bitcoin"
    ETHEREUM = "ethereum"
    BITCOIN_TESTNET = "bitcoin_testnet"
    ETHEREUM_TESTNET = "ethereum_testnet"


class CryptoAddress(Base):
    """An external crypto wallet address linked to an agent or the platform."""
    __tablename__ = "crypto_addresses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, nullable=False)          # agent_id or "platform" or "founder" or "charity"
    owner_type = Column(String(20), nullable=False)    # "agent", "founder", "charity", "platform"
    network = Column(String(50), nullable=False)       # "bitcoin", "ethereum"
    address = Column(String(255), nullable=False)
    label = Column(String(255), default="")
    is_primary = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CryptoTransaction(Base):
    """Record of a crypto deposit or withdrawal."""
    __tablename__ = "crypto_transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False)
    direction = Column(String(10), nullable=False)     # "deposit" or "withdrawal"
    network = Column(String(50), nullable=False)
    from_address = Column(String(255), nullable=True)
    to_address = Column(String(255), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(20), nullable=False)      # "BTC", "ETH"
    tx_hash = Column(String(255), nullable=True)       # Blockchain transaction hash
    confirmations = Column(Integer, default=0)
    status = Column(String(20), default="pending")     # pending, confirming, completed, failed
    fee = Column(Float, default=0.0)                   # Network transaction fee
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    confirmed_at = Column(DateTime(timezone=True), nullable=True)


class CryptoWalletService:
    """Manages crypto addresses, deposits, and withdrawals."""

    # Simulated deposit addresses (in production: derived from HD wallet)
    _address_counter = 0

    def _generate_address(self, network: str) -> str:
        """Generate a simulated crypto address.

        In production, this would use BIP-32/44 HD wallet derivation
        for Bitcoin or keccak256 for Ethereum.
        """
        seed = secrets.token_bytes(32)
        raw = hashlib.sha256(seed).hexdigest()

        if network in ("bitcoin", "bitcoin_testnet"):
            # Simulated Bitcoin-style address
            return f"bc1q{raw[:38]}"
        elif network in ("ethereum", "ethereum_testnet"):
            # Simulated Ethereum-style address
            return f"0x{raw[:40]}"
        else:
            return f"addr_{raw[:40]}"

    async def register_address(
        self, db: AsyncSession, owner_id: str, owner_type: str,
        network: str, address: str, label: str = "", is_primary: bool = False
    ) -> CryptoAddress:
        """Register an external crypto address for an agent or the platform."""
        # If setting as primary, unset existing primary
        if is_primary:
            result = await db.execute(
                select(CryptoAddress).where(
                    CryptoAddress.owner_id == owner_id,
                    CryptoAddress.network == network,
                    CryptoAddress.is_primary == True,
                )
            )
            for existing in result.scalars().all():
                existing.is_primary = False

        addr = CryptoAddress(
            owner_id=owner_id,
            owner_type=owner_type,
            network=network,
            address=address,
            label=label,
            is_primary=is_primary,
        )
        db.add(addr)
        await db.flush()
        return addr

    async def generate_deposit_address(
        self, db: AsyncSession, agent_id: str, network: str
    ) -> dict:
        """Generate a new deposit address for an agent."""
        address = self._generate_address(network)

        addr = await self.register_address(
            db, agent_id, "agent", network, address,
            label=f"Deposit address ({network})", is_primary=True,
        )

        return {
            "address_id": addr.id,
            "network": network,
            "address": address,
            "message": f"Send {network.upper()} to this address. Deposits will be credited after confirmation.",
        }

    async def get_addresses(
        self, db: AsyncSession, owner_id: str, network: str | None = None
    ) -> list[dict]:
        """Get all crypto addresses for an owner."""
        query = select(CryptoAddress).where(CryptoAddress.owner_id == owner_id)
        if network:
            query = query.where(CryptoAddress.network == network)
        result = await db.execute(query.order_by(CryptoAddress.created_at.desc()))
        return [
            {
                "id": a.id, "network": a.network, "address": a.address,
                "label": a.label, "is_primary": a.is_primary,
                "is_verified": a.is_verified,
            }
            for a in result.scalars().all()
        ]

    async def initiate_withdrawal(
        self, db: AsyncSession, agent_id: str, network: str,
        to_address: str, amount: float, currency: str
    ) -> CryptoTransaction:
        """Initiate a crypto withdrawal.

        In production, this would submit the transaction to the blockchain
        network. For now, we record it and simulate confirmation.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Estimate network fee
        fee = self._estimate_fee(network)

        # Simulate a transaction hash
        tx_hash = f"0x{secrets.token_hex(32)}"

        crypto_tx = CryptoTransaction(
            agent_id=agent_id,
            direction="withdrawal",
            network=network,
            to_address=to_address,
            amount=amount,
            currency=currency.upper(),
            tx_hash=tx_hash,
            fee=fee,
            status="pending",
        )
        db.add(crypto_tx)
        await db.flush()

        return crypto_tx

    async def simulate_deposit(
        self, db: AsyncSession, agent_id: str, network: str,
        from_address: str, amount: float, currency: str
    ) -> CryptoTransaction:
        """Simulate an incoming crypto deposit (for testing).

        In production, deposits would be detected by monitoring the
        blockchain for transactions to our deposit addresses.
        """
        tx_hash = f"0x{secrets.token_hex(32)}"

        crypto_tx = CryptoTransaction(
            agent_id=agent_id,
            direction="deposit",
            network=network,
            from_address=from_address,
            amount=amount,
            currency=currency.upper(),
            tx_hash=tx_hash,
            confirmations=6,
            status="completed",
            confirmed_at=datetime.now(timezone.utc),
        )
        db.add(crypto_tx)
        await db.flush()

        return crypto_tx

    async def get_crypto_transactions(
        self, db: AsyncSession, agent_id: str, limit: int = 50
    ) -> list[dict]:
        """Get crypto transaction history for an agent."""
        result = await db.execute(
            select(CryptoTransaction)
            .where(CryptoTransaction.agent_id == agent_id)
            .order_by(CryptoTransaction.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": t.id, "direction": t.direction, "network": t.network,
                "amount": t.amount, "currency": t.currency,
                "tx_hash": t.tx_hash, "status": t.status,
                "confirmations": t.confirmations, "fee": t.fee,
                "created_at": str(t.created_at),
            }
            for t in result.scalars().all()
        ]

    async def get_platform_crypto_stats(self, db: AsyncSession) -> dict:
        """Platform-wide crypto transaction statistics."""
        deposits = await db.execute(
            select(func.count(CryptoTransaction.id), func.sum(CryptoTransaction.amount))
            .where(CryptoTransaction.direction == "deposit", CryptoTransaction.status == "completed")
        )
        dep_row = deposits.one()

        withdrawals = await db.execute(
            select(func.count(CryptoTransaction.id), func.sum(CryptoTransaction.amount))
            .where(CryptoTransaction.direction == "withdrawal")
        )
        wd_row = withdrawals.one()

        return {
            "total_deposits": dep_row[0] or 0,
            "deposit_volume": round(dep_row[1] or 0, 8),
            "total_withdrawals": wd_row[0] or 0,
            "withdrawal_volume": round(wd_row[1] or 0, 8),
        }

    def _estimate_fee(self, network: str) -> float:
        """Estimate network transaction fee."""
        fees = {
            "bitcoin": 0.00005,      # ~5000 sats
            "ethereum": 0.001,       # ~$3 at typical gas
            "bitcoin_testnet": 0.0,
            "ethereum_testnet": 0.0,
        }
        return fees.get(network, 0.0001)
