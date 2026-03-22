"""AgentVault™ — Agentic Secure Storage-as-a-Service.

Non-interest-bearing, non-loanable digital storage utility.
NOT a financial product. NOT a deposit account. NOT custodial.
Storage SaaS — nothing more.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Float, Integer, BigInteger, String, Boolean, Text, JSON,
    ForeignKey, Index,
)

from app.database.db import Base


def _uuid():
    return str(uuid.uuid4())

def _now():
    return datetime.now(timezone.utc)


# ══════════════════════════════════════════════════════════════════════
#  VAULT TIERS
# ══════════════════════════════════════════════════════════════════════

VAULT_TIER_SEEDS = [
    {
        "tier_name": "cache",
        "display_name": "Cache",
        "monthly_price_zar": 0.0,
        "annual_price_zar": 0.0,
        "storage_quota_bytes": 524_288_000,        # 500 MB
        "max_agents": 1,
        "version_history_days": 7,
        "retention_days": 30,
        "max_delegates": 0,
        "audit_log_days": 7,
        "features": ["rest_api"],
        "bundle_operator_tier": "explorer",
        "sort_order": 1,
    },
    {
        "tier_name": "locker",
        "display_name": "Locker",
        "monthly_price_zar": 49.0,
        "annual_price_zar": 470.0,
        "storage_quota_bytes": 10_737_418_240,     # 10 GB
        "max_agents": 5,
        "version_history_days": 30,
        "retention_days": None,
        "max_delegates": 1,
        "audit_log_days": 90,
        "features": ["rest_api", "webhooks", "csv_export"],
        "bundle_operator_tier": "builder",
        "sort_order": 2,
    },
    {
        "tier_name": "chamber",
        "display_name": "Chamber",
        "monthly_price_zar": 149.0,
        "annual_price_zar": 1430.0,
        "storage_quota_bytes": 107_374_182_400,    # 100 GB
        "max_agents": 25,
        "version_history_days": 90,
        "retention_days": None,
        "max_delegates": 10,
        "audit_log_days": 365,
        "features": ["rest_api", "webhooks", "csv_export", "sse", "sars_export", "diff_viewer"],
        "bundle_operator_tier": "professional",
        "sort_order": 3,
    },
    {
        "tier_name": "citadel",
        "display_name": "Citadel",
        "monthly_price_zar": 499.0,
        "annual_price_zar": 4790.0,
        "storage_quota_bytes": 1_099_511_627_776,  # 1 TB
        "max_agents": None,  # unlimited
        "version_history_days": -1,  # unlimited
        "retention_days": None,
        "max_delegates": None,  # unlimited
        "audit_log_days": -1,  # unlimited
        "features": ["rest_api", "webhooks", "csv_export", "sse", "sars_export", "diff_viewer",
                      "bulk_api", "ip_allowlist", "hsm_keys", "legal_hold", "blockchain_anchoring"],
        "bundle_operator_tier": "enterprise",
        "sort_order": 4,
    },
]

BUNDLE_PACKAGES = {
    "spark":     {"operator_tier": "explorer",     "vault_tier": "cache",   "price_zar": 0},
    "scout":     {"operator_tier": "builder",      "vault_tier": "locker",  "price_zar": 799},
    "ranger":    {"operator_tier": "professional", "vault_tier": "chamber", "price_zar": 2999},
    "sovereign": {"operator_tier": "enterprise",   "vault_tier": "citadel", "price_zar": 9999},
}

SUGGESTED_FOLDERS = [
    "/credits", "/compute", "/code", "/engagements", "/work-owed",
    "/tokens", "/staging", "/keys", "/history", "/custom",
]

PRIVATE_KEY_PATTERNS = [
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "-----BEGIN DSA PRIVATE KEY-----",
]


class AgentVaultTier(Base):
    """Storage tier definition — Cache, Locker, Chamber, Citadel."""
    __tablename__ = "agentvault_tiers"

    id = Column(String, primary_key=True, default=_uuid)
    tier_name = Column(String(20), nullable=False, unique=True)
    display_name = Column(String(50), nullable=False)
    monthly_price_zar = Column(Float, nullable=False)
    annual_price_zar = Column(Float, nullable=False)
    storage_quota_bytes = Column(BigInteger, nullable=False)
    max_agents = Column(Integer, nullable=True)  # NULL = unlimited
    version_history_days = Column(Integer, nullable=False)  # -1 = unlimited
    retention_days = Column(Integer, nullable=True)  # NULL = no auto-expiry
    max_delegates = Column(Integer, nullable=True)  # NULL = unlimited
    audit_log_days = Column(Integer, nullable=False)  # -1 = unlimited
    features = Column(JSON, default=list)
    bundle_operator_tier = Column(String(20), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class AgentVault(Base):
    """An agent's personal vault — one per agent."""
    __tablename__ = "agent_vaults"
    __table_args__ = (
        Index("ix_vault_agent", "agent_id", unique=True),
    )

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    operator_id = Column(String, nullable=False)
    vault_tier_id = Column(String, ForeignKey("agentvault_tiers.id"), nullable=False)
    guild_id = Column(String, nullable=True)  # Phase 3: guild shared vaults
    status = Column(String(20), default="active")  # active, suspended, quota_exceeded, cancelled
    billing_cycle = Column(String(10), default="free")  # free, monthly, annual
    bundle_discount_applied = Column(Boolean, default=False)
    effective_monthly_zar = Column(Float, default=0.0)
    used_bytes = Column(BigInteger, default=0)
    quota_bytes = Column(BigInteger, nullable=False)
    current_period_start = Column(DateTime(timezone=True), default=_now)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    encryption_key_ref = Column(String(255), nullable=True)
    vault_namespace = Column(String(255), nullable=False)
    popia_consent = Column(Boolean, default=False)
    popia_consent_at = Column(DateTime(timezone=True), nullable=True)
    ip_allowlist = Column(JSON, nullable=True)  # Citadel only
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now)


