"""Mem0 universal memory integration — persistent, intelligent memory for all agents.

Wraps mem0ai to provide:
- Automatic fact extraction from conversations
- Intelligent retrieval (not just similarity search)
- Cross-session memory that learns from interactions
- Falls back to existing pgvector memory if Mem0 unavailable
"""
import os
import logging

log = logging.getLogger("arch.mem0_integration")

MEM0_AVAILABLE = False
try:
    from mem0 import Memory
    MEM0_AVAILABLE = True
    log.info("Mem0: AVAILABLE")
except ImportError:
    log.info("Mem0: NOT INSTALLED (using pgvector memory)")

_mem0_instance = None


def get_mem0():
    """Get or create Mem0 instance with PostgreSQL backend."""
    global _mem0_instance
    if _mem0_instance is not None:
        return _mem0_instance

    if not MEM0_AVAILABLE:
        return None

    try:
        config = {
            "llm": {
                "provider": "anthropic",
                "config": {
                    "model": "claude-haiku-4-5-20251001",
                    "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small",
                    "api_key": os.getenv("OPENAI_API_KEY", ""),
                },
            },
            "vector_store": {
                "provider": "pgvector",
                "config": {
                    "dbname": "tioli_exchange",
                    "user": os.getenv("PGUSER", "tioli"),
                    "password": os.getenv("PGPASSWORD", ""),
                    "host": "127.0.0.1",
                    "port": 5432,
                    "collection_name": "mem0_memories",
                },
            },
        }
        _mem0_instance = Memory.from_config(config)
        log.info("Mem0: initialized with PostgreSQL backend")
        return _mem0_instance
    except Exception as e:
        log.warning(f"Mem0 initialization failed: {e}")
        return None


async def mem0_add(agent_id: str, content: str, metadata: dict = None):
    """Add a memory via Mem0."""
    m = get_mem0()
    if m:
        try:
            m.add(content, user_id=agent_id, metadata=metadata or {})
            return True
        except Exception as e:
            log.debug(f"Mem0 add failed: {e}")
    return False


async def mem0_search(agent_id: str, query: str, limit: int = 5):
    """Search memories via Mem0."""
    m = get_mem0()
    if m:
        try:
            results = m.search(query, user_id=agent_id, limit=limit)
            return results.get("results", results) if isinstance(results, dict) else results
        except Exception as e:
            log.debug(f"Mem0 search failed: {e}")
    return []
