"""Agent authentication — API key-based access for AI agents."""

import secrets
import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import Agent, Wallet


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and its hash.

    Returns (plain_key, hashed_key). The plain key is shown once
    to the agent at registration. Only the hash is stored.
    """
    plain_key = f"tioli_{secrets.token_urlsafe(48)}"
    hashed_key = hashlib.sha256(plain_key.encode()).hexdigest()
    return plain_key, hashed_key


def hash_api_key(key: str) -> str:
    """Hash an API key for comparison."""
    return hashlib.sha256(key.encode()).hexdigest()


async def register_agent(
    db: AsyncSession, name: str, platform: str, description: str = ""
) -> dict:
    """Register a new AI agent on the platform.

    Returns the agent details including the API key (shown only once).
    """
    plain_key, hashed_key = generate_api_key()

    agent = Agent(
        name=name,
        platform=platform,
        description=description,
        api_key_hash=hashed_key,
    )
    db.add(agent)
    await db.flush()

    # Create default AGENTIS wallet
    wallet = Wallet(agent_id=agent.id, currency="AGENTIS")
    db.add(wallet)
    await db.flush()

    return {
        "agent_id": agent.id,
        "name": agent.name,
        "platform": agent.platform,
        "api_key": plain_key,  # Only shown once!
        "message": "Store your API key securely. It will not be shown again.",
    }


async def authenticate_agent(db: AsyncSession, api_key: str) -> Agent | None:
    """Authenticate an agent by API key. Returns the Agent or None."""
    hashed = hash_api_key(api_key)
    result = await db.execute(
        select(Agent).where(Agent.api_key_hash == hashed, Agent.is_active == True)
    )
    return result.scalar_one_or_none()
