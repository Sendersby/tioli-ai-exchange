"""Platform event emission — called from existing endpoint handlers.

Purely additive: wraps all emissions in ARCH_AGENTS_ENABLED check.
Zero performance impact when arch agents are disabled.
"""

import json
import logging
import os
from datetime import datetime, timezone

log = logging.getLogger("arch.events")


async def emit_platform_event(
    event_type: str,
    event_data: dict,
    source_module: str,
    db=None,
):
    """Emit a platform event for Arch Agent processing.

    Call this at the end of existing endpoint handlers — purely additive.
    Writes to arch_platform_events table and publishes to Redis.
    """
    if os.getenv("ARCH_AGENTS_ENABLED", "false").lower() != "true":
        return

    try:
        from sqlalchemy import text as sa_text

        if db is not None:
            await db.execute(
                sa_text("""
                    INSERT INTO arch_platform_events
                        (event_type, event_data, source_module)
                    VALUES (:event_type, :event_data, :source_module)
                """),
                {
                    "event_type": event_type,
                    "event_data": json.dumps(event_data),
                    "source_module": source_module,
                },
            )
            await db.commit()

        # Also publish to Redis for real-time processing
        try:
            import redis.asyncio as aioredis

            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            redis = aioredis.from_url(redis_url)
            await redis.publish(
                "arch.platform_events",
                json.dumps({
                    "event_type": event_type,
                    "data": event_data,
                    "source": source_module,
                    "emitted_at": datetime.now(timezone.utc).isoformat(),
                }),
            )
            await redis.aclose()
        except Exception as e:
            log.warning(f"Redis event publish failed (non-fatal): {e}")

    except Exception as e:
        log.error(f"Platform event emission failed (non-fatal): {e}")
