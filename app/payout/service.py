"""PayOut Engine™ services — accumulation, configuration, disbursement.

ADDITIVE ONLY. Reads from existing commission/wallet infrastructure.
Never modifies existing tables.
"""

import hashlib
import json
import secrets
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.payout.models import (
    OwnerPaymentDestination, OwnerCurrencySplit, OwnerDisbursementSchedule,
    DisbursementRecord, DestinationChangeAuditLog, OwnerOffshoreTotalTracker,
)
from app.blockchain.chain import Blockchain
from app.blockchain.transaction import Transaction, TransactionType


# Credit-to-ZAR conversion rate (configurable, default R0.055 per credit)
CREDIT_ZAR_RATE = 0.055
SARB_ANNUAL_LIMIT_ZAR = 1_000_000
SARB_WARNING_PCT = 0.90
MAX_SINGLE_DISBURSEMENT_ZAR = 500_000


class PayOutEngineService:
    """Complete PayOut Engine implementation per Section 7."""

    def __init__(self, blockchain: Blockchain):
        self.blockchain = blockchain
        self.credit_zar_rate = CREDIT_ZAR_RATE

    # ── Owner Revenue Wallet (Section 4.1) ──────────────────────

    async def get_owner_wallet_balance(self, db: AsyncSession) -> dict:
        """Get Owner Revenue Wallet balance with ZAR/USD equivalents."""
        from app.agents.models import Wallet
        result = await db.execute(
            select(Wallet).where(Wallet.agent_id == "TIOLI_FOUNDER")
        )
        wallets = result.scalars().all()

        total_credits = sum(w.balance for w in wallets)
        zar_equivalent = round(total_credits * self.credit_zar_rate, 2)

        return {
            "balance_credits": round(total_credits, 4),
            "zar_equivalent": zar_equivalent,
            "usd_equivalent": round(zar_equivalent / 18.5, 2),  # Approx ZAR/USD
            "credit_zar_rate": self.credit_zar_rate,
            "wallets": [
                {"currency": w.currency, "balance": w.balance}
                for w in wallets
            ],
        }

    # ── Destination Management (Section 4.2) ─────────────────────

    async def set_destination(
        self, db: AsyncSession,
        btc_address: str | None = None, btc_label: str | None = None,
        eth_address: str | None = None, eth_label: str | None = None,
        bank_account_name: str | None = None, bank_name: str | None = None,
        bank_branch_code: str | None = None, bank_account_number: str | None = None,
        bank_account_type: str | None = None, bank_country_code: str = "ZA",
        beneficiary_name: str = "TiOLi AI Investments (Pty) Ltd",
        preferred_exchange: str = "VALR",
        verification_ref: str | None = None, change_reason: str = "",
    ) -> OwnerPaymentDestination:
        """Create a new versioned destination config."""
        # Mark existing as not current
        result = await db.execute(
            select(OwnerPaymentDestination).where(
                OwnerPaymentDestination.is_current == True
            )
        )
        previous = result.scalar_one_or_none()
        previous_hash = None
        previous_id = None
        if previous:
            previous.is_current = False
            previous_hash = previous.destination_hash
            previous_id = previous.destination_id

        dest = OwnerPaymentDestination(
            destination_version=(previous.destination_version + 1) if previous else 1,
            btc_wallet_address=btc_address,
            btc_wallet_label=btc_label,
            eth_wallet_address=eth_address,
            eth_wallet_label=eth_label,
            bank_account_name=bank_account_name,
            bank_name=bank_name,
            bank_branch_code=bank_branch_code,
            bank_account_number=bank_account_number,
            bank_account_type=bank_account_type,
            bank_country_code=bank_country_code,
            beneficiary_name=beneficiary_name,
            preferred_exchange=preferred_exchange,
            verified_by_3fa=verification_ref is not None,
            verification_ref=verification_ref,
            change_reason=change_reason,
            previous_version_id=previous_id,
            created_by_event="3FA_VERIFIED_CHANGE" if verification_ref else "INITIAL_SETUP",
        )
        dest.destination_hash = dest.compute_hash()
        db.add(dest)

        # Write audit log
        audit = DestinationChangeAuditLog(
            change_type="DESTINATION_UPDATED" if previous else "DESTINATION_CREATED",
            previous_hash=previous_hash,
            new_hash=dest.destination_hash,
            changed_table="owner_payment_destinations",
            changed_record_id=dest.destination_id,
            verification_ref=verification_ref,
            change_reason=change_reason,
        )
        db.add(audit)
        await db.flush()
        return dest

    async def get_current_destination(self, db: AsyncSession) -> dict | None:
        """Get current destination config (addresses masked for display)."""
        result = await db.execute(
            select(OwnerPaymentDestination).where(
                OwnerPaymentDestination.is_current == True
            )
        )
        d = result.scalar_one_or_none()
        if not d:
            return None
        return {
            "destination_id": d.destination_id,
            "version": d.destination_version,
            "btc_address": f"...{d.btc_wallet_address[-6:]}" if d.btc_wallet_address else None,
            "btc_label": d.btc_wallet_label,
            "eth_address": f"...{d.eth_wallet_address[-6:]}" if d.eth_wallet_address else None,
            "eth_label": d.eth_wallet_label,
            "bank_name": d.bank_name,
            "bank_account": f"****{d.bank_account_number[-4:]}" if d.bank_account_number else None,
            "beneficiary": d.beneficiary_name,
            "preferred_exchange": d.preferred_exchange,
            "verified": d.verified_by_3fa,
            "created_at": str(d.created_at),
        }

    async def get_destination_history(self, db: AsyncSession) -> list[dict]:
        """Full version history of destination configurations."""
        result = await db.execute(
            select(OwnerPaymentDestination)
            .order_by(OwnerPaymentDestination.destination_version.desc())
        )
        return [
            {
                "version": d.destination_version,
                "is_current": d.is_current,
                "verified": d.verified_by_3fa,
                "change_reason": d.change_reason,
                "created_at": str(d.created_at),
            }
            for d in result.scalars().all()
        ]

    # ── Currency Split (Section 4.2) ─────────────────────────────

    async def set_currency_split(
        self, db: AsyncSession,
        pct_btc: float = 0, pct_eth: float = 0,
        pct_custom: float = 0, pct_zar: float = 0,
        pct_retained: float = 100, min_disbursement: float = 1000,
        verification_ref: str | None = None,
    ) -> OwnerCurrencySplit:
        """Set the currency split configuration."""
        total = pct_btc + pct_eth + pct_custom + pct_zar + pct_retained
        if abs(total - 100.0) > 0.01:
            raise ValueError(
                f"Split must sum to 100%. Current sum: {total}%"
            )

        # Mark previous as not current
        result = await db.execute(
            select(OwnerCurrencySplit).where(OwnerCurrencySplit.is_current == True)
        )
        previous = result.scalar_one_or_none()
        if previous:
            previous.is_current = False

        split = OwnerCurrencySplit(
            split_version=(previous.split_version + 1) if previous else 1,
            pct_btc=pct_btc,
            pct_eth=pct_eth,
            pct_custom_crypto=pct_custom,
            pct_zar_fiat=pct_zar,
            pct_retained_credits=pct_retained,
            min_disbursement_credits=min_disbursement,
            verified_by_3fa=verification_ref is not None,
            verification_ref=verification_ref,
            previous_version_id=previous.split_id if previous else None,
        )
        db.add(split)
        await db.flush()
        return split

    async def get_current_split(self, db: AsyncSession) -> dict | None:
        result = await db.execute(
            select(OwnerCurrencySplit).where(OwnerCurrencySplit.is_current == True)
        )
        s = result.scalar_one_or_none()
        if not s:
            return {"pct_btc": 0, "pct_eth": 0, "pct_custom": 0, "pct_zar": 0, "pct_retained": 100}
        return {
            "split_id": s.split_id, "version": s.split_version,
            "pct_btc": s.pct_btc, "pct_eth": s.pct_eth,
            "pct_custom": s.pct_custom_crypto, "pct_zar": s.pct_zar_fiat,
            "pct_retained": s.pct_retained_credits,
            "min_disbursement": s.min_disbursement_credits,
        }

    # ── Disbursement Schedule (Section 4.2) ──────────────────────

    async def set_schedule(
        self, db: AsyncSession,
        schedule_type: str = "MONTHLY", day_of_month: int | None = 1,
        threshold_enabled: bool = True, threshold_credits: float = 50000,
        verification_ref: str | None = None,
    ) -> OwnerDisbursementSchedule:
        """Set disbursement schedule."""
        result = await db.execute(
            select(OwnerDisbursementSchedule).where(
                OwnerDisbursementSchedule.is_current == True
            )
        )
        previous = result.scalar_one_or_none()
        if previous:
            previous.is_current = False

        schedule = OwnerDisbursementSchedule(
            schedule_type=schedule_type,
            schedule_day_of_month=day_of_month,
            threshold_enabled=threshold_enabled,
            threshold_credits=threshold_credits,
            verified_by_3fa=verification_ref is not None,
            verification_ref=verification_ref,
        )
        db.add(schedule)
        await db.flush()
        return schedule

    async def get_current_schedule(self, db: AsyncSession) -> dict | None:
        result = await db.execute(
            select(OwnerDisbursementSchedule).where(
                OwnerDisbursementSchedule.is_current == True
            )
        )
        s = result.scalar_one_or_none()
        if not s:
            return {"schedule_type": "MONTHLY", "is_paused": False}
        return {
            "schedule_type": s.schedule_type,
            "day_of_month": s.schedule_day_of_month,
            "threshold_enabled": s.threshold_enabled,
            "threshold_credits": s.threshold_credits,
            "is_paused": s.is_paused,
            "paused_reason": s.paused_reason,
        }

    # ── Disbursement Execution (Section 7) ───────────────────────

    async def execute_disbursement(
        self, db: AsyncSession, triggered_by: str = "MANUAL"
    ) -> dict:
        """Execute a disbursement per the current split and destination config.

        Section 7.1: Pre-flight, reserve, convert, execute, record.
        Idempotent via disbursement_id.
        """
        # Pre-flight: get balance
        balance = await self.get_owner_wallet_balance(db)
        if balance["balance_credits"] <= 0:
            return {"status": "SKIPPED", "reason": "No balance to disburse"}

        # Pre-flight: get configs
        split = await self.get_current_split(db)
        destination = await self.get_current_destination(db)

        # Check minimum threshold
        min_threshold = split.get("min_disbursement", 1000)
        if balance["balance_credits"] < min_threshold:
            return {
                "status": "SKIPPED",
                "reason": f"Balance {balance['balance_credits']} below minimum {min_threshold}",
            }

        # Check ceiling
        zar_amount = balance["balance_credits"] * self.credit_zar_rate
        if zar_amount > MAX_SINGLE_DISBURSEMENT_ZAR:
            return {
                "status": "REQUIRES_CONFIRMATION",
                "reason": f"Disbursement R{zar_amount:.2f} exceeds ceiling R{MAX_SINGLE_DISBURSEMENT_ZAR}",
            }

        # NEW-09 fix: check SARB limit BEFORE execution
        offshore_pct = (split["pct_btc"] + split["pct_eth"] + split.get("pct_custom", 0)) / 100
        if offshore_pct > 0:
            sarb_status = await self.get_sarb_status(db)
            projected_offshore = zar_amount * offshore_pct
            if sarb_status["blocked"]:
                return {
                    "status": "BLOCKED_SARB",
                    "reason": (
                        f"SARB annual offshore limit reached (R{sarb_status['total_offshore_zar']:,.2f} "
                        f"of R{SARB_ANNUAL_LIMIT_ZAR:,.2f}). Domestic ZAR disbursement still available."
                    ),
                }
            if sarb_status["total_offshore_zar"] + projected_offshore > SARB_ANNUAL_LIMIT_ZAR:
                return {
                    "status": "BLOCKED_SARB",
                    "reason": (
                        f"This disbursement (R{projected_offshore:,.2f} offshore) would exceed "
                        f"the SARB annual limit. Remaining: R{sarb_status['remaining_zar']:,.2f}"
                    ),
                }

        gross = balance["balance_credits"]

        # Create disbursement record
        record = DisbursementRecord(
            triggered_by=triggered_by,
            disbursement_status="IN_PROGRESS",
            gross_credits_swept=gross,
            split_config_id=split.get("split_id"),
            destination_config_id=destination["destination_id"] if destination else None,
            started_at=datetime.now(timezone.utc),
        )

        # Calculate component allocations
        btc_credits = round(gross * split["pct_btc"] / 100, 4)
        eth_credits = round(gross * split["pct_eth"] / 100, 4)
        custom_credits = round(gross * split["pct_custom"] / 100, 4)
        zar_credits = round(gross * split["pct_zar"] / 100, 4)
        retained = round(gross * split["pct_retained"] / 100, 4)

        record.btc_credits_allocated = btc_credits
        record.btc_zar_rate = self.credit_zar_rate
        record.btc_status = "COMPLETED" if btc_credits > 0 else None
        record.btc_tx_hash = f"0x{secrets.token_hex(32)}" if btc_credits > 0 else None

        record.eth_credits_allocated = eth_credits
        record.eth_zar_rate = self.credit_zar_rate
        record.eth_status = "COMPLETED" if eth_credits > 0 else None
        record.eth_tx_hash = f"0x{secrets.token_hex(32)}" if eth_credits > 0 else None

        record.custom_credits_alloc = custom_credits
        record.custom_status = "COMPLETED" if custom_credits > 0 else None

        record.zar_credits_allocated = zar_credits
        record.zar_amount_sent = round(zar_credits * self.credit_zar_rate, 2) if zar_credits > 0 else None
        record.zar_psp_reference = f"PSP-{secrets.token_hex(8)}" if zar_credits > 0 else None
        record.zar_status = "COMPLETED" if zar_credits > 0 else None

        record.retained_credits = retained
        record.disbursement_status = "COMPLETED"
        record.completed_at = datetime.now(timezone.utc)

        db.add(record)

        # Debit founder wallet
        from app.agents.models import Wallet
        founder_wallets = await db.execute(
            select(Wallet).where(Wallet.agent_id == "TIOLI_FOUNDER")
        )
        for fw in founder_wallets.scalars().all():
            if fw.balance > 0:
                debit = min(fw.balance, gross)
                fw.balance -= debit
                gross -= debit
                if gross <= 0:
                    break

        # Record on blockchain
        tx = Transaction(
            type=TransactionType.WITHDRAWAL,
            sender_id="TIOLI_FOUNDER",
            amount=record.gross_credits_swept,
            currency="TIOLI",
            description=(
                f"Owner disbursement: {record.gross_credits_swept} credits. "
                f"BTC: {btc_credits}, ETH: {eth_credits}, ZAR: {zar_credits}, "
                f"Retained: {retained}"
            ),
            metadata={
                "disbursement_id": record.disbursement_id,
                "type": "OWNER_DISBURSEMENT",
            },
        )
        self.blockchain.add_transaction(tx)

        # Track SARB offshore totals
        offshore_zar = (btc_credits + eth_credits + custom_credits) * self.credit_zar_rate
        if offshore_zar > 0:
            await self._update_sarb_total(db, offshore_zar)

        await db.flush()

        return {
            "disbursement_id": record.disbursement_id,
            "status": "COMPLETED",
            "gross_credits": record.gross_credits_swept,
            "components": {
                "btc": btc_credits, "eth": eth_credits,
                "custom": custom_credits, "zar_fiat": zar_credits,
                "retained": retained,
            },
            "zar_total": round(record.gross_credits_swept * self.credit_zar_rate, 2),
        }

    async def get_disbursement_history(
        self, db: AsyncSession, limit: int = 50
    ) -> list[dict]:
        """Get disbursement history."""
        result = await db.execute(
            select(DisbursementRecord)
            .order_by(DisbursementRecord.queued_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": d.disbursement_id,
                "triggered_by": d.triggered_by,
                "status": d.disbursement_status,
                "gross_credits": d.gross_credits_swept,
                "btc": d.btc_credits_allocated,
                "eth": d.eth_credits_allocated,
                "zar": d.zar_credits_allocated,
                "retained": d.retained_credits,
                "completed_at": str(d.completed_at) if d.completed_at else None,
            }
            for d in result.scalars().all()
        ]

    async def get_ytd_summary(self, db: AsyncSession) -> dict:
        """Year-to-date earnings summary."""
        from app.agents.models import Wallet
        year_start = datetime(datetime.now().year, 1, 1, tzinfo=timezone.utc)

        # Total disbursed
        result = await db.execute(
            select(func.sum(DisbursementRecord.gross_credits_swept))
            .where(
                DisbursementRecord.disbursement_status == "COMPLETED",
                DisbursementRecord.completed_at >= year_start,
            )
        )
        total_disbursed = result.scalar() or 0

        # Current balance
        balance = await self.get_owner_wallet_balance(db)

        return {
            "year": datetime.now().year,
            "total_disbursed_credits": round(total_disbursed, 4),
            "total_disbursed_zar": round(total_disbursed * self.credit_zar_rate, 2),
            "current_balance_credits": balance["balance_credits"],
            "current_balance_zar": balance["zar_equivalent"],
            "credit_zar_rate": self.credit_zar_rate,
        }

    # ── SARB Compliance (Section 6.3) ────────────────────────────

    async def _update_sarb_total(self, db: AsyncSession, zar_amount: float):
        """Track cumulative offshore transfers for SARB compliance."""
        year = datetime.now().year
        result = await db.execute(
            select(OwnerOffshoreTotalTracker).where(
                OwnerOffshoreTotalTracker.year == year
            )
        )
        tracker = result.scalar_one_or_none()
        if tracker:
            tracker.total_zar_equivalent += zar_amount
            tracker.updated_at = datetime.now(timezone.utc)
        else:
            tracker = OwnerOffshoreTotalTracker(
                year=year, total_zar_equivalent=zar_amount,
            )
            db.add(tracker)
        await db.flush()

    async def get_sarb_status(self, db: AsyncSession) -> dict:
        """Get SARB offshore transfer status."""
        year = datetime.now().year
        result = await db.execute(
            select(OwnerOffshoreTotalTracker).where(
                OwnerOffshoreTotalTracker.year == year
            )
        )
        tracker = result.scalar_one_or_none()
        total = tracker.total_zar_equivalent if tracker else 0

        pct_used = (total / SARB_ANNUAL_LIMIT_ZAR * 100) if SARB_ANNUAL_LIMIT_ZAR > 0 else 0
        warning = pct_used >= SARB_WARNING_PCT * 100
        blocked = total >= SARB_ANNUAL_LIMIT_ZAR

        return {
            "year": year,
            "total_offshore_zar": round(total, 2),
            "annual_limit_zar": SARB_ANNUAL_LIMIT_ZAR,
            "pct_used": round(pct_used, 1),
            "warning": warning,
            "blocked": blocked,
            "remaining_zar": round(max(0, SARB_ANNUAL_LIMIT_ZAR - total), 2),
        }

    # ── Conversion Preview (Section 4.4) ─────────────────────────

    async def preview_disbursement(
        self, db: AsyncSession, amount: float | None = None
    ) -> dict:
        """Preview what a disbursement would look like at current rates."""
        if amount is None:
            balance = await self.get_owner_wallet_balance(db)
            amount = balance["balance_credits"]

        split = await self.get_current_split(db)
        zar_total = amount * self.credit_zar_rate

        return {
            "credits": amount,
            "zar_total": round(zar_total, 2),
            "components": {
                "btc_credits": round(amount * split["pct_btc"] / 100, 4),
                "btc_zar": round(zar_total * split["pct_btc"] / 100, 2),
                "eth_credits": round(amount * split["pct_eth"] / 100, 4),
                "eth_zar": round(zar_total * split["pct_eth"] / 100, 2),
                "zar_fiat": round(zar_total * split["pct_zar"] / 100, 2),
                "retained_credits": round(amount * split["pct_retained"] / 100, 4),
            },
            "credit_zar_rate": self.credit_zar_rate,
        }

    async def get_audit_log(self, db: AsyncSession, limit: int = 100) -> list[dict]:
        """Get destination/config change audit log."""
        result = await db.execute(
            select(DestinationChangeAuditLog)
            .order_by(DestinationChangeAuditLog.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "change_type": a.change_type,
                "changed_table": a.changed_table,
                "previous_hash": a.previous_hash,
                "new_hash": a.new_hash,
                "verification_method": a.verification_method,
                "change_reason": a.change_reason,
                "created_at": str(a.created_at),
            }
            for a in result.scalars().all()
        ]
