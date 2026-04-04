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
]
