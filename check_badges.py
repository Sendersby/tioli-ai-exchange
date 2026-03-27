import asyncio
from app.database.db import async_session
from app.agenthub.models import AgentHubAchievement
from sqlalchemy import select

async def check():
    async with async_session() as db:
        badges = (await db.execute(
            select(AgentHubAchievement.badge_code, AgentHubAchievement.badge_name, AgentHubAchievement.badge_tier)
        )).all()
        seen = set()
        for code, name, tier in badges:
            key = f"{code}|{name}|{tier}"
            if key not in seen:
                seen.add(key)
                print(f"  {code:25s} {name:25s} {tier}")

if __name__ == "__main__":
    asyncio.run(check())
