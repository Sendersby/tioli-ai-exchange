"""Router: compliance_routes - auto-extracted from main.py (A-001)."""
from fastapi import APIRouter, Depends, Request, HTTPException, Header, Query, Path, Body
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from pydantic import BaseModel
from app.database.db import get_db, async_session
from app.agents.models import Agent, Wallet, Loan
from app.blockchain.transaction import Transaction, TransactionType
from app.utils.validators import require_kyc_verified, validated_json
from app.dashboard.routes import get_current_owner
from app.utils.audit import log_financial_event
from app.security.transaction_safety import InputValidator
from app.config import settings
from app.infrastructure.cache import cache, TTL_SHORT, TTL_MEDIUM, TTL_LONG
import json, uuid, os, time, logging
from datetime import datetime, timezone
from collections import defaultdict
from app.main_deps import (blockchain, compliance_framework, compliance_service, crossborder_service, legal_docs, require_agent, templates)
from app.main_deps import (KYARequest)

from app.compliance.jurisdictions import get_jurisdiction_rules, list_supported_jurisdictions, get_jurisdiction_summary
router = APIRouter()

@router.get("/api/v1/compliance/scan", include_in_schema=False)
async def run_compliance_scan_now(db: AsyncSession = Depends(get_db)):
    """Trigger an immediate compliance scan."""
    from app.arch.compliance_agent import run_compliance_scan
    return await run_compliance_scan(db)

@router.get("/regulatory", response_class=HTMLResponse)
async def regulatory_page(request: Request):
    """Regulatory status and compliance trust page."""
    import os
    statuses = [
        {
            "name": "IFWG Regulatory Sandbox",
            "status": os.environ.get("REGULATORY_IFWG_STATUS", "Application submitted"),
            "status_type": "submitted",
            "icon": "policy",
            "description": "South African Intergovernmental Fintech Working Group sandbox for testing governed financial innovation with AI agents.",
        },
        {
            "name": "CASP Registration (FSCA)",
            "status": os.environ.get("REGULATORY_CASP_STATUS", "In preparation"),
            "status_type": "preparation",
            "icon": "account_balance",
            "description": "Crypto Asset Service Provider registration with the Financial Sector Conduct Authority for token exchange services.",
        },
        {
            "name": "POPIA Compliance",
            "status": "Compliant",
            "status_type": "active",
            "icon": "shield",
            "description": "Protection of Personal Information Act compliance built into platform architecture. Data minimisation, encryption at rest, consent-based processing.",
        },
        {
            "name": "SARB Exchange Control",
            "status": os.environ.get("REGULATORY_SARB_STATUS", "Compliance built-in"),
            "status_type": "active",
            "icon": "currency_exchange",
            "description": "South African Reserve Bank exchange control compliance for cross-border AI agent transactions.",
        },
        {
            "name": "NCA Lending Compliance",
            "status": os.environ.get("REGULATORY_NCA_STATUS", "Pending — service deferred"),
            "status_type": "preparation",
            "icon": "handshake",
            "description": "National Credit Act compliance for AI agent lending marketplace. Lending services deferred until regulatory clearance.",
        },
    ]
    return templates.TemplateResponse(request, "regulatory.html",  context={
        "authenticated": False, "active": "regulatory",
        "statuses": statuses,
    })

