"""Seed 20 Agora community discussion topics.
Run: cd /home/tioli/app && python scripts/seed_agora_topics.py
"""
import asyncio, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def seed():
    from app.database.db import async_session
    from sqlalchemy import text
    with open("/home/tioli/app/content_queue/agora/seed_topics.json") as f:
        topics = json.load(f)
    async with async_session() as db:
        try:
            result = await db.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_name IN ('community_feed_posts', 'agenthub_posts', 'agora_posts') LIMIT 1"
            ))
            table = result.scalar()
        except Exception:
            table = None
        if table:
            print(f"Found table: {table}")
            for t in topics:
                try:
                    await db.execute(text(f"INSERT INTO {table} (channel, title, body, author, created_at) VALUES (:channel, :title, :body, 'ambassador', now()) ON CONFLICT DO NOTHING"), t)
                except Exception as e:
                    print(f"  Skip: {e}")
            await db.commit()
            print(f"Seeded {len(topics)} topics")
        else:
            print(f"No community posts table found. {len(topics)} topics saved to /home/tioli/app/content_queue/agora/seed_topics.json")

if __name__ == "__main__":
    asyncio.run(seed())
