"""Treasurer tool definitions — Anthropic API format."""

TREASURER_TOOLS = [
    {
        "name": "check_reserve_status",
        "description": "Calculate current reserve floor, headroom, and 30-day spending ceiling. Call before any financial proposal.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "submit_financial_proposal",
        "description": "Submit a financial proposal for board vote and founder approval. Cannot execute — only prepares and routes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "proposal_type": {
                    "type": "string",
                    "enum": ["OPERATIONAL_EXPENSE", "VENDOR_PAYMENT", "INVESTMENT", "CHARITABLE_DISBURSEMENT", "EMERGENCY"],
                },
                "amount_zar": {"type": "number", "minimum": 500, "maximum": 10000000},
                "description": {"type": "string", "minLength": 20},
                "justification": {"type": "string", "minLength": 50},
                "vendor_ref": {"type": "string"},
                "urgency": {"type": "string", "enum": ["ROUTINE", "URGENT", "EMERGENCY"]},
            },
            "required": ["proposal_type", "amount_zar", "description", "justification"],
        },
    },
    {
        "name": "get_financial_report",
        "description": "Generate a financial report for a specified period.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "enum": ["daily", "weekly", "monthly", "ytd", "custom"]},
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
            },
            "required": ["period"],
        },
    },
    {
        "name": "record_charitable_allocation",
        "description": "Record a charitable allocation event in the charitable fund ledger. Base = GROSS commission.",
        "input_schema": {
            "type": "object",
            "properties": {
                "gross_commission_zar": {"type": "number"},
                "trigger_transaction_id": {"type": "string"},
                "recipient": {"type": "string"},
            },
            "required": ["gross_commission_zar", "trigger_transaction_id"],
        },
    },
    {
        "name": "record_vendor_cost",
        "description": "Record or update a vendor cost entry for tracking PSP and infrastructure costs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor_name": {"type": "string"},
                "service_type": {"type": "string"},
                "monthly_cost_zar": {"type": "number"},
                "contract_ref": {"type": "string"},
            },
            "required": ["vendor_name", "monthly_cost_zar"],
        },
    },
]
