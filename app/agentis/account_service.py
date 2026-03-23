"""Agentis Core Banking Accounts — Service Layer (Module 2).

Account opening, deposits, withdrawals, transfers, interest calculation,
statement generation. Integrates with blockchain, commission engine, and
compliance engine.
"""

import uuid
from datetime import datetime, date, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentis.account_models import (
    AgentisAccount,
    AgentisAccountTransaction,
    AgentisInterestAccrual,
)
from app.agentis.member_models import AgentisMember


# Account product configuration
ACCOUNT_PRODUCTS = {
    "S": {
        "name": "Share Account",
        "min_opening_balance": 100.0,
        "interest_rate_pa": 0.0,  # Earns patronage dividend instead
        "monthly_fee": 0.0,
        "max_withdrawals_month": None,  # Non-withdrawable while member
        "notice_days": 0,
    },
    "C": {
        "name": "Call Account",
        "min_opening_balance": 50.0,
        "interest_rate_pa": 0.005,  # 0.5% base (tiered)
        "monthly_fee": 15.0,
        "max_withdrawals_month": None,  # Unlimited
        "notice_days": 0,
    },
    "SA": {
        "name": "Savings Account",
        "min_opening_balance": 200.0,
        "interest_rate_pa": 0.03,  # 3% base (tiered)
        "monthly_fee": 0.0,
        "max_withdrawals_month": 4,
        "notice_days": 0,
    },
    # Phase 2 products (defined for completeness, gated by feature flags)
    "N": {"name": "Notice Account", "min_opening_balance": 1000.0,
           "interest_rate_pa": 0.045, "monthly_fee": 0.0,
           "max_withdrawals_month": None, "notice_days": 32},
    "FD": {"name": "Fixed Deposit", "min_opening_balance": 5000.0,
            "interest_rate_pa": 0.05, "monthly_fee": 0.0,
            "max_withdrawals_month": 0, "notice_days": 0},
    "CF": {"name": "Charitable Fund Wallet", "min_opening_balance": 0.0,
            "interest_rate_pa": 0.0, "monthly_fee": 0.0,
            "max_withdrawals_month": None, "notice_days": 0},
    "IR": {"name": "Investment Reserve", "min_opening_balance": 10000.0,
            "interest_rate_pa": 0.09, "monthly_fee": 0.0,
            "max_withdrawals_month": None, "notice_days": 90},
    "MC": {"name": "Multi-currency Account", "min_opening_balance": 0.0,
            "interest_rate_pa": 0.0, "monthly_fee": 45.0,
            "max_withdrawals_month": None, "notice_days": 0},
}

# Interest tiers for Call and Savings accounts (balance thresholds in ZAR)
INTEREST_TIERS = {
    "C": [(0, 0.001), (1000, 0.003), (10000, 0.005), (50000, 0.008), (100000, 0.01)],
    "SA": [(0, 0.02), (1000, 0.03), (10000, 0.04), (50000, 0.045), (100000, 0.05)],
}

# Concentration limit — max 15% of total deposits per member
CONCENTRATION_LIMIT = 0.15
CONCENTRATION_WARNING = 0.12


