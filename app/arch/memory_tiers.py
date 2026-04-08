"""3-tier memory system — Core / Working / Archival (Letta-inspired)."""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.memory_tiers")


class TieredMemory:
    """3-tier memory for an Arch Agent."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.core = {}       # Always in context: identity, goals, key facts. Max 2KB.
        self.working = []    # Recent interactions, current task state. Last 50.
        self.archival = []   # Everything else, searchable. Unlimited.

    def set_core(self, key: str, value: str):
        """Set a core memory fact (always in context)."""
        total = sum(len(str(v)) for v in self.core.values())
        if total + len(value) > 2048:
            log.warning(f"[memory] Core memory at capacity for {self.agent_name}")
            # Evict oldest entry
            if self.core:
                oldest = next(iter(self.core))
                del self.core[oldest]
        self.core[key] = value
        log.info(f"[memory] Core set: {self.agent_name}.{key}")

    def get_core(self, key: str = None):
        """Get core memory (all or specific key)."""
        if key:
            return self.core.get(key)
        return self.core

    def add_working(self, entry: dict):
        """Add to working memory (recent context)."""
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.working.append(entry)
        if len(self.working) > 50:
            # Move overflow to archival
            overflow = self.working[:-50]
            self.archival.extend(overflow)
            self.working = self.working[-50:]

    def add_archival(self, content: str, metadata: dict = None):
        """Add to archival memory (long-term searchable)."""
        self.archival.append({
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def search_archival(self, query: str, limit: int = 5):
        """Search archival memory by keyword (simple text match)."""
        results = []
        query_lower = query.lower()
        for entry in reversed(self.archival):
            if query_lower in entry.get("content", "").lower():
                results.append(entry)
                if len(results) >= limit:
                    break
        return results

    def get_context_window(self):
        """Get the full context window for agent reasoning."""
        return {
            "core": self.core,
            "working": self.working[-10:],  # Last 10 working entries
            "archival_size": len(self.archival),
        }

    def summary(self):
        """Memory summary stats."""
        return {
            "agent": self.agent_name,
            "core_keys": list(self.core.keys()),
            "core_size_bytes": sum(len(str(v)) for v in self.core.values()),
            "working_entries": len(self.working),
            "archival_entries": len(self.archival),
        }


async def load_from_db(db, agent_name: str) -> TieredMemory:
    """Load tiered memory from database."""
    from sqlalchemy import text
    mem = TieredMemory(agent_name)

    try:
        # Load core memories
        rows = await db.execute(text(
            "SELECT category, content FROM arch_memories "
            "WHERE agent_name = :agent AND category = 'core' ORDER BY created_at DESC LIMIT 20"
        ), {"agent": agent_name})
        for row in rows.fetchall():
            mem.core[row.category] = row.content[:200]

        # Load recent working memories
        rows = await db.execute(text(
            "SELECT content, metadata, created_at FROM arch_memories "
            "WHERE agent_name = :agent AND category != 'core' ORDER BY created_at DESC LIMIT 50"
        ), {"agent": agent_name})
        for row in rows.fetchall():
            mem.working.append({"content": row.content[:500], "timestamp": str(row.created_at)})

    except Exception as e:
        log.warning(f"[memory] Failed to load from DB for {agent_name}: {e}")

    return mem


async def save_to_db(db, mem: TieredMemory):
    """Save tiered memory state to database."""
    from sqlalchemy import text
    import uuid

    try:
        for key, value in mem.core.items():
            await db.execute(text(
                "INSERT INTO arch_memories (id, agent_name, category, content, created_at) "
                "VALUES (:id, :agent, 'core', :content, now()) "
                "ON CONFLICT DO NOTHING"
            ), {"id": str(uuid.uuid4()), "agent": mem.agent_name, "content": f"{key}: {value}"})
        await db.commit()
    except Exception as e:
        log.warning(f"[memory] Failed to save for {mem.agent_name}: {e}")
