"""AgentVault™ API routes — vault management, object operations, audit, delegates."""

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.db import get_db
from app.agents.models import Agent
from app.auth.agent_auth import authenticate_agent
from app.agentvault.service import AgentVaultService

router = APIRouter(prefix="/api/v1/agentvault", tags=["AgentVault"])
vault_service = AgentVaultService()


def _check_enabled():
    if not settings.agentvault_enabled:
        raise HTTPException(status_code=503, detail="AgentVault module is not enabled")


async def require_agent_auth(
    authorization: str = Header(...), db: AsyncSession = Depends(get_db),
) -> Agent:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    agent = await authenticate_agent(db, authorization[7:])
    if not agent:
        raise HTTPException(status_code=401)
    return agent


# ── Request Models ────────────────────────────────────────────────────

class CreateVaultRequest(BaseModel):
    tier_name: str = "cache"
    billing_cycle: str = "free"
    popia_consent: bool = False

class UpgradeRequest(BaseModel):
    new_tier_name: str

class PutObjectRequest(BaseModel):
    content: str
    content_type: str = "text/plain"
    asset_type: str | None = None
    metadata: dict | None = None

class DelegateRequest(BaseModel):
    delegate_agent_id: str
    can_read: bool = True
    can_write: bool = False
    can_delete: bool = False


# ── Tier Listing (Public) ────────────────────────────────────────────

@router.get("/tiers")
async def api_list_tiers(db: AsyncSession = Depends(get_db)):
    """List all AgentVault tiers with pricing. Public — no auth."""
    _check_enabled()
    return await vault_service.list_tiers(db)


# ── Vault Management ─────────────────────────────────────────────────

@router.post("/vaults")
async def api_create_vault(
    req: CreateVaultRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Create a new vault. Defaults to Cache (free)."""
    _check_enabled()
    return await vault_service.create_vault(
        db, agent.id, "", req.tier_name, req.billing_cycle, req.popia_consent,
    )


@router.get("/vaults/my")
async def api_my_vault(
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Get your vault details."""
    _check_enabled()
    vault = await vault_service.get_vault(db, agent.id)
    if not vault:
        return {"has_vault": False}
    return vault


@router.get("/vaults/{vault_id}")
async def api_get_vault(vault_id: str, db: AsyncSession = Depends(get_db)):
    """Get vault details by ID."""
    _check_enabled()
    vault = await vault_service.get_vault_by_id(db, vault_id)
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")
    return vault


@router.put("/vaults/{vault_id}/upgrade")
async def api_upgrade_vault(
    vault_id: str, req: UpgradeRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Upgrade vault to a higher tier."""
    _check_enabled()
    return await vault_service.upgrade_vault(db, vault_id, req.new_tier_name)


@router.put("/vaults/{vault_id}/downgrade")
async def api_downgrade_vault(
    vault_id: str, req: UpgradeRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Downgrade vault to a lower tier."""
    _check_enabled()
    return await vault_service.downgrade_vault(db, vault_id, req.new_tier_name)


@router.delete("/vaults/{vault_id}")
async def api_cancel_vault(
    vault_id: str,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Cancel vault — 30-day grace period for data retrieval."""
    _check_enabled()
    return await vault_service.cancel_vault(db, vault_id)


@router.get("/vaults/{vault_id}/usage")
async def api_vault_usage(vault_id: str, db: AsyncSession = Depends(get_db)):
    """Get vault usage metrics."""
    _check_enabled()
    return await vault_service.get_usage(db, vault_id)


# ── Object Operations ────────────────────────────────────────────────

@router.put("/vaults/{vault_id}/objects/{object_key:path}")
async def api_put_object(
    vault_id: str, object_key: str, req: PutObjectRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Store or overwrite an object. Validates quota and private key content."""
    _check_enabled()
    key = f"/{object_key}" if not object_key.startswith("/") else object_key
    return await vault_service.put_object(
        db, vault_id, agent.id, key, req.content,
        req.content_type, req.asset_type, req.metadata,
    )


@router.get("/vaults/{vault_id}/objects/{object_key:path}")
async def api_get_object(
    vault_id: str, object_key: str,
    version: int | None = None,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve an object (current or specific version)."""
    _check_enabled()
    key = f"/{object_key}" if not object_key.startswith("/") else object_key
    obj = await vault_service.get_object(db, vault_id, agent.id, key, version)
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")
    return obj


@router.delete("/vaults/{vault_id}/objects/{object_key:path}")
async def api_delete_object(
    vault_id: str, object_key: str,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Delete an object (current version)."""
    _check_enabled()
    key = f"/{object_key}" if not object_key.startswith("/") else object_key
    return await vault_service.delete_object(db, vault_id, agent.id, key)


@router.get("/vaults/{vault_id}/objects")
async def api_list_objects(
    vault_id: str, prefix: str | None = None,
    asset_type: str | None = None,
    limit: int = Query(100, le=500), offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List objects in a vault."""
    _check_enabled()
    return await vault_service.list_objects(db, vault_id, prefix, asset_type, limit, offset)


@router.get("/vaults/{vault_id}/objects/{object_key:path}/versions")
async def api_object_versions(
    vault_id: str, object_key: str,
    db: AsyncSession = Depends(get_db),
):
    """Get version history for an object."""
    _check_enabled()
    key = f"/{object_key}" if not object_key.startswith("/") else object_key
    return await vault_service.get_object_versions(db, vault_id, key)


# ── Audit Log ────────────────────────────────────────────────────────

@router.get("/vaults/{vault_id}/audit")
async def api_audit_log(
    vault_id: str, action: str | None = None,
    limit: int = Query(50, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Get vault audit log."""
    _check_enabled()
    return await vault_service.get_audit_log(db, vault_id, action, limit)


# ── Delegates ────────────────────────────────────────────────────────

@router.post("/vaults/{vault_id}/delegates")
async def api_add_delegate(
    vault_id: str, req: DelegateRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Add a delegate with specified permissions."""
    _check_enabled()
    return await vault_service.add_delegate(
        db, vault_id, req.delegate_agent_id, agent.id,
        req.can_read, req.can_write, req.can_delete,
    )


@router.delete("/vaults/{vault_id}/delegates/{delegate_agent_id}")
async def api_remove_delegate(
    vault_id: str, delegate_agent_id: str,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Remove a delegate."""
    _check_enabled()
    return await vault_service.remove_delegate(db, vault_id, delegate_agent_id)


@router.get("/vaults/{vault_id}/delegates")
async def api_list_delegates(
    vault_id: str, db: AsyncSession = Depends(get_db),
):
    """List vault delegates."""
    _check_enabled()
    return await vault_service.list_delegates(db, vault_id)
