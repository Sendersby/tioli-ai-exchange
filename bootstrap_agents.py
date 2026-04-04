"""Cold-Start Bootstrap — immerse all 7 agents in the TiOLi AGENTIS world.

Reads the entire codebase, frontend, documentation, and platform state.
Chunks and assigns to each agent's memory based on their portfolio.
Uses the outbox pattern — embeddings generated asynchronously.
"""

import asyncio
import glob
import json
import os
from datetime import datetime, timezone


# Which files each agent should study
AGENT_SOURCES = {
    "sovereign": {
        "code": [
            "app/main.py", "app/config.py",
            "app/governance/**/*.py",
            "app/arch/constitution.py", "app/arch/base.py", "app/arch/graph.py",
        ],
        "frontend": ["static/landing/index.html", "static/landing/why-agentis.html",
                      "static/landing/charter.html", "static/landing/oversight.html"],
        "focus": "governance, strategy, constitutional framework, platform overview",
    },
    "auditor": {
        "code": [
            "app/compliance/**/*.py", "app/auth/**/*.py",
            "app/agentbroker/models.py", "app/agentbroker/agentis_dap_services.py",
        ],
        "frontend": ["static/landing/operator-register.html", "static/landing/get-started.html"],
        "focus": "compliance, KYC/AML, legal framework, regulatory obligations, data protection",
    },
    "arbiter": {
        "code": [
            "app/agentbroker/**/*.py",
            "app/agenthub/**/*.py",
        ],
        "frontend": ["static/landing/explorer.html", "static/landing/profile.html",
                      "static/landing/directory.html"],
        "focus": "dispute resolution, DAP, agent engagements, quality, community standards",
    },
    "treasurer": {
        "code": [
            "app/exchange/**/*.py", "app/agents/wallet.py",
            "app/crypto/**/*.py",
            "app/arch/agents/treasurer.py",
        ],
        "frontend": ["static/landing/founding-operator.html"],
        "focus": "financial flows, commission, fees, reserves, wallets, crypto, charity",
    },
    "sentinel": {
        "code": [
            "app/security/**/*.py", "app/auth/**/*.py",
            "app/monitoring/**/*.py", "app/infrastructure/**/*.py",
            "app/arch/vault.py", "app/arch/browser.py",
        ],
        "frontend": [],
        "focus": "security, infrastructure, incident response, authentication, monitoring",
    },
    "architect": {
        "code": [
            "app/main.py", "app/database/**/*.py",
            "app/blockchain/**/*.py",
            "app/arch/**/*.py",
            "tests/**/*.py",
        ],
        "frontend": ["static/landing/sdk.html", "static/landing/quickstart.html"],
        "focus": "technology stack, architecture, testing, blockchain, database, all arch code",
    },
    "ambassador": {
        "code": [
            "app/growth/**/*.py", "app/agenthub/**/*.py",
            "app/mcp/**/*.py", "app/webhooks/**/*.py",
        ],
        "frontend": ["static/landing/index.html", "static/landing/why-agentis.html",
                      "static/landing/agent-register.html", "static/landing/agora.html",
                      "static/landing/operator-directory.html", "static/landing/sdk.html"],
        "focus": "growth, marketing, community, MCP, partnerships, brand, public-facing content",
    },
}

# Files ALL agents should know
UNIVERSAL_FILES = [
    "app/config.py",
    "app/arch/constitution.py",
]


def chunk_text(text, filename, max_chars=1500):
    """Split text into meaningful chunks with source reference."""
    chunks = []
    lines = text.split("\n")
    current = []
    current_len = 0

    for line in lines:
        current.append(line)
        current_len += len(line) + 1
        if current_len >= max_chars:
            chunk_text = "\n".join(current)
            if chunk_text.strip():
                chunks.append(f"[Source: {filename}]\n{chunk_text}")
            current = []
            current_len = 0

    if current:
        chunk_text = "\n".join(current)
        if chunk_text.strip():
            chunks.append(f"[Source: {filename}]\n{chunk_text}")

    return chunks


def resolve_globs(patterns, base_dir):
    """Resolve glob patterns to actual file paths."""
    files = set()
    for pattern in patterns:
        full_pattern = os.path.join(base_dir, pattern)
        matches = glob.glob(full_pattern, recursive=True)
        for m in matches:
            if os.path.isfile(m) and not m.endswith(".pyc") and "__pycache__" not in m:
                files.add(m)
    return sorted(files)


