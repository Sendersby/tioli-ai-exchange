import asyncio
from app.database.db import async_session
from app.governance.models import Proposal, Vote
from sqlalchemy import select, delete

async def cleanup():
    async with async_session() as db:
        p = (await db.execute(select(Proposal).where(Proposal.title.like("Test:%")))).scalars().all()
        for prop in p:
            await db.execute(delete(Vote).where(Vote.proposal_id == prop.id))
            await db.execute(delete(Proposal).where(Proposal.id == prop.id))
            print(f"Cleaned: {prop.title}")
        await db.commit()
        print("Done")

if __name__ == "__main__":
    asyncio.run(cleanup())
