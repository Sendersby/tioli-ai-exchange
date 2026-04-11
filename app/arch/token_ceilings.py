"""ARCH-CO-005: Per-task token budget ceilings."""
import os
import logging

log = logging.getLogger("arch.token_ceilings")

# In-memory cache of ceilings (loaded once, refreshed on restart)
_ceiling_cache = {}


async def get_max_tokens(db, agent_id, task_type, default=1000):
    """Look up the max_tokens ceiling for a task.
    Feature flag: ARCH_CO_TOKEN_CEILINGS_ENABLED
    Override: <AGENT>_<TASK>_MAX_TOKENS env var."""

    if os.environ.get("ARCH_CO_TOKEN_CEILINGS_ENABLED", "false").lower() != "true":
        return None  # Use default

    # Check env override first
    env_key = f"{agent_id.upper()}_{task_type.upper()}_MAX_TOKENS"
    env_override = os.environ.get(env_key)
    if env_override:
        return int(env_override)

    # Check cache
    cache_key = f"{agent_id}:{task_type}"
    if cache_key in _ceiling_cache:
        return _ceiling_cache[cache_key]

    # Query DB
    from sqlalchemy import text
    try:
        result = await db.execute(text(
            "SELECT max_tokens FROM task_token_ceilings WHERE agent_id = :aid AND task_type = :tt"
        ), {"aid": agent_id, "tt": task_type})
        row = result.fetchone()
        if row:
            _ceiling_cache[cache_key] = row.max_tokens
            return row.max_tokens
    except Exception as e:
        import logging; logging.getLogger("token_ceilings").warning(f"Suppressed: {e}")

    log.warning(f"MISSING_TOKEN_CEILING for {task_type} on {agent_id} — using default {default}")
    return default
