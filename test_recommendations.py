"""Generate and test AI optimization recommendations."""
import asyncio
from app.database.db import async_session
from app.optimization.engine import SelfOptimizationEngine, OptimizationRecommendation
from app.blockchain.chain import Blockchain
from sqlalchemy import select, func


async def run():
    bc = Blockchain(storage_path="tioli_exchange_chain.json")
    engine = SelfOptimizationEngine(blockchain=bc)

    async with async_session() as db:
        count = (await db.execute(select(func.count(OptimizationRecommendation.id)))).scalar() or 0
        print(f"Existing recommendations: {count}")

        if count == 0:
            print("Running analyze_and_recommend...")
            try:
                result = await engine.analyze_and_recommend(db)
                await db.commit()
                print(f"Result: {result}")
            except Exception as e:
                print(f"Analysis error: {e}")

        count2 = (await db.execute(select(func.count(OptimizationRecommendation.id)))).scalar() or 0
        print(f"Total recommendations now: {count2}")

        recs = await engine.get_recommendations(db, limit=10)
        for r in recs:
            cat = r["category"]
            title = r["title"]
            impact = r["impact_score"]
            applied = "APPLIED" if r["applied"] else ""
            print(f"  [{cat}] {title} (impact: {impact}) {applied}")

        if not recs:
            print("  No recommendations. The engine needs more platform data to generate insights.")


if __name__ == "__main__":
    asyncio.run(run())
