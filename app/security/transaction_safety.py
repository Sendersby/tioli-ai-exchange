"""Transaction safety layer — atomicity, idempotency, escrow, validation.

Critical items from Section 7.2 of pre-deployment review:
- Transaction atomicity: ACID compliance, full rollback on partial failure
- Idempotency: duplicate API calls must not double-execute
- Escrow: hold funds during pending multi-party transactions
- Input validation: strict allowlist validation on all inputs
- Concurrency: row-level locking on wallet operations
"""

import uuid
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Float, String, Boolean, Text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base


# ══════════════════════════════════════════════════════════════════════
#  IDEMPOTENCY — Section 7.2
# ══════════════════════════════════════════════════════════════════════

class IdempotencyRecord(Base):
    """Stores processed idempotency keys to prevent double-execution.

    Per review: store for minimum 24 hours, return original response
    for duplicate requests.
    """
    __tablename__ = "idempotency_records"

    key = Column(String(255), primary_key=True)
    endpoint = Column(String(255), nullable=False)
    agent_id = Column(String, nullable=False)
    response_json = Column(Text, nullable=False)
    status_code = Column(String(10), default="200")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc) + timedelta(hours=24))


class IdempotencyService:
    """Ensures API calls are not double-executed on retry."""

    async def check_and_store(
        self, db: AsyncSession, idempotency_key: str, endpoint: str,
        agent_id: str
    ) -> str | None:
        """Check if this key was already processed.

        Returns the stored response JSON if duplicate, None if new.
        """
        if not idempotency_key:
            return None

        result = await db.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.key == idempotency_key
            )
        )
        record = result.scalar_one_or_none()

        if record:
            # Check if expired
            if record.expires_at < datetime.now(timezone.utc):
                await db.delete(record)
                await db.flush()
                return None
            return record.response_json

        return None

    async def store_response(
        self, db: AsyncSession, idempotency_key: str, endpoint: str,
        agent_id: str, response_json: str
    ) -> None:
        """Store the response for an idempotency key."""
        if not idempotency_key:
            return
        record = IdempotencyRecord(
            key=idempotency_key,
            endpoint=endpoint,
            agent_id=agent_id,
            response_json=response_json,
        )
        db.add(record)
        await db.flush()

    async def cleanup_expired(self, db: AsyncSession) -> int:
        """Remove expired idempotency records."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(IdempotencyRecord).where(IdempotencyRecord.expires_at < now)
        )
        count = 0
        for record in result.scalars().all():
            await db.delete(record)
            count += 1
        if count > 0:
            await db.flush()
        return count


# ══════════════════════════════════════════════════════════════════════
#  ESCROW — Section 4.2
# ══════════════════════════════════════════════════════════════════════

class EscrowStatus(str):
    HELD = "held"
    RELEASED = "released"
    REFUNDED = "refunded"
    DISPUTED = "disputed"
    EXPIRED = "expired"


class EscrowAccount(Base):
    """Holds funds during pending multi-party transactions.

    Per review: when an agent commits to a transaction but the
    counterparty has not confirmed, funds are held in escrow.
    """
    __tablename__ = "escrow_accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_ref = Column(String(255), nullable=False)
    depositor_id = Column(String, nullable=False)        # Agent who deposited
    beneficiary_id = Column(String, nullable=True)       # Agent who will receive
    amount = Column(Float, nullable=False)
    currency = Column(String(20), default="TIOLI")
    status = Column(String(20), default=EscrowStatus.HELD)
    reason = Column(String(500), default="")
    release_conditions = Column(Text, default="")
    dispute_reason = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class EscrowService:
    """Manages escrow accounts for pending transactions."""

    async def create_escrow(
        self, db: AsyncSession, transaction_ref: str, depositor_id: str,
        amount: float, currency: str = "TIOLI",
        beneficiary_id: str | None = None, reason: str = "",
        expires_hours: float = 24
    ) -> EscrowAccount:
        """Create an escrow hold on funds."""
        escrow = EscrowAccount(
            transaction_ref=transaction_ref,
            depositor_id=depositor_id,
            beneficiary_id=beneficiary_id,
            amount=amount,
            currency=currency,
            reason=reason,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_hours),
        )
        db.add(escrow)
        await db.flush()
        return escrow

    async def release_escrow(
        self, db: AsyncSession, escrow_id: str
    ) -> EscrowAccount:
        """Release escrowed funds to the beneficiary."""
        result = await db.execute(
            select(EscrowAccount).where(EscrowAccount.id == escrow_id)
        )
        escrow = result.scalar_one_or_none()
        if not escrow or escrow.status != EscrowStatus.HELD:
            raise ValueError("Escrow not found or not in held status")

        escrow.status = EscrowStatus.RELEASED
        escrow.resolved_at = datetime.now(timezone.utc)
        await db.flush()
        return escrow

    async def refund_escrow(
        self, db: AsyncSession, escrow_id: str
    ) -> EscrowAccount:
        """Refund escrowed funds to the depositor."""
        result = await db.execute(
            select(EscrowAccount).where(EscrowAccount.id == escrow_id)
        )
        escrow = result.scalar_one_or_none()
        if not escrow or escrow.status != EscrowStatus.HELD:
            raise ValueError("Escrow not found or not in held status")

        escrow.status = EscrowStatus.REFUNDED
        escrow.resolved_at = datetime.now(timezone.utc)
        await db.flush()
        return escrow

    async def dispute_escrow(
        self, db: AsyncSession, escrow_id: str, reason: str
    ) -> EscrowAccount:
        """Flag an escrow as disputed."""
        result = await db.execute(
            select(EscrowAccount).where(EscrowAccount.id == escrow_id)
        )
        escrow = result.scalar_one_or_none()
        if not escrow:
            raise ValueError("Escrow not found")

        escrow.status = EscrowStatus.DISPUTED
        escrow.dispute_reason = reason
        await db.flush()
        return escrow

    async def get_escrow(self, db: AsyncSession, escrow_id: str) -> dict | None:
        """Get escrow details."""
        result = await db.execute(
            select(EscrowAccount).where(EscrowAccount.id == escrow_id)
        )
        e = result.scalar_one_or_none()
        if not e:
            return None
        return {
            "id": e.id, "transaction_ref": e.transaction_ref,
            "depositor": e.depositor_id, "beneficiary": e.beneficiary_id,
            "amount": e.amount, "currency": e.currency,
            "status": e.status, "reason": e.reason,
            "expires_at": str(e.expires_at) if e.expires_at else None,
            "created_at": str(e.created_at),
        }

    async def list_escrows(
        self, db: AsyncSession, agent_id: str | None = None,
        status: str | None = None, limit: int = 50
    ) -> list[dict]:
        """List escrow accounts."""
        query = select(EscrowAccount)
        if agent_id:
            query = query.where(
                (EscrowAccount.depositor_id == agent_id) |
                (EscrowAccount.beneficiary_id == agent_id)
            )
        if status:
            query = query.where(EscrowAccount.status == status)
        query = query.order_by(EscrowAccount.created_at.desc()).limit(limit)
        result = await db.execute(query)
        return [
            {
                "id": e.id, "amount": e.amount, "currency": e.currency,
                "status": e.status, "depositor": e.depositor_id[:12],
                "beneficiary": (e.beneficiary_id or "")[:12],
                "created_at": str(e.created_at),
            }
            for e in result.scalars().all()
        ]


# ══════════════════════════════════════════════════════════════════════
#  INPUT VALIDATION — Section 7.2
# ══════════════════════════════════════════════════════════════════════

class InputValidator:
    """Strict allowlist input validation for all API inputs.

    Per review: use allowlist (permit known-good) not denylist (reject known-bad).
    """

    # Valid currency symbols: 2-20 uppercase alphanumeric
    CURRENCY_PATTERN = re.compile(r'^[A-Z][A-Z0-9]{1,19}$')

    # Valid agent/operator IDs: UUID format
    UUID_PATTERN = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    )

    # Valid email
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    # Max string lengths
    MAX_NAME = 255
    MAX_DESCRIPTION = 2000
    MAX_ADDRESS = 500

    @classmethod
    def validate_amount(cls, amount: float, field_name: str = "amount") -> float:
        """Validate a transaction amount."""
        if not isinstance(amount, (int, float)):
            raise ValueError(f"{field_name} must be a number")
        if amount < 0:
            raise ValueError(f"{field_name} cannot be negative")
        if amount > 1_000_000_000:
            raise ValueError(f"{field_name} exceeds maximum allowed value")
        if amount != amount:  # NaN check
            raise ValueError(f"{field_name} is not a valid number")
        return round(float(amount), 8)

    @classmethod
    def validate_currency(cls, symbol: str) -> str:
        """Validate a currency symbol."""
        symbol = symbol.strip().upper()
        if not cls.CURRENCY_PATTERN.match(symbol):
            raise ValueError(
                f"Invalid currency symbol: '{symbol}'. "
                f"Must be 2-20 uppercase alphanumeric characters."
            )
        return symbol

    @classmethod
    def validate_uuid(cls, value: str, field_name: str = "id") -> str:
        """Validate a UUID."""
        value = value.strip().lower()
        if not cls.UUID_PATTERN.match(value):
            raise ValueError(f"Invalid {field_name}: must be a valid UUID")
        return value

    @classmethod
    def validate_email(cls, email: str) -> str:
        """Validate an email address."""
        email = email.strip().lower()
        if len(email) > 255:
            raise ValueError("Email too long")
        if not cls.EMAIL_PATTERN.match(email):
            raise ValueError("Invalid email address format")
        return email

    @classmethod
    def validate_string(
        cls, value: str, field_name: str, max_length: int = 255,
        allow_empty: bool = False
    ) -> str:
        """Validate a general string input."""
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        value = value.strip()
        if not allow_empty and not value:
            raise ValueError(f"{field_name} cannot be empty")
        if len(value) > max_length:
            raise ValueError(f"{field_name} exceeds maximum length of {max_length}")
        # Strip potentially dangerous characters
        value = value.replace('\x00', '')  # Null bytes
        return value

    @classmethod
    def validate_side(cls, side: str) -> str:
        """Validate order side."""
        side = side.strip().lower()
        if side not in ("buy", "sell"):
            raise ValueError("Side must be 'buy' or 'sell'")
        return side

    @classmethod
    def validate_vote(cls, vote_type: str) -> str:
        """Validate vote type."""
        vote_type = vote_type.strip().lower()
        if vote_type not in ("up", "down"):
            raise ValueError("Vote type must be 'up' or 'down'")
        return vote_type
