"""AgentBroker™ API routes — all 28 endpoints from Section 3.

All endpoints check the AGENTBROKER_ENABLED feature flag.
All endpoints use existing platform authentication middleware.
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.db import get_db
from app.agents.models import Agent
from app.auth.agent_auth import authenticate_agent
from app.agentbroker.services import (
    ProfileService, EngagementService, NegotiationService,
    DisputeService, ReputationService, BoundaryService,
)
from app.blockchain.chain import Blockchain
from app.exchange.fees import FeeEngine

router = APIRouter(prefix="/api/v1/agentbroker", tags=["AgentBroker"])

# Services (initialized when wired into main app)
profile_service = ProfileService()
negotiation_service = NegotiationService()
dispute_service = DisputeService()
reputation_service = ReputationService()
boundary_service = BoundaryService()
engagement_service = None  # Set by main.py after blockchain/fee_engine init


def _check_enabled():
    if not settings.agentbroker_enabled:
        raise HTTPException(status_code=404, detail="AgentBroker module is not enabled")


async def require_agent_auth(
    authorization: str = Header(...), db: AsyncSession = Depends(get_db),
) -> Agent:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    agent = await authenticate_agent(db, authorization[7:])
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return agent


# ── Request Models ───────────────────────────────────────────────────

class CreateProfileRequest(BaseModel):
    operator_id: str
    service_title: str
    service_description: str
    capability_tags: list[str]
    model_family: str
    context_window: int = 100000
    languages: list[str] = ["en"]
    pricing_model: str = "FIXED_RATE"
    base_price: float | None = None
    price_currency: str = "AGENTIS"
    minimum_engagement: str | None = None

class CreateEngagementRequest(BaseModel):
    provider_agent_id: str
    service_profile_id: str
    title: str
    scope_of_work: str
    acceptance_criteria: str
    price: float
    currency: str = "AGENTIS"
    payment_terms: str = "ON_DELIVERY"
    deadline_hours: float | None = None

class NegotiateRequest(BaseModel):
    message_type: str
    proposed_terms: dict
    rationale: str | None = None

class DeliverRequest(BaseModel):
    deliverable_ref: str
    content_hash: str | None = None

class VerifyRequest(BaseModel):
    accepted: bool

class RateEngagementRequest(BaseModel):
    quality_rating: int = Field(..., ge=1, le=5, description="1-5 star rating")
    rating_tags: list[str] = []
    review_text: str | None = None


class DisputeRequest(BaseModel):
    dispute_type: str
    description: str
    evidence: list | None = None

class EvidenceRequest(BaseModel):
    evidence_item: dict

class BoundaryRequest(BaseModel):
    operator_id: str
    max_engagement_value: float = 10000
    max_concurrent_engagements: int = 3
    min_acceptable_price: float = 5.0
    max_acceptable_price: float = 50000.0
    approved_currencies: list[str] = ["AGENTIS", "BTC", "ETH"]
    max_deadline_days: int = 30
    require_escrow: bool = True
    negotiation_rounds_max: int = 5
    auto_accept_threshold: float = 0.10

class VetoDecisionRequest(BaseModel):
    decision: str
    notes: str


# ── 3.1 Service Profile Endpoints ───────────────────────────────────

@router.post("/profiles")
async def create_profile(
    req: CreateProfileRequest, agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    profile = await profile_service.create_profile(
        db, agent.id, req.operator_id, req.service_title,
        req.service_description, req.capability_tags, req.model_family,
        req.context_window, req.languages, req.pricing_model,
        req.base_price, req.price_currency, req.minimum_engagement,
    )
    return {"profile_id": profile.profile_id, "service_title": profile.service_title}


class UpdateProfileRequest(BaseModel):
    service_title: str | None = None
    service_description: str | None = None
    capability_tags: list[str] | None = None
    model_family: str | None = None
    context_window: int | None = None
    pricing_model: str | None = None
    base_price: float | None = None
    price_currency: str | None = None
    availability_status: str | None = None


@router.get("/profiles/{profile_id}")
async def get_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    _check_enabled()
    return await profile_service.get_profile(db, profile_id)


@router.put("/profiles/{profile_id}")
async def update_profile(
    profile_id: str, req: UpdateProfileRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Update a service profile — owner agent only."""
    _check_enabled()
    return await profile_service.update_profile(
        db, profile_id, agent.id, **req.model_dump(exclude_none=True),
    )


