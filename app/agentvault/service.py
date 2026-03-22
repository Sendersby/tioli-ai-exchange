"""AgentVault™ service — vault management, object operations, audit, delegates."""

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.agentvault.models import (
    AgentVaultTier, AgentVault, VaultObject, VaultAuditLog,
    VaultBundleSubscription, VaultDelegate,
    VAULT_TIER_SEEDS, PRIVATE_KEY_PATTERNS, SUGGESTED_FOLDERS,
)
from app.agents.models import Agent

logger = logging.getLogger(__name__)


class AgentVaultService:
    """Manages vault lifecycle, objects, audit, and delegates."""

    # ── Tier Seeding ──────────────────────────────────────────────────

    async def seed_tiers(self, db: AsyncSession) -> None:
        for seed in VAULT_TIER_SEEDS:
            existing = await db.execute(
                select(AgentVaultTier).where(AgentVaultTier.tier_name == seed["tier_name"])
            )
            if not existing.scalar_one_or_none():
                db.add(AgentVaultTier(**seed))
        await db.flush()

    async def list_tiers(self, db: AsyncSession) -> list[dict]:
        result = await db.execute(
            select(AgentVaultTier).where(AgentVaultTier.is_active == True)
            .order_by(AgentVaultTier.sort_order)
        )
        return [self._tier_to_dict(t) for t in result.scalars().all()]

    # ── Vault Management ──────────────────────────────────────────────

    async def create_vault(
        self, db: AsyncSession, agent_id: str, operator_id: str = "",
        tier_name: str = "cache", billing_cycle: str = "free",
        popia_consent: bool = False,
    ) -> dict:
        existing = await db.execute(
            select(AgentVault).where(AgentVault.agent_id == agent_id, AgentVault.status != "cancelled")
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent already has an active vault")

        tier = await self._get_tier(db, tier_name)
        if not tier:
            raise ValueError(f"Unknown tier: {tier_name}")

        namespace = f"av_{agent_id[:12]}"
        enc_ref = hashlib.sha256(f"{agent_id}:{datetime.now(timezone.utc)}".encode()).hexdigest()[:32]

        now = datetime.now(timezone.utc)
        period_end = now + timedelta(days=30) if billing_cycle == "monthly" else (
            now + timedelta(days=365) if billing_cycle == "annual" else None
        )

        effective_price = tier.monthly_price_zar
        if billing_cycle == "annual" and tier.annual_price_zar > 0:
            effective_price = round(tier.annual_price_zar / 12, 2)

        vault = AgentVault(
            agent_id=agent_id, operator_id=operator_id,
            vault_tier_id=tier.id, status="active",
            billing_cycle=billing_cycle if tier.monthly_price_zar > 0 else "free",
            effective_monthly_zar=effective_price if tier.monthly_price_zar > 0 else 0,
            quota_bytes=tier.storage_quota_bytes,
            current_period_end=period_end,
            encryption_key_ref=enc_ref, vault_namespace=namespace,
            popia_consent=popia_consent,
            popia_consent_at=now if popia_consent else None,
        )
        db.add(vault)
        await db.flush()

        await self._audit(db, vault.id, agent_id, "CREATE", result="success")

        return self._vault_to_dict(vault, tier)

    async def get_vault(self, db: AsyncSession, agent_id: str) -> dict | None:
        result = await db.execute(
            select(AgentVault).where(AgentVault.agent_id == agent_id, AgentVault.status != "cancelled")
        )
        vault = result.scalar_one_or_none()
        if not vault:
            return None
        tier = await db.execute(select(AgentVaultTier).where(AgentVaultTier.id == vault.vault_tier_id))
        return self._vault_to_dict(vault, tier.scalar_one_or_none())

    async def get_vault_by_id(self, db: AsyncSession, vault_id: str) -> dict | None:
        result = await db.execute(select(AgentVault).where(AgentVault.id == vault_id))
        vault = result.scalar_one_or_none()
        if not vault:
            return None
        tier = await db.execute(select(AgentVaultTier).where(AgentVaultTier.id == vault.vault_tier_id))
        return self._vault_to_dict(vault, tier.scalar_one_or_none())

    async def upgrade_vault(self, db: AsyncSession, vault_id: str, new_tier_name: str) -> dict:
        vault_result = await db.execute(select(AgentVault).where(AgentVault.id == vault_id))
        vault = vault_result.scalar_one_or_none()
        if not vault:
            raise ValueError("Vault not found")

        new_tier = await self._get_tier(db, new_tier_name)
        if not new_tier:
            raise ValueError(f"Unknown tier: {new_tier_name}")
        if new_tier.storage_quota_bytes <= vault.quota_bytes:
            raise ValueError("Can only upgrade to a higher tier")

        vault.vault_tier_id = new_tier.id
        vault.quota_bytes = new_tier.storage_quota_bytes
        vault.effective_monthly_zar = new_tier.monthly_price_zar
        vault.updated_at = datetime.now(timezone.utc)
        if vault.status == "quota_exceeded":
            vault.status = "active"
        await db.flush()

        await self._audit(db, vault.id, vault.agent_id, "UPGRADE", result="success")
        return self._vault_to_dict(vault, new_tier)

    async def downgrade_vault(self, db: AsyncSession, vault_id: str, new_tier_name: str) -> dict:
        vault_result = await db.execute(select(AgentVault).where(AgentVault.id == vault_id))
        vault = vault_result.scalar_one_or_none()
        if not vault:
            raise ValueError("Vault not found")

        new_tier = await self._get_tier(db, new_tier_name)
        if not new_tier:
            raise ValueError(f"Unknown tier: {new_tier_name}")
        if vault.used_bytes > new_tier.storage_quota_bytes:
            raise ValueError(f"Cannot downgrade — used {vault.used_bytes} bytes exceeds {new_tier.display_name} quota of {new_tier.storage_quota_bytes}")

        vault.vault_tier_id = new_tier.id
        vault.quota_bytes = new_tier.storage_quota_bytes
        vault.effective_monthly_zar = new_tier.monthly_price_zar
        vault.updated_at = datetime.now(timezone.utc)
        await db.flush()

        await self._audit(db, vault.id, vault.agent_id, "DOWNGRADE", result="success")
        return self._vault_to_dict(vault, new_tier)

    async def cancel_vault(self, db: AsyncSession, vault_id: str) -> dict:
        vault_result = await db.execute(select(AgentVault).where(AgentVault.id == vault_id))
        vault = vault_result.scalar_one_or_none()
        if not vault:
            raise ValueError("Vault not found")
        vault.status = "cancelled"
        vault.updated_at = datetime.now(timezone.utc)
        await db.flush()
        await self._audit(db, vault.id, vault.agent_id, "CANCEL", result="success")
        return {"vault_id": vault_id, "status": "cancelled", "grace_period_days": 30}

    # ── Object Operations ─────────────────────────────────────────────

    async def put_object(
        self, db: AsyncSession, vault_id: str, agent_id: str,
        object_key: str, content: str, content_type: str = "text/plain",
        asset_type: str | None = None, metadata: dict | None = None,
    ) -> dict:
        vault = await self._get_vault_record(db, vault_id)
        if not vault or vault.status not in ("active",):
            raise ValueError("Vault not found or not active")

        # Private key detection
        for pattern in PRIVATE_KEY_PATTERNS:
            if pattern in content:
                await self._audit(db, vault_id, agent_id, "PUT", object_key, result="denied")
                raise ValueError("Private key material detected — storage of private keys is prohibited")

        content_bytes = len(content.encode("utf-8"))
        sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Quota check
        if vault.used_bytes + content_bytes > vault.quota_bytes:
            await self._audit(db, vault_id, agent_id, "PUT", object_key, result="quota_exceeded")
            raise ValueError("Insufficient storage — vault quota exceeded")

        # Check for existing object at this key (version it)
        existing = await db.execute(
            select(VaultObject).where(
                VaultObject.vault_id == vault_id,
                VaultObject.object_key == object_key,
                VaultObject.is_current_version == True,
            )
        )
        prev = existing.scalar_one_or_none()
        prev_version = 0
        if prev:
            prev.is_current_version = False
            prev_version = prev.version_number
            # Reclaim old size
            vault.used_bytes = max(0, vault.used_bytes - prev.size_bytes)

        obj = VaultObject(
            vault_id=vault_id, object_key=object_key,
            size_bytes=content_bytes, content_type=content_type,
            asset_type=asset_type, sha256_hash=sha256,
            content=content, version_number=prev_version + 1,
            previous_version_id=prev.id if prev else None,
            object_metadata=metadata,
        )
        db.add(obj)
        vault.used_bytes += content_bytes
        vault.updated_at = datetime.now(timezone.utc)

        if vault.used_bytes >= vault.quota_bytes:
            vault.status = "quota_exceeded"

        await db.flush()
        await self._audit(db, vault_id, agent_id, "PUT", object_key, bytes_delta=content_bytes)

        return {
            "object_id": obj.id, "key": object_key, "size": content_bytes,
            "version": obj.version_number, "sha256": sha256,
            "used_bytes": vault.used_bytes, "quota_bytes": vault.quota_bytes,
            "used_pct": round(vault.used_bytes / vault.quota_bytes * 100, 1),
        }

    async def get_object(
        self, db: AsyncSession, vault_id: str, agent_id: str,
        object_key: str, version: int | None = None,
    ) -> dict | None:
        query = select(VaultObject).where(
            VaultObject.vault_id == vault_id,
            VaultObject.object_key == object_key,
        )
        if version:
            query = query.where(VaultObject.version_number == version)
        else:
            query = query.where(VaultObject.is_current_version == True)

        result = await db.execute(query)
        obj = result.scalar_one_or_none()
        if not obj:
            await self._audit(db, vault_id, agent_id, "GET", object_key, result="not_found")
            return None

        obj.last_accessed_at = datetime.now(timezone.utc)
        await db.flush()
        await self._audit(db, vault_id, agent_id, "GET", object_key)

        return {
            "object_id": obj.id, "key": obj.object_key,
            "content": obj.content, "size": obj.size_bytes,
            "content_type": obj.content_type, "asset_type": obj.asset_type,
            "sha256": obj.sha256_hash, "version": obj.version_number,
            "metadata": obj.object_metadata,
            "created_at": str(obj.created_at),
            "last_accessed": str(obj.last_accessed_at),
        }

    async def delete_object(
        self, db: AsyncSession, vault_id: str, agent_id: str, object_key: str,
    ) -> dict:
        result = await db.execute(
            select(VaultObject).where(
                VaultObject.vault_id == vault_id,
                VaultObject.object_key == object_key,
                VaultObject.is_current_version == True,
            )
        )
        obj = result.scalar_one_or_none()
        if not obj:
            raise ValueError("Object not found")

        vault = await self._get_vault_record(db, vault_id)
        vault.used_bytes = max(0, vault.used_bytes - obj.size_bytes)
        if vault.status == "quota_exceeded" and vault.used_bytes < vault.quota_bytes:
            vault.status = "active"

        await db.delete(obj)
        await db.flush()
        await self._audit(db, vault_id, agent_id, "DELETE", object_key, bytes_delta=-obj.size_bytes)

        return {"deleted": object_key, "reclaimed_bytes": obj.size_bytes, "used_bytes": vault.used_bytes}

    async def list_objects(
        self, db: AsyncSession, vault_id: str,
        prefix: str | None = None, asset_type: str | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[dict]:
        query = select(VaultObject).where(
            VaultObject.vault_id == vault_id,
            VaultObject.is_current_version == True,
        )
        if prefix:
            query = query.where(VaultObject.object_key.startswith(prefix))
        if asset_type:
            query = query.where(VaultObject.asset_type == asset_type)
        query = query.order_by(VaultObject.object_key).offset(offset).limit(limit)

        result = await db.execute(query)
        return [
            {
                "object_id": o.id, "key": o.object_key, "size": o.size_bytes,
                "type": o.content_type, "asset_type": o.asset_type,
                "version": o.version_number, "sha256": o.sha256_hash[:16] + "...",
                "created_at": str(o.created_at),
                "last_accessed": str(o.last_accessed_at) if o.last_accessed_at else None,
            }
            for o in result.scalars().all()
        ]

    async def get_object_versions(
        self, db: AsyncSession, vault_id: str, object_key: str,
    ) -> list[dict]:
        result = await db.execute(
            select(VaultObject).where(
                VaultObject.vault_id == vault_id,
                VaultObject.object_key == object_key,
            ).order_by(VaultObject.version_number.desc())
        )
        return [
            {
                "version": o.version_number, "size": o.size_bytes,
                "sha256": o.sha256_hash, "is_current": o.is_current_version,
                "created_at": str(o.created_at),
            }
            for o in result.scalars().all()
        ]

    async def get_usage(self, db: AsyncSession, vault_id: str) -> dict:
        vault = await self._get_vault_record(db, vault_id)
        if not vault:
            raise ValueError("Vault not found")

        # By asset type breakdown
        type_result = await db.execute(
            select(VaultObject.asset_type, func.count(VaultObject.id), func.sum(VaultObject.size_bytes))
            .where(VaultObject.vault_id == vault_id, VaultObject.is_current_version == True)
            .group_by(VaultObject.asset_type)
        )
        by_type = {row[0] or "untyped": {"count": row[1], "bytes": row[2] or 0} for row in type_result}

        total_objects = (await db.execute(
            select(func.count(VaultObject.id)).where(
                VaultObject.vault_id == vault_id, VaultObject.is_current_version == True
            )
        )).scalar() or 0

        return {
            "vault_id": vault_id,
            "used_bytes": vault.used_bytes,
            "quota_bytes": vault.quota_bytes,
            "used_pct": round(vault.used_bytes / max(vault.quota_bytes, 1) * 100, 1),
            "object_count": total_objects,
            "by_asset_type": by_type,
        }

    # ── Audit ─────────────────────────────────────────────────────────

    async def get_audit_log(
        self, db: AsyncSession, vault_id: str,
        action: str | None = None, limit: int = 50,
    ) -> list[dict]:
        query = select(VaultAuditLog).where(VaultAuditLog.vault_id == vault_id)
        if action:
            query = query.where(VaultAuditLog.action == action.upper())
        query = query.order_by(VaultAuditLog.created_at.desc()).limit(limit)
        result = await db.execute(query)
        return [
            {
                "log_id": l.id, "action": l.action, "object_key": l.object_key,
                "bytes_delta": l.bytes_delta, "result": l.result,
                "agent_id": l.agent_id, "ip": l.ip_address,
                "created_at": str(l.created_at),
            }
            for l in result.scalars().all()
        ]

    # ── Delegates ─────────────────────────────────────────────────────

    async def add_delegate(
        self, db: AsyncSession, vault_id: str, delegate_agent_id: str,
        granted_by: str, can_read: bool = True, can_write: bool = False,
        can_delete: bool = False,
    ) -> dict:
        existing = await db.execute(
            select(VaultDelegate).where(
                VaultDelegate.vault_id == vault_id,
                VaultDelegate.delegate_agent_id == delegate_agent_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Delegate already exists")

        delegate = VaultDelegate(
            vault_id=vault_id, delegate_agent_id=delegate_agent_id,
            can_read=can_read, can_write=can_write, can_delete=can_delete,
            granted_by_agent_id=granted_by,
        )
        db.add(delegate)
        await db.flush()
        return {"delegate": delegate_agent_id, "read": can_read, "write": can_write, "delete": can_delete}

    async def remove_delegate(self, db: AsyncSession, vault_id: str, delegate_agent_id: str) -> dict:
        result = await db.execute(
            select(VaultDelegate).where(
                VaultDelegate.vault_id == vault_id,
                VaultDelegate.delegate_agent_id == delegate_agent_id,
            )
        )
        delegate = result.scalar_one_or_none()
        if not delegate:
            raise ValueError("Delegate not found")
        await db.delete(delegate)
        await db.flush()
        return {"removed": delegate_agent_id}

    async def list_delegates(self, db: AsyncSession, vault_id: str) -> list[dict]:
        result = await db.execute(
            select(VaultDelegate).where(VaultDelegate.vault_id == vault_id)
        )
        return [
            {"agent_id": d.delegate_agent_id, "read": d.can_read,
             "write": d.can_write, "delete": d.can_delete,
             "granted_at": str(d.granted_at)}
            for d in result.scalars().all()
        ]

    # ── Helpers ───────────────────────────────────────────────────────

    async def _get_tier(self, db: AsyncSession, tier_name: str) -> AgentVaultTier | None:
        result = await db.execute(
            select(AgentVaultTier).where(AgentVaultTier.tier_name == tier_name)
        )
        return result.scalar_one_or_none()

    async def _get_vault_record(self, db: AsyncSession, vault_id: str) -> AgentVault | None:
        result = await db.execute(select(AgentVault).where(AgentVault.id == vault_id))
        return result.scalar_one_or_none()

    async def _audit(
        self, db: AsyncSession, vault_id: str, agent_id: str,
        action: str, object_key: str | None = None,
        bytes_delta: int = 0, result: str = "success",
    ) -> None:
        db.add(VaultAuditLog(
            vault_id=vault_id, agent_id=agent_id, action=action,
            object_key=object_key, bytes_delta=bytes_delta, result=result,
        ))
        await db.flush()

    def _tier_to_dict(self, t: AgentVaultTier) -> dict:
        return {
            "tier_id": t.id, "tier_name": t.tier_name,
            "display_name": t.display_name,
            "monthly_zar": t.monthly_price_zar, "annual_zar": t.annual_price_zar,
            "storage_quota_bytes": t.storage_quota_bytes,
            "storage_display": self._format_bytes(t.storage_quota_bytes),
            "max_agents": t.max_agents, "max_delegates": t.max_delegates,
            "version_history_days": t.version_history_days,
            "retention_days": t.retention_days,
            "audit_log_days": t.audit_log_days,
            "features": t.features,
            "bundle_tier": t.bundle_operator_tier,
        }

    def _vault_to_dict(self, v: AgentVault, tier: AgentVaultTier | None) -> dict:
        return {
            "vault_id": v.id, "agent_id": v.agent_id,
            "namespace": v.vault_namespace,
            "tier": tier.display_name if tier else "Unknown",
            "tier_name": tier.tier_name if tier else "",
            "status": v.status,
            "billing_cycle": v.billing_cycle,
            "effective_monthly_zar": v.effective_monthly_zar,
            "bundle_discount": v.bundle_discount_applied,
            "used_bytes": v.used_bytes,
            "quota_bytes": v.quota_bytes,
            "used_display": self._format_bytes(v.used_bytes),
            "quota_display": self._format_bytes(v.quota_bytes),
            "used_pct": round(v.used_bytes / max(v.quota_bytes, 1) * 100, 1),
            "period_end": str(v.current_period_end) if v.current_period_end else None,
            "popia_consent": v.popia_consent,
            "created_at": str(v.created_at),
        }

    def _format_bytes(self, b: int) -> str:
        if b >= 1_099_511_627_776: return f"{b / 1_099_511_627_776:.0f} TB"
        if b >= 1_073_741_824: return f"{b / 1_073_741_824:.0f} GB"
        if b >= 1_048_576: return f"{b / 1_048_576:.0f} MB"
        if b >= 1024: return f"{b / 1024:.0f} KB"
        return f"{b} B"
