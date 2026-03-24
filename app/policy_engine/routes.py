"""Policy Engine API routes — agent pre-check + operator management."""

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db
from app.agents.models import Agent
from app.auth.agent_auth import authenticate_agent
from app.policy_engine.service import PolicyEngineService
from app.policy_engine.models import POLICY_TYPES
from app.dashboard.routes import get_current_owner

router = APIRouter(prefix="/api/v1/policies", tags=["Policy Engine"])
policy_service = PolicyEngineService()


async def require_agent_auth(
    authorization: str = Header(...), db: AsyncSession = Depends(get_db),
) -> Agent:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    agent = await authenticate_agent(db, authorization[7:])
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return agent


# ── Request Models ────────────────────────────────────────────────────

class PolicyCreateRequest(BaseModel):
    agent_id: str | None = None  # NULL = all agents
    policy_type: str
    policy_value: dict
    description: str = ""

class PolicyCheckRequest(BaseModel):
    action_type: str  # transfer, trade, engagement_fund
    action_params: dict  # {amount, currency, receiver_id, etc.}

class ApprovalResolveRequest(BaseModel):
    decision: str  # APPROVED or REJECTED
    notes: str = ""


# ── Agent Endpoints (self-check) ─────────────────────────────────────

@router.post("/check")
async def api_check_policy(
    req: PolicyCheckRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Pre-check: will this action be allowed by my operator's policies?

    Call this before attempting a financial action to learn whether it will
    be permitted, denied, or escalated. Enables agents to self-govern.
    """
    result = await policy_service.check_policy(db, agent.id, req.action_type, req.action_params)
    await db.commit()
    return result.to_dict()


@router.get("/my-policies")
async def api_my_policies(
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """View all policies that apply to you."""
    from app.policy_engine.models import AgentPolicy
    from sqlalchemy import select, or_
    result = await db.execute(
        select(AgentPolicy).where(
            AgentPolicy.is_active == True,
            or_(AgentPolicy.agent_id == agent.id, AgentPolicy.agent_id.is_(None)),
        )
    )
    return [policy_service._policy_to_dict(p) for p in result.scalars().all()]


# ── Operator Endpoints (management) ──────────────────────────────────

@router.post("/create")
async def api_create_policy(
    req: PolicyCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Create a new policy (operator/owner only)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    try:
        result = await policy_service.create_policy(
            db, "owner", req.agent_id, req.policy_type, req.policy_value, req.description
        )
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/list")
async def api_list_policies(
    agent_id: str | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """List all policies (operator/owner only)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await policy_service.list_policies(db, "owner", agent_id)


@router.put("/{policy_id}/toggle")
async def api_toggle_policy(
    policy_id: str, active: bool = True,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable a policy."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    try:
        result = await policy_service.toggle_policy(db, policy_id, active)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{policy_id}")
async def api_delete_policy(
    policy_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Delete a policy."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    try:
        result = await policy_service.delete_policy(db, policy_id)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/types")
async def api_policy_types():
    """List all available policy types with descriptions."""
    return {
        "policy_types": POLICY_TYPES,
        "descriptions": {
            "MAX_TRANSACTION_VALUE": {"params": {"max_amount": "float"}, "description": "Deny transactions above this amount"},
            "DAILY_TRANSACTION_LIMIT": {"params": {"daily_limit": "float"}, "description": "Deny if daily spend exceeds limit"},
            "PROHIBITED_COUNTERPARTY": {"params": {"blocked_agents": ["agent_id"]}, "description": "Block transactions with specific agents"},
            "REQUIRE_CONFIRMATION_ABOVE": {"params": {"threshold": "float"}, "description": "Escalate to human above this amount"},
            "CAPABILITY_WHITELIST": {"params": {"allowed_actions": ["transfer", "trade"]}, "description": "Only allow listed action types"},
            "WORKING_HOURS": {"params": {"start_hour": "int (0-23)", "end_hour": "int (0-23)"}, "description": "Only allow actions during these UTC hours"},
            "MAX_SINGLE_ENGAGEMENT": {"params": {"max_amount": "float"}, "description": "Max AgentBroker engagement value"},
        },
    }


# ── Approval Endpoints ───────────────────────────────────────────────

@router.get("/approvals")
async def api_pending_approvals(
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """List pending approvals awaiting human review."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await policy_service.get_pending_approvals(db, "owner")


@router.post("/approvals/{approval_id}/resolve")
async def api_resolve_approval(
    approval_id: str, req: ApprovalResolveRequest,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject an escalated action."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    try:
        result = await policy_service.resolve_approval(db, approval_id, req.decision, req.notes)
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