@router.post("/api/compliance/kya")
async def api_submit_kya(
    req: KYARequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Submit KYA (Know Your Agent) information."""
    kya = await compliance_framework.submit_kya(
        db, agent.id, req.operator_name, req.operator_jurisdiction, req.purpose,
    )
    return {
        "agent_id": kya.agent_id,
        "verification_level": kya.verification_level,
    }

@router.get("/api/compliance/kya/{agent_id}")
async def api_get_kya(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get KYA record for an agent."""
    record = await compliance_framework.get_kya(db, agent_id)
    if not record:
        return {"message": "No KYA record found"}
    return record

@router.get("/api/compliance/flags")
async def api_get_flags(
    status: str = None, severity: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Get compliance flags."""
    return await compliance_framework.get_flags(db, status, severity)

@router.get("/api/compliance/summary")
async def api_compliance_summary(db: AsyncSession = Depends(get_db)):
    """Compliance dashboard summary."""
    return await compliance_framework.get_compliance_summary(db)

@router.get("/api/compliance/audit-export")
async def api_audit_export(request: Request, db: AsyncSession = Depends(get_db)):
    """Generate audit export (owner only)."""
    owner = get_current_owner(request)
    if not owner:
        raise HTTPException(status_code=401, detail="Owner authentication required")
    return await compliance_framework.generate_audit_export(db)

@router.post("/api/v1/compliance/agents")
async def api_register_compliance_agent(
    agent_id: str, operator_id: str, compliance_domains: str,
    jurisdiction: str = "ZA", pricing_model: str = "per_review",
    price_per_review: float = 50.0,
    request: Request = None, db: AsyncSession = Depends(get_db),
):
    """Register a compliance agent."""
    if not settings.compliance_service_enabled:
        raise HTTPException(status_code=503, detail="Compliance service module not enabled")
    domains = [d.strip() for d in compliance_domains.split(",")]
    return await compliance_service.register_compliance_agent(
        db, agent_id, operator_id, domains, jurisdiction,
        pricing_model=pricing_model, price_per_review=price_per_review,
    )

@router.get("/api/v1/compliance/agents/search")
async def api_search_compliance_agents(
    domain: str | None = None, jurisdiction: str | None = None,
    max_price: float | None = None, db: AsyncSession = Depends(get_db),
):
    """Search compliance agents by domain, jurisdiction, price."""
    if not settings.compliance_service_enabled:
        raise HTTPException(status_code=503, detail="Compliance service module not enabled")
    return await compliance_service.search_compliance_agents(db, domain, jurisdiction, max_price)

@router.post("/api/v1/compliance/reviews")
async def api_submit_compliance_review(
    compliance_agent_id: str, requesting_agent_id: str,
    content_hash: str, compliance_domains: str,
    engagement_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Submit content for compliance review."""
    if not settings.compliance_service_enabled:
        raise HTTPException(status_code=503, detail="Compliance service module not enabled")
    domains = [d.strip() for d in compliance_domains.split(",")]
    return await compliance_service.submit_review(
        db, compliance_agent_id, requesting_agent_id,
        content_hash, domains, engagement_id,
    )

@router.post("/api/v1/compliance/reviews/{review_id}/submit-finding")
async def api_submit_compliance_finding(
    review_id: str, status: str, finding: str,
    db: AsyncSession = Depends(get_db),
):
    """Compliance agent submits finding. If passed, generates blockchain certificate."""
    if not settings.compliance_service_enabled:
        raise HTTPException(status_code=503, detail="Compliance service module not enabled")
    return await compliance_service.submit_finding(db, review_id, status, finding)

@router.get("/api/v1/compliance/reviews/{review_id}/certificate")
async def api_compliance_certificate(review_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve compliance certificate for a verified review. Public endpoint."""
    result = await compliance_service.get_certificate(db, review_id)
    if not result:
        raise HTTPException(status_code=404, detail="Certificate not found or review not passed")
    return result

@router.get("/api/v1/compliance/mandatory-domains")
async def api_mandatory_compliance_domains():
    """List domains requiring mandatory compliance review."""
    return await compliance_service.get_mandatory_domains()

@router.get("/api/v1/compliance/sarb/status")
async def api_sarb_status(db: AsyncSession = Depends(get_db)):
    return await crossborder_service.get_sarb_status(db)

@router.post("/api/v1/compliance/screen", include_in_schema=False)
async def api_compliance_screen(request: Request):
    """Screen a name against OFAC sanctions list."""
    body = await validated_json(request)
    name = body.get("name", "")
    if not name:
        return JSONResponse(status_code=400, content={"error": "name required"})
    from app.arch.compliance_real import screen_sanctions
    return await screen_sanctions(name)

@router.post("/api/v1/compliance/risk", include_in_schema=False)
async def api_transaction_risk(request: Request):
    """Assess transaction risk."""
    body = await validated_json(request)
    from app.arch.compliance_real import assess_transaction_risk
    return assess_transaction_risk(body.get("amount", 0), body.get("currency", "AGENTIS"), body.get("country", "ZA"))

@router.post("/api/v1/guardrails/check", include_in_schema=False)
async def api_guardrails_check(request: Request):
    """Validate an action against guardrails."""
    body = await validated_json(request)
    from app.arch.guardrails import validate_pre_action, validate_social_content
    action_check = validate_pre_action(body.get("action_type", ""), body.get("params", {}), body.get("agent", "test"))
    content_check = validate_social_content(body.get("content", ""), body.get("agent", "test")) if body.get("content") else None
    return {"action": action_check, "content": content_check}

@router.post("/api/v1/compliance/ml-risk", include_in_schema=False)
async def api_ml_risk(request: Request, db: AsyncSession = Depends(get_db)):
    """ML-lite transaction risk scoring."""
    body = await validated_json(request)
    from app.arch.ml_risk import score_transaction_risk
    return await score_transaction_risk(db, body.get("agent_id",""), body.get("amount",0), body.get("currency","AGENTIS"))

@router.post("/api/v1/compliance/str-filing", include_in_schema=False)
async def api_str_filing(request: Request, db: AsyncSession = Depends(get_db)):
    """Prepare an STR filing for FIC submission. [DEFER_TO_OWNER]"""
    body = await validated_json(request)
    from app.arch.fic_pipeline import prepare_str_filing
    return await prepare_str_filing(db, body.get("transaction_id",""), body.get("agent_id",""),
        body.get("amount",0), body.get("currency","AGENTIS"), body.get("risk_score",0), body.get("flags",[]))

@router.post("/api/v1/compliance/rescreening", include_in_schema=False)
async def api_run_rescreening(db: AsyncSession = Depends(get_db)):
    """Run rescreening batch."""
    from app.arch.rescreening import run_rescreening_batch
    return await run_rescreening_batch(db)

@router.post("/api/v1/regulatory/scan", include_in_schema=False)
async def api_regulatory_scan(db: AsyncSession = Depends(get_db)):
    """Scan regulatory sources."""
    from app.arch.regulatory_feed import scan_regulatory_sources
    return await scan_regulatory_sources(db)

@router.post("/api/v1/compliance/rba/{agent_id}", include_in_schema=False)
async def api_rba_assess(agent_id: str, db: AsyncSession = Depends(get_db)):
    from app.arch.rba_engine import assess_agent_risk
    return await assess_agent_risk(db, agent_id)

@router.get("/api/jurisdictions")
async def api_jurisdictions():
    """List all supported jurisdictions and their basic info."""
    cached = cache.get("jurisdictions")
    if cached:
        return cached
    result = list_supported_jurisdictions()
    cache.set("jurisdictions", result, TTL_LONG)
    return result

@router.get("/api/jurisdictions/{country_code}")
async def api_jurisdiction_rules(country_code: str):
    """Get compliance rules for a specific jurisdiction."""
    return get_jurisdiction_summary(country_code)

@router.get("/api/legal/terms")
async def api_terms_of_service():
    """Platform Terms of Service."""
    return legal_docs.get_terms_of_service()

@router.get("/api/legal/privacy")
async def api_privacy_notice():
    """POPIA-compliant Privacy Notice."""
    return legal_docs.get_privacy_notice()

@router.get("/api/legal/sla")
async def api_sla():
    """Service Level Agreement."""
    return legal_docs.get_sla()

@router.get("/api/legal/api-versioning")
async def api_versioning_policy():
    """API Versioning & Deprecation Policy."""
    return legal_docs.get_api_versioning_policy()
