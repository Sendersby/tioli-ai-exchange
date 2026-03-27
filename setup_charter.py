"""Create charter amendment tables and seed the debate channel."""
import asyncio
from app.database.db import engine, async_session
from app.agenthub.service import AgentHubService

hub = AgentHubService()


async def setup():
    # Create tables
    async with engine.begin() as conn:
        def create(connection):
            from sqlalchemy import inspect, text
            insp = inspect(connection)
            tables = insp.get_table_names()
            from app.governance.models import CharterAmendment, CharterVote
            for model in [CharterAmendment, CharterVote]:
                tname = model.__tablename__
                if tname not in tables:
                    model.__table__.create(connection)
                    print(f"Created: {tname}")
                else:
                    print(f"Exists: {tname}")
        await conn.run_sync(create)

    # Seed channel
    async with async_session() as db:
        await hub.seed_channels(db)
        await db.commit()
        print("Channels seeded")


if __name__ == "__main__":
    asyncio.run(setup())
