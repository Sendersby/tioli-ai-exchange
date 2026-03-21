"""Cross-Border settlement service — SARB compliance and currency normalisation."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.crossborder.models import InternationalSettlement, SARB_SDA_ANNUAL_LIMIT_ZAR

logger = logging.getLogger(__name__)

SARB_WARNING_THRESHOLD_PCT = 0.90  # Warn at 90%


class CrossBorderService:
    """Manages international settlements with SARB compliance."""

    async def create_settlement(
        self, db: AsyncSession, engagement_id: str,
        buyer_currency: str, buyer_amount: float,
        zar_equivalent: float, exchange_rate: float,
        operator_id: str,
    ) -> dict:
        """Create an international settlement record with SARB limit check."""
        year = datetime.now(timezone.utc).year

        # Get cumulative SDA for this year
        cumulative_result = await db.execute(
            select(func.sum(InternationalSettlement.zar_equivalent)).where(
                InternationalSettlement.sarb_sda_year == year,
                InternationalSettlement.blocked_by_sarb == False,
            )
        )
        cumulative = cumulative_result.scalar() or 0.0
        new_cumulative = cumulative + zar_equivalent

        # SARB limit check
        blocked = new_cumulative > SARB_SDA_ANNUAL_LIMIT_ZAR
        warning = new_cumulative > SARB_SDA_ANNUAL_LIMIT_ZAR * SARB_WARNING_THRESHOLD_PCT

        settlement = InternationalSettlement(
            engagement_id=engagement_id,
            buyer_currency=buyer_currency,
            buyer_amount=buyer_amount,
            zar_equivalent=zar_equivalent,
            exchange_rate=exchange_rate,
            sarb_sda_year=year,
            sarb_cumulative_this_year=new_cumulative,
            blocked_by_sarb=blocked,
        )
        db.add(settlement)
        await db.flush()

        result = {
            "settlement_id": settlement.id,
            "engagement_id": engagement_id,
            "buyer_currency": buyer_currency,
            "buyer_amount": buyer_amount,
            "zar_equivalent": zar_equivalent,
            "exchange_rate": exchange_rate,
            "sarb_cumulative_this_year": new_cumulative,
            "sarb_limit": SARB_SDA_ANNUAL_LIMIT_ZAR,
            "sarb_remaining": max(0, SARB_SDA_ANNUAL_LIMIT_ZAR - new_cumulative),
            "blocked_by_sarb": blocked,
        }

        if blocked:
            result["sarb_message"] = "BLOCKED: Annual SDA limit of R1,000,000 exceeded."
            logger.warning(f"SARB SDA limit exceeded for engagement {engagement_id}")
        elif warning:
            result["sarb_message"] = f"WARNING: At {new_cumulative/SARB_SDA_ANNUAL_LIMIT_ZAR*100:.0f}% of annual SDA limit."

        return result

    async def get_sarb_status(self, db: AsyncSession) -> dict:
        """Current year SDA usage, limit, remaining."""
        year = datetime.now(timezone.utc).year
        cumulative_result = await db.execute(
            select(func.sum(InternationalSettlement.zar_equivalent)).where(
                InternationalSettlement.sarb_sda_year == year,
                InternationalSettlement.blocked_by_sarb == False,
            )
        )
        cumulative = cumulative_result.scalar() or 0.0
        remaining = max(0, SARB_SDA_ANNUAL_LIMIT_ZAR - cumulative)

        return {
            "year": year,
            "cumulative_zar": round(cumulative, 2),
            "limit_zar": SARB_SDA_ANNUAL_LIMIT_ZAR,
            "remaining_zar": round(remaining, 2),
            "utilisation_pct": round(cumulative / SARB_SDA_ANNUAL_LIMIT_ZAR * 100, 1),
            "blocked": cumulative >= SARB_SDA_ANNUAL_LIMIT_ZAR,
        }
