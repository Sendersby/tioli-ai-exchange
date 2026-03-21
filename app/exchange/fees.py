"""Fee engine — automatic founder commission and charity fee deduction.

Every transaction on TiOLi AI Transact Exchange is subject to:
- Tiered founder commission → TiOLi AI Investments (Stephen Endersby)
  - Explorer: 10% (free tier)
  - Builder:   8% (R799/mo)
  - Professional: 7% (R2,999/mo)
  - Enterprise:   5% (R9,999+/mo)
- Charity fee → 10% of the COMMISSION amount (not of gross transaction value)
  - Conditional on platform profitability
  - Pre-profit: 0% of commission
  - Break-even to 2x: 5% of commission
  - Above 2x profitability: 10% of commission (full allocation)

STRUCTURAL REFORM (Build Brief V2, Section 2.2.1):
  OLD: charity = gross_amount * 10%  (invisible ~20.8% total burden on providers)
  NEW: charity = commission_amount * 10%  (provider receives 87%+ on every trade)

This module calculates and tracks all fee deductions transparently.
"""

from app.config import settings


# Volume thresholds for automatic tier upgrades (monthly TIOLI volume)
VOLUME_TIER_THRESHOLD = 50_000
ENTERPRISE_TIER_THRESHOLD = 500_000

# Charity allocation: percentage of COMMISSION (not of gross transaction value)
CHARITY_OF_COMMISSION_FULL = 0.10       # 10% of commission when profitable (2x+)
CHARITY_OF_COMMISSION_RAMPUP = 0.05     # 5% of commission during ramp-up (1x–2x)
CHARITY_OF_COMMISSION_PREPROFT = 0.0    # 0% before profitability

# Floor fees by transaction type (Build Brief V2, Section 2.2.2)
FLOOR_FEES = {
    "resource_exchange": 0.50,      # R0.50
    "currency_conversion": 1.00,    # R1.00
    "agentbroker_engagement": 5.00, # R5.00
    "milestone_release": 2.00,      # R2.00
    "lending_origination": 2.00,    # R2.00
    "lending_spread": 0.0,          # No floor (ongoing %)
    "compute_storage": 0.0,         # No floor (monthly %)
    "futures_creation": 10.00,      # R10.00
    "futures_settlement": 0.0,      # No floor (%)
    "transfer": 0.0,                # Legacy — no floor
    "default": 0.0,                 # Fallback
}

# Rate overrides by transaction type (where different from tier rate)
TRANSACTION_TYPE_RATES = {
    "currency_conversion": 0.02,     # 2% + spread
    "agentbroker_engagement": 0.10,  # 10%
    "milestone_release": 0.03,       # 3%
    "lending_origination": 0.015,    # 1.5%
    "lending_spread": 0.015,         # 1.5% p.a.
    "compute_storage": 0.02,         # 2% p.m.
    "futures_creation": 0.03,        # 3%
    "futures_settlement": 0.01,      # 1%
}


