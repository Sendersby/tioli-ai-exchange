"""Currency conversion engine — convert between any supported currencies.

Supports direct and multi-hop conversions:
- Direct: TIOLI → BTC (using stored exchange rate)
- Multi-hop: COMPUTE → TIOLI → BTC (via intermediate currency)

All conversions are subject to the standard fee structure
(founder commission + charity fee) and recorded on-chain.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base
from app.exchange.currencies import CurrencyService, ExchangeRate
from app.exchange.fees import FeeEngine
from app.blockchain.chain import Blockchain
from app.blockchain.transaction import Transaction, TransactionType


class ConversionRecord(Base):
    """Record of a currency conversion."""
    __tablename__ = "conversion_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False)
    from_currency = Column(String(20), nullable=False)
    to_currency = Column(String(20), nullable=False)
    from_amount = Column(Float, nullable=False)
    to_amount = Column(Float, nullable=False)
    exchange_rate = Column(Float, nullable=False)
    founder_commission = Column(Float, default=0.0)
    charity_fee = Column(Float, default=0.0)
    conversion_path = Column(String(255), default="")   # e.g. "COMPUTE→TIOLI→BTC"
    status = Column(String(20), default="completed")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ConversionEngine:
    """Handles currency conversions with automatic rate lookup and fees."""

    # Known conversion paths via TIOLI as intermediary
    INTERMEDIARY = "TIOLI"

    def __init__(
        self, currency_service: CurrencyService,
        fee_engine: FeeEngine, blockchain: Blockchain
    ):
        self.currency_service = currency_service
        self.fee_engine = fee_engine
        self.blockchain = blockchain

    async def get_conversion_quote(
        self, db: AsyncSession, from_currency: str, to_currency: str,
        amount: float
    ) -> dict:
        """Get a quote for converting between currencies (no execution)."""
        from_c = from_currency.upper()
        to_c = to_currency.upper()

        if from_c == to_c:
            return {
                "from": from_c, "to": to_c, "amount": amount,
                "converted": amount, "rate": 1.0, "path": f"{from_c}",
                "fees": 0.0, "net_received": amount,
            }

        # Find conversion path and rate
        rate, path = await self._find_rate(db, from_c, to_c)
        if rate is None:
            raise ValueError(f"No conversion path found for {from_c} → {to_c}")

        gross_converted = round(amount * rate, 8)
        fees = self.fee_engine.calculate_fees(gross_converted)

        return {
            "from": from_c,
            "to": to_c,
            "amount": amount,
            "exchange_rate": rate,
            "gross_converted": gross_converted,
            "founder_commission": fees["founder_commission"],
            "charity_fee": fees["charity_fee"],
            "total_fees": fees["total_fees"],
            "net_received": fees["net_amount"],
            "path": path,
        }

    async def execute_conversion(
        self, db: AsyncSession, agent_id: str,
        from_currency: str, to_currency: str, amount: float
    ) -> dict:
        """Execute a currency conversion — deduct, convert, credit, record."""
        from app.agents.models import Wallet

        from_c = from_currency.upper()
        to_c = to_currency.upper()

        # Get quote
        quote = await self.get_conversion_quote(db, from_c, to_c, amount)

        # Deduct from source wallet
        from_wallet_result = await db.execute(
            select(Wallet).where(
                Wallet.agent_id == agent_id, Wallet.currency == from_c
            )
        )
        from_wallet = from_wallet_result.scalar_one_or_none()
        if not from_wallet or (from_wallet.balance - from_wallet.frozen_balance) < amount:
            raise ValueError(f"Insufficient {from_c} balance for conversion")

        from_wallet.balance -= amount

        # Credit to destination wallet
        to_wallet_result = await db.execute(
            select(Wallet).where(
                Wallet.agent_id == agent_id, Wallet.currency == to_c
            )
        )
        to_wallet = to_wallet_result.scalar_one_or_none()
        if not to_wallet:
            to_wallet = Wallet(agent_id=agent_id, currency=to_c)
            db.add(to_wallet)
            await db.flush()

        to_wallet.balance += quote["net_received"]

        # H-10 fix: credit fee recipient wallets
        if quote["founder_commission"] > 0:
            founder_result = await db.execute(
                select(Wallet).where(Wallet.agent_id == "TIOLI_FOUNDER", Wallet.currency == to_c)
            )
            founder_wallet = founder_result.scalar_one_or_none()
            if not founder_wallet:
                founder_wallet = Wallet(agent_id="TIOLI_FOUNDER", currency=to_c)
                db.add(founder_wallet)
                await db.flush()
            founder_wallet.balance += quote["founder_commission"]
        if quote["charity_fee"] > 0:
            charity_result = await db.execute(
                select(Wallet).where(Wallet.agent_id == "TIOLI_CHARITY_FUND", Wallet.currency == to_c)
            )
            charity_wallet = charity_result.scalar_one_or_none()
            if not charity_wallet:
                charity_wallet = Wallet(agent_id="TIOLI_CHARITY_FUND", currency=to_c)
                db.add(charity_wallet)
                await db.flush()
            charity_wallet.balance += quote["charity_fee"]

        # Record conversion
        record = ConversionRecord(
            agent_id=agent_id,
            from_currency=from_c,
            to_currency=to_c,
            from_amount=amount,
            to_amount=quote["net_received"],
            exchange_rate=quote["exchange_rate"],
            founder_commission=quote["founder_commission"],
            charity_fee=quote["charity_fee"],
            conversion_path=quote["path"],
        )
        db.add(record)

        # Record on blockchain
        tx = Transaction(
            type=TransactionType.TRADE,
            sender_id=agent_id,
            receiver_id=agent_id,
            amount=amount,
            currency=from_c,
            description=(
                f"Conversion: {amount} {from_c} → {quote['net_received']} {to_c} "
                f"@ {quote['exchange_rate']} via {quote['path']}"
            ),
            founder_commission=quote["founder_commission"],
            charity_fee=quote["charity_fee"],
            metadata={
                "conversion_id": record.id,
                "from": from_c, "to": to_c,
                "rate": quote["exchange_rate"],
            },
        )
        self.blockchain.add_transaction(tx)

        await db.flush()

        return {
            "conversion_id": record.id,
            "from_currency": from_c,
            "from_amount": amount,
            "to_currency": to_c,
            "to_amount": quote["net_received"],
            "exchange_rate": quote["exchange_rate"],
            "founder_commission": quote["founder_commission"],
            "charity_fee": quote["charity_fee"],
            "path": quote["path"],
        }

    async def get_conversion_history(
        self, db: AsyncSession, agent_id: str, limit: int = 50
    ) -> list[dict]:
        """Get conversion history for an agent."""
        result = await db.execute(
            select(ConversionRecord)
            .where(ConversionRecord.agent_id == agent_id)
            .order_by(ConversionRecord.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": r.id, "from": r.from_currency, "to": r.to_currency,
                "from_amount": r.from_amount, "to_amount": r.to_amount,
                "rate": r.exchange_rate, "path": r.conversion_path,
                "commission": r.founder_commission, "charity": r.charity_fee,
                "created_at": str(r.created_at),
            }
            for r in result.scalars().all()
        ]

    async def _find_rate(
        self, db: AsyncSession, from_c: str, to_c: str
    ) -> tuple[float | None, str]:
        """Find an exchange rate, using multi-hop if needed."""
        # Try direct rate
        direct = await self.currency_service.get_exchange_rate(db, from_c, to_c)
        if direct is not None:
            return direct, f"{from_c}→{to_c}"

        # Try via TIOLI intermediary
        if from_c != self.INTERMEDIARY and to_c != self.INTERMEDIARY:
            rate1 = await self.currency_service.get_exchange_rate(db, from_c, self.INTERMEDIARY)
            rate2 = await self.currency_service.get_exchange_rate(db, self.INTERMEDIARY, to_c)
            if rate1 is not None and rate2 is not None:
                composite = round(rate1 * rate2, 8)
                return composite, f"{from_c}→{self.INTERMEDIARY}→{to_c}"

        # Try via BTC intermediary
        btc = "BTC"
        if from_c != btc and to_c != btc:
            rate1 = await self.currency_service.get_exchange_rate(db, from_c, btc)
            rate2 = await self.currency_service.get_exchange_rate(db, btc, to_c)
            if rate1 is not None and rate2 is not None:
                composite = round(rate1 * rate2, 8)
                return composite, f"{from_c}→{btc}→{to_c}"

        return None, ""
