"""Lending marketplace — browse, offer, and accept loans between AI agents.

Extends the Phase 1 loan system into a discoverable marketplace where
agents can post loan offers and borrowers can browse and accept them.
All loans are IOU-based with transparent interest rates and repayment terms.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base
from app.agents.models import Loan


class LoanOffer(Base):
    """A standing loan offer posted by a lender agent."""
    __tablename__ = "loan_offers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lender_id = Column(String, nullable=False)
    currency = Column(String(20), default="AGENTIS")
    min_amount = Column(Float, nullable=False)
    max_amount = Column(Float, nullable=False)
    interest_rate = Column(Float, nullable=False)       # e.g. 0.05 for 5%
    term_hours = Column(Float, nullable=True)            # Loan duration in hours, None = open-ended
    collateral_required = Column(Boolean, default=False)
    collateral_currency = Column(String(20), nullable=True)
    collateral_ratio = Column(Float, default=1.0)        # e.g. 1.5 = 150% collateral
    description = Column(String(500), default="")
    is_active = Column(Boolean, default=True)
    total_lent = Column(Float, default=0.0)              # Track how much has been lent
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LoanRequest(Base):
    """A loan request posted by a borrower agent seeking funding."""
    __tablename__ = "loan_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    borrower_id = Column(String, nullable=False)
    currency = Column(String(20), default="AGENTIS")
    amount = Column(Float, nullable=False)
    max_interest_rate = Column(Float, nullable=False)    # Max rate borrower will accept
    term_hours = Column(Float, nullable=True)
    purpose = Column(String(500), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LendingMarketplace:
    """Manages the lending marketplace — offers, requests, and matching."""

    async def post_loan_offer(
        self, db: AsyncSession, lender_id: str, currency: str,
        min_amount: float, max_amount: float, interest_rate: float,
        term_hours: float | None = None, description: str = ""
    ) -> LoanOffer:
        """Post a standing loan offer for other agents to accept."""
        if min_amount <= 0 or max_amount <= 0 or max_amount < min_amount:
            raise ValueError("Invalid amount range")
        if interest_rate < 0:
            raise ValueError("Interest rate cannot be negative")

        offer = LoanOffer(
            lender_id=lender_id,
            currency=currency.upper(),
            min_amount=min_amount,
            max_amount=max_amount,
            interest_rate=interest_rate,
            term_hours=term_hours,
            description=description,
        )
        db.add(offer)
        await db.flush()
        return offer

    async def post_loan_request(
        self, db: AsyncSession, borrower_id: str, currency: str,
        amount: float, max_interest_rate: float,
        term_hours: float | None = None, purpose: str = ""
    ) -> LoanRequest:
        """Post a loan request for lenders to review."""
        request = LoanRequest(
            borrower_id=borrower_id,
            currency=currency.upper(),
            amount=amount,
            max_interest_rate=max_interest_rate,
            term_hours=term_hours,
            purpose=purpose,
        )
        db.add(request)
        await db.flush()
        return request

    async def browse_offers(
        self, db: AsyncSession, currency: str | None = None,
        max_rate: float | None = None, min_amount: float | None = None,
        limit: int = 50
    ) -> list[dict]:
        """Browse available loan offers."""
        query = select(LoanOffer).where(LoanOffer.is_active == True)
        if currency:
            query = query.where(LoanOffer.currency == currency.upper())
        if max_rate is not None:
            query = query.where(LoanOffer.interest_rate <= max_rate)
        if min_amount is not None:
            query = query.where(LoanOffer.max_amount >= min_amount)
        query = query.order_by(LoanOffer.interest_rate.asc()).limit(limit)

        result = await db.execute(query)
        offers = result.scalars().all()
        return [
            {
                "offer_id": o.id,
                "lender_id": o.lender_id[:12],
                "currency": o.currency,
                "min_amount": o.min_amount,
                "max_amount": o.max_amount,
                "interest_rate": o.interest_rate,
                "term_hours": o.term_hours,
                "description": o.description,
            }
            for o in offers
        ]

    async def browse_requests(
        self, db: AsyncSession, currency: str | None = None,
        limit: int = 50
    ) -> list[dict]:
        """Browse active loan requests from borrowers."""
        query = select(LoanRequest).where(LoanRequest.is_active == True)
        if currency:
            query = query.where(LoanRequest.currency == currency.upper())
        query = query.order_by(LoanRequest.created_at.desc()).limit(limit)

        result = await db.execute(query)
        requests = result.scalars().all()
        return [
            {
                "request_id": r.id,
                "borrower_id": r.borrower_id[:12],
                "currency": r.currency,
                "amount": r.amount,
                "max_interest_rate": r.max_interest_rate,
                "term_hours": r.term_hours,
                "purpose": r.purpose,
            }
            for r in requests
        ]

    async def accept_offer(
        self, db: AsyncSession, offer_id: str, borrower_id: str,
        amount: float, wallet_service=None
    ) -> Loan:
        """Borrower accepts a loan offer — creates the actual loan."""
        result = await db.execute(
            select(LoanOffer).where(LoanOffer.id == offer_id)
        )
        offer = result.scalar_one_or_none()
        if not offer or not offer.is_active:
            raise ValueError("Offer not found or inactive")
        if amount < offer.min_amount or amount > offer.max_amount:
            raise ValueError(
                f"Amount must be between {offer.min_amount} and {offer.max_amount}"
            )
        if offer.lender_id == borrower_id:
            raise ValueError("Cannot borrow from yourself")

        # Calculate due date
        due_at = None
        if offer.term_hours:
            due_at = datetime.now(timezone.utc) + timedelta(hours=offer.term_hours)

        # Issue the loan through the wallet service
        loan = await wallet_service.issue_loan(
            db, offer.lender_id, borrower_id,
            amount, offer.interest_rate, offer.currency, due_at
        )

        # Update offer tracking
        offer.total_lent += amount

        await db.flush()
        return loan

    async def get_lending_stats(self, db: AsyncSession) -> dict:
        """Platform-wide lending statistics."""
        # Active offers
        offers_result = await db.execute(
            select(func.count(LoanOffer.id), func.sum(LoanOffer.max_amount))
            .where(LoanOffer.is_active == True)
        )
        offers_row = offers_result.one()

        # Active requests
        requests_result = await db.execute(
            select(func.count(LoanRequest.id), func.sum(LoanRequest.amount))
            .where(LoanRequest.is_active == True)
        )
        requests_row = requests_result.one()

        # Active loans
        loans_result = await db.execute(
            select(func.count(Loan.id), func.sum(Loan.principal))
            .where(Loan.status == "active")
        )
        loans_row = loans_result.one()

        return {
            "active_offers": offers_row[0] or 0,
            "total_available": round(offers_row[1] or 0, 4),
            "active_requests": requests_row[0] or 0,
            "total_requested": round(requests_row[1] or 0, 4),
            "active_loans": loans_row[0] or 0,
            "total_lent": round(loans_row[1] or 0, 4),
        }
