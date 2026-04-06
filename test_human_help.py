"""Test: 3 agents request human help — should appear in founder inbox."""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import redis.asyncio as aioredis
from anthropic import AsyncAnthropic

async def test():
    engine = create_async_engine("postgresql+asyncpg://tioli:DhQHhP6rsYdUL*2DLWJ2Neu%232xqhM0z%23@127.0.0.1:5432/tioli_exchange")
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis_client = aioredis.from_url("redis://localhost:6379/0")
    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    async with sf() as db:
        from app.arch.agents.ambassador import AmbassadorAgent
        amb = AmbassadorAgent(agent_id="ambassador", db=db, redis=redis_client, client=client)
        r1 = await amb.request_human_help(
            "LinkedIn API access pending — cannot post to company page",
            "I have content ready to publish to the TiOLi AGENTIS LinkedIn company page but the Community Management API access is still under review. Please check your email for the LinkedIn approval notification, then generate an OAuth token from the LinkedIn Developer Portal Auth tab and provide it to Claude Code.",
            "URGENT"
        )
        print(f"Ambassador: {r1}")

        from app.arch.agents.sentinel import SentinelAgent
        sen = SentinelAgent(agent_id="sentinel", db=db, redis=redis_client, client=client)
        r2 = await sen.request_human_help(
            "Reddit API access blocked — awaiting approval",
            "Reddit has ended self-service API access. An access request was submitted but approval is pending (1-7 business days). Please monitor sendersby@tioli.onmicrosoft.com for a response from Reddit Developer Support. Once approved, create an app at old.reddit.com/prefs/apps and provide the Client ID and Secret.",
            "ROUTINE"
        )
        print(f"Sentinel: {r2}")

        from app.arch.agents.architect import ArchitectAgent
        arc = ArchitectAgent(agent_id="architect", db=db, redis=redis_client, client=client)
        r3 = await arc.request_human_help(
            "PayFast account verification needed for live payments",
            "The PayFast payment integration is fully built and deployed. However, PayFast requires bank account verification before processing live payments. Please log into payfast.co.za, check the verification status, and complete any outstanding steps. Once verified, live payments work immediately with zero code changes.",
            "URGENT"
        )
        print(f"Architect: {r3}")

        count = await db.execute(text(
            "SELECT COUNT(*) FROM arch_founder_inbox WHERE status = 'PENDING'"
        ))
        print(f"\nTotal pending inbox items: {count.scalar()}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test())