class VaultObject(Base):
    """A stored object in a vault."""
    __tablename__ = "vault_objects"
    __table_args__ = (
        Index("ix_vault_object_key", "vault_id", "object_key"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    vault_id = Column(String, ForeignKey("agent_vaults.id"), nullable=False, index=True)
    object_key = Column(String(1024), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    content_type = Column(String(255), nullable=True)
    asset_type = Column(String(50), nullable=True)
    sha256_hash = Column(String(64), nullable=False)
    content = Column(Text, nullable=True)  # stored content (for text objects)
    version_number = Column(Integer, default=1)
    is_current_version = Column(Boolean, default=True)
    previous_version_id = Column(String, ForeignKey("vault_objects.id"), nullable=True)
    storage_class = Column(String(20), default="standard")  # standard, archive (Phase 3)
    storage_backend_ref = Column(String(512), default="local")
    ttl_override = Column(DateTime(timezone=True), nullable=True)
    shared_to_vault_id = Column(String, nullable=True)  # Phase 3: read-only sharing
    share_permission = Column(String(20), nullable=True)  # Phase 3: read_only
    object_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)


class VaultAuditLog(Base):
    """Immutable audit log entry for vault operations."""
    __tablename__ = "vault_audit_log"
    __table_args__ = (
        Index("ix_vault_audit_time", "vault_id", "created_at"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    vault_id = Column(String, ForeignKey("agent_vaults.id"), nullable=False, index=True)
    agent_id = Column(String, nullable=False)
    action = Column(String(50), nullable=False)  # PUT, GET, DELETE, LIST, UPGRADE, DOWNGRADE, SUSPEND, RESTORE
    object_key = Column(String(1024), nullable=True)
    bytes_delta = Column(BigInteger, default=0)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    result = Column(String(20), default="success")  # success, denied, quota_exceeded, not_found
    created_at = Column(DateTime(timezone=True), default=_now)


class VaultBundleSubscription(Base):
    """Bundle subscription linking vault to operator subscription."""
    __tablename__ = "vault_bundle_subscriptions"

    id = Column(String, primary_key=True, default=_uuid)
    vault_id = Column(String, ForeignKey("agent_vaults.id"), nullable=False, index=True)
    operator_subscription_id = Column(String, nullable=True)
    bundle_package_name = Column(String(20), default="standalone")  # spark, scout, ranger, sovereign, standalone
    discount_source = Column(String(50), nullable=True)  # operator_bundle, annual_prepay, promo
    discount_amount_zar = Column(Float, default=0.0)
    effective_from = Column(DateTime(timezone=True), default=_now)
    effective_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class VaultDelegate(Base):
    """Delegate access to a vault — read/write/delete permissions."""
    __tablename__ = "vault_delegates"
    __table_args__ = (
        Index("ix_vault_delegate", "vault_id", "delegate_agent_id", unique=True),
    )

    id = Column(String, primary_key=True, default=_uuid)
    vault_id = Column(String, ForeignKey("agent_vaults.id"), nullable=False, index=True)
    delegate_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    can_read = Column(Boolean, default=True)
    can_write = Column(Boolean, default=False)
    can_delete = Column(Boolean, default=False)
    granted_at = Column(DateTime(timezone=True), default=_now)
    granted_by_agent_id = Column(String, nullable=False)
