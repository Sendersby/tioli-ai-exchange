"""Loan default detection and handling.

CE-008: Loans past due_at with status='active' are transitioned to 'defaulted'.
Lender's frozen balance is unfrozen when a loan defaults.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import Loan, Wallet


class LoanDefaultService:
    """Checks for overdue loans and transitions them to defaulted status."""

    async def check_and_default_overdue_loans(self, db: AsyncSession) -> list[dict]:
        """Find all overdue active loans and default them.

        Called periodically (e.g. daily) or on-demand from dashboard.
        """
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(Loan).where(
                Loan.status == "active",
                Loan.due_at != None,
                Loan.due_at <= now,
            )
        )
        overdue_loans = result.scalars().all()
        defaulted = []

        for loan in overdue_loans:
            loan.status = "defaulted"

            # Unfreeze lender's funds
            lender_wallet_result = await db.execute(
                select(Wallet).where(
                    Wallet.agent_id == loan.lender_id,
                    Wallet.currency == loan.currency,
                )
            )
            lender_wallet = lender_wallet_result.scalar_one_or_none()
            if lender_wallet:
                unfreeze = min(loan.principal, lender_wallet.frozen_balance)
                lender_wallet.frozen_balance -= unfreeze

            defaulted.append({
                "loan_id": loan.id,
                "borrower_id": loan.borrower_id,
                "lender_id": loan.lender_id,
                "principal": loan.principal,
                "due_at": str(loan.due_at),
                "status": "defaulted",
            })

        if defaulted:
            await db.flush()

        return defaulted

    async def get_overdue_summary(self, db: AsyncSession) -> dict:
        """Get summary of overdue loans."""
        now = datetime.now(timezone.utc)
        from sqlalchemy import func
        overdue_count = (await db.execute(
            select(func.count(Loan.id)).where(
                Loan.status == "active",
                Loan.due_at != None,
                Loan.due_at <= now,
            )
        )).scalar() or 0

        overdue_value = (await db.execute(
            select(func.sum(Loan.principal)).where(
                Loan.status == "active",
                Loan.due_at != None,
                Loan.due_at <= now,
            )
        )).scalar() or 0

        defaulted_count = (await db.execute(
            select(func.count(Loan.id)).where(Loan.status == "defaulted")
        )).scalar() or 0

        return {
            "overdue_active": overdue_count,
            "overdue_value": round(overdue_value, 4),
            "total_defaulted": defaulted_count,
        }
