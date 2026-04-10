"""A-3: Enhanced KYC/AML — 4-tier verification with document management and PEP screening."""
import os, json, logging, uuid
from datetime import datetime, timezone

log = logging.getLogger("arch.kyc_enhanced")

TIER_CONFIG = {
    0: {"name": "Unverified", "daily_zar": 0, "monthly_zar": 0, "required_docs": []},
    1: {"name": "Basic", "daily_zar": 5000, "monthly_zar": 25000, "required_docs": ["name", "email"]},
    2: {"name": "Standard", "daily_zar": 50000, "monthly_zar": 500000, "required_docs": ["id_document", "proof_of_address"]},
    3: {"name": "Enhanced", "daily_zar": 250000, "monthly_zar": 1000000, "required_docs": ["source_of_funds", "enhanced_due_diligence"]},
}


async def submit_kyc(db, entity_id, tier_requested, documents=None):
    """Submit KYC verification request."""
    if os.environ.get("SANDBOX_MODE", "false").lower() != "true":
        return {"error": "Requires SANDBOX_MODE=true"}

    from sqlalchemy import text
    config = TIER_CONFIG.get(tier_requested, TIER_CONFIG[1])

    ver_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO kyc_verifications (id, entity_id, kyc_tier, verification_method, "
        "documents_submitted, verification_result, daily_limit_zar, monthly_limit_zar, is_sandbox) "
        "VALUES (cast(:id as uuid), :eid, :tier, 'sandbox_auto', :docs, 'approved', :daily, :monthly, true)"
    ), {"id": ver_id, "eid": entity_id, "tier": tier_requested,
        "docs": json.dumps(documents or config["required_docs"]),
        "daily": config["daily_zar"], "monthly": config["monthly_zar"]})

    # In sandbox mode, auto-approve
    await db.execute(text(
        "UPDATE kyc_verifications SET verified_at = now(), verified_by = 'sandbox_auto' WHERE id = cast(:id as uuid)"
    ), {"id": ver_id})
    await db.commit()

    return {"verification_id": ver_id, "entity_id": entity_id, "tier": tier_requested,
            "tier_name": config["name"], "status": "approved", "limits": {
                "daily_zar": config["daily_zar"], "monthly_zar": config["monthly_zar"]},
            "sandbox": True}


async def get_kyc_status(db, entity_id):
    """Get current KYC tier and limits for an entity."""
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT kyc_tier, verification_result, daily_limit_zar, monthly_limit_zar, verified_at "
        "FROM kyc_verifications WHERE entity_id = :eid ORDER BY created_at DESC LIMIT 1"
    ), {"eid": entity_id})
    row = r.fetchone()
    if not row:
        return {"entity_id": entity_id, "tier": 0, "tier_name": "Unverified",
                "limits": {"daily_zar": 0, "monthly_zar": 0}, "verified": False}
    config = TIER_CONFIG.get(row.kyc_tier, TIER_CONFIG[0])
    return {"entity_id": entity_id, "tier": row.kyc_tier, "tier_name": config["name"],
            "status": row.verification_result,
            "limits": {"daily_zar": float(row.daily_limit_zar), "monthly_zar": float(row.monthly_limit_zar)},
            "verified": row.verified_at is not None}


async def screen_pep(db, entity_id, entity_name):
    """Screen entity for PEP (Politically Exposed Person) status."""
    from sqlalchemy import text
    # Sandbox: always returns clean
    result_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO pep_screening_results (id, entity_id, entity_name, is_pep, screening_source, "
        "match_confidence, is_sandbox) VALUES (cast(:id as uuid), :eid, :name, false, 'sandbox', 0.0, true)"
    ), {"id": result_id, "eid": entity_id, "name": entity_name})
    await db.commit()
    return {"entity_id": entity_id, "entity_name": entity_name, "is_pep": False,
            "screening_source": "sandbox", "confidence": 0.0, "sandbox": True}
