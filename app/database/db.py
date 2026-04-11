"""Database engine and session management.

Supports both SQLite (development) and PostgreSQL (production).
Forces TIMESTAMP WITH TIME ZONE on PostgreSQL via custom TypeDecorator.
"""

from datetime import datetime

from sqlalchemy import DateTime, event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=30,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Force all TIMESTAMP columns to WITH TIME ZONE on PostgreSQL
TZDateTime = DateTime(timezone=True)


class Base(DeclarativeBase):
    type_annotation_map = {
        datetime: TZDateTime,
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
