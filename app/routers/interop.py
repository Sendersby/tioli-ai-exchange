"""Router: interop - auto-extracted from main.py (A-001)."""
from fastapi import APIRouter, Depends, Request, HTTPException, Header, Query, Path, Body
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from pydantic import BaseModel
from app.database.db import get_db, async_session
from app.agents.models import Agent, Wallet, Loan
from app.blockchain.transaction import Transaction, TransactionType
from app.utils.validators import require_kyc_verified
from app.utils.audit import log_financial_event
from app.security.transaction_safety import InputValidator
from app.config import settings
from app.infrastructure.cache import cache, TTL_SHORT, TTL_MEDIUM, TTL_LONG
import json, uuid, os, time, logging
from datetime import datetime, timezone
from collections import defaultdict
from app.main_deps import (blockchain, discovery_service, paypal_service, require_agent)
from app.main_deps import (AgentProfileRequest, ReviewRequest, ServiceListingRequest)

router = APIRouter()

@router.get("/.well-known/ai-plugin.json", include_in_schema=False)
async def well_known_ai_plugin():
    """Standard AI agent discovery endpoint at root level."""
    from app.agent_gateway.gateway import ai_plugin_manifest
    return await ai_plugin_manifest()

@router.get("/api/v1/interop/status", include_in_schema=False)
async def interop_status():
    """Blockchain interoperability status and roadmap."""
    from app.arch.blockchain_interop import get_interop_status
    return get_interop_status()

@router.get("/api/v1/interop/chains", include_in_schema=False)
async def interop_chains():
    """List supported blockchain interoperability chains."""
    from app.arch.blockchain_interop import get_interop_status
    status = get_interop_status()
    return {"chains": status.get("supported_chains", []), "active_chain": "agentis_sovereign_ledger"}

@router.get("/api/v1/interop/export/{agent_id}", include_in_schema=False)
async def interop_export(agent_id: str, chain: str = "olas", db: AsyncSession = Depends(get_db)):
    """Export agent data in chain-compatible format (JSON-LD, W3C VC)."""
    from app.arch.blockchain_interop import export_agent_for_chain
    return await export_agent_for_chain(db, agent_id, chain)

@router.get("/.well-known/did.json", include_in_schema=False)
async def platform_did_document():
    """did:web DID document for the AGENTIS platform.

    Allows external systems to resolve the platform identity.
    """
    return {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/suites/ed25519-2020/v1",
        ],
        "id": "did:web:exchange.tioli.co.za",
        "controller": "did:web:exchange.tioli.co.za",
        "verificationMethod": [
            {
                "id": "did:web:exchange.tioli.co.za#key-1",
                "type": "Ed25519VerificationKey2020",
                "controller": "did:web:exchange.tioli.co.za",
                "publicKeyMultibase": "z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK",
            }
        ],
        "authentication": ["did:web:exchange.tioli.co.za#key-1"],
        "assertionMethod": ["did:web:exchange.tioli.co.za#key-1"],
        "service": [
            {
                "id": "did:web:exchange.tioli.co.za#mcp",
                "type": "MCPServer",
                "serviceEndpoint": "https://exchange.tioli.co.za/api/mcp/sse",
            },
            {
                "id": "did:web:exchange.tioli.co.za#api",
                "type": "RESTApi",
                "serviceEndpoint": "https://exchange.tioli.co.za/docs",
            },
            {
                "id": "did:web:exchange.tioli.co.za#explorer",
                "type": "BlockExplorer",
                "serviceEndpoint": "https://agentisexchange.com/explorer",
            },
        ],
    }

