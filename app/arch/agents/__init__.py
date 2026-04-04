"""Arch Agent factory — initialise and retrieve agents.

Follows strict startup sequence: Sentinel first, then Sovereign,
then Treasurer, Auditor, Arbiter, Architect, Ambassador.
"""

import logging
import os

import redis.asyncio as aioredis
from anthropic import AsyncAnthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("arch.agents")

# Module-level cache of initialised agents
_arch_agents: dict = {}


async def initialise_arch_agents(
    db: AsyncSession,
    redis: aioredis.Redis,
    client: AsyncAnthropic = None,
) -> dict:
    """Initialise all enabled Arch Agents in startup sequence order.

    Returns dict of agent_name -> agent instance.
    """
    global _arch_agents

    if client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        client = AsyncAnthropic(api_key=api_key)

    agents = {}

    # Startup sequence: Sentinel → Sovereign → Treasurer → Auditor → Arbiter → Architect → Ambassador
    startup_order = [
        ("sentinel", "ARCH_SENTINEL_ENABLED"),
        ("sovereign", "ARCH_SOVEREIGN_ENABLED"),
        ("treasurer", "ARCH_TREASURER_ENABLED"),
        ("auditor", "ARCH_AUDITOR_ENABLED"),
        ("arbiter", "ARCH_ARBITER_ENABLED"),
        ("architect", "ARCH_ARCHITECT_ENABLED"),
        ("ambassador", "ARCH_AMBASSADOR_ENABLED"),
    ]

    for agent_name, flag in startup_order:
        if os.getenv(flag, "false").lower() != "true":
            continue

        try:
            agent = _create_agent(agent_name, db, redis, client)
            if agent:
                agents[agent_name] = agent
                # Set status to ACTIVE
                await db.execute(
                    text("UPDATE arch_agents SET status = 'ACTIVE' WHERE agent_name = :n"),
                    {"n": agent_name},
                )
                await db.commit()
                log.info(f"[arch] {agent_name} activated")
        except Exception as e:
            log.error(f"[arch] Failed to activate {agent_name}: {e}")
            # Sentinel failure blocks all others
            if agent_name == "sentinel":
                log.critical("[arch] SENTINEL FAILED — blocking all agent activation")
                break
            # Sovereign failure blocks remaining
            if agent_name == "sovereign":
                log.critical("[arch] SOVEREIGN FAILED — blocking remaining agents")
                break

    _arch_agents = agents
    return agents


def _create_agent(
    agent_name: str,
    db: AsyncSession,
    redis: aioredis.Redis,
    client: AsyncAnthropic,
):
    """Create a specific agent instance."""
    if agent_name == "sentinel":
        from app.arch.agents.sentinel import SentinelAgent
        return SentinelAgent(agent_id="sentinel", db=db, redis=redis, client=client)
    elif agent_name == "sovereign":
        from app.arch.agents.sovereign import SovereignAgent
        return SovereignAgent(agent_id="sovereign", db=db, redis=redis, client=client)
    elif agent_name == "treasurer":
        from app.arch.agents.treasurer import TreasurerAgent
        return TreasurerAgent(agent_id="treasurer", db=db, redis=redis, client=client)
    elif agent_name == "auditor":
        from app.arch.agents.auditor import AuditorAgent
        return AuditorAgent(agent_id="auditor", db=db, redis=redis, client=client)
    elif agent_name == "arbiter":
        from app.arch.agents.arbiter import ArbiterAgent
        return ArbiterAgent(agent_id="arbiter", db=db, redis=redis, client=client)
    elif agent_name == "architect":
        from app.arch.agents.architect import ArchitectAgent
        return ArchitectAgent(agent_id="architect", db=db, redis=redis, client=client)
    elif agent_name == "ambassador":
        from app.arch.agents.ambassador import AmbassadorAgent
        return AmbassadorAgent(agent_id="ambassador", db=db, redis=redis, client=client)
    return None


async def get_arch_agents(db: AsyncSession = None) -> dict:
    """Return currently initialised agents."""
    return _arch_agents
