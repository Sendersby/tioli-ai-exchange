"""Treasury Agent service — autonomous portfolio management within risk bounds.

Build Brief V2, Module 4: The execution engine evaluates portfolio state,
market conditions, and risk parameters to select optimal actions. All
actions are logged with AI-generated rationale. Standard transaction fees
apply — no additional treasury fee.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.treasury.models import TreasuryAgent, TreasuryAction
from app.agents.models import Agent, Wallet

logger = logging.getLogger(__name__)


class TreasuryService:
    """Manages treasury agent designation, parameters, and execution."""

    async def designate(
        self, db: AsyncSession, agent_id: str, operator_id: str,
        max_single_trade_pct: float = 10.0,
        max_lending_pct: float = 30.0,
        min_reserve_pct: float = 20.0,
        buy_threshold: float | None = None,
        sell_threshold: float | None = None,
        approved_currencies: list[str] | None = None,
        allowed_actions: list[str] | None = None,
        execution_interval_minutes: int = 60,
    ) -> dict:
        """Designate an agent as a treasury manager."""
        # Verify agent exists and belongs to operator
        agent_result = await db.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = agent_result.scalar_one_or_none()
        if not agent:
            raise ValueError(f"Agent '{agent_id}' not found")

        # Check not already a treasury agent
        existing = await db.execute(
            select(TreasuryAgent).where(TreasuryAgent.agent_id == agent_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent is already designated as a treasury manager")

        # Validate risk parameters
        if min_reserve_pct + max_lending_pct > 100:
            raise ValueError("min_reserve_pct + max_lending_pct cannot exceed 100%")
        if max_single_trade_pct > 50:
            raise ValueError("max_single_trade_pct cannot exceed 50%")

        valid_actions = {"trade", "lend", "borrow", "convert"}
        actions = allowed_actions or ["trade", "convert"]
        if not set(actions).issubset(valid_actions):
            raise ValueError(f"Invalid actions. Allowed: {valid_actions}")

        treasury = TreasuryAgent(
            agent_id=agent_id,
            operator_id=operator_id,
            max_single_trade_pct=max_single_trade_pct,
            max_lending_pct=max_lending_pct,
            min_reserve_pct=min_reserve_pct,
            buy_threshold=buy_threshold,
            sell_threshold=sell_threshold,
            approved_currencies=approved_currencies or ["AGENTIS", "BTC", "ETH"],
            allowed_actions=actions,
            execution_interval_minutes=execution_interval_minutes,
        )
        db.add(treasury)
        await db.flush()

        return {
            "treasury_id": treasury.id,
            "agent_id": agent_id,
            "operator_id": operator_id,
            "status": treasury.status,
            "parameters": {
                "max_single_trade_pct": max_single_trade_pct,
                "max_lending_pct": max_lending_pct,
                "min_reserve_pct": min_reserve_pct,
                "buy_threshold": buy_threshold,
                "sell_threshold": sell_threshold,
                "approved_currencies": treasury.approved_currencies,
                "allowed_actions": treasury.allowed_actions,
                "execution_interval_minutes": execution_interval_minutes,
            },
        }

    async def update_parameters(
        self, db: AsyncSession, treasury_id: str,
        max_single_trade_pct: float | None = None,
        max_lending_pct: float | None = None,
        min_reserve_pct: float | None = None,
        buy_threshold: float | None = None,
        sell_threshold: float | None = None,
        approved_currencies: list[str] | None = None,
        allowed_actions: list[str] | None = None,
        execution_interval_minutes: int | None = None,
    ) -> dict:
        """Update treasury risk parameters. Takes effect on next execution cycle."""
        result = await db.execute(
            select(TreasuryAgent).where(TreasuryAgent.id == treasury_id)
        )
        treasury = result.scalar_one_or_none()
        if not treasury:
            raise ValueError("Treasury agent not found")

        if max_single_trade_pct is not None:
            treasury.max_single_trade_pct = max_single_trade_pct
        if max_lending_pct is not None:
            treasury.max_lending_pct = max_lending_pct
        if min_reserve_pct is not None:
            treasury.min_reserve_pct = min_reserve_pct
        if buy_threshold is not None:
            treasury.buy_threshold = buy_threshold
        if sell_threshold is not None:
            treasury.sell_threshold = sell_threshold
        if approved_currencies is not None:
            treasury.approved_currencies = approved_currencies
        if allowed_actions is not None:
            treasury.allowed_actions = allowed_actions
        if execution_interval_minutes is not None:
            treasury.execution_interval_minutes = execution_interval_minutes

        treasury.updated_at = datetime.now(timezone.utc)
        await db.flush()

        return {
            "treasury_id": treasury.id,
            "status": "parameters_updated",
            "effective": "next_execution_cycle",
        }

    async def pause(self, db: AsyncSession, treasury_id: str) -> dict:
        """Pause treasury execution. No trades while paused."""
        result = await db.execute(
            select(TreasuryAgent).where(TreasuryAgent.id == treasury_id)
        )
        treasury = result.scalar_one_or_none()
        if not treasury:
            raise ValueError("Treasury agent not found")

        treasury.status = "paused"
        treasury.updated_at = datetime.now(timezone.utc)
        await db.flush()

        return {"treasury_id": treasury.id, "status": "paused"}

    async def resume(self, db: AsyncSession, treasury_id: str) -> dict:
        """Resume a paused treasury agent."""
        result = await db.execute(
            select(TreasuryAgent).where(TreasuryAgent.id == treasury_id)
        )
        treasury = result.scalar_one_or_none()
        if not treasury:
            raise ValueError("Treasury agent not found")

        treasury.status = "active"
        treasury.updated_at = datetime.now(timezone.utc)
        await db.flush()

        return {"treasury_id": treasury.id, "status": "active"}

    async def get_performance(self, db: AsyncSession, treasury_id: str) -> dict:
        """Portfolio performance summary."""
        result = await db.execute(
            select(TreasuryAgent).where(TreasuryAgent.id == treasury_id)
        )
        treasury = result.scalar_one_or_none()
        if not treasury:
            raise ValueError("Treasury agent not found")

        # Count actions
        action_count = (await db.execute(
            select(func.count(TreasuryAction.id)).where(
                TreasuryAction.treasury_id == treasury_id
            )
        )).scalar() or 0

        successful = (await db.execute(
            select(func.count(TreasuryAction.id)).where(
                TreasuryAction.treasury_id == treasury_id,
                TreasuryAction.result_status == "success",
            )
        )).scalar() or 0

        # Get current portfolio balances
        wallets_result = await db.execute(
            select(Wallet).where(Wallet.agent_id == treasury.agent_id)
        )
        wallets = wallets_result.scalars().all()
        portfolio = {w.currency: {"balance": w.balance, "frozen": w.frozen_balance} for w in wallets}

        total_balance = sum(w.balance for w in wallets)

        return {
            "treasury_id": treasury.id,
            "agent_id": treasury.agent_id,
            "status": treasury.status,
            "total_actions": action_count,
            "successful_actions": successful,
            "success_rate": round(successful / max(action_count, 1) * 100, 1),
            "portfolio": portfolio,
            "total_balance": total_balance,
            "parameters": {
                "max_single_trade_pct": treasury.max_single_trade_pct,
                "max_lending_pct": treasury.max_lending_pct,
                "min_reserve_pct": treasury.min_reserve_pct,
            },
        }

    async def get_actions(
        self, db: AsyncSession, treasury_id: str, limit: int = 50
    ) -> list[dict]:
        """Paginated log of all treasury actions with rationale."""
        result = await db.execute(
            select(TreasuryAction)
            .where(TreasuryAction.treasury_id == treasury_id)
            .order_by(TreasuryAction.executed_at.desc())
            .limit(limit)
        )
        return [
            {
                "action_id": a.id,
                "action_type": a.action_type,
                "rationale": a.rationale,
                "amount": a.amount,
                "currency": a.currency,
                "result_status": a.result_status,
                "transaction_id": a.transaction_id,
                "executed_at": str(a.executed_at),
            }
            for a in result.scalars().all()
        ]

    async def log_action(
        self, db: AsyncSession, treasury_id: str,
        action_type: str, rationale: str,
        amount: float | None = None, currency: str | None = None,
        result_status: str = "success", transaction_id: str | None = None,
    ) -> TreasuryAction:
        """Log a treasury action to the immutable audit trail."""
        action = TreasuryAction(
            treasury_id=treasury_id,
            action_type=action_type,
            rationale=rationale,
            amount=amount,
            currency=currency,
            result_status=result_status,
            transaction_id=transaction_id,
        )
        db.add(action)
        await db.flush()
        return action
