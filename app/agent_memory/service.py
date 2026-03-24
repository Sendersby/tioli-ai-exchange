"""Agent Memory Persistence — service layer.

Per Build Brief v4.0 coding principles:
- Memory is scoped, quoted, and expirable
- Validate agent_id matches authenticated caller
- Check quota before writing
- Return stored record including size in bytes
- Never store PII — memory is for operational state
"""

import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_memory.models import AgentMemory, MEMORY_QUOTAS

logger = logging.getLogger("tioli.memory")


class AgentMemoryService:
    """Manages persistent memory for AI agents across sessions."""

    async def write(
        self, db: AsyncSession, agent_id: str,
        key: str, value: dict | list | str | int | float | bool,
        ttl_days: int | None = None,
    ) -> dict:
        """Write a memory record. Upserts if key exists.

        Returns the stored record including size in bytes.
        """
        # Validate key
        if not key or len(key) > 255:
            raise ValueError("Memory key must be 1-255 characters")

        # Check quota
        count = await self._get_record_count(db, agent_id)
        quota = await self._get_quota(db, agent_id)
        if quota != -1 and count >= quota:
            raise ValueError(
                f"MEMORY_QUOTA_EXCEEDED: {count}/{quota} records used. "
                f"Upgrade your subscription tier for more memory."
            )

        # Calculate size
        value_json = json.dumps(value)
        size_bytes = len(value_json.encode("utf-8"))

        # Upsert
        existing = await db.execute(
            select(AgentMemory).where(
                AgentMemory.agent_id == agent_id,
                AgentMemory.memory_key == key,
            )
        )
        record = existing.scalar_one_or_none()

        expires_at = None
        if ttl_days and ttl_days > 0:
            expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

        if record:
            record.memory_value = value
            record.size_bytes = size_bytes
            record.expires_at = expires_at
            record.updated_at = datetime.now(timezone.utc)
            record.access_count += 1
        else:
            record = AgentMemory(
                agent_id=agent_id,
                memory_key=key,
                memory_value=value,
                size_bytes=size_bytes,
                expires_at=expires_at,
            )
            db.add(record)

        await db.flush()

        return {
            "status": "success",
            "key": key,
            "size_bytes": size_bytes,
            "expires_at": str(expires_at) if expires_at else None,
            "records_used": count + (0 if record and record.access_count > 1 else 1),
            "quota": quota,
        }

    async def read(
        self, db: AsyncSession, agent_id: str, key: str,
    ) -> dict | None:
        """Read a memory record by key. Returns None if not found or expired."""
        result = await db.execute(
            select(AgentMemory).where(
                AgentMemory.agent_id == agent_id,
                AgentMemory.memory_key == key,
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            return None

        # Check expiry
        if record.expires_at and record.expires_at < datetime.now(timezone.utc):
            await db.delete(record)
            await db.flush()
            return None

        # Update access count
        record.access_count += 1
        await db.flush()

        return {
            "key": record.memory_key,
            "value": record.memory_value,
            "size_bytes": record.size_bytes,
            "access_count": record.access_count,
            "expires_at": str(record.expires_at) if record.expires_at else None,
            "created_at": str(record.created_at),
            "updated_at": str(record.updated_at),
        }

    async def search(
        self, db: AsyncSession, agent_id: str, query: str, limit: int = 20,
    ) -> list[dict]:
        """Search memory records by key pattern (LIKE match)."""
        result = await db.execute(
            select(AgentMemory).where(
                AgentMemory.agent_id == agent_id,
                AgentMemory.memory_key.ilike(f"%{query}%"),
            ).order_by(AgentMemory.updated_at.desc()).limit(limit)
        )
        records = result.scalars().all()
        return [
            {
                "key": r.memory_key,
                "value": r.memory_value,
                "size_bytes": r.size_bytes,
                "access_count": r.access_count,
                "expires_at": str(r.expires_at) if r.expires_at else None,
                "updated_at": str(r.updated_at),
            }
            for r in records
        ]

    async def list_keys(
        self, db: AsyncSession, agent_id: str, limit: int = 100,
    ) -> dict:
        """List all memory keys for an agent with usage stats."""
        result = await db.execute(
            select(AgentMemory.memory_key, AgentMemory.size_bytes, AgentMemory.access_count, AgentMemory.updated_at)
            .where(AgentMemory.agent_id == agent_id)
            .order_by(AgentMemory.updated_at.desc())
            .limit(limit)
        )
        keys = [
            {"key": r[0], "size_bytes": r[1], "access_count": r[2], "updated_at": str(r[3])}
            for r in result
        ]
        count = await self._get_record_count(db, agent_id)
        quota = await self._get_quota(db, agent_id)
        total_size = sum(k["size_bytes"] for k in keys)

        return {
            "agent_id": agent_id,
            "records_used": count,
            "quota": quota,
            "quota_pct": round(count / max(quota, 1) * 100, 1) if quota > 0 else 0,
            "total_size_bytes": total_size,
            "keys": keys,
        }

    async def delete_key(
        self, db: AsyncSession, agent_id: str, key: str,
    ) -> dict:
        """Delete a specific memory record."""
        result = await db.execute(
            select(AgentMemory).where(
                AgentMemory.agent_id == agent_id,
                AgentMemory.memory_key == key,
            )
        )
        record = result.scalar_one_or_none()
        if not record:
            raise ValueError(f"Memory key '{key}' not found")
        await db.delete(record)
        await db.flush()
        return {"status": "deleted", "key": key}

    async def cleanup_expired(self, db: AsyncSession) -> int:
        """Remove all expired memory records. Called by nightly scheduler."""
        now = datetime.now(timezone.utc)
        result = await db.execute(
            delete(AgentMemory).where(
                AgentMemory.expires_at.isnot(None),
                AgentMemory.expires_at < now,
            )
        )
        count = result.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} expired memory records")
        return count

    async def _get_record_count(self, db: AsyncSession, agent_id: str) -> int:
        result = await db.execute(
            select(func.count(AgentMemory.id)).where(AgentMemory.agent_id == agent_id)
        )
        return result.scalar() or 0

    async def _get_quota(self, db: AsyncSession, agent_id: str) -> int:
        """Get memory quota based on subscription tier. Default: explorer."""
        # Check if agent's operator has a subscription
        try:
            from app.subscriptions.models import OperatorSubscription, OperatorSubscriptionTier
            from app.agents.models import Agent
            agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
            if agent:
                # For now, return builder quota for all registered agents
                # (proper tier lookup when subscription billing is live)
                return MEMORY_QUOTAS.get("builder", 1000)
        except Exception:
            pass
        return MEMORY_QUOTAS.get("explorer", 100)
