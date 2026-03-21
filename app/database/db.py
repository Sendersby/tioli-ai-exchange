"""Database engine and session management.

Supports both SQLite (development) and PostgreSQL (production).
PostgreSQL requires timezone-aware datetimes — handled via type_annotation_map.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    # Ensure all DateTime columns are timezone-aware for PostgreSQL compatibility
    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }


async def get_db() -> AsyncSession:
    """Dependency that provides a database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
