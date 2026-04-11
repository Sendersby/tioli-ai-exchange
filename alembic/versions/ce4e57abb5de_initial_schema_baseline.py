"""initial_schema_baseline

Revision ID: ce4e57abb5de
Revises: 
Create Date: 2026-04-11 08:34:15.422510
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'ce4e57abb5de'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Baseline: 391 tables already exist in production.
    # This migration documents the schema state as of 2026-04-10.
    # All future schema changes MUST go through Alembic migrations.
    pass


def downgrade() -> None:
    pass
