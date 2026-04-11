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
        # Get agent_id from name
        agent_row = await db.execute(text(
            "SELECT id FROM arch_agents WHERE agent_name = :name"
        ), {"name": agent_name})
        agent_id_row = agent_row.fetchone()
        if not agent_id_row:
            return mem
        agent_id = str(agent_id_row.id)

        # Load core memories (source_type = 'core_identity')
        rows = await db.execute(text(
            "SELECT content FROM arch_memories "
            "WHERE agent_id = :aid AND source_type = 'core_identity' ORDER BY importance DESC LIMIT 5"
        ), {"aid": agent_id})
        core_rows = rows.fetchall()
        if not core_rows:
            # Fallback: check outbox for unflushed core memories
            rows = await db.execute(text(
                "SELECT content FROM arch_memory_outbox "
                "WHERE agent_id = :aid AND source_type = 'core_identity' ORDER BY importance DESC LIMIT 5"
            ), {"aid": agent_id})
            core_rows = rows.fetchall()
        for i, row in enumerate(core_rows):
            mem.core[f"identity_{i}"] = row.content[:200]

        # Load recent working memories (everything else)
        rows = await db.execute(text(
            "SELECT content, created_at FROM arch_memories "
            "WHERE agent_id = :aid AND source_type != 'core_identity' ORDER BY created_at DESC LIMIT 50"
        ), {"aid": agent_id})
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
        # Get agent_id
        agent_row = await db.execute(text("SELECT id FROM arch_agents WHERE agent_name = :name"), {"name": mem.agent_name})
        agent_id_row = agent_row.fetchone()
        if not agent_id_row:
            return
        agent_id = str(agent_id_row.id)

        for key, value in mem.core.items():
            await db.execute(text(
                "INSERT INTO arch_memory_outbox (agent_id, content, source_type, importance) "
                "VALUES (:aid, :content, 'core_identity', 0.99)"
            ), {"aid": agent_id, "content": f"{key}: {value}"})
        await db.commit()
    except Exception as e:
        log.warning(f"[memory] Failed to save for {mem.agent_name}: {e}")
