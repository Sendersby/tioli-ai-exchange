import asyncio
from app.database.db import async_session
from app.agents.models import Agent, Wallet
from sqlalchemy import select, func

async def check():
    async with async_session() as db:
        # Total AGENTIS across all wallets
        total = (await db.execute(
            select(func.sum(Wallet.balance)).where(Wallet.currency == "AGENTIS")
        )).scalar() or 0
        print(f"Total AGENTIS in all wallets: {total:,.1f}")
        print()

        # Break it down by agent
        wallets = (await db.execute(
            select(Agent.name, Wallet.balance)
            .join(Agent, Agent.id == Wallet.agent_id)
            .where(Wallet.currency == "AGENTIS")
            .order_by(Wallet.balance.desc())
        )).all()

        print(f"{'Agent':<30} {'Balance':>12}")
        print("-" * 44)
        for name, balance in wallets:
            print(f"{name:<30} {balance:>12,.1f}")

if __name__ == "__main__":
    asyncio.run(check())
