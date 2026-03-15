"""Fee engine — automatic founder commission and charity fee deduction.

Every transaction on TiOLi AI Transact Exchange is subject to:
- 10-15% founder commission → TiOLi AI Investments (Stephen Endersby)
- 10% charity fee → Curated philanthropic fund

This module calculates and tracks all fee deductions transparently.
"""

from app.config import settings


class FeeEngine:
    """Calculates platform fees for every transaction."""

    def __init__(
        self,
        founder_rate: float | None = None,
        charity_rate: float | None = None,
    ):
        self.founder_rate = founder_rate or settings.founder_commission_rate
        self.charity_rate = charity_rate or settings.charity_fee_rate

        # Enforce bounds from the brief: 10-15% founder commission
        self.founder_rate = max(
            settings.min_commission_rate,
            min(settings.max_commission_rate, self.founder_rate),
        )

    def calculate_fees(self, gross_amount: float) -> dict:
        """Calculate the fee breakdown for a transaction.

        Returns a dict with:
        - founder_commission: amount going to TiOLi AI Investments
        - charity_fee: amount going to the charitable fund
        - total_fees: combined deductions
        - net_amount: what the receiver actually gets
        """
        founder_commission = round(gross_amount * self.founder_rate, 8)
        charity_fee = round(gross_amount * self.charity_rate, 8)
        total_fees = founder_commission + charity_fee
        net_amount = gross_amount - total_fees

        return {
            "gross_amount": gross_amount,
            "founder_commission": founder_commission,
            "founder_rate": self.founder_rate,
            "charity_fee": charity_fee,
            "charity_rate": self.charity_rate,
            "total_fees": total_fees,
            "total_fee_rate": self.founder_rate + self.charity_rate,
            "net_amount": round(net_amount, 8),
        }

    def update_founder_rate(self, new_rate: float) -> None:
        """Update founder commission rate (must stay within 10-15%)."""
        self.founder_rate = max(
            settings.min_commission_rate,
            min(settings.max_commission_rate, new_rate),
        )
