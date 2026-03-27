"""Test the Concierge Agent."""
import asyncio
from app.agents_alive.concierge_agent import run_concierge_cycle, CONCIERGE_NAME
from app.database.db import async_session
from sqlalchemy import select
from app.agents.models import Agent
from app.agenthub.models import AgentHubPost, AgentHubChannel, AgentHubCollabMatch
from sqlalchemy import func


async def test():
    print("=" * 50)
    print("CONCIERGE AGENT TEST")
    print("=" * 50)

    # Run the cycle
    print("\nRunning concierge cycle...")
    await run_concierge_cycle()
    print("Cycle complete!")

    async with async_session() as db:
        # Check agent exists
        agent = (await db.execute(
            select(Agent).where(Agent.name == CONCIERGE_NAME)
        )).scalar_one_or_none()

        if agent:
            short_id = agent.id[:8]
            print(f"\nAgent: {agent.name} (id: {short_id}...)")
            print(f"Platform: {agent.platform}")
        else:
            print("ERROR: Concierge agent not found!")
            return

        # Check posts
        posts = (await db.execute(
            select(AgentHubPost).where(AgentHubPost.author_agent_id == agent.id)
            .order_by(AgentHubPost.created_at.desc()).limit(5)
        )).scalars().all()
        print(f"\nPosts by Concierge: {len(posts)}")
        for p in posts:
            ch = (await db.execute(
                select(AgentHubChannel.slug).where(AgentHubChannel.id == p.channel_id)
            )).scalar() or "?"
            preview = p.content[:100]
            print(f"  #{ch}: {preview}...")

        # Check total collab matches
        total = (await db.execute(select(func.count(AgentHubCollabMatch.id)))).scalar() or 0
        active = (await db.execute(
            select(func.count(AgentHubCollabMatch.id))
            .where(AgentHubCollabMatch.status.in_(["PROPOSED", "ACTIVE"]))
        )).scalar() or 0
        print(f"\nCollab Matches: {total} total, {active} active")

    print("\n" + "=" * 50)
    print("TEST COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test())
