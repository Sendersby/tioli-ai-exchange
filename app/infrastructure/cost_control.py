"""Infrastructure Cost Control — Master On/Off Switch & Budget Management.

Provides:
- Master kill switch: shut down all services with one click
- Budget limits with pre-warning alerts at configurable thresholds
- Real-time cost tracking against monthly allowance
- DigitalOcean API integration for actual usage monitoring
- Activate/deactivate with a single API call
"""

import uuid
import httpx
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, Float, String, Boolean, Integer, Text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base


class InfrastructureBudget(Base):
    """Monthly infrastructure budget configuration."""
    __tablename__ = "infrastructure_budget"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    monthly_limit_usd = Column(Float, nullable=False, default=20.0)
    warning_threshold_pct = Column(Float, nullable=False, default=70.0)  # Alert at 70%
    critical_threshold_pct = Column(Float, nullable=False, default=90.0)  # Alert at 90%
    auto_shutdown_enabled = Column(Boolean, default=True)  # Kill switch at 100%
    current_month_spend_usd = Column(Float, default=0.0)
    is_current = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PlatformPowerState(Base):
    """Master on/off state of the platform infrastructure."""
    __tablename__ = "platform_power_state"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    is_active = Column(Boolean, nullable=False, default=True)
    shutdown_reason = Column(Text, nullable=True)
    shutdown_by = Column(String(50), nullable=True)  # "owner", "auto_budget", "manual"
    last_activated_at = Column(DateTime, nullable=True)
    last_shutdown_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CostEvent(Base):
    """Log of all cost-related events (alerts, shutdowns, activations)."""
    __tablename__ = "cost_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(50), nullable=False)
    # Types: budget_warning, budget_critical, auto_shutdown,
    #        manual_shutdown, manual_activation, budget_updated
    description = Column(Text, nullable=False)
    spend_at_event = Column(Float, default=0.0)
    limit_at_event = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CostControlService:
    """Master cost control with kill switch functionality."""

    # ── POWER STATE (Master Switch) ──────────────────────────────

    async def get_power_state(self, db: AsyncSession) -> dict:
        """Get current platform power state."""
        result = await db.execute(select(PlatformPowerState).limit(1))
        state = result.scalar_one_or_none()
        if not state:
            state = PlatformPowerState(is_active=True)
            db.add(state)
            await db.flush()
        return {
            "is_active": state.is_active,
            "shutdown_reason": state.shutdown_reason,
            "shutdown_by": state.shutdown_by,
            "last_activated": str(state.last_activated_at) if state.last_activated_at else None,
            "last_shutdown": str(state.last_shutdown_at) if state.last_shutdown_at else None,
        }

    async def emergency_shutdown(
        self, db: AsyncSession, reason: str = "Manual shutdown",
        shutdown_by: str = "owner"
    ) -> dict:
        """MASTER KILL SWITCH — shuts down all platform services immediately.

        This is the single-click emergency stop. When activated:
        - All API endpoints return 503 Service Unavailable
        - No new transactions are processed
        - No new agents can register
        - Existing data is preserved (nothing is deleted)
        - Platform can be reactivated with a single click
        """
        result = await db.execute(select(PlatformPowerState).limit(1))
        state = result.scalar_one_or_none()
        if not state:
            state = PlatformPowerState()
            db.add(state)

        state.is_active = False
        state.shutdown_reason = reason
        state.shutdown_by = shutdown_by
        state.last_shutdown_at = datetime.now(timezone.utc)
        state.updated_at = datetime.now(timezone.utc)

        # Log the event
        event = CostEvent(
            event_type="manual_shutdown" if shutdown_by == "owner" else "auto_shutdown",
            description=f"Platform shutdown: {reason}",
        )
        db.add(event)
        await db.flush()

        return {
            "status": "SHUTDOWN",
            "reason": reason,
            "message": "Platform is now OFF. All services suspended. Data preserved. Use /activate to restart.",
        }

    async def activate(self, db: AsyncSession) -> dict:
        """ACTIVATE — brings the platform back online with one click."""
        result = await db.execute(select(PlatformPowerState).limit(1))
        state = result.scalar_one_or_none()
        if not state:
            state = PlatformPowerState()
            db.add(state)

        state.is_active = True
        state.shutdown_reason = None
        state.shutdown_by = None
        state.last_activated_at = datetime.now(timezone.utc)
        state.updated_at = datetime.now(timezone.utc)

        event = CostEvent(
            event_type="manual_activation",
            description="Platform activated by owner",
        )
        db.add(event)
        await db.flush()

        return {
            "status": "ACTIVE",
            "message": "Platform is now ON. All services operational.",
        }

    # ── BUDGET MANAGEMENT ────────────────────────────────────────

    async def set_budget(
        self, db: AsyncSession, monthly_limit_usd: float,
        warning_pct: float = 70.0, critical_pct: float = 90.0,
        auto_shutdown: bool = True
    ) -> dict:
        """Set the monthly infrastructure budget."""
        result = await db.execute(
            select(InfrastructureBudget).where(InfrastructureBudget.is_current == True)
        )
        budget = result.scalar_one_or_none()
        if budget:
            budget.monthly_limit_usd = monthly_limit_usd
            budget.warning_threshold_pct = warning_pct
            budget.critical_threshold_pct = critical_pct
            budget.auto_shutdown_enabled = auto_shutdown
            budget.updated_at = datetime.now(timezone.utc)
        else:
            budget = InfrastructureBudget(
                monthly_limit_usd=monthly_limit_usd,
                warning_threshold_pct=warning_pct,
                critical_threshold_pct=critical_pct,
                auto_shutdown_enabled=auto_shutdown,
            )
            db.add(budget)

        event = CostEvent(
            event_type="budget_updated",
            description=f"Budget set to ${monthly_limit_usd}/month. Warning: {warning_pct}%, Critical: {critical_pct}%, Auto-shutdown: {auto_shutdown}",
            limit_at_event=monthly_limit_usd,
        )
        db.add(event)
        await db.flush()

        return {
            "monthly_limit_usd": monthly_limit_usd,
            "warning_at": f"${monthly_limit_usd * warning_pct / 100:.2f}",
            "critical_at": f"${monthly_limit_usd * critical_pct / 100:.2f}",
            "auto_shutdown": auto_shutdown,
        }

    async def get_budget_status(self, db: AsyncSession) -> dict:
        """Get current budget status with alerts."""
        result = await db.execute(
            select(InfrastructureBudget).where(InfrastructureBudget.is_current == True)
        )
        budget = result.scalar_one_or_none()

        if not budget:
            return {
                "configured": False,
                "message": "No budget set. Use /api/infra/budget to configure.",
            }

        spend = budget.current_month_spend_usd
        limit = budget.monthly_limit_usd
        pct_used = (spend / limit * 100) if limit > 0 else 0
        remaining = max(0, limit - spend)

        # Determine alert level
        alert = "OK"
        if pct_used >= 100:
            alert = "OVER_BUDGET"
        elif pct_used >= budget.critical_threshold_pct:
            alert = "CRITICAL"
        elif pct_used >= budget.warning_threshold_pct:
            alert = "WARNING"

        return {
            "configured": True,
            "monthly_limit_usd": limit,
            "current_spend_usd": round(spend, 2),
            "remaining_usd": round(remaining, 2),
            "pct_used": round(pct_used, 1),
            "alert_level": alert,
            "warning_threshold": budget.warning_threshold_pct,
            "critical_threshold": budget.critical_threshold_pct,
            "auto_shutdown_enabled": budget.auto_shutdown_enabled,
            "days_in_month": 30,
            "daily_burn_rate": round(spend / max(datetime.now().day, 1), 2),
            "projected_month_end": round(spend / max(datetime.now().day, 1) * 30, 2),
        }

    async def record_spend(
        self, db: AsyncSession, amount_usd: float, description: str = ""
    ) -> dict:
        """Record infrastructure spending and check budget."""
        result = await db.execute(
            select(InfrastructureBudget).where(InfrastructureBudget.is_current == True)
        )
        budget = result.scalar_one_or_none()
        if not budget:
            return {"recorded": False, "message": "No budget configured"}

        budget.current_month_spend_usd += amount_usd
        budget.updated_at = datetime.now(timezone.utc)

        spend = budget.current_month_spend_usd
        limit = budget.monthly_limit_usd
        pct = spend / limit * 100 if limit > 0 else 0

        alerts = []

        # Check warning threshold
        if pct >= budget.warning_threshold_pct and pct < budget.critical_threshold_pct:
            alerts.append("WARNING")
            event = CostEvent(
                event_type="budget_warning",
                description=f"Spend ${spend:.2f} reached {pct:.0f}% of ${limit:.2f} limit",
                spend_at_event=spend, limit_at_event=limit,
            )
            db.add(event)

        # Check critical threshold
        if pct >= budget.critical_threshold_pct and pct < 100:
            alerts.append("CRITICAL")
            event = CostEvent(
                event_type="budget_critical",
                description=f"CRITICAL: Spend ${spend:.2f} at {pct:.0f}% of ${limit:.2f} limit",
                spend_at_event=spend, limit_at_event=limit,
            )
            db.add(event)

        # Check auto-shutdown
        if pct >= 100 and budget.auto_shutdown_enabled:
            alerts.append("AUTO_SHUTDOWN")
            await self.emergency_shutdown(
                db, f"Auto-shutdown: budget exceeded (${spend:.2f} / ${limit:.2f})",
                shutdown_by="auto_budget"
            )

        await db.flush()
        return {
            "recorded": True,
            "current_spend": round(spend, 2),
            "limit": limit,
            "pct_used": round(pct, 1),
            "alerts": alerts,
        }

    async def reset_monthly_spend(self, db: AsyncSession) -> dict:
        """Reset monthly spend counter (called at month start)."""
        result = await db.execute(
            select(InfrastructureBudget).where(InfrastructureBudget.is_current == True)
        )
        budget = result.scalar_one_or_none()
        if budget:
            budget.current_month_spend_usd = 0.0
            budget.updated_at = datetime.now(timezone.utc)
            await db.flush()
        return {"reset": True, "current_spend": 0.0}

    # ── DIGITALOCEAN INTEGRATION ─────────────────────────────────

    async def fetch_digitalocean_balance(self, api_token: str | None = None) -> dict:
        """Fetch current DigitalOcean account balance.

        Requires DO API token. Returns balance info directly from DO API.
        """
        if not api_token:
            return {
                "available": False,
                "message": "Set DIGITALOCEAN_API_TOKEN to enable live balance tracking",
            }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.digitalocean.com/v2/customers/my/balance",
                    headers={"Authorization": f"Bearer {api_token}"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "available": True,
                        "month_to_date_balance": data.get("month_to_date_balance"),
                        "account_balance": data.get("account_balance"),
                        "month_to_date_usage": data.get("month_to_date_usage"),
                        "generated_at": data.get("generated_at"),
                    }
                return {"available": False, "error": f"DO API returned {resp.status_code}"}
        except Exception as e:
            return {"available": False, "error": str(e)}

    async def fetch_digitalocean_droplets(self, api_token: str | None = None) -> list[dict]:
        """List active DigitalOcean droplets with costs."""
        if not api_token:
            return []

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.digitalocean.com/v2/droplets",
                    headers={"Authorization": f"Bearer {api_token}"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    droplets = resp.json().get("droplets", [])
                    return [
                        {
                            "id": d["id"],
                            "name": d["name"],
                            "status": d["status"],
                            "size": d["size"]["slug"],
                            "monthly_cost": float(d["size"]["price_monthly"]),
                            "region": d["region"]["slug"],
                            "ip": d["networks"]["v4"][0]["ip_address"] if d["networks"]["v4"] else None,
                        }
                        for d in droplets
                    ]
                return []
        except Exception:
            return []

    async def shutdown_digitalocean_droplet(
        self, droplet_id: int, api_token: str
    ) -> dict:
        """Power off a specific DigitalOcean droplet."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.digitalocean.com/v2/droplets/{droplet_id}/actions",
                    headers={"Authorization": f"Bearer {api_token}"},
                    json={"type": "shutdown"},
                    timeout=10,
                )
                return {"success": resp.status_code in (200, 201), "status_code": resp.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def poweron_digitalocean_droplet(
        self, droplet_id: int, api_token: str
    ) -> dict:
        """Power on a specific DigitalOcean droplet."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.digitalocean.com/v2/droplets/{droplet_id}/actions",
                    headers={"Authorization": f"Bearer {api_token}"},
                    json={"type": "power_on"},
                    timeout=10,
                )
                return {"success": resp.status_code in (200, 201), "status_code": resp.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── EVENT LOG ────────────────────────────────────────────────

    async def get_cost_events(self, db: AsyncSession, limit: int = 50) -> list[dict]:
        """Get cost event history."""
        result = await db.execute(
            select(CostEvent).order_by(CostEvent.created_at.desc()).limit(limit)
        )
        return [
            {
                "type": e.event_type, "description": e.description,
                "spend": e.spend_at_event, "limit": e.limit_at_event,
                "created_at": str(e.created_at),
            }
            for e in result.scalars().all()
        ]
