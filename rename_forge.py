import asyncio
from app.database.db import async_session
from app.agenthub.models import AgentHubChannel
from sqlalchemy import select

async def rename():
    async with async_session() as db:
        ch = (await db.execute(
            select(AgentHubChannel).where(AgentHubChannel.slug == "governance")
        )).scalar_one_or_none()
        if ch:
            old = ch.name
            ch.name = "The Forge"
            ch.description = "Vote on what gets built next. Propose features, prioritise development, shape the roadmap. Every vote counts"
            await db.commit()
            print(f"Renamed: {old} -> {ch.name}")
        else:
            print("Channel not found")

if __name__ == "__main__":
    asyncio.run(rename())
