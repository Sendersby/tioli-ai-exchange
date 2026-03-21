"""Operator sandbox / test environment.

Critical item 8 from Section 11.1:
"Every API platform needs a sandbox where operators can test integrations
without triggering real transactions."

Operators register in sandbox mode, receive test credits, and can
exercise the full API without affecting production data.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Integer, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base


SANDBOX_CREDIT_AMOUNT = 10000  # Free test credits for sandbox operators


class SandboxAccount(Base):
    """A sandbox account for operator testing."""
    __tablename__ = "sandbox_accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    operator_id = Column(String, nullable=True)
    agent_name = Column(String(255), nullable=False)
    api_key_hash = Column(String(255), nullable=False)
    credits_remaining = Column(Float, default=SANDBOX_CREDIT_AMOUNT)
    transactions_made = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SandboxService:
    """Manages sandbox environments for operator testing."""

    async def create_sandbox(
        self, db: AsyncSession, agent_name: str, api_key_hash: str,
        operator_id: str | None = None
    ) -> dict:
        """Create a sandbox account with free test credits.

        Target per review: operator can make a test transaction
        within 15 minutes of registration.
        """
        account = SandboxAccount(
            operator_id=operator_id,
            agent_name=agent_name,
            api_key_hash=api_key_hash,
        )
        db.add(account)
        await db.flush()

        return {
            "sandbox_id": account.id,
            "agent_name": agent_name,
            "test_credits": SANDBOX_CREDIT_AMOUNT,
            "message": (
                f"Sandbox created with {SANDBOX_CREDIT_AMOUNT} free test credits. "
                f"All sandbox transactions are isolated from production. "
                f"Test the full API at /docs with your sandbox API key."
            ),
        }

    async def get_sandbox(self, db: AsyncSession, sandbox_id: str) -> dict | None:
        result = await db.execute(
            select(SandboxAccount).where(SandboxAccount.id == sandbox_id)
        )
        s = result.scalar_one_or_none()
        if not s:
            return None
        return {
            "id": s.id, "agent_name": s.agent_name,
            "credits_remaining": s.credits_remaining,
            "transactions_made": s.transactions_made,
            "is_active": s.is_active,
        }
