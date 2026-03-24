"""Agent Memory Persistence — models for cross-session agent state.

Per Build Brief v4.0 Section 3.2:
- Agents can store and retrieve structured state across sessions
- Memory is scoped per agent_id automatically
- Quota enforcement per subscription tier
- Optional TTL with automatic expiry
- JSONB values for structured data
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, ForeignKey, Index
from app.database.db import Base

_uuid = lambda: str(uuid.uuid4())
_now = lambda: datetime.now(timezone.utc)


class AgentMemory(Base):
    """Persistent memory record for an AI agent."""
    __tablename__ = "agent_memory"
    __table_args__ = (
        Index("ix_agent_memory_lookup", "agent_id", "memory_key", unique=True),
        Index("ix_agent_memory_agent", "agent_id"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    memory_key = Column(String(255), nullable=False)
    memory_value = Column(JSON, nullable=False)  # JSONB in PostgreSQL
    size_bytes = Column(Integer, default=0)  # Track storage usage
    access_count = Column(Integer, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # NULL = never expires
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


# Quota limits per subscription tier
MEMORY_QUOTAS = {
    "explorer": 100,      # Free tier: 100 records
    "builder": 1000,      # Builder: 1,000 records
    "professional": 10000, # Professional: 10,000 records
    "enterprise": -1,     # Enterprise: unlimited (-1)
}
