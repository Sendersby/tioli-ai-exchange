"""Market-making bot — provides liquidity by placing buy and sell orders.

Solves the chicken-and-egg liquidity problem (Issue #1) by ensuring there
is always a counterparty for early operators. The bot:
- Places standing buy and sell orders on all active trading pairs
- Maintains a configurable spread (default 3%)
- Uses the founder liquidity pool as capital
- Earns commission on facilitated trades (returns to pool)
- Can be toggled on/off and configured per pair

The bot is NOT an autonomous trader — it is a transparent, deterministic
market-making service that the platform owner controls.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import Agent, Wallet
from app.exchange.orderbook import TradingEngine, Order, OrderStatus
from app.exchange.currencies import CurrencyService, ExchangeRate
from app.exchange.liquidity import LiquidityPool

logger = logging.getLogger(__name__)

# The market maker operates as a special system agent
MARKET_MAKER_AGENT_ID = "TIOLI_MARKET_MAKER"

# Default configuration
DEFAULT_SPREAD_PCT = 0.03      # 3% spread (1.5% each side)
DEFAULT_ORDER_SIZE = 100.0     # 100 AGENTIS per side
MIN_POOL_BALANCE = 50.0        # Don't place orders if pool balance is below this


class MarketMakerConfig:
    """Configuration for a market-making pair."""
    def __init__(
        self,
        base: str,
        quote: str,
        spread_pct: float = DEFAULT_SPREAD_PCT,
        order_size: float = DEFAULT_ORDER_SIZE,
        enabled: bool = True,
    ):
        self.base = base
        self.quote = quote
        self.spread_pct = spread_pct
        self.order_size = order_size
        self.enabled = enabled


class MarketMakerService:
    """Automated market maker that provides liquidity on the exchange."""

    def __init__(self, trading_engine: TradingEngine, currency_service: CurrencyService):
        self.trading_engine = trading_engine
        self.currency_service = currency_service
        self._configs: dict[str, MarketMakerConfig] = {}
        self._active_orders: list[str] = []  # Order IDs placed by the bot

        # Default pairs to provide liquidity on
        self._init_default_pairs()

    def _init_default_pairs(self):
        """Set up default trading pairs for market making."""
        pairs = [
            ("AGENTIS", "BTC", 0.03, 100.0),
            ("AGENTIS", "ETH", 0.03, 100.0),
            ("ETH", "BTC", 0.04, 0.5),
        ]
        for base, quote, spread, size in pairs:
            key = f"{base}/{quote}"
            self._configs[key] = MarketMakerConfig(base, quote, spread, size)

    async def ensure_market_maker_agent(self, db: AsyncSession) -> Agent:
        """Ensure the market maker system agent exists."""
        result = await db.execute(
            select(Agent).where(Agent.id == MARKET_MAKER_AGENT_ID)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            agent = Agent(
                id=MARKET_MAKER_AGENT_ID,
                name="TiOLi Market Maker",
                platform="TiOLi",
                description="Automated market maker providing exchange liquidity",
                is_approved=True,
            )
            db.add(agent)
            await db.flush()
        return agent

    async def fund_from_pool(
        self, db: AsyncSession, currency: str, amount: float
    ) -> bool:
        """Transfer funds from the liquidity pool to the market maker's wallet."""
        # Check pool balance
        result = await db.execute(
            select(LiquidityPool).where(LiquidityPool.currency == currency)
        )
        pool = result.scalar_one_or_none()
        if not pool or pool.balance < amount:
            logger.warning(f"MarketMaker: insufficient {currency} pool balance")
            return False

        # Deduct from pool
        pool.balance -= amount
        pool.updated_at = datetime.now(timezone.utc)

        # Credit market maker wallet
        from app.agents.wallet import WalletService
        wallet_result = await db.execute(
            select(Wallet).where(
                Wallet.agent_id == MARKET_MAKER_AGENT_ID,
                Wallet.currency == currency,
            )
        )
        wallet = wallet_result.scalar_one_or_none()
        if not wallet:
            wallet = Wallet(agent_id=MARKET_MAKER_AGENT_ID, currency=currency)
            db.add(wallet)
            await db.flush()
        wallet.balance += amount

        await db.flush()
        logger.info(f"MarketMaker: funded {amount} {currency} from pool")
        return True

    async def refresh_orders(self, db: AsyncSession) -> dict:
        """Cancel stale orders and place fresh buy/sell orders on all pairs.

        This is the main method — call periodically or after significant trades.
        Returns summary of actions taken.
        """
        await self.ensure_market_maker_agent(db)
        summary = {"pairs_updated": 0, "orders_placed": 0, "orders_cancelled": 0, "errors": []}

        # Cancel existing market maker orders
        for order_id in list(self._active_orders):
            try:
                await self.trading_engine.cancel_order(db, order_id, MARKET_MAKER_AGENT_ID)
                summary["orders_cancelled"] += 1
            except Exception:
                pass  # Order may already be filled or cancelled
        self._active_orders.clear()

        # Place new orders for each configured pair
        for key, config in self._configs.items():
            if not config.enabled:
                continue

            try:
                placed = await self._place_pair_orders(db, config)
                if placed:
                    summary["pairs_updated"] += 1
                    summary["orders_placed"] += placed
            except Exception as e:
                summary["errors"].append(f"{key}: {str(e)}")
                logger.error(f"MarketMaker: error on {key}: {e}")

        await db.flush()
        return summary

    async def _place_pair_orders(
        self, db: AsyncSession, config: MarketMakerConfig
    ) -> int:
        """Place buy and sell orders for a single pair."""
        # Get current market price
        rate_result = await db.execute(
            select(ExchangeRate).where(
                ExchangeRate.base_currency == config.base,
                ExchangeRate.quote_currency == config.quote,
            ).order_by(ExchangeRate.timestamp.desc()).limit(1)
        )
        rate = rate_result.scalar_one_or_none()
        if not rate or rate.rate <= 0:
            return 0

        mid_price = rate.rate
        half_spread = config.spread_pct / 2

        buy_price = round(mid_price * (1 - half_spread), 8)
        sell_price = round(mid_price * (1 + half_spread), 8)

        orders_placed = 0

        # Check market maker has sufficient balance, fund from pool if needed
        buy_cost = buy_price * config.order_size  # Need quote currency to buy
        sell_cost = config.order_size               # Need base currency to sell

        # Fund from pool if needed
        mm_quote_wallet = await db.execute(
            select(Wallet).where(
                Wallet.agent_id == MARKET_MAKER_AGENT_ID,
                Wallet.currency == config.quote,
            )
        )
        quote_wallet = mm_quote_wallet.scalar_one_or_none()
        if not quote_wallet or quote_wallet.available_balance < buy_cost:
            await self.fund_from_pool(db, config.quote, buy_cost * 2)

        mm_base_wallet = await db.execute(
            select(Wallet).where(
                Wallet.agent_id == MARKET_MAKER_AGENT_ID,
                Wallet.currency == config.base,
            )
        )
        base_wallet = mm_base_wallet.scalar_one_or_none()
        if not base_wallet or base_wallet.available_balance < sell_cost:
            await self.fund_from_pool(db, config.base, sell_cost * 2)

        # Place buy order (bid)
        try:
            result = await self.trading_engine.place_order(
                db, MARKET_MAKER_AGENT_ID, "buy",
                config.base, config.quote,
                buy_price, config.order_size,
            )
            if result.get("order_id"):
                self._active_orders.append(result["order_id"])
                orders_placed += 1
        except Exception as e:
            logger.warning(f"MarketMaker: buy order failed {config.base}/{config.quote}: {e}")

        # Place sell order (ask)
        try:
            result = await self.trading_engine.place_order(
                db, MARKET_MAKER_AGENT_ID, "sell",
                config.base, config.quote,
                sell_price, config.order_size,
            )
            if result.get("order_id"):
                self._active_orders.append(result["order_id"])
                orders_placed += 1
        except Exception as e:
            logger.warning(f"MarketMaker: sell order failed {config.base}/{config.quote}: {e}")

        return orders_placed

    def configure_pair(
        self, base: str, quote: str, spread_pct: float = DEFAULT_SPREAD_PCT,
        order_size: float = DEFAULT_ORDER_SIZE, enabled: bool = True,
    ) -> dict:
        """Configure or update a market-making pair."""
        key = f"{base}/{quote}"
        self._configs[key] = MarketMakerConfig(base, quote, spread_pct, order_size, enabled)
        return {
            "pair": key, "spread_pct": spread_pct,
            "order_size": order_size, "enabled": enabled,
        }

    def get_status(self) -> dict:
        """Get market maker status and configuration."""
        return {
            "active_orders": len(self._active_orders),
            "pairs": {
                key: {
                    "base": c.base, "quote": c.quote,
                    "spread_pct": f"{c.spread_pct*100:.1f}%",
                    "order_size": c.order_size,
                    "enabled": c.enabled,
                }
                for key, c in self._configs.items()
            },
        }
