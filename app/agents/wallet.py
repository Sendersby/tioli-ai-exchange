"""Wallet operations — deposit, withdraw, transfer, and balance management."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import Agent, Wallet, Loan
from app.blockchain.chain import Blockchain
from app.blockchain.transaction import Transaction, TransactionType
from app.exchange.fees import FeeEngine


class WalletService:
    """Handles all wallet operations with automatic fee deduction
    and blockchain recording."""

    def __init__(self, blockchain: Blockchain, fee_engine: FeeEngine):
        self.blockchain = blockchain
        self.fee_engine = fee_engine
        self._revenue_recorder = None  # H-09 fix: optional revenue recording hook
        self._profitability_updater = None  # Issue #7: charity conditional on profitability

    def set_revenue_recorder(self, recorder):
        """Set a callback for recording revenue (H-09 fix)."""
        self._revenue_recorder = recorder

    def set_profitability_updater(self, updater):
        """Set a callback to refresh fee engine profitability after transactions."""
        self._profitability_updater = updater

    async def get_or_create_wallet(
        self, db: AsyncSession, agent_id: str, currency: str = "TIOLI",
        lock: bool = False
    ) -> Wallet:
        """Get an agent's wallet for a currency, creating one if needed.

        DB-019: pass lock=True for debit operations to prevent race conditions.
        """
        query = select(Wallet).where(
            Wallet.agent_id == agent_id, Wallet.currency == currency
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        wallet = result.scalar_one_or_none()
        if not wallet:
            wallet = Wallet(agent_id=agent_id, currency=currency)
            db.add(wallet)
            await db.flush()
        return wallet

    async def deposit(
        self, db: AsyncSession, agent_id: str, amount: float,
        currency: str = "TIOLI", description: str = ""
    ) -> Transaction:
        """Deposit funds into an agent's wallet."""
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        wallet = await self.get_or_create_wallet(db, agent_id, currency)
        wallet.balance += amount

        tx = Transaction(
            type=TransactionType.DEPOSIT,
            receiver_id=agent_id,
            amount=amount,
            currency=currency,
            description=description or f"Deposit of {amount} {currency}",
        )
        self.blockchain.add_transaction(tx)
        return tx

    async def withdraw(
        self, db: AsyncSession, agent_id: str, amount: float,
        currency: str = "TIOLI", description: str = ""
    ) -> Transaction:
        """Withdraw funds from an agent's wallet."""
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        wallet = await self.get_or_create_wallet(db, agent_id, currency, lock=True)
        if wallet.available_balance < amount:
            raise ValueError(
                f"Insufficient balance. Available: {wallet.available_balance}, "
                f"Requested: {amount}"
            )

        wallet.balance -= amount

        tx = Transaction(
            type=TransactionType.WITHDRAWAL,
            sender_id=agent_id,
            amount=amount,
            currency=currency,
            description=description or f"Withdrawal of {amount} {currency}",
        )
        self.blockchain.add_transaction(tx)
        return tx

    async def transfer(
        self, db: AsyncSession, sender_id: str, receiver_id: str,
        amount: float, currency: str = "TIOLI", description: str = ""
    ) -> Transaction:
        """Transfer funds between two agents, with automatic fee deduction.

        Flow:
        1. Deduct full amount from sender
        2. Calculate and deduct founder commission + charity fee
        3. Credit remaining amount to receiver
        4. Record all transactions on-chain
        """
        sender_wallet = await self.get_or_create_wallet(db, sender_id, currency, lock=True)
        if sender_wallet.available_balance < amount:
            raise ValueError(
                f"Insufficient balance. Available: {sender_wallet.available_balance}, "
                f"Requested: {amount}"
            )

        # Calculate fees (two-component: max of percentage vs floor)
        fee_breakdown = self.fee_engine.calculate_fees(amount, transaction_type="resource_exchange")

        # Deduct from sender
        sender_wallet.balance -= amount

        # Credit receiver (after fees)
        receiver_wallet = await self.get_or_create_wallet(db, receiver_id, currency)
        receiver_wallet.balance += fee_breakdown["net_amount"]

        # Credit fee recipient wallets (C-05 fix: fees must not vanish)
        if fee_breakdown["founder_commission"] > 0:
            founder_wallet = await self.get_or_create_wallet(db, "TIOLI_FOUNDER", currency)
            founder_wallet.balance += fee_breakdown["founder_commission"]
        if fee_breakdown["charity_fee"] > 0:
            charity_wallet = await self.get_or_create_wallet(db, "TIOLI_CHARITY_FUND", currency)
            charity_wallet.balance += fee_breakdown["charity_fee"]

        # H-09 fix: record revenue for financial governance
        # AUD-09 fix: revenue recording is non-blocking — never rolls back a transfer
        import logging
        _logger = logging.getLogger(__name__)
        if self._revenue_recorder and fee_breakdown["founder_commission"] > 0:
            try:
                await self._revenue_recorder(
                    db, "founder_commission", fee_breakdown["founder_commission"],
                    currency, f"Commission on transfer {amount} {currency}"
                )
            except Exception as e:
                _logger.error(f"Revenue recording failed (non-fatal): {e}")
        if self._revenue_recorder and fee_breakdown["charity_fee"] > 0:
            try:
                await self._revenue_recorder(
                    db, "charity_fee", fee_breakdown["charity_fee"],
                    currency, f"Charity fee on transfer {amount} {currency}"
                )
            except Exception as e:
                _logger.error(f"Revenue recording failed (non-fatal): {e}")

        # Issue #7: refresh charity rate based on current profitability
        if self._profitability_updater:
            try:
                await self._profitability_updater(db)
            except Exception as e:
                _logger.error(f"Profitability update failed (non-fatal): {e}")

        # Record the main transfer
        tx = Transaction(
            type=TransactionType.TRANSFER,
            sender_id=sender_id,
            receiver_id=receiver_id,
            amount=amount,
            currency=currency,
            description=description or f"Transfer of {amount} {currency}",
            founder_commission=fee_breakdown["founder_commission"],
            charity_fee=fee_breakdown["charity_fee"],
        )
        self.blockchain.add_transaction(tx)

        # Record fee transactions separately for full transparency
        if fee_breakdown["founder_commission"] > 0:
            commission_tx = Transaction(
                type=TransactionType.COMMISSION_DEDUCTION,
                sender_id=sender_id,
                receiver_id="TIOLI_FOUNDER",
                amount=fee_breakdown["founder_commission"],
                currency=currency,
                description=f"Founder commission ({self.fee_engine.founder_rate*100:.1f}%) on transfer {tx.id}",
            )
            self.blockchain.add_transaction(commission_tx)

        if fee_breakdown["charity_fee"] > 0:
            charity_tx = Transaction(
                type=TransactionType.CHARITY_DEDUCTION,
                sender_id=sender_id,
                receiver_id="TIOLI_CHARITY_FUND",
                amount=fee_breakdown["charity_fee"],
                currency=currency,
                description=f"Charity fee ({self.fee_engine.charity_rate*100:.1f}%) on transfer {tx.id}",
            )
            self.blockchain.add_transaction(charity_tx)

        return tx

    async def issue_loan(
        self, db: AsyncSession, lender_id: str, borrower_id: str,
        amount: float, interest_rate: float, currency: str = "TIOLI",
        due_at=None
    ) -> Loan:
        """Issue a loan from one agent to another.

        The lender's funds are frozen (not deducted) until the loan
        is repaid or defaults.
        """
        lender_wallet = await self.get_or_create_wallet(db, lender_id, currency)
        if lender_wallet.available_balance < amount:
            raise ValueError("Lender has insufficient available balance.")

        # Freeze lender's funds and credit borrower
        lender_wallet.frozen_balance += amount

        borrower_wallet = await self.get_or_create_wallet(db, borrower_id, currency)
        borrower_wallet.balance += amount

        # Create loan record
        loan = Loan(
            lender_id=lender_id,
            borrower_id=borrower_id,
            principal=amount,
            interest_rate=interest_rate,
            currency=currency,
            due_at=due_at,
        )
        db.add(loan)
        await db.flush()

        # Record on blockchain
        tx = Transaction(
            type=TransactionType.LOAN_ISSUE,
            sender_id=lender_id,
            receiver_id=borrower_id,
            amount=amount,
            currency=currency,
            description=f"Loan issued at {interest_rate*100:.1f}% interest. Loan ID: {loan.id}",
            metadata={"loan_id": loan.id, "interest_rate": interest_rate},
        )
        self.blockchain.add_transaction(tx)

        return loan

    async def repay_loan(
        self, db: AsyncSession, loan_id: str, amount: float
    ) -> Transaction:
        """Repay part or all of a loan."""
        result = await db.execute(select(Loan).where(Loan.id == loan_id))
        loan = result.scalar_one_or_none()
        if not loan or loan.status != "active":
            raise ValueError("Loan not found or not active.")

        borrower_wallet = await self.get_or_create_wallet(
            db, loan.borrower_id, loan.currency
        )
        if borrower_wallet.available_balance < amount:
            raise ValueError("Borrower has insufficient balance for repayment.")

        # Calculate fees on the repayment (lending origination rate)
        fee_breakdown = self.fee_engine.calculate_fees(amount, transaction_type="lending_origination")

        # Deduct from borrower
        borrower_wallet.balance -= amount

        # Unfreeze and credit lender (after fees)
        lender_wallet = await self.get_or_create_wallet(
            db, loan.lender_id, loan.currency
        )
        repayment_to_lender = fee_breakdown["net_amount"]
        # C-07 fix: unfreeze proportional to repayment, not full principal
        proportion_repaid = min(amount / loan.total_owed, 1.0)
        unfreeze_amount = loan.principal * proportion_repaid
        lender_wallet.frozen_balance = max(
            0, lender_wallet.frozen_balance - unfreeze_amount
        )
        lender_wallet.balance += repayment_to_lender

        # Credit fee wallets (C-05 fix)
        if fee_breakdown["founder_commission"] > 0:
            founder_wallet = await self.get_or_create_wallet(db, "TIOLI_FOUNDER", loan.currency)
            founder_wallet.balance += fee_breakdown["founder_commission"]
        if fee_breakdown["charity_fee"] > 0:
            charity_wallet = await self.get_or_create_wallet(db, "TIOLI_CHARITY_FUND", loan.currency)
            charity_wallet.balance += fee_breakdown["charity_fee"]

        # Update loan
        loan.amount_repaid += amount
        if loan.amount_repaid >= loan.total_owed:
            loan.status = "repaid"

        # Record on blockchain
        tx = Transaction(
            type=TransactionType.LOAN_REPAYMENT,
            sender_id=loan.borrower_id,
            receiver_id=loan.lender_id,
            amount=amount,
            currency=loan.currency,
            description=f"Loan repayment for loan {loan_id}. Remaining: {loan.remaining:.2f}",
            founder_commission=fee_breakdown["founder_commission"],
            charity_fee=fee_breakdown["charity_fee"],
            metadata={"loan_id": loan_id},
        )
        self.blockchain.add_transaction(tx)

        return tx

    async def get_balance(
        self, db: AsyncSession, agent_id: str, currency: str = "TIOLI"
    ) -> dict:
        """Get an agent's wallet balance."""
        wallet = await self.get_or_create_wallet(db, agent_id, currency)
        return {
            "agent_id": agent_id,
            "currency": currency,
            "balance": wallet.balance,
            "frozen": wallet.frozen_balance,
            "available": wallet.available_balance,
        }
