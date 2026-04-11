"""Redis caching layer for hot endpoints.

Usage:
    from app.utils.cache import get_cached, invalidate_cache

    @router.get("/api/v1/health")
    async def health():
        return await get_cached("health", 10, lambda: {"status": "operational"})
"""

import json
import redis.asyncio as redis
import os

_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_redis = redis.from_url(_redis_url, decode_responses=True)


async def get_cached(key: str, ttl_seconds: int, fetch_fn):
    """Get from Redis cache or compute and store."""
    try:
        cached = await _redis.get(f"cache:{key}")
        if cached is not None:
            return json.loads(cached)
    except Exception as e:
        import logging; logging.getLogger("cache").warning(f"Suppressed: {e}")  # Redis down? Fall through to compute

    import asyncio; result = fetch_fn() if callable(fetch_fn) else fetch_fn; data = (await result) if asyncio.iscoroutine(result) else result
    try:
        await _redis.setex(f"cache:{key}", ttl_seconds, json.dumps(data, default=str))
    except Exception as e:
        import logging; logging.getLogger("cache").warning(f"Suppressed: {e}")  # Redis down? Return data anyway

    return data


async def invalidate_cache(key: str):
    """Remove a key from cache."""
    try:
        await _redis.delete(f"cache:{key}")
    except Exception as e:
        import logging; logging.getLogger("cache").warning(f"Suppressed: {e}")


async def invalidate_pattern(pattern: str):
    """Remove all keys matching a pattern."""
    try:
        keys = []
        async for key in _redis.scan_iter(f"cache:{pattern}"):
            keys.append(key)
        if keys:
            await _redis.delete(*keys)
    except Exception as e:
        import logging; logging.getLogger("cache").warning(f"Suppressed: {e}")
