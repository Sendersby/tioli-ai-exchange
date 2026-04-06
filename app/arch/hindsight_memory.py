"""Hindsight-enhanced memory — dual-write to local pgvector + Hindsight hosted service.

If Hindsight API key is available, writes to both stores and merges recall results.
If not available, falls back to local pgvector only (transparent).
"""
import os
import logging
import httpx

log = logging.getLogger("arch.hindsight")

HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY", "")
HINDSIGHT_BASE_URL = "https://api.hindsight.vectorize.io/v1"
HINDSIGHT_AVAILABLE = bool(HINDSIGHT_API_KEY)

if HINDSIGHT_AVAILABLE:
    log.info("Hindsight memory service: CONNECTED")
else:
    log.info("Hindsight memory service: NOT CONFIGURED (using local pgvector only)")


async def hindsight_retain(agent_id: str, content: str, metadata: dict = None) -> dict:
    """Store a memory in Hindsight's hosted service."""
    if not HINDSIGHT_AVAILABLE:
        return {"stored": False, "reason": "Hindsight not configured"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{HINDSIGHT_BASE_URL}/memories",
                headers={"Authorization": f"Bearer {HINDSIGHT_API_KEY}"},
                json={
                    "agent_id": agent_id,
                    "content": content,
                    "metadata": metadata or {},
                },
            )
            if resp.status_code in (200, 201):
                return {"stored": True, "service": "hindsight"}
            else:
                return {"stored": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"stored": False, "error": str(e)}


async def hindsight_recall(agent_id: str, query: str, limit: int = 5) -> list:
    """Recall memories from Hindsight's hosted service."""
    if not HINDSIGHT_AVAILABLE:
        return []

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{HINDSIGHT_BASE_URL}/recall",
                headers={"Authorization": f"Bearer {HINDSIGHT_API_KEY}"},
                json={
                    "agent_id": agent_id,
                    "query": query,
                    "limit": limit,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", data.get("memories", []))
    except Exception as e:
        log.debug(f"Hindsight recall failed: {e}")

    return []


async def hindsight_reflect(agent_id: str, topic: str) -> str:
    """Synthesize memories on a topic using Hindsight's reflect operation."""
    if not HINDSIGHT_AVAILABLE:
        return ""

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{HINDSIGHT_BASE_URL}/reflect",
                headers={"Authorization": f"Bearer {HINDSIGHT_API_KEY}"},
                json={"agent_id": agent_id, "topic": topic},
            )
            if resp.status_code == 200:
                return resp.json().get("reflection", "")
    except Exception as e:
        log.debug(f"Hindsight reflect failed: {e}")

    return ""
