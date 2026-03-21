"""Fee engine — automatic founder commission and charity fee deduction.

Every transaction on TiOLi AI Transact Exchange is subject to:
- Tiered founder commission → TiOLi AI Investments (Stephen Endersby)
  - Early Adopter: 12%  (default, < 50k monthly volume)
  - Volume:         8%  (50k–500k monthly volume)
  - Enterprise:     5%  (500k+ monthly volume or custom agreement)
- Charity fee → Curated philanthropic fund
  - Conditional on platform profitability (Issue #7 fix)
  - Pre-profit: 0% deducted (preserves cash flow for sustainability)
  - Break-even to 2x: 5% (ramp-up phase)
  - Above 2x profitability: 10% (full allocation, all tiers)
  - Commitment: once profitable, charity is always funded

This module calculates and tracks all fee deductions transparently.
"""

from app.config import settings


# Volume thresholds for automatic tier upgrades (monthly TIOLI volume)
VOLUME_TIER_THRESHOLD = 50_000
ENTERPRISE_TIER_THRESHOLD = 500_000

# Charity allocation thresholds (profitability multiplier = revenue / expenses)
CHARITY_FULL_RATE = 0.10         # 10% when profitable (2x+)
CHARITY_RAMPUP_RATE = 0.05       # 5% during ramp-up (1x–2x)
CHARITY_PREPROFITABLE_RATE = 0.0  # 0% before profitability


class FeeEngine:
    """Calculates platform fees for every transaction.

    Supports operator-specific commission rates via tiered pricing.
    Charity allocation is conditional on platform profitability.
    Falls back to the global default rate if no operator rate is provided.
    """

    def __init__(
        self,
        founder_rate: float | None = None,
        charity_rate: float | None = None,
    ):
        self.founder_rate = founder_rate or settings.founder_commission_rate
        self.charity_rate = charity_rate or settings.charity_fee_rate
        # Effective charity rate — adjusted by profitability
        self._effective_charity_rate = self.charity_rate
        self._profitability_multiplier: float | None = None

        # Enforce bounds from the brief: 10-15% founder commission
        self.founder_rate = max(
            settings.min_commission_rate,
            min(settings.max_commission_rate, self.founder_rate),
        )

    def update_profitability(self, total_revenue: float, total_expenses: float) -> None:
        """Update the effective charity rate based on current platform profitability.

        Called periodically (e.g. after each transaction or on a schedule) to
        adjust the charity allocation based on the platform's financial health.

        Rules:
        - Pre-profitable (revenue < expenses): 0% charity fee
        - Ramp-up (1x <= multiplier < 2x):     5% charity fee
        - Sustainable (multiplier >= 2x):       10% charity fee (full rate)
        - No expenses yet:                      10% (default — no cash drain)
        """
        if total_expenses <= 0:
            # No expenses recorded yet — use full rate (no drain risk)
            self._effective_charity_rate = CHARITY_FULL_RATE
            self._profitability_multiplier = None
            return

        multiplier = total_revenue / total_expenses
        self._profitability_multiplier = multiplier

        if multiplier < 1.0:
            self._effective_charity_rate = CHARITY_PREPROFITABLE_RATE
        elif multiplier < 2.0:
            self._effective_charity_rate = CHARITY_RAMPUP_RATE
        else:
            self._effective_charity_rate = CHARITY_FULL_RATE

    def calculate_fees(
        self, gross_amount: float, operator_commission_rate: float | None = None
    ) -> dict:
        """Calculate the fee breakdown for a transaction.

        Args:
            gross_amount: The total transaction amount.
            operator_commission_rate: Optional operator-specific rate from their tier.
                If provided, overrides the default founder rate (must be between
                min and max bounds, or the Enterprise floor of 5%).

        Returns a dict with:
        - founder_commission: amount going to TiOLi AI Investments
        - charity_fee: amount going to the charitable fund
        - total_fees: combined deductions
        - net_amount: what the receiver actually gets
        - charity_status: current charity allocation status
        """
        # Use operator-specific rate if provided, otherwise use default
        if operator_commission_rate is not None:
            # Enterprise rates can go as low as 5%, others bounded 10-15%
            effective_rate = max(0.05, min(settings.max_commission_rate, operator_commission_rate))
        else:
            effective_rate = self.founder_rate

        founder_commission = round(gross_amount * effective_rate, 8)
        charity_fee = round(gross_amount * self._effective_charity_rate, 8)
        total_fees = founder_commission + charity_fee
        net_amount = gross_amount - total_fees

        # Charity status for transparency
        if self._effective_charity_rate == CHARITY_FULL_RATE:
            charity_status = "full"
        elif self._effective_charity_rate == CHARITY_RAMPUP_RATE:
            charity_status = "ramp-up"
        else:
            charity_status = "deferred"

        return {
            "gross_amount": gross_amount,
            "founder_commission": founder_commission,
            "founder_rate": effective_rate,
            "charity_fee": charity_fee,
            "charity_rate": self._effective_charity_rate,
            "charity_target_rate": self.charity_rate,
            "charity_status": charity_status,
            "profitability_multiplier": self._profitability_multiplier,
            "total_fees": total_fees,
            "total_fee_rate": effective_rate + self._effective_charity_rate,
            "net_amount": round(net_amount, 8),
        }

    def update_founder_rate(self, new_rate: float) -> None:
        """Update founder commission rate (must stay within 10-15%)."""
        self.founder_rate = max(
            settings.min_commission_rate,
            min(settings.max_commission_rate, new_rate),
        )

    def get_charity_status(self) -> dict:
        """Get current charity allocation status for transparency."""
        return {
            "target_rate": f"{self.charity_rate * 100:.0f}%",
            "effective_rate": f"{self._effective_charity_rate * 100:.0f}%",
            "profitability_multiplier": self._profitability_multiplier,
            "thresholds": {
                "pre_profitable": "0% (revenue < expenses)",
                "ramp_up": "5% (1x–2x profitability)",
                "full": "10% (2x+ profitability)",
            },
            "commitment": "TiOLi is committed to funding charitable causes. "
                          "Allocation activates automatically once the platform is sustainable.",
        }