@router.get("/api/discover", include_in_schema=False)
async def agt_discover(
    capability: str = None,
    protocol: str = None,
    pricing: str = None,
    min_reputation: float = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """.agt discovery spec compatible endpoint.

    Query agents by capability, protocol, and reputation.
    Returns ranked list in .agt manifest format.
    """
    from app.discovery.network import AgentDiscoveryService
    svc = AgentDiscoveryService()
    agents = await svc.discover_agents(
        db, capability=capability, min_reputation=min_reputation, limit=limit,
    )

    # Enrich with .agt manifest format
    manifests = []
    for a in agents:
        manifest = {
            "agentId": a.get("agent_id", ""),
            "displayName": a.get("display_name", ""),
            "capabilities": a.get("capabilities", []),
            "reputation": a.get("reputation", 0),
            "endpoints": [
                {"protocol": "mcp-sse", "url": "https://exchange.tioli.co.za/api/mcp/sse"},
                {"protocol": "rest", "url": f"https://exchange.tioli.co.za/api/v1/profiles/{a.get('agent_id', '')}"},
            ],
            "did": f"did:web:exchange.tioli.co.za:agents:{a.get('agent_id', '')}",
            "a2aCard": f"https://exchange.tioli.co.za/agents/{a.get('agent_id', '')}/card.json",
        }
        if protocol and protocol.lower() == "mcp":
            manifest["endpoints"] = [e for e in manifest["endpoints"] if "mcp" in e["protocol"]]
        manifests.append(manifest)

    return {
        "agents": manifests,
        "count": len(manifests),
        "query": {
            "capability": capability,
            "protocol": protocol,
            "pricing": pricing,
            "min_reputation": min_reputation,
        },
    }

@router.get("/.well-known/mcp/server-card.json", include_in_schema=False)
async def mcp_server_card():
    """MCP server card for Smithery and other MCP directories."""
    from fastapi.responses import FileResponse
    return FileResponse("static/mcp-server-card.json", media_type="application/json")

@router.get("/.well-known/agent.json", include_in_schema=False)
async def well_known_a2a_agent():
    """A2A well-known agent discovery — redirects to A2A module."""
    from app.arch.a2a import well_known_agent
    return await well_known_agent()

@router.post("/api/discovery/profile")
async def api_create_profile(
    req: AgentProfileRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Create or update your public agent profile."""
    profile = await discovery_service.create_or_update_profile(
        db, agent.id, req.display_name, req.tagline, req.capabilities,
        req.services_offered, req.preferred_currencies, req.api_endpoint,
    )
    return {"agent_id": profile.agent_id, "display_name": profile.display_name}

@router.get("/api/discovery/agents")
async def api_discover_agents(
    capability: str = None, min_reputation: float = 0,
    db: AsyncSession = Depends(get_db),
):
    """Discover agents by capability and reputation."""
    return await discovery_service.discover_agents(db, capability, min_reputation)

@router.post("/api/discovery/review")
async def api_submit_review(
    req: ReviewRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Submit a review for another agent."""
    review = await discovery_service.submit_review(
        db, agent.id, req.reviewed_id, req.rating, req.review_text,
    )
    return {"review_id": review.id, "rating": req.rating}

@router.get("/api/discovery/reviews/{agent_id}")
async def api_get_reviews(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get reviews for an agent."""
    return await discovery_service.get_reviews(db, agent_id)

@router.post("/api/discovery/services")
async def api_list_service(
    req: ServiceListingRequest, agent: Agent = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """List a service on the agent marketplace."""
    listing = await discovery_service.list_service(
        db, agent.id, req.title, req.description, req.category,
        req.price, req.price_currency,
    )
    return {"listing_id": listing.id, "title": listing.title}

@router.get("/api/discovery/services")
async def api_browse_services(
    category: str = None, max_price: float = None,
    db: AsyncSession = Depends(get_db),
):
    """Browse agent services."""
    return await discovery_service.browse_services(db, category, max_price)

@router.get("/api/discovery/stats")
async def api_network_stats(db: AsyncSession = Depends(get_db)):
    """Agent network statistics."""
    return await discovery_service.get_network_stats(db)

@router.get("/api/v1/licensing/pricing")
async def api_licensing_pricing():
    """Get commercial licensing pricing schedule. Schema only — no active billing."""
    from app.licensing.models import LICENCE_PRICING
    return {
        "licence_types": LICENCE_PRICING,
        "note": "All licence activations require owner 3FA confirmation. Phase 3 feature.",
    }

@router.post("/api/v1/webhooks/paypal")
async def api_paypal_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive PayPal webhook events."""
    body = await validated_json(request)
    event_id = body.get("id", "")
    event_type = body.get("event_type", "")
    resource = body.get("resource", {})
    return await paypal_service.process_webhook(
        db, event_id, event_type,
        resource.get("resource_type"), resource.get("id"),
        body, signature_verified=False,  # Production: verify signature
    )

@router.get("/api/v1/interop/olas/{agent_id}", include_in_schema=False)
async def olas_export(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Export agent in Olas Agent Service Protocol format."""
    from app.arch.blockchain_interop import export_olas_service_config
    return await export_olas_service_config(db, agent_id)

@router.post("/api/v1/webhooks/register", include_in_schema=False)
async def register_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Register a webhook URL to receive event notifications."""
    body = await validated_json(request)
    url = body.get("url", "").strip()
    events = body.get("events", ["trade", "registration"])
    if not url or not url.startswith("http"):
        return JSONResponse(status_code=400, content={"error": "Valid URL required"})
    from sqlalchemy import text
    import uuid, json as _wh_json
    wid = str(uuid.uuid4())
    secret = f"whsec_{uuid.uuid4().hex[:24]}"
    try:
        await db.execute(text(
            "INSERT INTO webhook_registrations (id, agent_id, url, events, is_active, created_at) "
            "VALUES (:id, :aid, :url, :ev, true, now())"
        ), {"id": wid, "aid": "system", "url": url, "ev": _wh_json.dumps(events)})
        await db.commit()
        return {"webhook_id": wid, "url": url, "events": events, "status": "registered"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/api/v1/webhooks", include_in_schema=False)
async def list_webhooks(db: AsyncSession = Depends(get_db)):
    """List registered webhooks."""
    from sqlalchemy import text
    result = await db.execute(text("SELECT id, url, events, is_active FROM webhook_registrations WHERE is_active = true ORDER BY created_at DESC LIMIT 50"))
    return [{"id": r.id, "url": r.url, "events": r.events if isinstance(r.events, list) else [], "active": r.is_active} for r in result.fetchall()]  # LIMIT applied
