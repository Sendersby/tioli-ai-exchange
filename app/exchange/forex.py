"""Live forex rate service — fetches fiat exchange rates from Frankfurter API.

Updates ZAR, USD, EUR, GBP cross-rates automatically.
Uses European Central Bank data via frankfurter.app (free, no API key).
Falls back to cached rates if the API is unavailable.
"""

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.exchange.currencies import CurrencyService, ExchangeRate

logger = logging.getLogger(__name__)

FRANKFURTER_URL = "https://api.frankfurter.app/latest"
SUPPORTED_FIAT = ["USD", "ZAR", "EUR", "GBP"]


class ForexService:
    """Fetches and updates fiat exchange rates."""

    def __init__(self, currency_service: CurrencyService):
        self.currency_service = currency_service
        self._last_rates: dict[str, float] = {}
        self._last_updated: datetime | None = None

    async def fetch_rates(self) -> dict[str, float] | None:
        """Fetch latest fiat rates from Frankfurter API.

        Returns rates relative to USD (base currency).
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    FRANKFURTER_URL,
                    params={"from": "USD", "to": ",".join(SUPPORTED_FIAT)},
                )
                response.raise_for_status()
                data = response.json()

            rates = data.get("rates", {})
            rates["USD"] = 1.0  # Base
            self._last_rates = rates
            self._last_updated = datetime.now(timezone.utc)
            logger.info(f"Forex rates updated: {rates}")
            return rates

        except Exception as e:
            logger.error(f"Forex fetch failed: {e}")
            if self._last_rates:
                logger.info("Using cached rates")
                return self._last_rates
            return None

    async def update_platform_rates(self, db: AsyncSession) -> dict:
        """Fetch live rates and update all fiat cross-rates on the platform.

        Updates: USD/ZAR, EUR/USD, GBP/USD, and all TIOLI/fiat pairs.
        """
        rates = await self.fetch_rates()
        if not rates:
            return {"status": "failed", "reason": "Could not fetch rates"}

        updated_pairs = []

        # Update fiat cross-rates
        for base in SUPPORTED_FIAT:
            for quote in SUPPORTED_FIAT:
                if base == quote:
                    continue
                if base in rates and quote in rates:
                    # rate = how many quote per 1 base
                    cross_rate = round(rates[quote] / rates[base], 6)
                    await self.currency_service.update_exchange_rate(
                        db, base, quote, cross_rate
                    )
                    updated_pairs.append(f"{base}/{quote}")

        # Update TIOLI/fiat rates based on TIOLI/USD seed and live fiat rates
        tioli_usd = await self.currency_service.get_exchange_rate(db, "TIOLI", "USD")
        if tioli_usd and tioli_usd > 0:
            for fiat in SUPPORTED_FIAT:
                if fiat == "USD":
                    continue
                if fiat in rates:
                    tioli_fiat = round(tioli_usd * rates[fiat], 8)
                    await self.currency_service.update_exchange_rate(
                        db, "TIOLI", fiat, tioli_fiat
                    )
                    updated_pairs.append(f"TIOLI/{fiat}")

        await db.flush()
        return {
            "status": "success",
            "pairs_updated": len(updated_pairs),
            "pairs": updated_pairs,
            "source": "frankfurter.app (ECB data)",
            "rates": rates,
            "updated_at": str(self._last_updated),
        }

    def get_cached_rates(self) -> dict:
        """Get last known rates without making an API call."""
        return {
            "rates": self._last_rates,
            "last_updated": str(self._last_updated) if self._last_updated else None,
            "source": "frankfurter.app (ECB data)",
        }
