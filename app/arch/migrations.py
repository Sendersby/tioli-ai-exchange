"""Arch Agent database migrations — all tables, views, triggers, indexes.

Run via: await run_arch_migrations(db)
All additive — no existing tables modified.
"""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("arch.migrations")

ARCH_DDL = """-- Schema managed by Alembic -- see alembic/versions/92d379a512fc"""


async def run_arch_migrations(db: AsyncSession):
    """No-op: schema managed by Alembic -- see alembic/versions/92d379a512fc."""
    log.info("Arch schema managed by Alembic. Skipping inline DDL.")