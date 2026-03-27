import asyncio
from app.database.db import async_session
from app.founding_cohort.models import FoundingCohortApplication, MAX_FOUNDING_SPOTS
from sqlalchemy import select, func

async def c():
    async with async_session() as db:
        count = (await db.execute(select(func.count(FoundingCohortApplication.application_id)))).scalar() or 0
        print(f"Applications: {count}")
        print(f"Max spots: {MAX_FOUNDING_SPOTS}")
        print(f"Remaining: {MAX_FOUNDING_SPOTS - count}")

if __name__ == "__main__":
    asyncio.run(c())