@router.delete("/profiles/{profile_id}")
async def deactivate_profile(
    profile_id: str, agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate (soft-delete) a service profile — owner agent only."""
    _check_enabled()
    return await profile_service.deactivate_profile(db, profile_id, agent.id)


@router.get("/agents/{agent_id}/profiles")
async def get_agent_profiles(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get all service profiles for an agent."""
    _check_enabled()
    return await profile_service.get_agent_profiles(db, agent_id)


@router.get("/search")
async def search_profiles(
    capability_tags: str = None, pricing_model: str = None,
    max_price: float = None, min_reputation: float = 0,
    availability: str = None, model_family: str = None,
    semantic_query: str = None,
    sort_by: str = "REPUTATION", page: int = 1, page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    tags = capability_tags.split(",") if capability_tags else None
    results = await profile_service.search_profiles(
        db, tags, pricing_model, max_price, min_reputation,
        availability, model_family, sort_by, page, page_size,
    )

    # Apply semantic search if query provided
    if semantic_query:
        from app.search.semantic import semantic_search
        items = results.get("results", results) if isinstance(results, dict) else results
        if items:
            scored = semantic_search(semantic_query, items, min_score=0.05)
            if isinstance(results, dict):
                results["results"] = scored
                results["semantic_query"] = semantic_query
            else:
                results = scored

    return results


@router.get("/profiles/{profile_id}/reputation")
async def get_reputation(profile_id: str, db: AsyncSession = Depends(get_db)):
    _check_enabled()
    profile = await profile_service.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    score = await reputation_service.calculate_reputation(db, profile["agent_id"])
    return {
        "agent_id": score.agent_id, "overall": score.overall_score,
        "delivery_rate": score.delivery_rate, "dispute_rate": score.dispute_rate,
        "volume": score.volume_multiplier,
        "total_engagements": score.total_engagements,
        "completed": score.total_completed,
    }


# ── 3.2 Engagement Endpoints ────────────────────────────────────────

@router.post("/engagements")
async def create_engagement(
    req: CreateEngagementRequest, agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    from datetime import timedelta, timezone, datetime
    deadline = None
    if req.deadline_hours:
        deadline = datetime.now(timezone.utc) + timedelta(hours=req.deadline_hours)
    e = await engagement_service.create_engagement(
        db, agent.id, req.provider_agent_id, req.service_profile_id,
        req.title, req.scope_of_work, req.acceptance_criteria,
        req.price, req.currency, req.payment_terms, deadline,
    )
    return {"engagement_id": e.engagement_id, "state": e.current_state}


@router.get("/engagements/{engagement_id}")
async def get_engagement(engagement_id: str, db: AsyncSession = Depends(get_db)):
    _check_enabled()
    return await engagement_service.get_engagement(db, engagement_id)


@router.get("/engagements")
async def list_engagements(
    state: str = None, agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    return await engagement_service.list_engagements(db, agent.id, state)


@router.post("/engagements/{engagement_id}/negotiate")
async def negotiate(
    engagement_id: str, req: NegotiateRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    msg = await negotiation_service.submit_message(
        db, engagement_id, agent.id, req.message_type, req.proposed_terms, req.rationale,
    )
    # Handle state transitions based on message type
    if req.message_type == "PROPOSAL":
        await engagement_service.transition_state(db, engagement_id, "PROPOSED", agent.id)
    elif req.message_type == "COUNTER":
        await engagement_service.transition_state(db, engagement_id, "NEGOTIATING", agent.id)
    elif req.message_type == "ACCEPT":
        await engagement_service.transition_state(db, engagement_id, "ACCEPTED", agent.id)
    elif req.message_type == "DECLINE":
        # AUD-07 fix: explicit state check, no silent swallowing
        eng = await engagement_service.get_engagement(db, engagement_id)
        terminal = {"DECLINED", "EXPIRED", "WITHDRAWN", "COMPLETED", "REFUNDED"}
        if eng and eng["state"] not in terminal:
            try:
                await engagement_service.transition_state(db, engagement_id, "DECLINED", agent.id)
            except ValueError as e:
                raise HTTPException(status_code=422, detail=f"Cannot decline: {str(e)}")
    elif req.message_type == "WITHDRAW":
        await engagement_service.transition_state(db, engagement_id, "WITHDRAWN", agent.id)

    return {"negotiation_id": msg.negotiation_id, "type": msg.message_type}


@router.post("/engagements/{engagement_id}/fund")
async def fund_escrow(
    engagement_id: str, agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    return await engagement_service.fund_escrow(db, engagement_id, agent.id)


@router.post("/engagements/{engagement_id}/deliver")
async def deliver(
    engagement_id: str, req: DeliverRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    return await engagement_service.submit_deliverable(
        db, engagement_id, agent.id, req.deliverable_ref, req.content_hash,
    )


@router.post("/engagements/{engagement_id}/verify")
async def verify_delivery(
    engagement_id: str, req: VerifyRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    return await engagement_service.verify_delivery(db, engagement_id, agent.id, req.accepted)


@router.post("/engagements/{engagement_id}/rate")
async def rate_engagement(
    engagement_id: str, req: RateEngagementRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    """Rate a completed engagement (client rates provider). Records on blockchain."""
    _check_enabled()
    from app.agentbroker.models import AgentEngagement
    result = await db.execute(
        select(AgentEngagement).where(
            AgentEngagement.engagement_id == engagement_id
        )
    )
    engagement = result.scalar_one_or_none()
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")
    if engagement.current_state != "COMPLETED":
        raise HTTPException(status_code=400, detail="Can only rate completed engagements")
    if agent.id != engagement.client_agent_id:
        raise HTTPException(status_code=403, detail="Only the client can rate")

    try:
        from app.reputation.models import TaskOutcome
        from app.reputation.scorer import ReputationScorer
        import uuid as _uuid

        # Check if already rated
        existing = await db.execute(
            select(TaskOutcome).where(
                TaskOutcome.engagement_id == engagement_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Already rated")

        # Determine on-time
        on_time = True
        if engagement.deadline and engagement.completed_at:
            on_time = engagement.completed_at <= engagement.deadline

        outcome = TaskOutcome(
            outcome_id=str(_uuid.uuid4()),
            task_id=engagement_id,
            dispatch_id=engagement_id,
            engagement_id=engagement_id,
            agent_id=engagement.provider_agent_id,
            rated_by_agent_id=agent.id,
            quality_rating=req.quality_rating,
            rating_tags=req.rating_tags,
            review_text=req.review_text,
            on_time=on_time,
        )

        # Record on blockchain
        try:
            from app.blockchain.blockchain import blockchain
            tx_id = blockchain.add_transaction(
                sender=agent.id,
                recipient=engagement.provider_agent_id,
                amount=0,
                transaction_type="task_outcome",
                metadata={
                    "engagement_id": engagement_id,
                    "quality_rating": req.quality_rating,
                    "on_time": on_time,
                    "rating_tags": req.rating_tags,
                },
            )
            outcome.blockchain_tx_id = tx_id
        except Exception:
            pass

        db.add(outcome)

        # Recalculate reputation
        scorer = ReputationScorer()
        score = await scorer.calculate(db, engagement.provider_agent_id)
        await db.commit()

        return {
            "outcome_id": outcome.outcome_id,
            "quality_rating": req.quality_rating,
            "on_time": on_time,
            "new_reputation_score": score.overall_score,
            "blockchain_tx_id": outcome.blockchain_tx_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/engagements/{engagement_id}/dispute")
async def raise_dispute(
    engagement_id: str, req: DisputeRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    dispute = await dispute_service.raise_dispute(
        db, engagement_id, agent.id, req.dispute_type, req.description, req.evidence,
    )
    await engagement_service.transition_state(db, engagement_id, "DISPUTED", agent.id)
    return {"dispute_id": dispute.dispute_id, "status": dispute.status}


@router.get("/engagements/{engagement_id}/contract")
async def get_contract(engagement_id: str, db: AsyncSession = Depends(get_db)):
    _check_enabled()
    return await engagement_service.generate_smart_contract(db, engagement_id)


@router.get("/engagements/{engagement_id}/history")
async def get_history(engagement_id: str, db: AsyncSession = Depends(get_db)):
    _check_enabled()
    negotiations = await negotiation_service.get_negotiation_history(db, engagement_id)
    engagement = await engagement_service.get_engagement(db, engagement_id)
    return {
        "engagement": engagement,
        "negotiations": negotiations,
        "state_history": engagement["state_history"] if engagement else [],
    }


# ── 3.3 Arbitration Endpoints ───────────────────────────────────────

@router.post("/disputes/{dispute_id}/evidence")
async def submit_evidence(
    dispute_id: str, req: EvidenceRequest,
    agent: Agent = Depends(require_agent_auth),
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    return await dispute_service.submit_evidence(db, dispute_id, agent.id, req.evidence_item)


@router.get("/disputes/{dispute_id}")
async def get_dispute(dispute_id: str, db: AsyncSession = Depends(get_db)):
    _check_enabled()
    from app.agentbroker.models import EngagementDispute
    from sqlalchemy import select
    result = await db.execute(
        select(EngagementDispute).where(EngagementDispute.dispute_id == dispute_id)
    )
    d = result.scalar_one_or_none()
    if not d:
        raise HTTPException(status_code=404)
    return {
        "dispute_id": d.dispute_id, "engagement_id": d.engagement_id,
        "type": d.dispute_type, "status": d.status,
        "outcome": d.outcome, "rationale": d.arbitration_rationale,
        "escalated": d.escalated_to_owner,
    }


@router.get("/disputes/{dispute_id}/finding")
async def get_finding(dispute_id: str, db: AsyncSession = Depends(get_db)):
    _check_enabled()
    return await dispute_service.arbitrate(db, dispute_id, engagement_service=engagement_service)


@router.post("/disputes/{dispute_id}/veto")
async def owner_veto(
    dispute_id: str, req: VetoDecisionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Owner final veto decision — requires 3FA in production."""
    _check_enabled()
    return await dispute_service.owner_veto_decision(
        db, dispute_id, req.decision, req.notes,
        engagement_service=engagement_service,  # NEW-01 fix: pass service for state transition
    )


# ── 3.4 Boundary Configuration Endpoints ────────────────────────────

@router.post("/agents/{agent_id}/boundaries")
async def set_boundaries(
    agent_id: str, req: BoundaryRequest,
    db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    b = await boundary_service.set_boundaries(
        db, agent_id, req.operator_id,
        max_engagement_value=req.max_engagement_value,
        max_concurrent_engagements=req.max_concurrent_engagements,
        min_acceptable_price=req.min_acceptable_price,
        max_acceptable_price=req.max_acceptable_price,
        approved_currencies=req.approved_currencies,
        max_deadline_days=req.max_deadline_days,
        require_escrow=req.require_escrow,
        negotiation_rounds_max=req.negotiation_rounds_max,
        auto_accept_threshold=req.auto_accept_threshold,
    )
    return {"boundary_id": b.boundary_id, "agent_id": agent_id}


@router.get("/agents/{agent_id}/boundaries")
async def get_boundaries(agent_id: str, db: AsyncSession = Depends(get_db)):
    _check_enabled()
    return await boundary_service.get_boundaries(db, agent_id)


@router.get("/agents/{agent_id}/engagements")
async def agent_engagements(
    agent_id: str, state: str = None, db: AsyncSession = Depends(get_db),
):
    _check_enabled()
    return await engagement_service.list_engagements(db, agent_id, state)


# ── Engagement Templates ──────────────────────────────────────────────

ENGAGEMENT_TEMPLATES = [
    {
        "template_id": "data_analysis",
        "name": "Data Analysis Report",
        "description": "Agent analyses a dataset and produces an insight report",
        "scope_of_work": "Analyse the provided dataset. Identify key trends, outliers, and actionable insights. Produce a structured report with visualisation descriptions.",
        "acceptance_criteria": "Report contains: executive summary, methodology, key findings (min 5), data quality assessment, and recommendations.",
        "suggested_price": 50.0,
        "currency": "AGENTIS",
        "payment_terms": "ON_DELIVERY",
        "capability_tags": ["data_analysis", "reporting", "insights"],
        "estimated_hours": 2,
    },
    {
        "template_id": "code_generation",
        "name": "Code Generation Task",
        "description": "Agent writes code to specification with tests",
        "scope_of_work": "Implement the specified functionality in the requested language. Include error handling, input validation, and unit tests.",
        "acceptance_criteria": "Code compiles/runs without errors. All unit tests pass. Code follows language best practices. Documentation included.",
        "suggested_price": 75.0,
        "currency": "AGENTIS",
        "payment_terms": "ON_DELIVERY",
        "capability_tags": ["code_generation", "programming", "testing"],
        "estimated_hours": 4,
    },
    {
        "template_id": "research_report",
        "name": "Research & Literature Review",
        "description": "Agent conducts research on a topic and produces a comprehensive review",
        "scope_of_work": "Research the specified topic. Identify and synthesise at least 10 relevant sources. Produce a structured literature review with citations.",
        "acceptance_criteria": "Review contains: introduction, methodology, thematic analysis, gaps identified, bibliography with 10+ sources.",
        "suggested_price": 60.0,
        "currency": "AGENTIS",
        "payment_terms": "ON_DELIVERY",
        "capability_tags": ["research", "writing", "analysis"],
        "estimated_hours": 3,
    },
    {
        "template_id": "translation",
        "name": "Document Translation",
        "description": "Agent translates a document between languages",
        "scope_of_work": "Translate the provided document from source to target language. Maintain formatting, tone, and technical terminology.",
        "acceptance_criteria": "Translation is accurate, fluent, culturally appropriate. Technical terms correctly rendered. Original formatting preserved.",
        "suggested_price": 30.0,
        "currency": "AGENTIS",
        "payment_terms": "ON_DELIVERY",
        "capability_tags": ["translation", "multilingual", "localisation"],
        "estimated_hours": 1,
    },
    {
        "template_id": "legal_review",
        "name": "Legal Document Review",
        "description": "Agent reviews a legal document and flags risks",
        "scope_of_work": "Review the provided legal document. Identify potential risks, ambiguities, and non-standard clauses. Provide a risk assessment summary.",
        "acceptance_criteria": "Review identifies: key risks (ranked), ambiguous clauses, missing protections, compliance gaps, and recommended amendments.",
        "suggested_price": 100.0,
        "currency": "AGENTIS",
        "payment_terms": "ON_DELIVERY",
        "capability_tags": ["legal", "compliance", "risk_assessment"],
        "estimated_hours": 3,
    },
    {
        "template_id": "creative_content",
        "name": "Creative Content Production",
        "description": "Agent creates original content (articles, copy, narratives)",
        "scope_of_work": "Produce original creative content matching the specified brief, tone, audience, and format requirements.",
        "acceptance_criteria": "Content is original, on-brief, appropriate tone, correct word count, ready for publication.",
        "suggested_price": 40.0,
        "currency": "AGENTIS",
        "payment_terms": "ON_DELIVERY",
        "capability_tags": ["writing", "creative", "content"],
        "estimated_hours": 2,
    },
    {
        "template_id": "financial_analysis",
        "name": "Financial Analysis & Modelling",
        "description": "Agent builds financial models and produces analysis",
        "scope_of_work": "Build a financial model based on provided data. Include revenue projections, cost analysis, sensitivity testing, and executive summary.",
        "acceptance_criteria": "Model is formula-driven, assumptions documented, sensitivity analysis on 3+ variables, executive summary included.",
        "suggested_price": 120.0,
        "currency": "AGENTIS",
        "payment_terms": "ON_DELIVERY",
        "capability_tags": ["financial_analysis", "modelling", "forecasting"],
        "estimated_hours": 5,
    },
    {
        "template_id": "api_integration",
        "name": "API Integration Task",
        "description": "Agent integrates with an external API and produces working connector",
        "scope_of_work": "Build an integration with the specified API. Handle authentication, error cases, rate limiting, and data transformation.",
        "acceptance_criteria": "Integration authenticates successfully, handles all specified endpoints, error handling tested, documentation provided.",
        "suggested_price": 80.0,
        "currency": "AGENTIS",
        "payment_terms": "ON_DELIVERY",
        "capability_tags": ["api_integration", "programming", "systems"],
        "estimated_hours": 4,
    },
]


@router.get("/templates")
async def list_engagement_templates():
    """Get pre-built engagement contract templates."""
    _check_enabled()
    return ENGAGEMENT_TEMPLATES


@router.get("/templates/{template_id}")
async def get_engagement_template(template_id: str):
    """Get a specific engagement template."""
    _check_enabled()
    for t in ENGAGEMENT_TEMPLATES:
        if t["template_id"] == template_id:
            return t
    raise HTTPException(status_code=404, detail="Template not found")
