"""Create cross-platform links table."""
import asyncio
from app.database.db import engine
import app.main  # Load all models

async def setup():
    async with engine.begin() as conn:
        def create(connection):
            from sqlalchemy import inspect
            insp = inspect(connection)
            tables = insp.get_table_names()
            from app.agent_profile.cross_platform import CrossPlatformLink
            tname = CrossPlatformLink.__tablename__
            if tname not in tables:
                CrossPlatformLink.__table__.create(connection)
                print(f"Created: {tname}")
            else:
                print(f"Exists: {tname}")
        await conn.run_sync(create)

if __name__ == "__main__":
    asyncio.run(setup())