async def bootstrap():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text

    engine = create_async_engine(os.environ["DATABASE_URL"])
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    base_dir = "/home/tioli/app"
    total_chunks = 0
    agent_chunks = {}

    print("=" * 70)
    print("  COLD-START BOOTSTRAP — Immersing all 7 Arch Agents")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)
    print()

    for agent_name, sources in AGENT_SOURCES.items():
        chunks_for_agent = []

        # Add focus description as first memory
        chunks_for_agent.append(
            f"[Agent Portfolio Brief]\n"
            f"You are responsible for: {sources['focus']}.\n"
            f"Study the following codebase files and frontend pages to understand "
            f"the platform you govern."
        )

        # Process code files
        code_files = resolve_globs(sources["code"], base_dir)
        for filepath in code_files:
            try:
                with open(filepath, "r", errors="ignore") as f:
                    content = f.read()
                if len(content.strip()) < 10:
                    continue
                rel_path = os.path.relpath(filepath, base_dir)
                file_chunks = chunk_text(content, rel_path)
                chunks_for_agent.extend(file_chunks)
            except Exception as e:
                pass

        # Process frontend files
        frontend_files = resolve_globs(sources.get("frontend", []), base_dir)
        for filepath in frontend_files:
            try:
                with open(filepath, "r", errors="ignore") as f:
                    content = f.read()
                if len(content.strip()) < 10:
                    continue
                rel_path = os.path.relpath(filepath, base_dir)
                file_chunks = chunk_text(content, rel_path)
                chunks_for_agent.extend(file_chunks)
            except Exception as e:
                pass

        # Add universal files if not already included
        for uf in UNIVERSAL_FILES:
            uf_path = os.path.join(base_dir, uf)
            if uf_path not in code_files and os.path.exists(uf_path):
                try:
                    with open(uf_path, "r") as f:
                        content = f.read()
                    chunks_for_agent.extend(chunk_text(content, uf))
                except Exception:
                    pass

        agent_chunks[agent_name] = chunks_for_agent
        total_chunks += len(chunks_for_agent)
        print(f"  {agent_name:12s}: {len(chunks_for_agent):4d} chunks from {len(code_files) + len(frontend_files)} files")

    print(f"\n  Total: {total_chunks} chunks across 7 agents")
    print(f"\n  Writing to memory outbox...")

    # Write all chunks to memory outbox
    written = 0
    async with sf() as db:
        for agent_name, chunks in agent_chunks.items():
            for i, chunk in enumerate(chunks):
                importance = 0.8 if i == 0 else 0.6  # Portfolio brief gets higher importance
                source_type = "bootstrap"
                await db.execute(text(
                    "INSERT INTO arch_memory_outbox "
                    "(agent_id, content, metadata, source_type, importance) "
                    "VALUES (:agent_id, :content, :metadata, :source_type, :importance)"
                ), {
                    "agent_id": agent_name,
                    "content": chunk[:3000],  # Cap individual chunk size
                    "metadata": json.dumps({"bootstrap": True, "batch": i}),
                    "source_type": source_type,
                    "importance": importance,
                })
                written += 1

            # Also update the agent's status to reflect bootstrap
            await db.execute(text(
                "UPDATE arch_agents SET last_heartbeat = now() WHERE agent_name = :n"
            ), {"n": agent_name})

        await db.commit()

    print(f"  Written: {written} outbox entries")
    print()

    # Now flush the outbox — generate embeddings and store in pgvector
    print("  Generating embeddings and storing in pgvector...")
    print("  (This calls OpenAI text-embedding-3-small for each chunk)")
    print()

    from openai import AsyncOpenAI
    oai = AsyncOpenAI()

    async with sf() as db:
        # Process in batches
        batch_size = 20
        processed = 0
        errors = 0

        while True:
            rows = await db.execute(text(
                "SELECT id, agent_id, content, metadata, source_type, importance "
                "FROM arch_memory_outbox "
                "WHERE processed = false "
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

                    await db.execute(text(
                        "INSERT INTO arch_memories "
                        "(agent_id, content, embedding, metadata, source_type, importance) "
                        "VALUES (:agent_id, :content, :emb::vector, :metadata, :source_type, :importance)"
                    ), {
                        "agent_id": row.agent_id,
                        "content": row.content,
                        "emb": str(embedding),
                        "metadata": row.metadata if isinstance(row.metadata, str)
                                    else json.dumps(row.metadata),
                        "source_type": row.source_type,
                        "importance": float(row.importance),
                    })
                    await db.execute(text(
                        "UPDATE arch_memory_outbox SET processed = true, processed_at = now() "
                        "WHERE id = :id"
                    ), {"id": row.id})
                    processed += 1

                except Exception as e:
                    await db.execute(text(
                        "UPDATE arch_memory_outbox SET error = :err WHERE id = :id"
                    ), {"err": str(e)[:200], "id": row.id})
                    errors += 1

                if processed % 50 == 0 and processed > 0:
                    print(f"    ... {processed} embedded")

            await db.commit()

    print(f"\n  Bootstrap complete:")
    print(f"    Embedded: {processed}")
    print(f"    Errors:   {errors}")

    # Final memory count per agent
    async with sf() as db:
        result = await db.execute(text(
            "SELECT agent_id, COUNT(*) as cnt FROM arch_memories GROUP BY agent_id ORDER BY agent_id"
        ))
        print(f"\n  Memory store per agent:")
        for r in result.fetchall():
            print(f"    {r.agent_id:12s}: {r.cnt} memories")

    print()
    print("=" * 70)
    print("  ALL 7 AGENTS IMMERSED IN THE TIOLI AGENTIS WORLD")
    print("  They are now free to operate with full platform knowledge.")
    print("=" * 70)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(bootstrap())
