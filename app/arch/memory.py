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




# ── HuggingFace Cross-Encoder Reranking ──────────────────────────
import httpx as _httpx

async def _hf_rerank(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    """Rerank candidates using HuggingFace Inference API (BAAI/bge-reranker-v2-m3).
    Falls back to input order if API unavailable."""
    hf_token = os.getenv("HF_TOKEN", "")
    if not hf_token or not candidates:
        return candidates[:top_k]

    try:
        passages = [c.get("content", "")[:500] for c in candidates[:20]]
        async with _httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://router.huggingface.co/hf-inference/models/BAAI/bge-reranker-v2-m3",
                headers={"Authorization": f"Bearer {hf_token}"},
                json={"query": query, "texts": passages, "raw_scores": False},
            )
            if resp.status_code == 200:
                scores = resp.json()
                # scores is a list of floats, same order as passages
                if isinstance(scores, list) and len(scores) == len(candidates[:20]):
                    for i, score in enumerate(scores):
                        if i < len(candidates):
                            candidates[i]["rerank_score"] = score if isinstance(score, (int, float)) else 0
                    candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
                    logger.debug(f"HF reranking: top score={candidates[0].get('rerank_score', 0):.3f}")
                    return candidates[:top_k]
            else:
                logger.debug(f"HF reranking unavailable: HTTP {resp.status_code}")
    except Exception as e:
        logger.debug(f"HF reranking failed: {e}")

    return candidates[:top_k]


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
        """Hybrid retrieval: weighted RRF fusion of semantic (pgvector) + keyword (ILIKE) search."""
        k = k or self.k
        results_map = {}  # content_key -> data dict

        # 1. Semantic search (pgvector cosine similarity)
        try:
            embedding = await self._embed(query)
            semantic = await self.db.execute(
                text("""
                    SELECT content, metadata, source_type,
                           1 - (embedding <=> cast(:emb as vector)) AS similarity
                    FROM arch_memories
                    WHERE agent_id = :agent_id
                      AND 1 - (embedding <=> cast(:emb as vector)) > :threshold
                    ORDER BY embedding <=> cast(:emb as vector)
                    LIMIT :k
                """),
                {"agent_id": self.agent_id, "emb": str(embedding), "threshold": self.threshold, "k": k * 2},
            )
            for rank, r in enumerate(semantic.fetchall()):
                key = r.content[:100]
                results_map[key] = {
                    "content": r.content,
                    "metadata": json.loads(r.metadata) if isinstance(r.metadata, str) else r.metadata,
                    "source_type": r.source_type,
                    "similarity": float(r.similarity),
                    "semantic_rank": rank + 1,
                    "keyword_rank": None,
                }
        except Exception as e:
            logger.warning(f"Semantic search failed: {e}")

        # 2. Keyword search (ILIKE)
        try:
            terms = [t.strip().lower() for t in query.split() if len(t.strip()) > 3]
            if terms:
                conditions = " OR ".join([f"lower(content) LIKE :t{i}" for i in range(len(terms))])
                params = {f"t{i}": f"%{t}%" for i, t in enumerate(terms)}
                params["agent_id"] = self.agent_id
                params["k"] = k * 2
                keyword = await self.db.execute(
                    text(f"""
                        SELECT content, metadata, source_type
                        FROM arch_memories
                        WHERE agent_id = :agent_id AND ({conditions})
                        ORDER BY created_at DESC
                        LIMIT :k
                    """),
                    params,
                )
                for rank, r in enumerate(keyword.fetchall()):
                    key = r.content[:100]
                    if key in results_map:
                        results_map[key]["keyword_rank"] = rank + 1
                    else:
                        results_map[key] = {
                            "content": r.content,
                            "metadata": json.loads(r.metadata) if isinstance(r.metadata, str) else r.metadata,
                            "source_type": r.source_type,
                            "similarity": 0.0,
                            "semantic_rank": None,
                            "keyword_rank": rank + 1,
                        }
        except Exception as e:
            logger.warning(f"Keyword search failed: {e}")

        # 3. Weighted RRF fusion
        specific_terms = ["payfast", "jwt", "api", "endpoint", "error", "config", "password", "token", "webhook", "nginx"]
        is_factual = any(t in query.lower() for t in specific_terms)
        kw_weight = 0.7 if is_factual else 0.3
        sem_weight = 0.3 if is_factual else 0.7
        rrf_k = 60

        scored = []
        for data in results_map.values():
            score = 0
            if data["semantic_rank"]:
                score += sem_weight / (rrf_k + data["semantic_rank"])
            if data["keyword_rank"]:
                score += kw_weight / (rrf_k + data["keyword_rank"])
            scored.append({**data, "rrf_score": score})

        scored.sort(key=lambda x: x["rrf_score"], reverse=True)

        # Take top candidates for potential reranking
        candidates = scored[:k * 3] if len(scored) > k else scored

        # Lightweight reranking: if we have more candidates than needed,
        # use string-overlap scoring to boost exact-match relevance
        if len(candidates) > k:
            query_terms = set(query.lower().split())
            for c in candidates:
                content_terms = set(c["content"].lower().split())
                overlap = len(query_terms & content_terms)
                # Boost RRF score by term overlap ratio
                c["rrf_score"] += (overlap / max(len(query_terms), 1)) * 0.01
            candidates.sort(key=lambda x: x["rrf_score"], reverse=True)

        # Cross-encoder reranking via HuggingFace API (if available)
        reranked = await _hf_rerank(query, candidates, top_k=k)

        return [
            {
                "content": r["content"],
                "metadata": r["metadata"],
                "similarity": r.get("rerank_score", r.get("similarity", r["rrf_score"])),
                "source_type": r["source_type"],
            }
            for r in reranked
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
