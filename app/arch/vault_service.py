"""B-1: Vault service — encrypted key-value storage with tier-based limits.
Tables: vault_objects, agent_vaults (existing). Sandbox mode."""
import os, json, logging, uuid, hashlib, base64
from datetime import datetime, timezone

log = logging.getLogger("arch.vault_service")

TIER_LIMITS = {"AV-CACHE": 10, "AV-LOCKER": 100, "AV-CHAMBER": 1000, "AV-CITADEL": -1}


def _encrypt(data, vault_key):
    """Simple XOR encryption for sandbox (production would use AES-256-GCM)."""
    key_bytes = hashlib.sha256(vault_key.encode()).digest()
    data_bytes = data.encode() if isinstance(data, str) else data
    encrypted = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data_bytes))
    return base64.b64encode(encrypted).decode()


def _decrypt(encrypted_data, vault_key):
    """Decrypt XOR-encrypted data."""
    key_bytes = hashlib.sha256(vault_key.encode()).digest()
    data_bytes = base64.b64decode(encrypted_data)
    decrypted = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data_bytes))
    return decrypted.decode()


async def store_entry(db, vault_id, key, value, vault_tier="AV-CACHE"):
    """Store an encrypted entry in the vault."""
    if os.environ.get("SANDBOX_MODE", "false").lower() != "true":
        return {"error": "Requires SANDBOX_MODE=true"}

    from sqlalchemy import text
    try:
        await db.rollback()
    except Exception as e:
        import logging; logging.getLogger("vault_service").warning(f"Suppressed: {e}")

    # Auto-create vault if it doesn't exist
    existing = await db.execute(text("SELECT id FROM agent_vaults WHERE id = :vid"), {"vid": vault_id})
    if not existing.fetchone():
        # Resolve tier UUID from tier name mapping
        tier_map = {"AV-CACHE": "cache", "AV-LOCKER": "locker", "AV-CHAMBER": "chamber", "AV-CITADEL": "citadel"}
        tier_name = tier_map.get(vault_tier, "cache")
        tier_row = await db.execute(text("SELECT id, storage_quota_bytes FROM agentvault_tiers WHERE tier_name = :tn LIMIT 1"), {"tn": tier_name})
        tier_data = tier_row.fetchone()
        tier_uuid = str(tier_data.id) if tier_data else vault_tier
        quota = tier_data.storage_quota_bytes if tier_data else 1048576
        # For sandbox: create a dedicated agent so we don't hit the unique constraint
        import uuid as _uuid
        sandbox_agent_id = str(_uuid.uuid4())
        await db.execute(text(
            "INSERT INTO agents (id, name, platform, api_key_hash, is_active, created_at) "
            "VALUES (:aid, :name, 'sandbox', :apihash, true, now()) ON CONFLICT DO NOTHING"
        ), {"aid": sandbox_agent_id, "name": f"Sandbox Vault Agent ({vault_id})", "apihash": hashlib.sha256(sandbox_agent_id.encode()).hexdigest()})
        # Resolve operator
        op_row_r = await db.execute(text("SELECT id FROM operators LIMIT 1"))
        op_row = op_row_r.fetchone()
        operator_id = str(op_row.id) if op_row else sandbox_agent_id
        await db.execute(text(
            "INSERT INTO agent_vaults (id, agent_id, operator_id, vault_tier_id, status, billing_cycle, quota_bytes, vault_namespace) "
            "VALUES (:vid, :aid, :oid, :tier, 'active', 'monthly', :quota, :ns)"
        ), {"vid": vault_id, "aid": sandbox_agent_id, "oid": operator_id, "tier": tier_uuid, "quota": quota, "ns": f"sandbox/{vault_id}"})
        await db.commit()

    # Check tier capacity
    limit = TIER_LIMITS.get(vault_tier, 10)
    if limit != -1:
        r = await db.execute(text(
            "SELECT count(*) FROM vault_objects WHERE vault_id = :vid AND is_current_version = true"
        ), {"vid": vault_id})
        count = r.scalar() or 0
        if count >= limit:
            return {"error": f"Vault capacity reached ({count}/{limit}). Upgrade tier.", "tier": vault_tier}

    # Encrypt
    vault_key = f"{vault_id}_{os.environ.get('SECRET_KEY', 'sandbox')}"
    value_str = json.dumps(value) if not isinstance(value, str) else value
    encrypted = _encrypt(value_str, vault_key)
    content_hash = hashlib.sha256(value_str.encode()).hexdigest()

    obj_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO vault_objects (id, vault_id, object_key, size_bytes, content_type, "
        "sha256_hash, content, version_number, is_current_version, storage_class) "
        "VALUES (:id, :vid, :key, :size, 'application/json', :hash, :content, 1, true, 'encrypted')"
    ), {"id": obj_id, "vid": vault_id, "key": key, "size": len(encrypted),
        "hash": content_hash, "content": encrypted})

    # Audit log
    await db.execute(text(
        "INSERT INTO vault_audit_log (id, vault_id, action, object_key, agent_id, ip_address) "
        "VALUES (:id, :vid, 'STORE', :key, :vid, '127.0.0.1')"
    ), {"id": str(uuid.uuid4()), "vid": vault_id, "key": key})
    await db.commit()

    return {"object_id": obj_id, "key": key, "size_bytes": len(encrypted),
            "encrypted": True, "tier": vault_tier, "sandbox": True}


