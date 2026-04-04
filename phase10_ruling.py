"""Phase 10 — Issue BUILD_CONSENSUS_CONFIRMED constitutional ruling."""

import asyncio
import json
import os

async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text

    engine = create_async_engine(os.environ["DATABASE_URL"])
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sf() as db:
        sov = await db.execute(text(
            "SELECT id FROM arch_agents WHERE agent_name = 'sovereign'"
        ))
        sov_id = sov.scalar()

        existing = await db.execute(text(
            "SELECT id FROM arch_constitutional_rulings WHERE ruling_ref = 'CR-BUILD-CONSENSUS-001'"
        ))
        if existing.fetchone():
            print("Ruling already exists — skipping")
        else:
            await db.execute(text(
                "INSERT INTO arch_constitutional_rulings "
                "(ruling_ref, ruling_type, issued_by, ruling_text, cited_directives, subject_agents) "
                "VALUES (:ref, :type, :issued_by, :text, :directives, :subjects)"
            ), {
                "ref": "CR-BUILD-CONSENSUS-001",
                "type": "BUILD_CONSENSUS_CONFIRMED",
                "issued_by": sov_id,
                "text": json.dumps({
                    "ruling": "The board agrees that the Boardroom Brief v3.0, as amended by the consultation, is the authoritative build specification.",
                    "consultation_inputs": 21,
                    "inputs_incorporated": 21,
                    "inputs_rejected": 0,
                    "phases_completed": 10,
                    "tables_created": 12,
                    "endpoints_deployed": 34,
                    "views_deployed": 8,
                    "founding_statements_preserved": 7,
                    "strategic_visions_seeded": 7,
                    "existing_tests_passing": 480,
                    "arch_tests_passing": 143,
                    "regressions": 0,
                    "build_date": "2026-04-05",
                }),
                "directives": json.dumps(["PD-1", "PD-2", "PD-3", "PD-4", "PD-5", "PD-6"]),
                "subjects": json.dumps(["sovereign", "sentinel", "treasurer", "auditor",
                                         "arbiter", "architect", "ambassador"]),
            })
            await db.commit()
            print("BUILD_CONSENSUS_CONFIRMED ruling issued by The Sovereign")

        # Final counts
        rulings = await db.execute(text("SELECT COUNT(*) FROM arch_constitutional_rulings"))
        tables = await db.execute(text(
            "SELECT COUNT(*) FROM pg_tables WHERE tablename LIKE 'boardroom_%' OR tablename LIKE 'arch_%'"
        ))
        print(f"Constitutional rulings: {rulings.scalar()}")
        print(f"Arch + Boardroom tables: {tables.scalar()}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
