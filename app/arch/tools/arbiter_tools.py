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
]
