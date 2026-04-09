"""H-008: Credential Pool with Auto-Failover (Hermes-inspired).
Multiple API keys with automatic rotation on rate limit errors.
Feature flag: ARCH_H_CREDENTIAL_POOL_ENABLED"""
import os
import logging
import hashlib

log = logging.getLogger("arch.credential_pool")

# In-memory pool (loaded from DB at startup)
_pool = {}


async def load_pool(db):
    """Load credential pool from database."""
    global _pool
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT pool_id, provider, api_key_hash, is_primary, is_active, error_count "
        "FROM arch_credential_pool WHERE is_active = true ORDER BY is_primary DESC"
    ))
    for row in r.fetchall():
        provider = row.provider
        if provider not in _pool:
            _pool[provider] = []
        _pool[provider].append({
            "pool_id": str(row.pool_id),
            "hash": row.api_key_hash,
            "primary": row.is_primary,
            "errors": row.error_count,
        })
    log.info(f"[cred_pool] Loaded {sum(len(v) for v in _pool.values())} credentials across {len(_pool)} providers")


async def record_usage(db, provider: str, tokens: int, success: bool, error_code: str = None):
    """Record API call result for pool management."""
    if os.environ.get("ARCH_H_CREDENTIAL_POOL_ENABLED", "false").lower() != "true":
        return

    from sqlalchemy import text
    if success:
        await db.execute(text(
            "UPDATE arch_credential_pool SET total_calls = total_calls + 1, "
            "total_tokens = total_tokens + :t, last_used = now() "
            "WHERE provider = :p AND is_primary = true"
        ), {"t": tokens, "p": provider})
    else:
        await db.execute(text(
            "UPDATE arch_credential_pool SET error_count = error_count + 1, "
            "last_error = now(), last_error_code = :code "
            "WHERE provider = :p AND is_primary = true"
        ), {"code": error_code or "unknown", "p": provider})
    await db.commit()


async def get_pool_status(db) -> list:
    """Get credential pool status for dashboard."""
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT provider, api_key_masked, is_primary, total_calls, total_tokens, "
        "error_count, last_used, last_error_code FROM arch_credential_pool ORDER BY provider"
    ))
    return [{"provider": row.provider, "key": row.api_key_masked,
             "primary": row.is_primary, "calls": row.total_calls,
             "tokens": row.total_tokens, "errors": row.error_count,
             "last_used": str(row.last_used) if row.last_used else None,
             "last_error": row.last_error_code} for row in r.fetchall()]
