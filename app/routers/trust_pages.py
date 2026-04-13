"""Trust Centre routes — public /trust page + /api/v1/trust/status JSON.

Workstream A from COMPETITOR_ADOPTION_PLAN.md.
Standing rule reference: knock-on touchpoints checked on commit, canonical footer
present in trust.html, public-nav.js loaded, no agent action so inbox delivery N/A.
"""

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import async_session

log = logging.getLogger("tioli.trust")

router = APIRouter(tags=["Trust"])


def _compute_trust_status() -> dict:
    """Compute the current trust posture. v1 is mostly static + env-driven; later
    versions will read from arch_trust_status (refreshed by scheduler) once that
    table accumulates real audit history."""
    return {
        "encryption": {
            "in_transit": "TLS 1.2+ with HSTS",
            "at_rest": "AES-256-GCM (PBKDF2 key derivation)",
            "database": "PostgreSQL 16 encrypted connections",
            "api_keys": "SHA-256 hashed before storage",
        },
        "compliance_certifications": {
            "popia": "registered",
            "sarb_casp": "in_progress",
            "ifwg_sandbox": "submitted",
            "soc2": "not_started",
            "iso27001": "not_started",
        },
        "last_audit_date": None,
        "open_incidents": 0,
        "incident_history": [],
        "dpo_email": os.getenv("TRUST_DPO_EMAIL", "dpo@tioli.co.za"),
        "responsible_disclosure_email": os.getenv(
            "TRUST_RESPONSIBLE_DISCLOSURE_EMAIL", "security@tioli.co.za"
        ),
        "company": {
            "name": "TiOLi Group Holdings (Pty) Ltd",
            "registration": "2011/001439/07",
            "vat": "4190262677",
            "trading_as": "AGENTIS",
        },
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "cache_ttl_seconds": 300,
    }


@router.get("/trust", include_in_schema=False)
async def serve_trust_page():
    """Serve the public Trust Centre HTML."""
    return FileResponse(
        "static/landing/trust.html",
        media_type="text/html",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/api/v1/trust/status")
async def trust_status():
    """Return the live trust posture as JSON. Public, cached 5 minutes.

    Used by the Trust Centre page to render compliance badges and incident
    summary. Also useful for integrators wanting machine-readable trust state.
    """
    payload = _compute_trust_status()

    # Best-effort: log a refresh row so we have a history of when status was
    # served. Failures here MUST NOT break the response.
    try:
        async with async_session() as db:  # type: AsyncSession
            await db.execute(
                text(
                    """
                    INSERT INTO arch_trust_status
                        (refreshed_at, compliance_certifications, open_incidents, dpo_contact)
                    VALUES (now(), CAST(:certs AS jsonb), :incidents, :dpo)
                    """
                ),
                {
                    "certs": __import__("json").dumps(payload["compliance_certifications"]),
                    "incidents": payload["open_incidents"],
                    "dpo": payload["dpo_email"],
                },
            )
            await db.commit()
    except Exception as exc:
        log.warning(f"trust status refresh log failed (non-fatal): {exc}")

    return JSONResponse(
        content=payload,
        headers={"Cache-Control": "public, max-age=300"},
    )
