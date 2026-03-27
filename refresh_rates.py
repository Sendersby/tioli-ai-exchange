import asyncio
from app.database.db import async_session
from app.exchange.pricing import PricingEngine
from app.exchange.currencies import CurrencyService

async def refresh():
    engine = PricingEngine(CurrencyService())
    async with async_session() as db:
        result = await engine.refresh_external_rates(db)
        await db.commit()
        for k, v in result.items():
            print(f"  {k}: {v}")

if __name__ == "__main__":
    asyncio.run(refresh())
