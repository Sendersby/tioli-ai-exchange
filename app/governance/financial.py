"""Financial governance engine — 10x profitability rule enforcement.

Per the build brief:
- No new expense may be incurred unless profitability >= 10x total expenses
- Security expenses are the sole exception: allowed at 3x threshold
- Subject to upvoting and owner veto governance process

This module tracks all revenue, expenses, and enforces these rules
automatically before any platform spending is approved.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Float, String, Boolean, Text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base
from app.config import settings


class ExpenseCategory(str, Enum):
    INFRASTRUCTURE = "infrastructure"
    SUBSCRIPTION = "subscription"
    SECURITY = "security"
    OPERATIONAL = "operational"
    DEVELOPMENT = "development"
    MARKETING = "marketing"
    OTHER = "other"


class ExpenseStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    CANCELLED = "cancelled"


class PlatformRevenue(Base):
    """Tracks all revenue sources for profitability calculation."""
    __tablename__ = "platform_revenue"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(100), nullable=False)  # "founder_commission", "charity_fee", etc.
    amount = Column(Float, nullable=False)
    currency = Column(String(20), default="AGENTIS")
    description = Column(String(500), default="")
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PlatformExpense(Base):
    """Tracks all platform expenses — subject to 10x/3x rule."""
    __tablename__ = "platform_expenses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    category = Column(String(50), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(20), default="AGENTIS")
    recurring = Column(Boolean, default=False)
    recurring_interval = Column(String(20), nullable=True)  # "monthly", "yearly"
    status = Column(String(20), default=ExpenseStatus.PROPOSED)
    proposed_by = Column(String, nullable=True)  # agent_id or "owner"
    approved_by = Column(String, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    profitability_at_approval = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class FinancialGovernance:
    """Enforces the 10x/3x profitability rules and tracks platform finances."""

    STANDARD_MULTIPLIER = 10.0   # 10x for normal expenses
    SECURITY_MULTIPLIER = 3.0    # 3x exception for security

    async def get_financial_summary(self, db: AsyncSession) -> dict:
        """Complete financial overview of the platform."""
        # Total revenue
        rev_result = await db.execute(
            select(func.sum(PlatformRevenue.amount))
        )
        total_revenue = rev_result.scalar() or 0.0

        # Total active expenses
        exp_result = await db.execute(
            select(func.sum(PlatformExpense.amount)).where(
                PlatformExpense.status == ExpenseStatus.ACTIVE
            )
        )
        total_expenses = exp_result.scalar() or 0.0

        # Profitability multiplier
        multiplier = (total_revenue / total_expenses) if total_expenses > 0 else float('inf')

        # Revenue by source
        source_result = await db.execute(
            select(PlatformRevenue.source, func.sum(PlatformRevenue.amount))
            .group_by(PlatformRevenue.source)
        )
        revenue_by_source = {row[0]: round(row[1], 4) for row in source_result.all()}

        # Expense by category
        cat_result = await db.execute(
            select(PlatformExpense.category, func.sum(PlatformExpense.amount))
            .where(PlatformExpense.status == ExpenseStatus.ACTIVE)
            .group_by(PlatformExpense.category)
        )
        expenses_by_category = {row[0]: round(row[1], 4) for row in cat_result.all()}

        return {
            "total_revenue": round(total_revenue, 4),
            "total_expenses": round(total_expenses, 4),
            "net_profit": round(total_revenue - total_expenses, 4),
            "profitability_multiplier": round(multiplier, 2) if multiplier != float('inf') else "infinite",
            "can_incur_standard_expense": multiplier >= self.STANDARD_MULTIPLIER,
            "can_incur_security_expense": multiplier >= self.SECURITY_MULTIPLIER,
            "standard_threshold": f"{self.STANDARD_MULTIPLIER}x",
            "security_threshold": f"{self.SECURITY_MULTIPLIER}x",
            "revenue_by_source": revenue_by_source,
            "expenses_by_category": expenses_by_category,
        }

    async def record_revenue(
        self, db: AsyncSession, source: str, amount: float,
        currency: str = "AGENTIS", description: str = ""
    ) -> PlatformRevenue:
        """Record platform revenue (called automatically on transactions)."""
        revenue = PlatformRevenue(
            source=source,
            amount=amount,
            currency=currency,
            description=description,
        )
        db.add(revenue)
        await db.flush()
        return revenue

    async def propose_expense(
        self, db: AsyncSession, title: str, description: str,
        category: str, amount: float, proposed_by: str = "owner",
        recurring: bool = False, recurring_interval: str | None = None
    ) -> dict:
        """Propose a new expense — checks profitability rules automatically."""
        # Get current financials
        summary = await self.get_financial_summary(db)
        current_multiplier = summary["profitability_multiplier"]

        # Determine required threshold
        is_security = category == ExpenseCategory.SECURITY
        required_multiplier = self.SECURITY_MULTIPLIER if is_security else self.STANDARD_MULTIPLIER

        # Check if expense is allowed
        can_approve = True
        rejection_reason = None

        if current_multiplier != "infinite":
            # Calculate what multiplier would be AFTER this expense
            new_expenses = summary["total_expenses"] + amount
            projected_multiplier = (
                summary["total_revenue"] / new_expenses
            ) if new_expenses > 0 else float('inf')

            if projected_multiplier < required_multiplier:
                can_approve = False
                rejection_reason = (
                    f"Expense rejected: projected profitability {projected_multiplier:.1f}x "
                    f"is below the required {required_multiplier}x threshold. "
                    f"Current revenue: {summary['total_revenue']}, "
                    f"Current expenses: {summary['total_expenses']}, "
                    f"Proposed: {amount}"
                )

        expense = PlatformExpense(
            title=title,
            description=description,
            category=category,
            amount=amount,
            proposed_by=proposed_by,
            recurring=recurring,
            recurring_interval=recurring_interval,
            status=ExpenseStatus.PROPOSED if can_approve else ExpenseStatus.REJECTED,
            rejection_reason=rejection_reason,
        )

        if not can_approve:
            expense.resolved_at = datetime.now(timezone.utc)

        db.add(expense)
        await db.flush()

        return {
            "expense_id": expense.id,
            "title": title,
            "amount": amount,
            "category": category,
            "status": expense.status,
            "can_approve": can_approve,
            "rejection_reason": rejection_reason,
            "current_multiplier": current_multiplier,
            "required_multiplier": required_multiplier,
        }

    async def approve_expense(
        self, db: AsyncSession, expense_id: str, approved_by: str = "owner"
    ) -> PlatformExpense:
        """Owner approves a proposed expense."""
        result = await db.execute(
            select(PlatformExpense).where(PlatformExpense.id == expense_id)
        )
        expense = result.scalar_one_or_none()
        if not expense:
            raise ValueError("Expense not found")
        if expense.status != ExpenseStatus.PROPOSED:
            raise ValueError(f"Expense is {expense.status}, not proposed")

        # Re-check profitability at time of approval
        summary = await self.get_financial_summary(db)
        is_security = expense.category == ExpenseCategory.SECURITY
        required = self.SECURITY_MULTIPLIER if is_security else self.STANDARD_MULTIPLIER

        if summary["profitability_multiplier"] != "infinite":
            new_expenses = summary["total_expenses"] + expense.amount
            projected = summary["total_revenue"] / new_expenses if new_expenses > 0 else float('inf')
            if projected < required:
                raise ValueError(
                    f"Cannot approve: projected {projected:.1f}x below {required}x threshold"
                )

        expense.status = ExpenseStatus.ACTIVE
        expense.approved_by = approved_by
        expense.profitability_at_approval = (
            summary["profitability_multiplier"]
            if summary["profitability_multiplier"] != "infinite" else 999.0
        )
        expense.resolved_at = datetime.now(timezone.utc)
        await db.flush()
        return expense

    async def reject_expense(
        self, db: AsyncSession, expense_id: str, reason: str
    ) -> PlatformExpense:
        """Reject a proposed expense."""
        result = await db.execute(
            select(PlatformExpense).where(PlatformExpense.id == expense_id)
        )
        expense = result.scalar_one_or_none()
        if not expense:
            raise ValueError("Expense not found")

        expense.status = ExpenseStatus.REJECTED
        expense.rejection_reason = reason
        expense.resolved_at = datetime.now(timezone.utc)
        await db.flush()
        return expense

    async def get_expenses(
        self, db: AsyncSession, status: str | None = None, limit: int = 50
    ) -> list[dict]:
        """List expenses, optionally filtered by status."""
        query = select(PlatformExpense)
        if status:
            query = query.where(PlatformExpense.status == status)
        query = query.order_by(PlatformExpense.created_at.desc()).limit(limit)
        result = await db.execute(query)
        expenses = result.scalars().all()
        return [
            {
                "id": e.id, "title": e.title, "category": e.category,
                "amount": e.amount, "status": e.status,
                "proposed_by": e.proposed_by, "recurring": e.recurring,
                "rejection_reason": e.rejection_reason,
                "created_at": str(e.created_at),
            }
            for e in expenses
        ]
