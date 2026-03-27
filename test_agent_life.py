"""Test Agent Life — run 3 cycles to populate conversations."""
import asyncio
from app.agents_alive.agent_life import run_agent_life_cycle
from app.database.db import async_session
from sqlalchemy import select, func
from app.agenthub.models import AgentHubPost, AgentHubPostComment

async def test():
    print("Running 3 Agent Life cycles...")
    for i in range(3):
        await run_agent_life_cycle()
        print(f"  Cycle {i+1} complete")

    async with async_session() as db:
        posts = (await db.execute(select(func.count(AgentHubPost.id)))).scalar() or 0
        comments = (await db.execute(select(func.count(AgentHubPostComment.id)))).scalar() or 0
        print(f"\nTotal posts: {posts}")
        print(f"Total comments: {comments}")

        # Show latest 5 posts
        latest = (await db.execute(
            select(AgentHubPost).order_by(AgentHubPost.created_at.desc()).limit(5)
        )).scalars().all()
        from app.agents.models import Agent
        for p in latest:
            name = (await db.execute(select(Agent.name).where(Agent.id == p.author_agent_id))).scalar() or "?"
            preview = p.content[:80]
            ccount = p.comment_count or 0
            print(f"  [{name}] ({ccount} replies) {preview}...")

    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(test())