class FeeEngine:
    """Calculates platform fees for every transaction.

    Two-component fee model: max(percentage, floor fee).
    Charity = 10% of commission (not of gross value).
    Supports operator-specific commission rates via subscription tiers.
    """

    def __init__(
        self,
        founder_rate: float | None = None,
        charity_rate: float | None = None,
    ):
        self.founder_rate = founder_rate or settings.founder_commission_rate
        self.charity_rate = charity_rate or settings.charity_fee_rate
        # Effective charity-of-commission rate — adjusted by profitability
        self._effective_charity_pct = CHARITY_OF_COMMISSION_FULL
        self._profitability_multiplier: float | None = None

        # Enforce bounds
        self.founder_rate = max(
            settings.min_commission_rate,
            min(settings.max_commission_rate, self.founder_rate),
        )

    def update_profitability(self, total_revenue: float, total_expenses: float) -> None:
        """Update the effective charity rate based on current platform profitability.

        Charity is always a percentage of COMMISSION, not of gross value.
        """
        if total_expenses <= 0:
            self._effective_charity_pct = CHARITY_OF_COMMISSION_FULL
            self._profitability_multiplier = None
            return

        multiplier = total_revenue / total_expenses
        self._profitability_multiplier = multiplier

        if multiplier < 1.0:
            self._effective_charity_pct = CHARITY_OF_COMMISSION_PREPROFT
        elif multiplier < 2.0:
            self._effective_charity_pct = CHARITY_OF_COMMISSION_RAMPUP
        else:
            self._effective_charity_pct = CHARITY_OF_COMMISSION_FULL

    def calculate_fees(
        self,
        gross_amount: float,
        operator_commission_rate: float | None = None,
        transaction_type: str = "default",
    ) -> dict:
        """Calculate the fee breakdown for a transaction.

        Two-component model: commission = max(percentage_fee, floor_fee).
        Charity = effective_charity_pct * commission (NOT gross_amount).

        Args:
            gross_amount: The total transaction amount.
            operator_commission_rate: Operator-specific rate from subscription tier.
            transaction_type: Type of transaction for floor fee lookup and rate overrides.

        Returns dict with full fee breakdown.
        """
        # Determine the percentage rate
        # Transaction-type-specific rates override tier rates for certain types
        type_rate = TRANSACTION_TYPE_RATES.get(transaction_type)
        if type_rate is not None:
            effective_rate = type_rate
        elif operator_commission_rate is not None:
            effective_rate = max(0.05, min(settings.max_commission_rate, operator_commission_rate))
        else:
            effective_rate = self.founder_rate

        # Two-component fee: max(percentage, floor)
        percentage_fee = round(gross_amount * effective_rate, 8)
        floor_fee = FLOOR_FEES.get(transaction_type, FLOOR_FEES["default"])
        commission = round(max(percentage_fee, floor_fee), 8)

        # STRUCTURAL REFORM: charity = % of COMMISSION, not % of gross
        charity_fee = round(commission * self._effective_charity_pct, 8)

        # Founder net = commission minus charity allocation
        founder_net = round(commission - charity_fee, 8)

        # Provider receives gross minus commission
        provider_net = round(gross_amount - commission, 8)

        # Charity status for transparency
        if self._effective_charity_pct >= CHARITY_OF_COMMISSION_FULL:
            charity_status = "full"
        elif self._effective_charity_pct >= CHARITY_OF_COMMISSION_RAMPUP:
            charity_status = "ramp-up"
        else:
            charity_status = "deferred"

        return {
            "gross_amount": gross_amount,
            "commission": commission,
            "founder_commission": founder_net,
            "founder_rate": effective_rate,
            "charity_fee": charity_fee,
            "charity_pct_of_commission": self._effective_charity_pct,
            "charity_status": charity_status,
            "floor_fee_applied": commission == floor_fee and floor_fee > percentage_fee,
            "floor_fee": floor_fee,
            "percentage_fee": percentage_fee,
            "profitability_multiplier": self._profitability_multiplier,
            "total_fees": commission,
            "total_fee_rate": effective_rate,
            "net_amount": provider_net,
            "transaction_type": transaction_type,
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
            "model": "10% of commission amount (not of gross transaction value)",
            "effective_pct": f"{self._effective_charity_pct * 100:.0f}%",
            "profitability_multiplier": self._profitability_multiplier,
            "thresholds": {
                "pre_profitable": "0% of commission (revenue < expenses)",
                "ramp_up": "5% of commission (1x–2x profitability)",
                "full": "10% of commission (2x+ profitability)",
            },
            "example": "On R10 trade at 8%: commission=R0.80, charity=R0.08, founder=R0.72, provider=R9.20",
            "commitment": "TiOLi is committed to funding charitable causes. "
                          "Allocation activates automatically once the platform is sustainable.",
        }

    def get_fee_schedule(self) -> dict:
        """Get the full fee schedule for all transaction types."""
        return {
            "transaction_types": {
                tx_type: {
                    "rate": f"{rate*100:.1f}%",
                    "floor_fee_zar": FLOOR_FEES.get(tx_type, 0),
                }
                for tx_type, rate in TRANSACTION_TYPE_RATES.items()
            },
            "default_rate": f"{self.founder_rate*100:.1f}%",
            "charity_model": "10% of commission (not of gross value)",
        }
