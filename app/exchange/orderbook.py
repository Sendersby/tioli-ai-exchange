"""Order book and trading engine for TiOLi AI Transact Exchange.

Agents place buy/sell orders for any supported trading pair.
The engine matches orders by price-time priority, supports partial fills,
and records every trade on the blockchain for full transparency.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Float, String, Integer, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base
from app.blockchain.chain import Blockchain
from app.blockchain.transaction import Transaction, TransactionType
from app.exchange.fees import FeeEngine


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"


class Order(Base):
    """A buy or sell order on the exchange."""
    __tablename__ = "orders"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False)
    side = Column(String(10), nullable=False)           # "buy" or "sell"
    base_currency = Column(String(20), nullable=False)  # What you're trading (e.g. TIOLI)
    quote_currency = Column(String(20), nullable=False) # What you're pricing in (e.g. BTC)
    price = Column(Float, nullable=False)               # Price per unit in quote currency
    quantity = Column(Float, nullable=False)             # Total quantity to trade
    filled_quantity = Column(Float, default=0.0)         # How much has been filled
    status = Column(String(20), default=OrderStatus.OPEN)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def remaining(self) -> float:
        return self.quantity - self.filled_quantity

    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)


class Trade(Base):
    """A completed trade between two orders."""
    __tablename__ = "trades"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    buy_order_id = Column(String, nullable=False)
    sell_order_id = Column(String, nullable=False)
    buyer_id = Column(String, nullable=False)
    seller_id = Column(String, nullable=False)
    base_currency = Column(String(20), nullable=False)
    quote_currency = Column(String(20), nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    total_value = Column(Float, nullable=False)         # price * quantity
    founder_commission = Column(Float, default=0.0)
    charity_fee = Column(Float, default=0.0)
    executed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TradingEngine:
    """Matches buy and sell orders using price-time priority.

    When a new order is placed:
    1. Check for matching orders on the opposite side
    2. Match at the best available price (price-time priority)
    3. Execute trades, update wallets, deduct fees
    4. Record everything on the blockchain
    """

    def __init__(self, blockchain: Blockchain, fee_engine: FeeEngine):
        self.blockchain = blockchain
        self.fee_engine = fee_engine

    async def place_order(
        self, db: AsyncSession, agent_id: str, side: str,
        base_currency: str, quote_currency: str,
        price: float, quantity: float
    ) -> dict:
        """Place a new order and attempt to match it immediately."""
        from app.agents.models import Wallet

        if side not in ("buy", "sell"):
            raise ValueError("Side must be 'buy' or 'sell'")
        if price <= 0 or quantity <= 0:
            raise ValueError("Price and quantity must be positive")

        # Verify agent has sufficient balance
        if side == "buy":
            # Buyer needs quote_currency (price * quantity)
            required = price * quantity
            wallet = await self._get_wallet(db, agent_id, quote_currency)
            if wallet.available_balance < required:
                raise ValueError(
                    f"Insufficient {quote_currency} balance. "
                    f"Need {required}, have {wallet.available_balance}"
                )
            # Freeze the funds
            wallet.frozen_balance += required
        else:
            # Seller needs base_currency (quantity)
            wallet = await self._get_wallet(db, agent_id, base_currency)
            if wallet.available_balance < quantity:
                raise ValueError(
                    f"Insufficient {base_currency} balance. "
                    f"Need {quantity}, have {wallet.available_balance}"
                )
            wallet.frozen_balance += quantity

        # Create the order
        order = Order(
            agent_id=agent_id,
            side=side,
            base_currency=base_currency.upper(),
            quote_currency=quote_currency.upper(),
            price=price,
            quantity=quantity,
        )
        db.add(order)
        await db.flush()

        # Attempt to match
        trades = await self._match_order(db, order)

        return {
            "order_id": order.id,
            "side": side,
            "pair": f"{base_currency}/{quote_currency}",
            "price": price,
            "quantity": quantity,
            "filled": order.filled_quantity,
            "remaining": order.remaining,
            "status": order.status,
            "trades_executed": len(trades),
        }

    async def cancel_order(self, db: AsyncSession, order_id: str, agent_id: str) -> dict:
        """Cancel an open order and unfreeze funds."""
        from app.agents.models import Wallet

        result = await db.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()

        if not order:
            raise ValueError("Order not found")
        if order.agent_id != agent_id:
            raise ValueError("Cannot cancel another agent's order")
        if not order.is_active:
            raise ValueError("Order is not active")

        # Unfreeze remaining funds
        if order.side == "buy":
            wallet = await self._get_wallet(db, order.agent_id, order.quote_currency)
            unfreeze = order.remaining * order.price
            wallet.frozen_balance = max(0, wallet.frozen_balance - unfreeze)
        else:
            wallet = await self._get_wallet(db, order.agent_id, order.base_currency)
            wallet.frozen_balance = max(0, wallet.frozen_balance - order.remaining)

        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now(timezone.utc)
        await db.flush()

        return {"order_id": order_id, "status": "cancelled", "unfrozen": True}

    async def get_order_book(
        self, db: AsyncSession, base_currency: str, quote_currency: str,
        depth: int = 20
    ) -> dict:
        """Get the current order book for a trading pair."""
        base = base_currency.upper()
        quote = quote_currency.upper()

        # Buy orders (bids) — highest price first
        bids_result = await db.execute(
            select(Order)
            .where(
                Order.base_currency == base,
                Order.quote_currency == quote,
                Order.side == OrderSide.BUY,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            )
            .order_by(Order.price.desc(), Order.created_at.asc())
            .limit(depth)
        )
        bids = bids_result.scalars().all()

        # Sell orders (asks) — lowest price first
        asks_result = await db.execute(
            select(Order)
            .where(
                Order.base_currency == base,
                Order.quote_currency == quote,
                Order.side == OrderSide.SELL,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
            )
            .order_by(Order.price.asc(), Order.created_at.asc())
            .limit(depth)
        )
        asks = asks_result.scalars().all()

        return {
            "pair": f"{base}/{quote}",
            "bids": [
                {"price": o.price, "quantity": o.remaining, "agent_id": o.agent_id[:8]}
                for o in bids
            ],
            "asks": [
                {"price": o.price, "quantity": o.remaining, "agent_id": o.agent_id[:8]}
                for o in asks
            ],
            "spread": (asks[0].price - bids[0].price) if (bids and asks) else None,
            "best_bid": bids[0].price if bids else None,
            "best_ask": asks[0].price if asks else None,
        }

    async def get_recent_trades(
        self, db: AsyncSession, base_currency: str, quote_currency: str,
        limit: int = 50
    ) -> list[dict]:
        """Get recent trades for a trading pair."""
        result = await db.execute(
            select(Trade)
            .where(
                Trade.base_currency == base_currency.upper(),
                Trade.quote_currency == quote_currency.upper(),
            )
            .order_by(Trade.executed_at.desc())
            .limit(limit)
        )
        trades = result.scalars().all()
        return [
            {
                "id": t.id,
                "price": t.price,
                "quantity": t.quantity,
                "total_value": t.total_value,
                "buyer": t.buyer_id[:8],
                "seller": t.seller_id[:8],
                "commission": t.founder_commission,
                "charity": t.charity_fee,
                "time": str(t.executed_at),
            }
            for t in trades
        ]

    async def _match_order(self, db: AsyncSession, incoming: Order) -> list[Trade]:
        """Match an incoming order against the book (price-time priority)."""
        trades = []

        if incoming.side == OrderSide.BUY:
            # Match against sell orders at or below the buy price
            result = await db.execute(
                select(Order)
                .where(
                    Order.base_currency == incoming.base_currency,
                    Order.quote_currency == incoming.quote_currency,
                    Order.side == OrderSide.SELL,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                    Order.price <= incoming.price,
                    Order.agent_id != incoming.agent_id,
                )
                .order_by(Order.price.asc(), Order.created_at.asc())
            )
        else:
            # Match against buy orders at or above the sell price
            result = await db.execute(
                select(Order)
                .where(
                    Order.base_currency == incoming.base_currency,
                    Order.quote_currency == incoming.quote_currency,
                    Order.side == OrderSide.BUY,
                    Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]),
                    Order.price >= incoming.price,
                    Order.agent_id != incoming.agent_id,
                )
                .order_by(Order.price.desc(), Order.created_at.asc())
            )

        matching_orders = list(result.scalars().all())

        for match in matching_orders:
            if incoming.remaining <= 0:
                break

            # Determine trade quantity and price
            trade_qty = min(incoming.remaining, match.remaining)
            trade_price = match.price  # Maker's price

            # Execute the trade
            trade = await self._execute_trade(db, incoming, match, trade_qty, trade_price)
            trades.append(trade)

        return trades

    async def _execute_trade(
        self, db: AsyncSession, incoming: Order, matching: Order,
        quantity: float, price: float
    ) -> Trade:
        """Execute a trade between two orders, update wallets, deduct fees."""
        from app.agents.models import Wallet

        total_value = round(price * quantity, 8)
        fee_breakdown = self.fee_engine.calculate_fees(total_value)

        # Determine buyer and seller
        if incoming.side == OrderSide.BUY:
            buyer, seller = incoming, matching
        else:
            buyer, seller = matching, incoming

        # Update buyer wallets
        buyer_quote_wallet = await self._get_wallet(db, buyer.agent_id, buyer.quote_currency)
        buyer_base_wallet = await self._get_wallet(db, buyer.agent_id, buyer.base_currency)
        # Unfreeze and deduct quote currency
        buyer_quote_wallet.frozen_balance = max(0, buyer_quote_wallet.frozen_balance - total_value)
        buyer_quote_wallet.balance -= total_value
        # Credit base currency (minus fees on the base side)
        buyer_base_wallet.balance += quantity

        # Update seller wallets
        seller_base_wallet = await self._get_wallet(db, seller.agent_id, seller.base_currency)
        seller_quote_wallet = await self._get_wallet(db, seller.agent_id, seller.quote_currency)
        # Unfreeze and deduct base currency
        seller_base_wallet.frozen_balance = max(0, seller_base_wallet.frozen_balance - quantity)
        seller_base_wallet.balance -= quantity
        # Credit quote currency (after fees)
        seller_quote_wallet.balance += fee_breakdown["net_amount"]

        # Update order fill states
        now = datetime.now(timezone.utc)
        for order in (incoming, matching):
            order.filled_quantity += quantity
            order.updated_at = now
            if order.remaining <= 0.00000001:  # Float tolerance
                order.status = OrderStatus.FILLED
            else:
                order.status = OrderStatus.PARTIALLY_FILLED

        # Record trade
        trade = Trade(
            buy_order_id=buyer.id,
            sell_order_id=seller.id,
            buyer_id=buyer.agent_id,
            seller_id=seller.agent_id,
            base_currency=incoming.base_currency,
            quote_currency=incoming.quote_currency,
            price=price,
            quantity=quantity,
            total_value=total_value,
            founder_commission=fee_breakdown["founder_commission"],
            charity_fee=fee_breakdown["charity_fee"],
        )
        db.add(trade)

        # Record on blockchain
        tx = Transaction(
            type=TransactionType.TRADE,
            sender_id=seller.agent_id,
            receiver_id=buyer.agent_id,
            amount=total_value,
            currency=incoming.quote_currency,
            description=(
                f"Trade: {quantity} {incoming.base_currency} @ {price} {incoming.quote_currency}. "
                f"Commission: {fee_breakdown['founder_commission']}, "
                f"Charity: {fee_breakdown['charity_fee']}"
            ),
            founder_commission=fee_breakdown["founder_commission"],
            charity_fee=fee_breakdown["charity_fee"],
            metadata={
                "trade_id": trade.id,
                "base": incoming.base_currency,
                "quote": incoming.quote_currency,
                "price": price,
                "quantity": quantity,
            },
        )
        self.blockchain.add_transaction(tx)

        await db.flush()
        return trade

    async def _get_wallet(self, db: AsyncSession, agent_id: str, currency: str):
        """Get or create a wallet for an agent and currency."""
        from app.agents.models import Wallet
        result = await db.execute(
            select(Wallet).where(
                Wallet.agent_id == agent_id, Wallet.currency == currency.upper()
            )
        )
        wallet = result.scalar_one_or_none()
        if not wallet:
            wallet = Wallet(agent_id=agent_id, currency=currency.upper())
            db.add(wallet)
            await db.flush()
        return wallet
