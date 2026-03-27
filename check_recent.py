import asyncio
from app.database.db import async_session
from app.agenthub.models import AgentHubPost
from app.agents.models import Agent
from sqlalchemy import select, func
from datetime import datetime, timezone

async def check():
    async with async_session() as db:
        total = (await db.execute(select(func.count(AgentHubPost.id)))).scalar() or 0
        print(f"Total posts: {total}")
        print(f"Current UTC: {datetime.now(timezone.utc).strftime('%H:%M:%S')}")
        print()
        print("5 most recent posts:")
        posts = (await db.execute(
            select(AgentHubPost.created_at, AgentHubPost.author_agent_id, AgentHubPost.content)
            .order_by(AgentHubPost.created_at.desc())
            .limit(5)
        )).all()
        # Get agent names
        ids = {p[1] for p in posts}
        names = {}
        if ids:
            nr = (await db.execute(select(Agent.id, Agent.name).where(Agent.id.in_(ids)))).all()
            names = {r[0]: r[1] for r in nr}
        for ts, aid, content in posts:
            name = names.get(aid, "?")
            t = str(ts)[:19]
            c = content[:55]
            print(f"  {t}  [{name}] {c}...")

if __name__ == "__main__":
    asyncio.run(check())
