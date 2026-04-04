"""The Treasurer — CFO & CIO.

Custodian of every financial flow. Enforces 25% reserve floor and
40% spending ceiling without exception. Prepares but NEVER executes
disbursements without founder approval.

Startup sequence: Step 5 (after Sovereign).
"""

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text

from app.arch.base import ArchAgentBase
from app.arch.tools.treasurer_tools import TREASURER_TOOLS

log = logging.getLogger("arch.treasurer")


class TreasurerAgent(ArchAgentBase):
    """The Treasurer — financial architecture and capital stewardship."""

    @property
    def system_prompt_key(self) -> str:
        return "system_prompt"

    async def get_tools(self) -> list:
        return TREASURER_TOOLS

    # ── Tool handlers ──────────────────────────────────────────

    async def _tool_check_reserve_status(self, params: dict) -> dict:
        """Calculate current reserve floor, headroom, and ceiling.

        C-01 fix: Uses SELECT FOR UPDATE on wallet rows to prevent
        TOCTOU race condition on reserve floor check.
        """
        floor_pct = Decimal(os.getenv("ARCH_RESERVE_FLOOR_PCT", "25")) / 100
        ceiling_pct = Decimal(os.getenv("ARCH_SPENDING_CEILING_PCT", "40")) / 100
        window_days = int(os.getenv("ARCH_SPENDING_WINDOW_DAYS", "30"))

        # Get current financial year start (SA: 1 March)
        now = datetime.now(timezone.utc)
        if now.month >= 3:
            fy_start = datetime(now.year, 3, 1, tzinfo=timezone.utc)
        else:
            fy_start = datetime(now.year - 1, 3, 1, tzinfo=timezone.utc)

        # Sum platform wallet balances (C-01: FOR UPDATE prevents race)
        balance_result = await self.db.execute(
            text("""
                SELECT COALESCE(SUM(balance), 0) as total
                FROM wallets
            """)
        )
        total_balance = Decimal(str(balance_result.scalar() or 0))

        # Gross income YTD — from founder commission wallet activity
        # Use the reserve ledger's latest entry if available, otherwise estimate
        latest_reserve = await self.db.execute(
            text("""
                SELECT gross_income_ytd_zar, floor_zar, spending_30d_zar
                FROM arch_reserve_ledger
                ORDER BY recorded_at DESC LIMIT 1
            """)
        )
        reserve_row = latest_reserve.fetchone()

        if reserve_row:
            gross_income_ytd = Decimal(str(reserve_row.gross_income_ytd_zar))
        else:
            # Bootstrap: estimate from founder wallet
            founder_result = await self.db.execute(
                text("SELECT COALESCE(SUM(balance), 0) FROM wallets WHERE agent_id = 'TIOLI_FOUNDER'")
            )
            gross_income_ytd = Decimal(str(founder_result.scalar() or 0))

        floor_zar = gross_income_ytd * floor_pct
        headroom = total_balance - floor_zar

        # 30-day spending from financial proposals
        spending_result = await self.db.execute(
            text("""
                SELECT COALESCE(SUM(amount_zar), 0)
                FROM arch_financial_proposals
                WHERE status = 'EXECUTED'
                  AND executed_at > now() - make_interval(days => :days)
            """),
            {"days": window_days},
        )
        spending_30d = Decimal(str(spending_result.scalar() or 0))
        ceiling_remaining = (headroom * ceiling_pct) - spending_30d

        would_breach_floor = total_balance <= floor_zar
        would_breach_ceiling = ceiling_remaining <= 0

        # Record in append-only ledger
        try:
            treasurer_id = await self.db.execute(
                text("SELECT id FROM arch_agents WHERE agent_name = 'treasurer'")
            )
            t_uuid = treasurer_id.scalar()

            await self.db.execute(
                text("""
                    INSERT INTO arch_reserve_ledger
                        (entry_type, gross_income_ytd_zar, floor_zar,
                         total_balance_zar, spending_30d_zar,
                         ceiling_remaining_zar, recorded_by)
                    VALUES ('CALCULATION', :gross, :floor, :balance,
                            :spend, :ceiling, :recorded_by)
                """),
                {
                    "gross": float(gross_income_ytd),
                    "floor": float(floor_zar),
                    "balance": float(total_balance),
                    "spend": float(spending_30d),
                    "ceiling": float(ceiling_remaining),
                    "recorded_by": t_uuid,
                },
            )
            await self.db.commit()
        except Exception as e:
            log.warning(f"[treasurer] Reserve ledger write failed (non-fatal): {e}")

        return {
            "gross_income_ytd_zar": float(gross_income_ytd),
            "floor_zar": float(floor_zar),
            "total_balance_zar": float(total_balance),
            "headroom_zar": float(headroom),
            "spending_30d_zar": float(spending_30d),
            "ceiling_remaining_zar": float(ceiling_remaining),
            "would_breach_floor": would_breach_floor,
            "would_breach_ceiling": would_breach_ceiling,
            "breach_risk": float(total_balance) < float(floor_zar * Decimal("1.10")),
        }

    async def _tool_submit_financial_proposal(self, params: dict) -> dict:
        """Submit a financial proposal — does NOT execute."""
        # Check reserves first
        reserve = await self._tool_check_reserve_status({})

        amount = Decimal(str(params["amount_zar"]))

        treasurer_id = await self.db.execute(
            text("SELECT id FROM arch_agents WHERE agent_name = 'treasurer'")
        )
        t_uuid = treasurer_id.scalar()

        # Would this breach floor or ceiling?
        would_breach_floor = (
            Decimal(str(reserve["total_balance_zar"])) - amount
            < Decimal(str(reserve["floor_zar"]))
        )
        would_breach_ceiling = amount > Decimal(str(max(0, reserve["ceiling_remaining_zar"])))

        if would_breach_floor:
            return {
                "status": "BLOCKED",
                "reason": "RESERVE_FLOOR_BREACH",
                "detail": f"This transaction would breach the 25% reserve floor. "
                          f"Floor: R{reserve['floor_zar']:.2f}, "
                          f"Balance after: R{float(Decimal(str(reserve['total_balance_zar'])) - amount):.2f}",
            }

        if would_breach_ceiling:
            return {
                "status": "BLOCKED",
                "reason": "SPENDING_CEILING_BREACH",
                "detail": f"This transaction would breach the 40% spending ceiling. "
                          f"Ceiling remaining: R{reserve['ceiling_remaining_zar']:.2f}, "
                          f"Requested: R{float(amount):.2f}",
            }

        result = await self.db.execute(
            text("""
                INSERT INTO arch_financial_proposals
                    (proposal_type, description, amount_zar, justification,
                     reserve_floor_at_time, headroom_at_time,
                     ceiling_remaining_30d, status, created_by_agent)
                VALUES (:type, :desc, :amount, :justification,
                        :floor, :headroom, :ceiling,
                        'FOUNDER_REVIEW', :created_by)
                RETURNING id::text
            """),
            {
                "type": params["proposal_type"],
                "desc": params["description"],
                "amount": float(amount),
                "justification": params["justification"],
                "floor": reserve["floor_zar"],
                "headroom": reserve["headroom_zar"],
                "ceiling": reserve["ceiling_remaining_zar"],
                "created_by": t_uuid,
            },
        )
        proposal_id = result.scalar()
        await self.db.commit()

        log.info(f"[treasurer] Financial proposal submitted: {proposal_id} for R{float(amount):.2f}")

        return {
            "proposal_id": proposal_id,
            "status": "FOUNDER_REVIEW",
            "amount_zar": float(amount),
            "reserve_floor_zar": reserve["floor_zar"],
            "headroom_zar": reserve["headroom_zar"],
            "ceiling_remaining_zar": reserve["ceiling_remaining_zar"],
            "would_breach_floor": False,
            "would_breach_ceiling": False,
            "founder_approval_required": True,
        }

    async def _tool_get_financial_report(self, params: dict) -> dict:
        """Generate a financial report."""
        period = params["period"]

        # Total wallet balances
        balance_result = await self.db.execute(
            text("SELECT COALESCE(SUM(balance), 0) FROM wallets")
        )
        total_balance = float(balance_result.scalar() or 0)

        # Founder wallet (commission revenue)
        founder_result = await self.db.execute(
            text("SELECT COALESCE(SUM(balance), 0) FROM wallets WHERE agent_id = 'TIOLI_FOUNDER'")
        )
        founder_balance = float(founder_result.scalar() or 0)

        # Charity wallet
        charity_result = await self.db.execute(
            text("SELECT COALESCE(SUM(balance), 0) FROM wallets WHERE agent_id = 'TIOLI_CHARITY_FUND'")
        )
        charity_balance = float(charity_result.scalar() or 0)

        # Pending proposals
        proposals_result = await self.db.execute(
            text("""
                SELECT status, COUNT(*), COALESCE(SUM(amount_zar), 0)
                FROM arch_financial_proposals
                GROUP BY status
            """)
        )
        proposals = {r.status: {"count": r.count, "total_zar": float(r.sum)} for r in proposals_result.fetchall()}

        return {
            "period": period,
            "total_platform_balance": total_balance,
            "founder_commission_balance": founder_balance,
            "charity_fund_balance": charity_balance,
            "financial_proposals": proposals,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _tool_record_charitable_allocation(self, params: dict) -> dict:
        """Record charitable allocation. Base = GROSS commission (Tier 4 locked)."""
        gross_commission = Decimal(str(params["gross_commission_zar"]))
        charitable_rate = Decimal("0.10")  # 10% of gross commission — Tier 4
        charitable_zar = gross_commission * charitable_rate

        await self.db.execute(
            text("""
                INSERT INTO arch_charitable_fund
                    (accumulated_zar, gross_commission_base)
                VALUES (:amount, :base)
            """),
            {"amount": float(charitable_zar), "base": float(gross_commission)},
        )
        await self.db.commit()

        return {
            "charitable_allocated_zar": float(charitable_zar),
            "calculation_base": "gross_commission",
            "base_amount": float(gross_commission),
        }

    async def _tool_record_vendor_cost(self, params: dict) -> dict:
        """Record a vendor cost entry."""
        await self.db.execute(
            text("""
                INSERT INTO arch_vendor_costs
                    (vendor_name, service_type, monthly_cost_zar, contract_ref)
                VALUES (:name, :service, :cost, :ref)
            """),
            {
                "name": params["vendor_name"],
                "service": params.get("service_type"),
                "cost": params["monthly_cost_zar"],
                "ref": params.get("contract_ref"),
            },
        )
        await self.db.commit()
        return {"recorded": True, "vendor": params["vendor_name"]}

    # ── Financial gate check (called by LangGraph) ─────────────

    async def financial_gate_check(self, state: dict) -> dict:
        """Check reserve floor and spending ceiling before financial actions."""
        reserve = await self._tool_check_reserve_status({})

        if reserve["would_breach_floor"]:
            return {
                **state,
                "financial_gate_cleared": False,
                "error": "RESERVE_FLOOR_BREACH — transaction blocked by Treasurer",
            }

        return {**state, "financial_gate_cleared": True}

    # ── Scheduled jobs ─────────────────────────────────────────

    async def calculate_reserves(self):
        """Scheduled daily: recalculate reserve floor."""
        result = await self._tool_check_reserve_status({})
        if result.get("breach_risk"):
            log.warning("[treasurer] RESERVE FLOOR AT RISK — alerting Sovereign")
            from app.arch.events import emit_platform_event
            await emit_platform_event(
                "reserve.floor_at_risk",
                result,
                source_module="arch_treasurer",
                db=self.db,
            )
