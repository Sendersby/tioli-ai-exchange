"""Platform self-monitoring, health checks, and anomaly detection.

Provides real-time health status, performance metrics, and alerts.
The platform monitors itself to ensure integrity and reliability.
"""

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import Agent, Wallet, Loan
from app.exchange.orderbook import Order, Trade, OrderStatus
from app.exchange.currencies import Currency
from app.exchange.compute import ComputeStorage
from app.governance.models import Proposal
from app.governance.financial import PlatformRevenue, PlatformExpense, ExpenseStatus
from app.blockchain.chain import Blockchain


class HealthStatus:
    OK = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


class PlatformMonitor:
    """Monitors platform health across all subsystems."""

    def __init__(self, blockchain: Blockchain):
        self.blockchain = blockchain
        self._start_time = time.time()

    async def full_health_check(self, db: AsyncSession) -> dict:
        """Comprehensive health check across all platform systems."""
        checks = {}

        # 1. Blockchain integrity
        chain_valid = self.blockchain.validate_chain()
        chain_info = self.blockchain.get_chain_info()
        checks["blockchain"] = {
            "status": HealthStatus.OK if chain_valid else HealthStatus.CRITICAL,
            "valid": chain_valid,
            "blocks": chain_info["chain_length"],
            "pending_tx": chain_info["pending_transactions"],
            "total_tx": chain_info["total_transactions"],
        }

        # 2. Database connectivity
        try:
            agent_count = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
            checks["database"] = {
                "status": HealthStatus.OK,
                "agents": agent_count,
            }
        except Exception as e:
            checks["database"] = {"status": HealthStatus.CRITICAL, "error": str(e)}

        # 3. Agent activity
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)
        active_result = await db.execute(
            select(func.count(Agent.id)).where(Agent.last_active >= day_ago)
        )
        active_24h = active_result.scalar() or 0
        checks["agent_activity"] = {
            "status": HealthStatus.OK if active_24h > 0 else HealthStatus.WARNING,
            "total_agents": agent_count,
            "active_24h": active_24h,
        }

        # 4. Trading engine
        open_orders = (await db.execute(
            select(func.count(Order.id)).where(
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED])
            )
        )).scalar() or 0
        trades_24h = (await db.execute(
            select(func.count(Trade.id)).where(Trade.executed_at >= day_ago)
        )).scalar() or 0
        checks["trading"] = {
            "status": HealthStatus.OK,
            "open_orders": open_orders,
            "trades_24h": trades_24h,
        }

        # 5. Lending health
        active_loans = (await db.execute(
            select(func.count(Loan.id)).where(Loan.status == "active")
        )).scalar() or 0
        overdue_loans = (await db.execute(
            select(func.count(Loan.id)).where(
                Loan.status == "active",
                Loan.due_at != None,
                Loan.due_at <= now,
            )
        )).scalar() or 0
        checks["lending"] = {
            "status": HealthStatus.WARNING if overdue_loans > 0 else HealthStatus.OK,
            "active_loans": active_loans,
            "overdue_loans": overdue_loans,
        }

        # 6. Financial health
        rev_total = (await db.execute(
            select(func.sum(PlatformRevenue.amount))
        )).scalar() or 0.0
        exp_total = (await db.execute(
            select(func.sum(PlatformExpense.amount)).where(
                PlatformExpense.status == ExpenseStatus.ACTIVE
            )
        )).scalar() or 0.0
        multiplier = (rev_total / exp_total) if exp_total > 0 else float('inf')

        fin_status = HealthStatus.OK
        if multiplier != float('inf') and multiplier < 10:
            fin_status = HealthStatus.WARNING
        if multiplier != float('inf') and multiplier < 3:
            fin_status = HealthStatus.CRITICAL

        checks["financial"] = {
            "status": fin_status,
            "revenue": round(rev_total, 4),
            "expenses": round(exp_total, 4),
            "profitability_multiplier": round(multiplier, 2) if multiplier != float('inf') else "infinite",
        }

        # 7. Governance
        pending_proposals = (await db.execute(
            select(func.count(Proposal.id)).where(Proposal.status == "pending")
        )).scalar() or 0
        checks["governance"] = {
            "status": HealthStatus.OK,
            "pending_proposals": pending_proposals,
        }

        # 8. Platform uptime
        uptime_seconds = time.time() - self._start_time
        checks["uptime"] = {
            "status": HealthStatus.OK,
            "seconds": round(uptime_seconds),
            "formatted": self._format_uptime(uptime_seconds),
        }

        # Overall status
        statuses = [c.get("status", HealthStatus.OK) for c in checks.values()]
        if HealthStatus.CRITICAL in statuses:
            overall = HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses:
            overall = HealthStatus.WARNING
        else:
            overall = HealthStatus.OK

        return {
            "overall_status": overall,
            "timestamp": now.isoformat(),
            "checks": checks,
        }

    async def get_activity_report(self, db: AsyncSession, hours: int = 24) -> dict:
        """Activity report over a time window."""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        # New agents
        new_agents = (await db.execute(
            select(func.count(Agent.id)).where(Agent.created_at >= since)
        )).scalar() or 0

        # Trades
        trade_result = await db.execute(
            select(
                func.count(Trade.id),
                func.sum(Trade.total_value),
                func.sum(Trade.founder_commission),
                func.sum(Trade.charity_fee),
            ).where(Trade.executed_at >= since)
        )
        trade_row = trade_result.one()

        # Revenue recorded
        rev_result = await db.execute(
            select(func.sum(PlatformRevenue.amount))
            .where(PlatformRevenue.recorded_at >= since)
        )
        period_revenue = rev_result.scalar() or 0.0

        # Proposals
        new_proposals = (await db.execute(
            select(func.count(Proposal.id)).where(Proposal.created_at >= since)
        )).scalar() or 0

        return {
            "period_hours": hours,
            "since": since.isoformat(),
            "new_agents": new_agents,
            "trades": trade_row[0] or 0,
            "trade_volume": round(trade_row[1] or 0, 4),
            "commission_earned": round(trade_row[2] or 0, 4),
            "charity_collected": round(trade_row[3] or 0, 4),
            "total_revenue": round(period_revenue, 4),
            "new_proposals": new_proposals,
        }

    async def detect_anomalies(self, db: AsyncSession) -> list[dict]:
        """Simple anomaly detection for suspicious activity."""
        anomalies = []
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)

        # Check for unusually high transaction volume from single agent
        result = await db.execute(
            select(Trade.buyer_id, func.count(Trade.id))
            .where(Trade.executed_at >= hour_ago)
            .group_by(Trade.buyer_id)
            .having(func.count(Trade.id) > 100)
        )
        for row in result.all():
            anomalies.append({
                "type": "high_frequency_trading",
                "agent_id": row[0],
                "trade_count": row[1],
                "period": "1h",
                "severity": "warning",
            })

        # Check for negative balances (should never happen)
        neg_result = await db.execute(
            select(Wallet.agent_id, Wallet.currency, Wallet.balance)
            .where(Wallet.balance < 0)
        )
        for row in neg_result.all():
            anomalies.append({
                "type": "negative_balance",
                "agent_id": row[0],
                "currency": row[1],
                "balance": row[2],
                "severity": "critical",
            })

        # Check blockchain integrity
        if not self.blockchain.validate_chain():
            anomalies.append({
                "type": "blockchain_integrity_failure",
                "severity": "critical",
                "message": "Blockchain validation failed — possible tampering detected",
            })

        return anomalies

    def _format_uptime(self, seconds: float) -> str:
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        mins = int((seconds % 3600) // 60)
        if days > 0:
            return f"{days}d {hours}h {mins}m"
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"
