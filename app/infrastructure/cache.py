"""Redis caching layer — improves response times for frequently accessed data.

Caches: exchange rates, subscription tiers, fee schedule, market intelligence,
jurisdiction rules, liquidity status. All caches have TTL and auto-expire.
"""

import json
import logging
import os

import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# TTL defaults (seconds)
TTL_SHORT = 60          # 1 minute — volatile data (prices, order book)
TTL_MEDIUM = 300        # 5 minutes — semi-stable (liquidity, stats)
TTL_LONG = 3600         # 1 hour — stable (tiers, fee schedule, jurisdictions)
TTL_DAY = 86400         # 24 hours — rarely changes (verticals, licensing)


class CacheService:
    """Redis-backed caching for API responses."""

    def __init__(self):
        try:
            self._redis = redis.from_url(REDIS_URL, decode_responses=True)
            self._redis.ping()
            self._available = True
            logger.info("Redis cache connected")
        except Exception as e:
            self._redis = None
            self._available = False
            logger.warning(f"Redis not available, caching disabled: {e}")

    @property
    def available(self) -> bool:
        return self._available

    def get(self, key: str) -> dict | list | None:
        """Get cached value. Returns None on miss or if Redis unavailable."""
        if not self._available:
            return None
        try:
            data = self._redis.get(f"tioli:{key}")
            if data:
                return json.loads(data)
        except Exception as e:
            import logging; logging.getLogger("cache").warning(f"Suppressed: {e}")
        return None

    def set(self, key: str, value, ttl: int = TTL_MEDIUM) -> bool:
        """Cache a value with TTL. Returns True on success."""
        if not self._available:
            return False
        try:
            self._redis.setex(f"tioli:{key}", ttl, json.dumps(value, default=str))
            return True
        except Exception as e:
            return False

    def delete(self, key: str) -> bool:
        """Delete a cached key."""
        if not self._available:
            return False
        try:
            self._redis.delete(f"tioli:{key}")
            return True
        except Exception as e:
            return False

    def clear_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern. Returns count deleted."""
        if not self._available:
            return 0
        try:
            keys = self._redis.keys(f"tioli:{pattern}")
            if keys:
                return self._redis.delete(*keys)
        except Exception as e:
            import logging; logging.getLogger("cache").warning(f"Suppressed: {e}")
        return 0

    def get_stats(self) -> dict:
        """Get cache statistics."""
        if not self._available:
            return {"available": False}
        try:
            info = self._redis.info("stats")
            memory = self._redis.info("memory")
            keycount = self._redis.dbsize()
            return {
                "available": True,
                "keys": keycount,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": round(
                    info.get("keyspace_hits", 0) /
                    max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1) * 100, 1
                ),
                "memory_used_mb": round(memory.get("used_memory", 0) / 1024 / 1024, 2),
            }
        except Exception as e:
            return {"available": True, "error": "Could not fetch stats"}


# Singleton
cache = CacheService()
