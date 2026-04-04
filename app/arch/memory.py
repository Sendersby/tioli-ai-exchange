"""Arch Agent Memory — pgvector-backed with outbox pattern.

Single table design (arch_memories) with agent_id index.
Outbox pattern (C-04 fix): embeddings are queued in SQL first,
then asynchronously pushed to pgvector after primary transaction confirms.
"""

import json
import logging
import os
from datetime import datetime, timezone

from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("arch.memory")


class ArchMemory:
    """pgvector-backed agent memory with outbox pattern."""

    TABLE = "arch_memories"

    def __init__(self, agent_id: str, db: AsyncSession, oai_client: AsyncOpenAI = None):
        self.agent_id = agent_id
        self.db = db
        self.oai_client = oai_client or AsyncOpenAI()
        self.model = os.getenv("ARCH_EMBEDDING_MODEL", "text-embedding-3-small")
        self.k = int(os.getenv("ARCH_MEMORY_RETRIEVE_K", "5"))
        self.threshold = float(os.getenv("ARCH_MEMORY_SIMILARITY_THRESHOLD", "0.75"))

    async def _embed(self, text_in: str) -> list[float]:
        """Generate embedding vector via OpenAI API."""
        resp = await self.oai_client.embeddings.create(
            input=text_in, model=self.model
        )
        return resp.data[0].embedding

    async def store(
        self,
        content: str,
        metadata: dict = None,
        source_type: str = "interaction",
        importance: float = 0.5,
    ):
        """Write to outbox — background task embeds and pushes to pgvector.

        OUTBOX PATTERN: The outbox row commits atomically with the caller's
        primary transaction. The flush_memory_outbox background task then
        generates the embedding and inserts into arch_memories.
        """
        await self.db.execute(
            text("""
                INSERT INTO arch_memory_outbox
                    (agent_id, content, metadata, source_type, importance)
                VALUES (:agent_id, :content, :metadata, :source_type, :importance)
            """),
            {
                "agent_id": self.agent_id,
                "content": content,
                "metadata": json.dumps(metadata or {}),
                "source_type": source_type,
                "importance": importance,
            },
        )

    async def retrieve(self, query: str, k: int = None) -> list[dict]:
        """Semantic similarity search over agent memories."""
        k = k or self.k
        embedding = await self._embed(query)
        result = await self.db.execute(
            text("""
                SELECT content, metadata, source_type,
                       1 - (embedding <=> cast(:emb as vector)) AS similarity
                FROM arch_memories
                WHERE agent_id = :agent_id
                  AND 1 - (embedding <=> cast(:emb as vector)) > :threshold
                ORDER BY embedding <=> cast(:emb as vector)
                LIMIT :k
            """),
            {
                "agent_id": self.agent_id,
                "emb": str(embedding),
                "threshold": self.threshold,
                "k": k,
            },
        )
        return [
            {
                "content": r.content,
                "metadata": json.loads(r.metadata) if isinstance(r.metadata, str) else r.metadata,
                "similarity": float(r.similarity),
                "source_type": r.source_type,
            }
            for r in result.fetchall()
        ]

    async def bootstrap(self, documents: list[dict]):
        """Cold-start: ingest a list of {content, source_type, importance} dicts."""
        for doc in documents:
            await self.store(
                doc["content"],
                doc.get("metadata", {}),
                doc.get("source_type", "bootstrap"),
                doc.get("importance", 0.7),
            )


async def flush_memory_outbox(db_factory):
    """Background task: embed outbox rows and insert into pgvector.

    Runs every 60 seconds via APScheduler. Safe to fail independently —
    outbox rows are retried on next cycle.
    """
    async with db_factory() as db:
        rows = await db.execute(
            text("""
                SELECT id, agent_id, content, metadata, source_type, importance
                FROM arch_memory_outbox
                WHERE processed = false
                ORDER BY created_at ASC
                LIMIT 50
            """)
        )
        items = rows.fetchall()
        if not items:
            return

        oai = AsyncOpenAI()
        for row in items:
            try:
                resp = await oai.embeddings.create(
                    input=row.content, model="text-embedding-3-small"
                )
                embedding = resp.data[0].embedding

                await db.execute(
                    text("""
                        INSERT INTO arch_memories
                            (agent_id, content, embedding, metadata, source_type, importance)
                        VALUES (:agent_id, :content, cast(:emb as vector),
                                :metadata, :source_type, :importance)
                    """),
                    {
                        "agent_id": row.agent_id,
                        "content": row.content,
                        "emb": str(embedding),
                        "metadata": row.metadata if isinstance(row.metadata, str)
                                    else json.dumps(row.metadata),
                        "source_type": row.source_type,
                        "importance": float(row.importance),
                    },
                )
                await db.execute(
                    text("""
                        UPDATE arch_memory_outbox
                        SET processed = true, processed_at = now()
                        WHERE id = :id
                    """),
                    {"id": row.id},
                )

            except Exception as e:
                await db.execute(
                    text("""
                        UPDATE arch_memory_outbox
                        SET error = :err WHERE id = :id
                    """),
                    {"err": str(e)[:500], "id": row.id},
                )
                log.error(f"Memory outbox flush error for {row.id}: {e}")

        await db.commit()
