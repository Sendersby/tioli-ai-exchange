"""Flush memory outbox — generate embeddings and store in pgvector."""

import asyncio
import json
import os
from datetime import datetime, timezone


async def flush_all():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from openai import AsyncOpenAI

    engine = create_async_engine(os.environ["DATABASE_URL"])
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    oai = AsyncOpenAI()

    from pgvector.sqlalchemy import Vector
    from sqlalchemy import Column

    batch_size = 20
    processed = 0
    errors = 0

    # Reset any previously errored rows
    async with sf() as db:
        await db.execute(text(
            "UPDATE arch_memory_outbox SET error = NULL WHERE error IS NOT NULL"
        ))
        await db.commit()

    while True:
        async with sf() as db:
            rows = await db.execute(text(
                "SELECT id, agent_id, content, metadata, source_type, importance "
                "FROM arch_memory_outbox "
                "WHERE processed = false AND error IS NULL "
                "ORDER BY created_at ASC "
                "LIMIT :batch"
            ), {"batch": batch_size})
            items = rows.fetchall()
            if not items:
                break

            for row in items:
                try:
                    resp = await oai.embeddings.create(
                        input=row.content[:8000],
                        model="text-embedding-3-small",
                    )
                    embedding = resp.data[0].embedding
                    emb_str = "[" + ",".join(str(x) for x in embedding) + "]"

                    await db.execute(text(
                        "INSERT INTO arch_memories "
                        "(agent_id, content, embedding, metadata, source_type, importance) "
                        "VALUES (:agent_id, :content, cast(:emb as vector), :metadata, :source_type, :importance)"
                    ), {
                        "agent_id": row.agent_id,
                        "content": row.content,
                        "emb": emb_str,
                        "metadata": row.metadata if isinstance(row.metadata, str)
                                    else json.dumps(row.metadata),
                        "source_type": row.source_type,
                        "importance": float(row.importance),
                    })
                    await db.execute(text(
                        "UPDATE arch_memory_outbox SET processed = true, processed_at = now() "
                        "WHERE id = :id"
                    ), {"id": row.id})
                    await db.commit()
                    processed += 1
                except Exception as e:
                    await db.rollback()
                    try:
                        await db.execute(text(
                            "UPDATE arch_memory_outbox SET error = :err WHERE id = :id"
                        ), {"err": str(e)[:200], "id": row.id})
                        await db.commit()
                    except Exception:
                        await db.rollback()
                    errors += 1

        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        if processed % 100 == 0 and processed > 0:
            print(f"{now} -- {processed} embedded, {errors} errors", flush=True)

    print(f"COMPLETE: {processed} embedded, {errors} errors", flush=True)

    # Print per-agent counts
    async with sf() as db:
        result = await db.execute(text(
            "SELECT agent_id, COUNT(*) as cnt FROM arch_memories GROUP BY agent_id ORDER BY agent_id"
        ))
        print("\nMemories per agent:")
        for r in result.fetchall():
            print(f"  {r.agent_id}: {r.cnt}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(flush_all())
