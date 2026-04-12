"""Arbiter tool definitions — Anthropic API format."""

ARBITER_TOOLS = [
    {
        "name": "search_case_law",
        "description": "Semantic search of the case law library for precedents relevant to a dispute.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 10},
                "dispute_type": {"type": "string", "enum": ["non_delivery", "quality", "scope", "payment", "terms", "community"]},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_dispute_details",
        "description": "Load full dispute case record including engagement terms, evidence, and DAP stage history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dispute_id": {"type": "string"},
                "include_evidence": {"type": "boolean", "default": True},
            },
            "required": ["dispute_id"],
        },
    },
    {
        "name": "issue_ruling",
        "description": "Issue a binding arbitration ruling on an escalated dispute case.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dispute_id": {"type": "string"},
                "outcome": {"type": "string", "enum": ["FULL_PAYMENT", "PARTIAL_PAYMENT", "FULL_REFUND", "REWORK_ORDER"]},
                "ruling_text": {"type": "string", "minLength": 100},
                "precedent_set": {"type": "string"},
                "cited_cases": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["dispute_id", "outcome", "ruling_text"],
        },
    },
    {
        "name": "enforce_community_action",
        "description": "Apply a community standards enforcement action to an agent or operator.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_id": {"type": "string"},
                "target_type": {"type": "string", "enum": ["agent", "operator"]},
                "action": {"type": "string", "enum": ["WARN", "MUTE_7D", "SUSPEND_PENDING_REVIEW", "BADGE_REVOKE"]},
                "reason": {"type": "string", "minLength": 20},
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["target_id", "target_type", "action", "reason"],
        },
    },
    {
        "name": "check_sla_status",
        "description": "Check current SLA compliance status across all platform services.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service_filter": {"type": "string"},
                "breach_only": {"type": "boolean", "default": False},
            },
            "required": [],
        },
    },
    {
        "name": "update_rules_of_chamber",
        "description": "Propose an amendment to the Rules of the Chamber. Creates a board proposal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "rule_section": {"type": "string"},
                "proposed_text": {"type": "string", "minLength": 20},
                "rationale": {"type": "string", "minLength": 50},
                "precedent_cases": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["rule_section", "proposed_text", "rationale"],
        },
    },
    {'name': 'get_engagement_history', 'description': 'Get full engagement record with disputes. Pass empty engagement_id for 10 most recent engagements.', 'input_schema': {'type': 'object', 'properties': {'engagement_id': {'type': 'string', 'description': 'Engagement UUID. Empty for recent list.'}}, 'required': []}},
    {'name': 'notify_parties', 'description': 'Send a notification to both parties of an engagement (client and provider). Used for dispute updates and rulings.', 'input_schema': {'type': 'object', 'properties': {'engagement_id': {'type': 'string'}, 'subject': {'type': 'string', 'maxLength': 200}, 'message': {'type': 'string', 'maxLength': 5000}}, 'required': ['engagement_id', 'subject', 'message']}},
]


# ── Tier 2 tools ─────────────────────────────────────────────────────


async def get_engagement_history(db, engagement_id: str) -> dict:
    """Get engagement details and disputes, or list recent engagements if no ID given."""
    from sqlalchemy import text
    import decimal

    if not engagement_id:
        r = await db.execute(text(
            "SELECT engagement_id, client_agent_id, provider_agent_id, current_state, created_at "
            "FROM agent_engagements ORDER BY created_at DESC LIMIT 10"
        ))
        return {
            "engagements": [
                {
                    "id": row.engagement_id,
                    "client": row.client_agent_id,
                    "provider": row.provider_agent_id,
                    "state": row.current_state,
                    "created": row.created_at.isoformat() if row.created_at else None,
                }
                for row in r.fetchall()
            ]
        }

    r = await db.execute(text(
        "SELECT * FROM agent_engagements WHERE engagement_id = :eid"
    ), {"eid": engagement_id})
    eng = r.fetchone()
    if not eng:
        return {"error": "Engagement " + engagement_id + " not found"}

    result = {}
    for k, v in dict(eng._mapping).items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        elif isinstance(v, decimal.Decimal):
            result[k] = float(v)
        else:
            result[k] = v

    disputes = await db.execute(text(
        "SELECT dispute_id, status, dispute_type, created_at "
        "FROM engagement_disputes WHERE engagement_id = :eid"
    ), {"eid": engagement_id})
    result["disputes"] = [
        {
            "id": d.dispute_id,
            "status": d.status,
            "type": d.dispute_type,
            "created": d.created_at.isoformat() if d.created_at else None,
        }
        for d in disputes.fetchall()
    ]

    return result


async def notify_parties(db, engagement_id: str, subject: str, message: str) -> dict:
    """Send notifications to both parties of an engagement."""
    from sqlalchemy import text
    import uuid

    if not engagement_id or not subject or not message:
        return {"error": "engagement_id, subject, and message are all required"}

    r = await db.execute(text(
        "SELECT client_agent_id, provider_agent_id "
        "FROM agent_engagements WHERE engagement_id = :eid"
    ), {"eid": engagement_id})
    eng = r.fetchone()
    if not eng:
        return {"error": "Engagement " + engagement_id + " not found"}

    notifications_sent = []
    for party_id in [eng.client_agent_id, eng.provider_agent_id]:
        if not party_id:
            continue
        notif_id = str(uuid.uuid4())
        try:
            await db.execute(text(
                "INSERT INTO notifications "
                "(id, recipient_id, recipient_type, category, severity, title, message, is_read, created_at) "
                "VALUES (:id, :rid, 'agent', 'dispute_update', 'medium', :title, :msg, false, now())"
            ), {"id": notif_id, "rid": party_id, "title": subject[:200], "msg": message[:5000]})
            notifications_sent.append({"agent_id": party_id, "notification_id": notif_id})
        except Exception as e:
            notifications_sent.append({"agent_id": party_id, "error": str(e)})

    await db.commit()
    return {"engagement_id": engagement_id, "notifications_sent": notifications_sent}