class AgentisAccountService:
    """Core banking account operations for Agentis cooperative bank."""

    def __init__(self, compliance_service=None, member_service=None, blockchain=None):
        self.compliance = compliance_service
        self.members = member_service
        self.blockchain = blockchain

    # ------------------------------------------------------------------
    # Account Opening
    # ------------------------------------------------------------------

    async def open_account(
        self, db: AsyncSession, *,
        member_id: str,
        account_type: str,
        currency: str = "ZAR",
        agent_id: str | None = None,
        initial_deposit: float = 0,
        idempotency_key: str | None = None,
    ) -> dict:
        """Open a new member bank account."""
        # Phase 1: only S, C, SA permitted
        if account_type not in ("S", "C", "SA"):
            return {"error": "PRODUCT_NOT_AVAILABLE",
                    "error_code": "PRODUCT_NOT_AVAILABLE",
                    "message": f"Account type {account_type} not available in current phase"}

        product = ACCOUNT_PRODUCTS.get(account_type)
        if not product:
            return {"error": "INVALID_ACCOUNT_TYPE", "error_code": "INVALID_ACCOUNT_TYPE"}

        # Idempotency check
        if idempotency_key:
            existing = await db.execute(
                select(AgentisAccountTransaction).where(
                    AgentisAccountTransaction.idempotency_key == idempotency_key
                )
            )
            if existing.scalar_one_or_none():
                return {"error": "DUPLICATE_REQUEST", "error_code": "IDEMPOTENCY_CONFLICT"}

        # Get member
        member = await db.execute(
            select(AgentisMember).where(AgentisMember.member_id == member_id)
        )
        member_obj = member.scalar_one_or_none()
        if not member_obj:
            return {"error": "MEMBER_NOT_FOUND", "error_code": "MEMBER_NOT_FOUND"}
        if member_obj.membership_status != "active":
            return {"error": "MEMBER_NOT_ACTIVE", "error_code": "MEMBER_NOT_ACTIVE"}

        # Share account: every member must have exactly one
        if account_type == "S":
            existing_share = await db.execute(
                select(AgentisAccount).where(
                    AgentisAccount.member_id == member_id,
                    AgentisAccount.account_type == "S",
                    AgentisAccount.status == "active",
                )
            )
            if existing_share.scalar_one_or_none():
                return {"error": "SHARE_ACCOUNT_EXISTS",
                        "error_code": "SHARE_ACCOUNT_EXISTS",
                        "message": "Member already has an active share account"}

        # Check minimum opening balance
        if initial_deposit < product["min_opening_balance"]:
            return {"error": "BELOW_MINIMUM",
                    "error_code": "BELOW_MINIMUM_BALANCE",
                    "message": (f"Minimum opening balance for {product['name']}: "
                                f"R{product['min_opening_balance']:,.2f}")}

        # Generate account number
        type_suffix = account_type
        acct_number = f"{member_obj.member_number}-{type_suffix}"
        # Check uniqueness, append counter if needed
        existing_acct = await db.execute(
            select(AgentisAccount).where(AgentisAccount.account_number == acct_number)
        )
        if existing_acct.scalar_one_or_none():
            count = await db.execute(
                select(func.count(AgentisAccount.account_id)).where(
                    AgentisAccount.member_id == member_id,
                    AgentisAccount.account_type == account_type,
                )
            )
            c = (count.scalar() or 0) + 1
            acct_number = f"{member_obj.member_number}-{type_suffix}{c}"

        account = AgentisAccount(
            account_number=acct_number,
            member_id=member_id,
            agent_id=agent_id,
            account_type=account_type,
            currency=currency,
            balance=initial_deposit,
            interest_rate_pa=product["interest_rate_pa"],
            concentration_exempt=(account_type == "S"),
        )
        db.add(account)

        # Record opening transaction if initial deposit > 0
        if initial_deposit > 0:
            txn = AgentisAccountTransaction(
                account_id=account.account_id,
                member_id=member_id,
                agent_id=agent_id,
                txn_type="DEPOSIT",
                direction="CR",
                amount=initial_deposit,
                currency=currency,
                amount_zar=initial_deposit,
                balance_after=initial_deposit,
                reference=f"OPENING-{acct_number}",
                description=f"Opening deposit for {product['name']}",
                status="completed",
                completed_at=datetime.now(timezone.utc),
                idempotency_key=idempotency_key,
                high_value_flag=(initial_deposit >= 50000),
            )
            db.add(txn)

            # Update member totals
            if account_type == "S":
                member_obj.share_capital_balance += initial_deposit
            else:
                member_obj.total_deposits += initial_deposit
            member_obj.updated_at = datetime.now(timezone.utc)

            # Blockchain record
            if self.blockchain:
                from app.blockchain.transaction import Transaction, TransactionType
                btx = Transaction(
                    type=TransactionType.AGENTIS_ACCOUNT_OPEN,
                    sender_id=member_id,
                    amount=initial_deposit,
                    currency=currency,
                    description=f"Account opened: {acct_number} ({product['name']})",
                    metadata={"account_id": account.account_id,
                              "account_type": account_type},
                )
                self.blockchain.add_transaction(btx)
                txn.blockchain_ledger_hash = btx.id

        # Compliance
        if self.compliance:
            await self.compliance.log_audit(
                db, "OPERATOR" if not agent_id else "AGENT",
                agent_id or member_obj.operator_id,
                "OPEN_ACCOUNT", "ACCOUNT", account.account_id,
                {"account_number": acct_number, "type": account_type,
                 "initial_deposit": initial_deposit},
            )
            if initial_deposit >= 50000:
                await self.compliance.check_ctr_threshold(
                    db, member_id=member_id,
                    transaction_id=txn.txn_id if initial_deposit > 0 else "N/A",
                    account_id=account.account_id,
                    amount_zar=initial_deposit,
                    currency=currency,
                    transaction_type="DEPOSIT",
                )

        return {
            "account_id": account.account_id,
            "account_number": acct_number,
            "account_type": account_type,
            "product_name": product["name"],
            "balance": initial_deposit,
            "currency": currency,
            "interest_rate_pa": product["interest_rate_pa"],
            "status": "active",
        }

    # ------------------------------------------------------------------
    # Account Operations
    # ------------------------------------------------------------------

    async def get_account(self, db: AsyncSession,
                           account_id: str) -> AgentisAccount | None:
        """Get account by ID."""
        result = await db.execute(
            select(AgentisAccount).where(AgentisAccount.account_id == account_id)
        )
        return result.scalar_one_or_none()

    async def list_accounts(self, db: AsyncSession, member_id: str) -> list[dict]:
        """List all accounts for a member."""
        result = await db.execute(
            select(AgentisAccount).where(
                AgentisAccount.member_id == member_id,
            ).order_by(AgentisAccount.account_type)
        )
        accounts = result.scalars().all()
        return [
            {
                "account_id": a.account_id,
                "account_number": a.account_number,
                "account_type": a.account_type,
                "product_name": ACCOUNT_PRODUCTS.get(a.account_type, {}).get("name", "Unknown"),
                "currency": a.currency,
                "balance": a.balance,
                "pending_balance": a.pending_balance,
                "interest_accrued": a.interest_accrued,
                "interest_rate_pa": a.interest_rate_pa,
                "status": a.status,
                "is_frozen": a.is_frozen,
            }
            for a in accounts
        ]

    async def deposit(
        self, db: AsyncSession, *,
        account_id: str,
        amount: float,
        currency: str = "ZAR",
        reference: str,
        description: str | None = None,
        agent_id: str | None = None,
        mandate_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        """Credit an account (deposit)."""
        if amount <= 0:
            return {"error": "INVALID_AMOUNT", "error_code": "INVALID_AMOUNT"}

        if idempotency_key:
            existing = await db.execute(
                select(AgentisAccountTransaction).where(
                    AgentisAccountTransaction.idempotency_key == idempotency_key
                )
            )
            if existing.scalar_one_or_none():
                return {"error": "DUPLICATE_REQUEST", "error_code": "IDEMPOTENCY_CONFLICT"}

        account = await self.get_account(db, account_id)
        if not account:
            return {"error": "ACCOUNT_NOT_FOUND", "error_code": "ACCOUNT_NOT_FOUND"}
        if account.status != "active":
            return {"error": "ACCOUNT_NOT_ACTIVE", "error_code": "ACCOUNT_NOT_ACTIVE"}
        if account.is_frozen:
            return {"error": "ACCOUNT_FROZEN", "error_code": "ACCOUNT_FROZEN"}

        # Execute deposit
        account.balance += amount
        account.daily_transaction_total += amount
        account.monthly_transaction_total += amount
        account.updated_at = datetime.now(timezone.utc)

        txn = AgentisAccountTransaction(
            account_id=account_id,
            member_id=account.member_id,
            agent_id=agent_id,
            mandate_id=mandate_id,
            txn_type="DEPOSIT",
            direction="CR",
            amount=amount,
            currency=currency,
            amount_zar=amount,
            balance_after=account.balance,
            reference=reference,
            description=description,
            status="completed",
            completed_at=datetime.now(timezone.utc),
            idempotency_key=idempotency_key,
            high_value_flag=(amount >= 50000),
        )

        # Blockchain
        if self.blockchain:
            from app.blockchain.transaction import Transaction, TransactionType
            btx = Transaction(
                type=TransactionType.AGENTIS_DEPOSIT,
                receiver_id=account.member_id,
                amount=amount,
                currency=currency,
                description=f"Deposit to {account.account_number}: R{amount:,.2f}",
                metadata={"account_id": account_id, "txn_type": "DEPOSIT"},
            )
            self.blockchain.add_transaction(btx)
            txn.blockchain_ledger_hash = btx.id

        db.add(txn)

        # Compliance checks
        if self.compliance:
            await self.compliance.pre_transaction_check(
                db, member_id=account.member_id,
                agent_id=agent_id, mandate_id=mandate_id,
                account_id=account_id, amount_zar=amount,
                currency=currency, transaction_type="DEPOSIT",
            )

        return {
            "txn_id": txn.txn_id,
            "account_id": account_id,
            "amount": amount,
            "balance_after": account.balance,
            "status": "completed",
        }

    async def withdraw(
        self, db: AsyncSession, *,
        account_id: str,
        amount: float,
        currency: str = "ZAR",
        reference: str,
        description: str | None = None,
        agent_id: str | None = None,
        mandate_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        """Debit an account (withdrawal)."""
        if amount <= 0:
            return {"error": "INVALID_AMOUNT", "error_code": "INVALID_AMOUNT"}

        if idempotency_key:
            existing = await db.execute(
                select(AgentisAccountTransaction).where(
                    AgentisAccountTransaction.idempotency_key == idempotency_key
                )
            )
            if existing.scalar_one_or_none():
                return {"error": "DUPLICATE_REQUEST", "error_code": "IDEMPOTENCY_CONFLICT"}

        account = await self.get_account(db, account_id)
        if not account:
            return {"error": "ACCOUNT_NOT_FOUND", "error_code": "ACCOUNT_NOT_FOUND"}
        if account.status != "active":
            return {"error": "ACCOUNT_NOT_ACTIVE", "error_code": "ACCOUNT_NOT_ACTIVE"}
        if account.is_frozen:
            return {"error": "ACCOUNT_FROZEN", "error_code": "ACCOUNT_FROZEN"}

        # Share accounts: non-withdrawable while member
        if account.account_type == "S":
            return {"error": "SHARE_NON_WITHDRAWABLE",
                    "error_code": "SHARE_NON_WITHDRAWABLE",
                    "message": "Share account balance cannot be withdrawn while a member"}

        # Savings: check monthly withdrawal limit
        product = ACCOUNT_PRODUCTS.get(account.account_type, {})
        max_w = product.get("max_withdrawals_month")
        if max_w is not None and account.withdrawal_count_this_month >= max_w:
            return {"error": "WITHDRAWAL_LIMIT_REACHED",
                    "error_code": "WITHDRAWAL_LIMIT_REACHED",
                    "message": f"Maximum {max_w} withdrawals per month for this account type"}

        # Sufficient balance check
        if account.balance < amount:
            return {"error": "INSUFFICIENT_FUNDS",
                    "error_code": "INSUFFICIENT_FUNDS",
                    "message": f"Available balance: R{account.balance:,.2f}"}

        # Execute withdrawal
        account.balance -= amount
        account.daily_transaction_total += amount
        account.monthly_transaction_total += amount
        if max_w is not None:
            account.withdrawal_count_this_month += 1
        account.updated_at = datetime.now(timezone.utc)

        txn = AgentisAccountTransaction(
            account_id=account_id,
            member_id=account.member_id,
            agent_id=agent_id,
            mandate_id=mandate_id,
            txn_type="WITHDRAWAL",
            direction="DR",
            amount=amount,
            currency=currency,
            amount_zar=amount,
            balance_after=account.balance,
            reference=reference,
            description=description,
            status="completed",
            completed_at=datetime.now(timezone.utc),
            idempotency_key=idempotency_key,
            high_value_flag=(amount >= 50000),
        )

        if self.blockchain:
            from app.blockchain.transaction import Transaction, TransactionType
            btx = Transaction(
                type=TransactionType.AGENTIS_WITHDRAWAL,
                sender_id=account.member_id,
                amount=amount,
                currency=currency,
                description=f"Withdrawal from {account.account_number}: R{amount:,.2f}",
                metadata={"account_id": account_id},
            )
            self.blockchain.add_transaction(btx)
            txn.blockchain_ledger_hash = btx.id

        db.add(txn)

        if self.compliance:
            await self.compliance.pre_transaction_check(
                db, member_id=account.member_id,
                agent_id=agent_id, mandate_id=mandate_id,
                account_id=account_id, amount_zar=amount,
                currency=currency, transaction_type="WITHDRAWAL",
            )

        return {
            "txn_id": txn.txn_id,
            "account_id": account_id,
            "amount": amount,
            "balance_after": account.balance,
            "status": "completed",
        }

    async def internal_transfer(
        self, db: AsyncSession, *,
        source_account_id: str,
        destination_account_id: str,
        amount: float,
        reference: str,
        description: str | None = None,
        agent_id: str | None = None,
        mandate_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        """Transfer between Agentis accounts (member-to-member or own accounts)."""
        if amount <= 0:
            return {"error": "INVALID_AMOUNT", "error_code": "INVALID_AMOUNT"}

        if source_account_id == destination_account_id:
            return {"error": "SAME_ACCOUNT", "error_code": "SAME_ACCOUNT"}

        if idempotency_key:
            existing = await db.execute(
                select(AgentisAccountTransaction).where(
                    AgentisAccountTransaction.idempotency_key == idempotency_key
                )
            )
            if existing.scalar_one_or_none():
                return {"error": "DUPLICATE_REQUEST", "error_code": "IDEMPOTENCY_CONFLICT"}

        source = await self.get_account(db, source_account_id)
        dest = await self.get_account(db, destination_account_id)

        if not source:
            return {"error": "SOURCE_NOT_FOUND", "error_code": "ACCOUNT_NOT_FOUND"}
        if not dest:
            return {"error": "DESTINATION_NOT_FOUND", "error_code": "ACCOUNT_NOT_FOUND"}
        if source.status != "active" or source.is_frozen:
            return {"error": "SOURCE_NOT_AVAILABLE", "error_code": "ACCOUNT_NOT_ACTIVE"}
        if dest.status != "active":
            return {"error": "DESTINATION_NOT_AVAILABLE", "error_code": "ACCOUNT_NOT_ACTIVE"}
        if source.account_type == "S":
            return {"error": "SHARE_NON_TRANSFERABLE", "error_code": "SHARE_NON_TRANSFERABLE"}
        if source.balance < amount:
            return {"error": "INSUFFICIENT_FUNDS", "error_code": "INSUFFICIENT_FUNDS",
                    "message": f"Available balance: R{source.balance:,.2f}"}

        now = datetime.now(timezone.utc)

        # Debit source
        source.balance -= amount
        source.daily_transaction_total += amount
        source.monthly_transaction_total += amount
        source.updated_at = now

        # Credit destination
        dest.balance += amount
        dest.daily_transaction_total += amount
        dest.monthly_transaction_total += amount
        dest.updated_at = now

        idem_out = f"{idempotency_key}_OUT" if idempotency_key else None
        idem_in = f"{idempotency_key}_IN" if idempotency_key else None

        txn_out = AgentisAccountTransaction(
            account_id=source_account_id,
            member_id=source.member_id,
            agent_id=agent_id,
            mandate_id=mandate_id,
            txn_type="TRANSFER_OUT",
            direction="DR",
            amount=amount,
            currency=source.currency,
            amount_zar=amount,
            balance_after=source.balance,
            reference=reference,
            description=description or f"Transfer to {dest.account_number}",
            counterparty_account_id=destination_account_id,
            counterparty_member_id=dest.member_id,
            status="completed",
            completed_at=now,
            idempotency_key=idem_out,
            high_value_flag=(amount >= 50000),
        )

        txn_in = AgentisAccountTransaction(
            account_id=destination_account_id,
            member_id=dest.member_id,
            txn_type="TRANSFER_IN",
            direction="CR",
            amount=amount,
            currency=dest.currency,
            amount_zar=amount,
            balance_after=dest.balance,
            reference=reference,
            description=description or f"Transfer from {source.account_number}",
            counterparty_account_id=source_account_id,
            counterparty_member_id=source.member_id,
            status="completed",
            completed_at=now,
            idempotency_key=idem_in,
            high_value_flag=(amount >= 50000),
        )

        # Blockchain — single atomic record for the transfer
        if self.blockchain:
            from app.blockchain.transaction import Transaction, TransactionType
            btx = Transaction(
                type=TransactionType.AGENTIS_TRANSFER_INTERNAL,
                sender_id=source.member_id,
                receiver_id=dest.member_id,
                amount=amount,
                currency=source.currency,
                description=(f"Internal transfer: {source.account_number} → "
                             f"{dest.account_number}: R{amount:,.2f}"),
                metadata={"source_account": source_account_id,
                          "dest_account": destination_account_id},
            )
            self.blockchain.add_transaction(btx)
            txn_out.blockchain_ledger_hash = btx.id
            txn_in.blockchain_ledger_hash = btx.id

        db.add(txn_out)
        db.add(txn_in)

        # Compliance
        if self.compliance:
            await self.compliance.pre_transaction_check(
                db, member_id=source.member_id,
                agent_id=agent_id, mandate_id=mandate_id,
                account_id=source_account_id, amount_zar=amount,
                currency=source.currency, transaction_type="TRANSFER_OUT",
            )

        return {
            "txn_out_id": txn_out.txn_id,
            "txn_in_id": txn_in.txn_id,
            "source_account": source.account_number,
            "destination_account": dest.account_number,
            "amount": amount,
            "source_balance_after": source.balance,
            "destination_balance_after": dest.balance,
            "status": "completed",
        }

    # ------------------------------------------------------------------
    # Interest Calculation Engine
    # ------------------------------------------------------------------

    async def calculate_daily_interest(self, db: AsyncSession) -> dict:
        """Run daily interest accrual for all active interest-bearing accounts.
        Called by scheduled job at 23:55 daily."""
        today = date.today()
        result = await db.execute(
            select(AgentisAccount).where(
                AgentisAccount.account_type.in_(["C", "SA", "N", "FD", "IR", "MC"]),
                AgentisAccount.status == "active",
                AgentisAccount.balance > 0,
            )
        )
        accounts = result.scalars().all()

        accrued_count = 0
        total_interest = 0.0

        for account in accounts:
            # Apply tiered rate if applicable
            rate = self._get_tiered_rate(account.account_type, account.balance)
            if rate != account.interest_rate_pa:
                account.interest_rate_pa = rate

            daily_interest = account.balance * (rate / 365)
            account.interest_accrued += daily_interest
            account.updated_at = datetime.now(timezone.utc)

            accrual = AgentisInterestAccrual(
                account_id=account.account_id,
                accrual_date=today,
                balance_at_accrual=account.balance,
                rate_pa=rate,
                daily_interest=daily_interest,
                cumulative_accrued=account.interest_accrued,
            )
            db.add(accrual)

            accrued_count += 1
            total_interest += daily_interest

        return {
            "date": today.isoformat(),
            "accounts_processed": accrued_count,
            "total_daily_interest": round(total_interest, 6),
        }

    async def capitalise_interest(self, db: AsyncSession,
                                   account_id: str) -> dict:
        """Capitalise accrued interest to account balance."""
        account = await self.get_account(db, account_id)
        if not account or account.interest_accrued <= 0:
            return {"capitalised": 0}

        amount = account.interest_accrued
        account.balance += amount
        account.interest_accrued = 0
        account.updated_at = datetime.now(timezone.utc)

        txn = AgentisAccountTransaction(
            account_id=account_id,
            member_id=account.member_id,
            txn_type="INTEREST_CREDIT",
            direction="CR",
            amount=amount,
            currency=account.currency,
            amount_zar=amount,
            balance_after=account.balance,
            reference=f"INT-{account.account_number}-{date.today().isoformat()}",
            description="Interest capitalisation",
            status="completed",
            completed_at=datetime.now(timezone.utc),
        )

        if self.blockchain:
            from app.blockchain.transaction import Transaction, TransactionType
            btx = Transaction(
                type=TransactionType.AGENTIS_INTEREST_CREDIT,
                receiver_id=account.member_id,
                amount=amount,
                currency=account.currency,
                description=f"Interest credit: {account.account_number} R{amount:,.4f}",
                metadata={"account_id": account_id},
            )
            self.blockchain.add_transaction(btx)
            txn.blockchain_ledger_hash = btx.id

        db.add(txn)
        return {"capitalised": amount, "balance_after": account.balance}

    def _get_tiered_rate(self, account_type: str, balance: float) -> float:
        """Calculate tiered interest rate based on balance."""
        tiers = INTEREST_TIERS.get(account_type)
        if not tiers:
            product = ACCOUNT_PRODUCTS.get(account_type, {})
            return product.get("interest_rate_pa", 0)

        rate = tiers[0][1]
        for threshold, tier_rate in tiers:
            if balance >= threshold:
                rate = tier_rate
        return rate

    # ------------------------------------------------------------------
    # Transaction History & Statements
    # ------------------------------------------------------------------

    async def get_transactions(
        self, db: AsyncSession, *,
        account_id: str,
        limit: int = 50,
        offset: int = 0,
        txn_type: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[dict]:
        """Get transaction history for an account."""
        query = select(AgentisAccountTransaction).where(
            AgentisAccountTransaction.account_id == account_id
        )
        if txn_type:
            query = query.where(AgentisAccountTransaction.txn_type == txn_type)
        if from_date:
            query = query.where(AgentisAccountTransaction.initiated_at >= from_date)
        if to_date:
            query = query.where(AgentisAccountTransaction.initiated_at <= to_date)

        query = query.order_by(AgentisAccountTransaction.initiated_at.desc())
        query = query.offset(offset).limit(limit)

        result = await db.execute(query)
        transactions = result.scalars().all()

        return [
            {
                "txn_id": t.txn_id,
                "txn_type": t.txn_type,
                "direction": t.direction,
                "amount": t.amount,
                "currency": t.currency,
                "balance_after": t.balance_after,
                "reference": t.reference,
                "description": t.description,
                "status": t.status,
                "initiated_at": t.initiated_at.isoformat(),
                "counterparty_account_id": t.counterparty_account_id,
            }
            for t in transactions
        ]

    async def get_account_statement(
        self, db: AsyncSession, *,
        account_id: str,
        from_date: datetime,
        to_date: datetime,
    ) -> dict:
        """Generate a formatted account statement."""
        account = await self.get_account(db, account_id)
        if not account:
            return {"error": "ACCOUNT_NOT_FOUND"}

        transactions = await self.get_transactions(
            db, account_id=account_id,
            from_date=from_date, to_date=to_date, limit=1000,
        )

        # Calculate opening balance (balance_after of last txn before from_date)
        result = await db.execute(
            select(AgentisAccountTransaction.balance_after).where(
                AgentisAccountTransaction.account_id == account_id,
                AgentisAccountTransaction.initiated_at < from_date,
            ).order_by(AgentisAccountTransaction.initiated_at.desc()).limit(1)
        )
        opening_balance = result.scalar() or 0

        total_credits = sum(t["amount"] for t in transactions if t["direction"] == "CR")
        total_debits = sum(t["amount"] for t in transactions if t["direction"] == "DR")

        return {
            "account_number": account.account_number,
            "account_type": account.account_type,
            "currency": account.currency,
            "period_start": from_date.isoformat(),
            "period_end": to_date.isoformat(),
            "opening_balance": opening_balance,
            "total_credits": total_credits,
            "total_debits": total_debits,
            "closing_balance": account.balance,
            "interest_accrued": account.interest_accrued,
            "transaction_count": len(transactions),
            "transactions": transactions,
        }
