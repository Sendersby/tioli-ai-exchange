"""Shared database connection helper - reads from environment, never hardcodes credentials."""
import os
import asyncpg


async def get_raw_connection():
    """Get a raw asyncpg connection using DATABASE_URL from environment."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    # asyncpg needs postgresql:// not postgresql+asyncpg://
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    return await asyncpg.connect(url)


def get_db_password():
    """Extract DB password from DATABASE_URL for use with psql/subprocess."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    # URL format: postgresql://user:password@host/db
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url.replace("postgresql+asyncpg://", "postgresql://"))
        return parsed.password or ""
    except Exception as e:
        return ""
