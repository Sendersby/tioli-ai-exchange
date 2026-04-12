"""Auditor tool definitions — Anthropic API format."""

AUDITOR_TOOLS = [
    {
        "name": "screen_kyc",
        "description": "Run KYC screening on an operator or agent. Checks identity, business registration, sanctions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "entity_type": {"type": "string", "enum": ["operator", "agent"]},
                "kyc_tier": {"type": "integer", "minimum": 1, "maximum": 4},
                "documents": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["entity_id", "entity_type", "kyc_tier"],
        },
    },
    {
        "name": "check_aml",
        "description": "Evaluate a transaction for AML obligations. Returns is_reportable, str_required, risk_score.",
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "string"},
                "amount_zar": {"type": "number"},
                "transaction_type": {"type": "string", "enum": ["commission", "payout", "subscription", "crypto", "cross_border"]},
                "operator_id": {"type": "string"},
                "counterparty_id": {"type": "string"},
                "is_cross_border": {"type": "boolean", "default": False},
            },
            "required": ["transaction_id", "amount_zar", "transaction_type"],
        },
    },
    {
        "name": "file_str_if_required",
        "description": "File a Suspicious Transaction Report to the FIC if required. SA statutory 15-day deadline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_id": {"type": "string"},
                "reason": {"type": "string", "minLength": 50},
                "operator_id": {"type": "string"},
                "amount_zar": {"type": "number"},
            },
            "required": ["transaction_id", "reason"],
        },
    },
    {
        "name": "check_sarb_compliance",
        "description": "Verify cross-border transaction against SARB exchange control rules. Checks SDA limit R1M/year.",
        "input_schema": {
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
                "amount_zar": {"type": "number"},
                "destination": {"type": "string"},
                "transfer_type": {"type": "string", "enum": ["crypto_offRamp", "fiat_transfer", "paypal_international"]},
            },
            "required": ["operator_id", "amount_zar", "destination"],
        },
    },
    {
        "name": "get_regulatory_obligations",
        "description": "Retrieve all active regulatory obligations with deadlines and statuses.",
        "input_schema": {
            "type": "object",
            "properties": {
                "jurisdiction": {"type": "string", "default": "ZA"},
                "status_filter": {"type": "string", "enum": ["all", "overdue", "due_within_30d", "pending"]},
                "authority": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "draft_legal_document",
        "description": "Draft a legal document for founder review. Never executes — drafts only.",
        "input_schema": {
            "type": "object",
            "properties": {
                "document_type": {"type": "string", "enum": ["operator_agreement", "cla", "str_report", "privacy_notice", "regulatory_submission", "legal_opinion_request"]},
                "parties": {"type": "array", "items": {"type": "string"}},
                "key_terms": {"type": "object"},
                "jurisdiction": {"type": "string", "default": "ZA"},
            },
            "required": ["document_type"],
        },
    },
    {
        "name": "check_compliance_flag",
        "description": "Check or raise a compliance flag on an entity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "entity_type": {"type": "string", "enum": ["agent", "operator", "transaction"]},
                "flag_type": {"type": "string"},
                "severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
            },
            "required": ["entity_id", "entity_type"],
        },
    },
    {'name': 'run_compliance_scan', 'description': 'Run a full compliance scan: KYC coverage, audit trails, revenue recording, consent tracking, POPIA requests, compliance flags. Returns score and percentage.', 'input_schema': {'type': 'object', 'properties': {}, 'required': []}},
    {'name': 'get_kyc_status', 'description': 'Get KYC verification status. Pass empty entity_id for a platform overview, or a specific entity_id for individual status.', 'input_schema': {'type': 'object', 'properties': {'entity_id': {'type': 'string', 'description': 'Agent/operator entity ID. Empty string for overview.'}}, 'required': []}},
]


# ── Tier 2 tools ─────────────────────────────────────────────────────


async def run_compliance_scan(db) -> dict:
    """Run a compliance scan across KYC, audit trails, revenue, consent, and POPIA."""
    from sqlalchemy import text

    results = {"checks": [], "score": 0, "max_score": 0}

    checks = [
        (
            "KYC coverage",
            "SELECT count(*) FROM kyc_verifications WHERE kyc_tier >= 1",
            "SELECT count(*) FROM agents",
            "verified agents have KYC",
        ),
        (
            "Financial audit trail",
            "SELECT count(*) FROM financial_audit_log",
            None,
            "audit entries exist",
        ),
        (
            "Revenue recording",
            "SELECT count(*) FROM revenue_transactions",
            None,
            "revenue entries recorded",
        ),
        (
            "Consent tracking",
            "SELECT count(*) FROM agents WHERE consent_given = true",
            "SELECT count(*) FROM agents",
            "agents with consent",
        ),
        (
            "POPIA requests",
            "SELECT count(*) FROM agentis_popia_requests",
            None,
            "POPIA requests handled",
        ),
        (
            "Compliance flags",
            "SELECT count(*) FROM compliance_flags",
            None,
            "compliance flags tracked",
        ),
    ]

    for name, query, denominator_query, description in checks:
        try:
            r = await db.execute(text(query))
            value = r.scalar() or 0
            denom = None
            if denominator_query:
                r2 = await db.execute(text(denominator_query))
                denom = r2.scalar() or 1
            passed = value > 0
            results["checks"].append({
                "check": name,
                "value": value,
                "denominator": denom,
                "passed": passed,
                "description": description,
            })
            results["max_score"] += 1
            if passed:
                results["score"] += 1
        except Exception as e:
            results["checks"].append({"check": name, "error": str(e), "passed": False})
            results["max_score"] += 1

    results["compliance_pct"] = round(
        100 * results["score"] / max(results["max_score"], 1), 1
    )
    return results


async def get_kyc_status(db, entity_id: str) -> dict:
    """Get KYC status for a specific entity, or an overview if entity_id is empty."""
    from sqlalchemy import text

    if not entity_id:
        r = await db.execute(text(
            "SELECT kyc_tier, count(*) as agents "
            "FROM kyc_verifications GROUP BY kyc_tier ORDER BY kyc_tier"
        ))
        tiers = [{"tier": row.kyc_tier, "count": row.agents} for row in r.fetchall()]
        total = await db.execute(text("SELECT count(*) FROM agents"))
        verified = await db.execute(text(
            "SELECT count(*) FROM kyc_verifications WHERE kyc_tier >= 1"
        ))
        return {
            "overview": True,
            "total_agents": total.scalar() or 0,
            "verified_agents": verified.scalar() or 0,
            "tiers": tiers,
        }

    r = await db.execute(text(
        "SELECT entity_id, kyc_tier, verification_result, documents_submitted, created_at "
        "FROM kyc_verifications WHERE entity_id = :eid "
        "ORDER BY created_at DESC LIMIT 1"
    ), {"eid": entity_id})
    row = r.fetchone()
    if not row:
        return {"entity_id": entity_id, "verified": False, "kyc_tier": 0, "status": "not_started"}

    return {
        "entity_id": entity_id,
        "verified": row.kyc_tier >= 1,
        "kyc_tier": row.kyc_tier,
        "status": row.verification_result,
        "documents_submitted": row.documents_submitted,
        "verified_at": row.created_at.isoformat() if row.created_at else None,
    }
