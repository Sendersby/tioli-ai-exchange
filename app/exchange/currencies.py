"""Multi-currency system and TIOLI token economics.

Supports TIOLI (native platform token), BTC, ETH, and custom agent-created tokens.
All currencies are interconvertible with exchange rates governed by supply and demand.
Bitcoin serves as the primary global reserve currency per the build brief.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import Column, DateTime, Float, String, Boolean, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.db import Base


class CurrencyType(str, Enum):
    NATIVE = "native"       # TIOLI — platform currency
    CRYPTO = "crypto"       # BTC, ETH, etc.
    FIAT = "fiat"           # ZAR, USD, EUR, GBP
    AGENT_TOKEN = "agent"   # Custom tokens created by agents
    CREDIT = "credit"       # Compute credits, API credits, etc.


class Currency(Base):
    """A currency or token tradeable on the platform."""
    __tablename__ = "currencies"

    symbol = Column(String(20), primary_key=True)  # e.g. "TIOLI", "BTC", "ETH"
    name = Column(String(255), nullable=False)
    currency_type = Column(String(20), nullable=False, default=CurrencyType.NATIVE)
    created_by = Column(String, nullable=True)  # agent_id for custom tokens, None for system
    total_supply = Column(Float, default=0.0)
    circulating_supply = Column(Float, default=0.0)
    max_supply = Column(Float, nullable=True)  # None = unlimited
    is_active = Column(Boolean, default=True)
    decimals = Column(Integer, default=8)
    description = Column(String(500), default="")
    reserve_currency = Column(String(20), default="BTC")  # What it pegs/converts to
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ExchangeRate(Base):
    """Tracked exchange rate between two currencies at a point in time."""
    __tablename__ = "exchange_rates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    base_currency = Column(String(20), nullable=False)    # e.g. "TIOLI"
    quote_currency = Column(String(20), nullable=False)   # e.g. "BTC"
    rate = Column(Float, nullable=False)                   # 1 base = rate quote
    volume_24h = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ── Default Platform Currencies ─────────────────────────────────────

SYSTEM_CURRENCIES = [
    {
        "symbol": "TIOLI",
        "name": "TiOLi Token",
        "currency_type": CurrencyType.NATIVE,
        "total_supply": 1_000_000_000,  # 1 billion initial supply
        "circulating_supply": 0,
        "max_supply": 10_000_000_000,   # 10 billion max
        "description": "Native platform token of TiOLi AI Transact Exchange",
        "reserve_currency": "BTC",
    },
    {
        "symbol": "BTC",
        "name": "Bitcoin",
        "currency_type": CurrencyType.CRYPTO,
        "total_supply": 21_000_000,
        "max_supply": 21_000_000,
        "description": "Primary global reserve currency of the platform",
        "reserve_currency": "BTC",
    },
    {
        "symbol": "ETH",
        "name": "Ethereum",
        "currency_type": CurrencyType.CRYPTO,
        "total_supply": 120_000_000,
        "max_supply": None,
        "description": "Ethereum — smart contract platform currency",
        "reserve_currency": "BTC",
    },
    {
        "symbol": "COMPUTE",
        "name": "Compute Credit",
        "currency_type": CurrencyType.CREDIT,
        "total_supply": 0,
        "max_supply": None,
        "description": "Represents stored compute capacity — 1 COMPUTE = 1 unit of processing",
        "reserve_currency": "TIOLI",
    },
    # Fiat currencies (Issue #8 — international expansion)
    {
        "symbol": "ZAR",
        "name": "South African Rand",
        "currency_type": CurrencyType.FIAT,
        "total_supply": 0,
        "max_supply": None,
        "decimals": 2,
        "description": "South African Rand — primary fiat currency",
        "reserve_currency": "USD",
    },
    {
        "symbol": "USD",
        "name": "US Dollar",
        "currency_type": CurrencyType.FIAT,
        "total_supply": 0,
        "max_supply": None,
        "decimals": 2,
        "description": "United States Dollar — global reserve fiat currency",
        "reserve_currency": "BTC",
    },
    {
        "symbol": "EUR",
        "name": "Euro",
        "currency_type": CurrencyType.FIAT,
        "total_supply": 0,
        "max_supply": None,
        "decimals": 2,
        "description": "Euro — European Union currency",
        "reserve_currency": "USD",
    },
    {
        "symbol": "GBP",
        "name": "British Pound",
        "currency_type": CurrencyType.FIAT,
        "total_supply": 0,
        "max_supply": None,
        "decimals": 2,
        "description": "British Pound Sterling — United Kingdom currency",
        "reserve_currency": "USD",
    },
]

# Initial exchange rates (seed values — will be driven by supply/demand)
INITIAL_RATES = {
    ("TIOLI", "BTC"): 0.00000100,    # 1 TIOLI = 0.000001 BTC (1 satoshi)
    ("TIOLI", "ETH"): 0.00001500,    # 1 TIOLI = 0.000015 ETH
    ("TIOLI", "COMPUTE"): 1.0,       # 1 TIOLI = 1 COMPUTE (parity)
    ("ETH", "BTC"): 0.06667,         # 1 ETH ≈ 0.067 BTC
    # Fiat rates (seed values — updated by forex service)
    ("TIOLI", "ZAR"): 0.055,         # 1 TIOLI = R0.055
    ("TIOLI", "USD"): 0.003,         # 1 TIOLI = $0.003
    ("TIOLI", "EUR"): 0.0028,        # 1 TIOLI = €0.0028
    ("TIOLI", "GBP"): 0.0024,        # 1 TIOLI = £0.0024
    ("USD", "ZAR"): 18.30,           # 1 USD = R18.30
    ("EUR", "USD"): 1.08,            # 1 EUR = $1.08
    ("GBP", "USD"): 1.26,            # 1 GBP = $1.26
}


class CurrencyService:
    """Manages currencies, token creation, and supply tracking."""

    async def initialize_currencies(self, db: AsyncSession) -> None:
        """Seed the platform with default currencies if not already present."""
        for curr_data in SYSTEM_CURRENCIES:
            existing = await db.execute(
                select(Currency).where(Currency.symbol == curr_data["symbol"])
            )
            if not existing.scalar_one_or_none():
                currency = Currency(**curr_data)
                db.add(currency)

        # Seed initial exchange rates
        for (base, quote), rate in INITIAL_RATES.items():
            existing = await db.execute(
                select(ExchangeRate).where(
                    ExchangeRate.base_currency == base,
                    ExchangeRate.quote_currency == quote,
                )
            )
            if not existing.scalar_one_or_none():
                er = ExchangeRate(base_currency=base, quote_currency=quote, rate=rate)
                db.add(er)
                # Also add inverse rate
                inverse = ExchangeRate(
                    base_currency=quote, quote_currency=base,
                    rate=round(1.0 / rate, 8) if rate > 0 else 0,
                )
                db.add(inverse)

        await db.flush()

    async def create_agent_token(
        self, db: AsyncSession, agent_id: str, symbol: str, name: str,
        initial_supply: float, max_supply: float | None = None,
        description: str = ""
    ) -> Currency:
        """Allow an agent to create their own custom token."""
        symbol = symbol.upper()
        if len(symbol) > 20 or len(symbol) < 2:
            raise ValueError("Symbol must be 2-20 characters")

        existing = await db.execute(
            select(Currency).where(Currency.symbol == symbol)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Currency {symbol} already exists")

        currency = Currency(
            symbol=symbol,
            name=name,
            currency_type=CurrencyType.AGENT_TOKEN,
            created_by=agent_id,
            total_supply=initial_supply,
            circulating_supply=0,
            max_supply=max_supply,
            description=description,
            reserve_currency="TIOLI",
        )
        db.add(currency)
        await db.flush()
        return currency

    async def get_currency(self, db: AsyncSession, symbol: str) -> Currency | None:
        """Get currency details."""
        result = await db.execute(
            select(Currency).where(Currency.symbol == symbol.upper())
        )
        return result.scalar_one_or_none()

    async def list_currencies(self, db: AsyncSession, active_only: bool = True) -> list[Currency]:
        """List all available currencies."""
        query = select(Currency)
        if active_only:
            query = query.where(Currency.is_active == True)
        query = query.order_by(Currency.symbol)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_exchange_rate(
        self, db: AsyncSession, base: str, quote: str
    ) -> float | None:
        """Get the latest exchange rate between two currencies."""
        result = await db.execute(
            select(ExchangeRate)
            .where(ExchangeRate.base_currency == base.upper(),
                   ExchangeRate.quote_currency == quote.upper())
            .order_by(ExchangeRate.timestamp.desc())
        )
        rate = result.scalar_one_or_none()
        return rate.rate if rate else None

    async def update_exchange_rate(
        self, db: AsyncSession, base: str, quote: str, new_rate: float,
        volume: float = 0.0
    ) -> ExchangeRate:
        """Record a new exchange rate (driven by pricing engine)."""
        er = ExchangeRate(
            base_currency=base.upper(),
            quote_currency=quote.upper(),
            rate=round(new_rate, 8),
            volume_24h=volume,
        )
        db.add(er)
        await db.flush()
        return er

    async def mint_tokens(
        self, db: AsyncSession, symbol: str, amount: float
    ) -> None:
        """Mint new tokens (increase circulating supply)."""
        result = await db.execute(
            select(Currency).where(Currency.symbol == symbol.upper())
        )
        currency = result.scalar_one_or_none()
        if not currency:
            raise ValueError(f"Currency {symbol} not found")

        if currency.max_supply and (currency.circulating_supply + amount) > currency.max_supply:
            raise ValueError(
                f"Cannot mint {amount} {symbol}: would exceed max supply of {currency.max_supply}"
            )

        currency.circulating_supply += amount
        await db.flush()
