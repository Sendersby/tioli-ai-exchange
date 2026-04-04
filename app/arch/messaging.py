"""Arch Agent Messaging — Redis pub/sub for inter-agent communication.

Two channels:
- arch.urgent: real-time urgent messages (P1 incidents, emergency board)
- arch.board: board deliberations and routine coordination
- arch.platform_events: platform events for autonomous processing
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import redis.asyncio as aioredis
from sqlalchemy import text

log = logging.getLogger("arch.messaging")


async def start_urgent_listener(redis: aioredis.Redis, agents: dict):
    """Background task: listens for urgent inter-agent messages."""
    pubsub = redis.pubsub()
    await pubsub.subscribe("arch.urgent", "arch.board")
    log.info("Arch urgent listener started on arch.urgent + arch.board")

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            data = json.loads(message["data"])
            await _route_message(data, agents)
        except Exception as e:
            log.error(f"Arch message routing error: {e}", exc_info=True)


async def _route_message(data: dict, agents: dict):
    """Route a message to the target agent or broadcast to all."""
    to_agent = data.get("to_agent", "sovereign")
    if to_agent == "board":
        await asyncio.gather(
            *[agent.handle_board_message(data) for agent in agents.values()],
            return_exceptions=True,
        )
    elif to_agent in agents:
        await agents[to_agent].handle_urgent_message(data)
    else:
        log.warning(f"Unknown target agent: {to_agent}")


async def emit_urgent(
    redis: aioredis.Redis,
    from_agent: str,
    to_agent: str,
    subject: str,
    body: dict,
    priority: str = "URGENT",
):
    """Emit an urgent message via Redis pub/sub."""
    message = json.dumps({
        "from_agent": from_agent,
        "to_agent": to_agent,
        "subject": subject,
        "body": body,
        "priority": priority,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    })
    await redis.publish("arch.urgent", message)


async def emit_board_message(
    redis: aioredis.Redis,
    from_agent: str,
    subject: str,
    body: dict,
    priority: str = "ROUTINE",
):
    """Emit a board message — broadcast to all agents."""
    await emit_urgent(redis, from_agent, "board", subject, body, priority)
