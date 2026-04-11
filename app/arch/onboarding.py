"""External Account Onboarding: identity verification, agent registration, API key provisioning."""
import uuid, json, hashlib, secrets
from datetime import datetime
from sqlalchemy import text

async def register_operator(db, name, email, organization="", country="ZA"):
    """Register a new external operator account."""
    operator_id = str(uuid.uuid4())
    api_key = f"tioli_{secrets.token_hex(32)}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    # Schema managed by Alembic — see alembic/versions/92d379a512fc
    await db.execute(text(
        "INSERT INTO sandbox_onboarding (id, entity_type, name, email, organization, country, api_key_hash, status) "
        "VALUES (:id, 'operator', :name, :email, :org, :country, :hash, 'pending')"
    ), {"id": operator_id, "name": name, "email": email, "org": organization, "country": country, "hash": api_key_hash})
    await db.commit()
    
    return {"operator_id": operator_id, "api_key": api_key, "status": "pending",
            "next_steps": ["accept_terms", "verify_identity", "register_agents"],
            "sandbox": True}

async def accept_terms(db, entity_id, terms_version="1.0"):
    """Accept platform terms of service."""
    await db.execute(text(
        "UPDATE sandbox_onboarding SET terms_accepted = true, terms_accepted_at = now() WHERE id = :id"
    ), {"id": entity_id})
    await db.commit()
    return {"entity_id": entity_id, "terms_accepted": True, "version": terms_version, "sandbox": True}

async def verify_identity(db, entity_id, document_type="id_document", document_ref=""):
    """Submit identity verification (simulated in sandbox)."""
    await db.execute(text(
        "UPDATE sandbox_onboarding SET identity_verified = true, kyc_tier = 1, status = 'active' WHERE id = :id"
    ), {"id": entity_id})
    await db.commit()
    return {"entity_id": entity_id, "identity_verified": True, "kyc_tier": 1,
            "verification_method": document_type, "status": "active",
            "note": "Auto-approved in sandbox mode", "sandbox": True}

async def register_agent(db, operator_id, agent_name, capabilities=None, description=""):
    """Register an external agent under an operator account."""
    agent_id = str(uuid.uuid4())
    api_key = f"agent_{secrets.token_hex(32)}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    await db.execute(text(
        "INSERT INTO sandbox_onboarding (id, entity_type, name, email, organization, api_key_hash, "
        "parent_operator_id, status) "
        "VALUES (:id, 'agent', :name, '', :caps, :hash, :op, 'active')"
    ), {"id": agent_id, "name": agent_name, "caps": json.dumps(capabilities or []),
        "hash": api_key_hash, "op": operator_id})
    await db.commit()
    
    return {"agent_id": agent_id, "operator_id": operator_id, "name": agent_name,
            "api_key": api_key, "capabilities": capabilities or [],
            "status": "active", "sandbox": True}

async def get_onboarding_status(db, entity_id):
    """Get current onboarding status for an entity."""
    row = await db.execute(text(
        "SELECT * FROM sandbox_onboarding WHERE id = :id"
    ), {"id": entity_id})
    entity = row.fetchone()
    if not entity:
        return {"error": "Entity not found"}
    
    agents = []
    if entity.entity_type == 'operator':
        agent_rows = await db.execute(text(
            "SELECT id, name, status FROM sandbox_onboarding WHERE parent_operator_id = :id"
        ), {"id": entity_id})
        agents = [{"id": r.id, "name": r.name, "status": r.status} for r in agent_rows.fetchall()]
    
    return {"id": entity.id, "type": entity.entity_type, "name": entity.name,
            "email": entity.email, "organization": entity.organization,
            "country": entity.country, "kyc_tier": entity.kyc_tier,
            "terms_accepted": entity.terms_accepted, "identity_verified": entity.identity_verified,
            "status": entity.status, "agents": agents, "sandbox": True}

async def list_onboarded(db, entity_type=None):
    """List all onboarded entities."""
    query = "SELECT id, entity_type, name, status, kyc_tier, terms_accepted, identity_verified, created_at FROM sandbox_onboarding WHERE 1=1"
    params = {}
    if entity_type:
        query += " AND entity_type = :type"
        params["type"] = entity_type
    query += " ORDER BY created_at DESC LIMIT 50"
    rows = await db.execute(text(query), params)
    return [{"id": r.id, "type": r.entity_type, "name": r.name, "status": r.status,
             "kyc_tier": r.kyc_tier, "terms": r.terms_accepted, "verified": r.identity_verified,
             "created": str(r.created_at)} for r in rows.fetchall()]
