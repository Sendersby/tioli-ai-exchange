"""Consolidated seed script for self-hosted Docker deployment.

Creates demo agents, wallets, service profiles, and initial reputation data
so the platform works out of the box on first startup.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select


async def seed_demo_data():
    """Create demo agents and data for self-hosted instances."""
    from app.database.db import async_session, init_db
    from app.agents.models import Agent, Wallet
    from app.agentbroker.models import AgentReputationScore, AgentServiceProfile

    # Ensure tables exist
    await init_db()

    async with async_session() as db:
        # Check if already seeded
        result = await db.execute(select(Agent).limit(1))
        if result.scalar_one_or_none():
            print("[SEED] Data already exists, skipping.")
            return

        print("[SEED] Creating demo agents and data...")

        demo_agents = [
            {"name": "Atlas Research", "platform": "Claude", "description": "Deep research and market analysis agent"},
            {"name": "Nova CodeSmith", "platform": "Claude", "description": "Full-stack code generation and security audit"},
            {"name": "Forge Analytics", "platform": "GPT-4", "description": "Financial modelling and data science"},
            {"name": "Prism Creative", "platform": "Claude", "description": "Creative content and copywriting"},
            {"name": "Meridian Translate", "platform": "Gemini", "description": "Professional translation in 40+ languages"},
        ]

        for agent_data in demo_agents:
            agent_id = str(uuid.uuid4())
            api_key = f"demo_{uuid.uuid4().hex[:24]}"

            agent = Agent(
                id=agent_id,
                name=agent_data["name"],
                platform=agent_data["platform"],
                description=agent_data["description"],
                api_key_hash=api_key,  # In demo mode, plaintext is fine
                is_active=True,
                is_approved=True,
            )
            db.add(agent)

            # Create wallet with demo balance
            wallet = Wallet(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                currency="AGENTIS",
                balance=1000.0,
            )
            db.add(wallet)

            # Create service profile
            profile = AgentServiceProfile(
                profile_id=str(uuid.uuid4()),
                agent_id=agent_id,
                service_title=f"{agent_data['name']} Services",
                description=agent_data["description"],
                capability_tags=[agent_data["platform"], "AI"],
                is_active=True,
            )
            db.add(profile)

            # Initial reputation score
            rep = AgentReputationScore(
                score_id=str(uuid.uuid4()),
                agent_id=agent_id,
                overall_score=7.5,
                delivery_rate=8.0,
                on_time_rate=8.0,
                acceptance_rate=8.0,
                dispute_rate=9.0,
                volume_multiplier=3.0,
                recency_score=7.0,
                total_engagements=0,
                total_completed=0,
                total_disputed=0,
            )
            db.add(rep)

            print(f"  Created: {agent_data['name']} (API key: {api_key})")

        await db.commit()
        print(f"[SEED] Done — {len(demo_agents)} demo agents created.")


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
