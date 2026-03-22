"""Supply/demand pricing engine for TiOLi AGENTIS.

Algorithmically determines real-time exchange rates based on:
- Order book depth and spread
- Recent trade volume and price
- Supply and demand dynamics
- Weighted moving averages

All rates are transparent and auditable.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.exchange.orderbook import Order, Trade, OrderSide, OrderStatus
from app.exchange.currencies import ExchangeRate, CurrencyService


class PricingEngine:
    """Calculates real-time exchange rates from market activity."""

    def __init__(self, currency_service: CurrencyService):
        self.currency_service = currency_service

    async def get_market_price(
        self, db: AsyncSession, base: str, quote: str
    ) -> dict:
        """Get the current market price for a trading pair.

        Uses a weighted combination of:
        1. Mid-price from order book (best bid + best ask / 2)
        2. Last trade price
        3. Volume-weighted average price (VWAP) over last 24h
        """
        base, quote = base.upper(), quote.upper()

        # 1. Order book mid-price
        mid_price = await self._get_mid_price(db, base, quote)

        # 2. Last trade price
        last_trade = await self._get_last_trade_price(db, base, quote)

        # 3. VWAP over 24h
        vwap = await self._get_vwap(db, base, quote, hours=24)

        # Weighted composite: prioritize order book when available
        prices = []
        weights = []
        if mid_price is not None:
            prices.append(mid_price)
            weights.append(0.5)
        if last_trade is not None:
            prices.append(last_trade)
            weights.append(0.3)
        if vwap is not None:
            prices.append(vwap)
            weights.append(0.2)

        if not prices:
            # Fall back to stored exchange rate
            stored = await self.currency_service.get_exchange_rate(db, base, quote)
            return {
                "pair": f"{base}/{quote}",
                "price": stored,
                "source": "stored_rate",
                "mid_price": None,
                "last_trade": None,
                "vwap_24h": None,
            }

        # Normalize weights
        total_weight = sum(weights)
        composite = sum(p * w for p, w in zip(prices, weights)) / total_weight

        return {
            "pair": f"{base}/{quote}",
            "price": round(composite, 8),
            "source": "market",
            "mid_price": mid_price,
            "last_trade": last_trade,
            "vwap_24h": vwap,
        }

    async def update_rates_from_trade(
        self, db: AsyncSession, base: str, quote: str
    ) -> float | None:
        """Recalculate and store the exchange rate after a trade occurs."""
        market = await self.get_market_price(db, base, quote)
        price = market["price"]

        if price is not None and price > 0:
            # Get 24h volume
            volume = await self._get_24h_volume(db, base, quote)

            # Update stored rate
            await self.currency_service.update_exchange_rate(
                db, base, quote, price, volume
            )
            # Update inverse
            await self.currency_service.update_exchange_rate(
                db, quote, base, round(1.0 / price, 8), volume
            )

        return price

    async def get_market_summary(
        self, db: AsyncSession, base: str, quote: str
    ) -> dict:
        """Full market summary for a trading pair."""
        base, quote = base.upper(), quote.upper()
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)

        # Current price
        market = await self.get_market_price(db, base, quote)

        # 24h stats
        result = await db.execute(
            select(
                func.count(Trade.id),
                func.sum(Trade.quantity),
                func.sum(Trade.total_value),
                func.min(Trade.price),
                func.max(Trade.price),
            ).where(
                Trade.base_currency == base,
                Trade.quote_currency == quote,
                Trade.executed_at >= day_ago,
            )
        )
        row = result.one()
        trade_count, total_qty, total_value, low, high = row

        # Open orders count
        open_result = await db.execute(
            select(func.count(Order.id)).where(
                Order.base_currency == base,
                Order.quote_currency == quote,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            )
        )
        open_orders = open_result.scalar() or 0

        return {
            "pair": f"{base}/{quote}",
            "price": market["price"],
            "price_source": market["source"],
            "24h_trades": trade_count or 0,
            "24h_volume_base": round(total_qty or 0, 8),
            "24h_volume_quote": round(total_value or 0, 8),
            "24h_low": low,
            "24h_high": high,
            "open_orders": open_orders,
            "mid_price": market["mid_price"],
            "vwap": market["vwap_24h"],
        }

    async def get_all_rates(self, db: AsyncSession) -> list[dict]:
        """Get current rates for all active trading pairs."""
        result = await db.execute(
            select(
                ExchangeRate.base_currency,
                ExchangeRate.quote_currency,
                ExchangeRate.rate,
                ExchangeRate.volume_24h,
                ExchangeRate.timestamp,
            )
            .distinct(ExchangeRate.base_currency, ExchangeRate.quote_currency)
            .order_by(
                ExchangeRate.base_currency,
                ExchangeRate.quote_currency,
                ExchangeRate.timestamp.desc(),
            )
        )
        rates = result.all()
        return [
            {
                "base": r[0],
                "quote": r[1],
                "rate": r[2],
                "volume_24h": r[3],
                "updated": str(r[4]),
            }
            for r in rates
        ]

    async def _get_mid_price(
        self, db: AsyncSession, base: str, quote: str
    ) -> float | None:
        """Calculate mid-price from best bid and best ask."""
        # Best bid
        bid_result = await db.execute(
            select(Order.price)
            .where(
                Order.base_currency == base,
                Order.quote_currency == quote,
                Order.side == OrderSide.BUY,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            )
            .order_by(Order.price.desc())
            .limit(1)
        )
        best_bid = bid_result.scalar_one_or_none()

        # Best ask
        ask_result = await db.execute(
            select(Order.price)
            .where(
                Order.base_currency == base,
                Order.quote_currency == quote,
                Order.side == OrderSide.SELL,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            )
            .order_by(Order.price.asc())
            .limit(1)
        )
        best_ask = ask_result.scalar_one_or_none()

        if best_bid is not None and best_ask is not None:
            return round((best_bid + best_ask) / 2, 8)
        return best_bid or best_ask

    async def _get_last_trade_price(
        self, db: AsyncSession, base: str, quote: str
    ) -> float | None:
        """Get the price of the most recent trade."""
        result = await db.execute(
            select(Trade.price)
            .where(Trade.base_currency == base, Trade.quote_currency == quote)
            .order_by(Trade.executed_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_vwap(
        self, db: AsyncSession, base: str, quote: str, hours: int = 24
    ) -> float | None:
        """Volume-weighted average price over a time window."""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await db.execute(
            select(
                func.sum(Trade.total_value),
                func.sum(Trade.quantity),
            ).where(
                Trade.base_currency == base,
                Trade.quote_currency == quote,
                Trade.executed_at >= since,
            )
        )
        row = result.one()
        total_value, total_qty = row
        if total_value and total_qty and total_qty > 0:
            return round(total_value / total_qty, 8)
        return None

    async def _get_24h_volume(
        self, db: AsyncSession, base: str, quote: str
    ) -> float:
        """Total trade volume in last 24 hours."""
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await db.execute(
            select(func.sum(Trade.total_value)).where(
                Trade.base_currency == base,
                Trade.quote_currency == quote,
                Trade.executed_at >= since,
            )
        )
        return result.scalar() or 0.0