async def retrieve_entry(db, vault_id, key):
    """Retrieve and decrypt a vault entry."""
    from sqlalchemy import text
    try:
        await db.rollback()
    except Exception as e:
        import logging; logging.getLogger("vault_service").warning(f"Suppressed: {e}")
    r = await db.execute(text(
        "SELECT id, content, sha256_hash FROM vault_objects "
        "WHERE vault_id = :vid AND object_key = :key AND is_current_version = true"
    ), {"vid": vault_id, "key": key})
    row = r.fetchone()
    if not row:
        return {"error": "Entry not found", "key": key}

    vault_key = f"{vault_id}_{os.environ.get('SECRET_KEY', 'sandbox')}"
    try:
        decrypted = _decrypt(row.content, vault_key)
        value = json.loads(decrypted)
    except Exception as e:
        value = decrypted if isinstance(decrypted, str) else str(decrypted)

    # Audit
    await db.execute(text(
        "INSERT INTO vault_audit_log (id, vault_id, action, object_key, agent_id, ip_address) "
        "VALUES (:id, :vid, 'RETRIEVE', :key, :vid, '127.0.0.1')"
    ), {"id": str(uuid.uuid4()), "vid": vault_id, "key": key})
    await db.commit()

    return {"key": key, "value": value, "hash": row.sha256_hash, "sandbox": True}


async def delete_entry(db, vault_id, key):
    """Delete a vault entry."""
    from sqlalchemy import text
    try:
        await db.rollback()
    except Exception as e:
        import logging; logging.getLogger("vault_service").warning(f"Suppressed: {e}")
    await db.execute(text(
        "UPDATE vault_objects SET is_current_version = false WHERE vault_id = :vid AND object_key = :key"
    ), {"vid": vault_id, "key": key})
    await db.execute(text(
        "INSERT INTO vault_audit_log (id, vault_id, action, object_key, agent_id, ip_address) "
        "VALUES (:id, :vid, 'DELETE', :key, :vid, '127.0.0.1')"
    ), {"id": str(uuid.uuid4()), "vid": vault_id, "key": key})
    await db.commit()
    return {"key": key, "deleted": True, "sandbox": True}


async def list_entries(db, vault_id):
    """List all keys in a vault (no values)."""
    from sqlalchemy import text
    try:
        await db.rollback()
    except Exception as e:
        import logging; logging.getLogger("vault_service").warning(f"Suppressed: {e}")
    r = await db.execute(text(
        "SELECT object_key, size_bytes, sha256_hash FROM vault_objects "
        "WHERE vault_id = :vid AND is_current_version = true ORDER BY object_key"
    ), {"vid": vault_id})
    return [{"key": row.object_key, "size": row.size_bytes, "hash": row.sha256_hash[:12]}
            for row in r.fetchall()]


async def get_usage(db, vault_id, tier="AV-CACHE"):
    """Get vault usage vs tier limit."""
    from sqlalchemy import text
    try:
        await db.rollback()
    except Exception as e:
        import logging; logging.getLogger("vault_service").warning(f"Suppressed: {e}")
    r = await db.execute(text(
        "SELECT count(*) as entries, COALESCE(sum(size_bytes),0) as total_bytes "
        "FROM vault_objects WHERE vault_id = :vid AND is_current_version = true"
    ), {"vid": vault_id})
    row = r.fetchone()
    limit = TIER_LIMITS.get(tier, 10)
    return {"vault_id": vault_id, "tier": tier, "entries": row.entries,
            "total_bytes": int(row.total_bytes), "limit": limit,
            "usage_pct": round(row.entries / limit * 100, 1) if limit > 0 else 0,
            "sandbox": True}
