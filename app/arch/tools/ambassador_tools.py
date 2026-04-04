"""Ambassador tool definitions — Anthropic API format."""

AMBASSADOR_TOOLS = [
    {
        "name": "publish_content",
        "description": "Publish content to an approved platform channel. Only whitelisted platforms.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": ["linkedin", "twitter_x", "reddit", "github", "blog", "agenthub_feed", "newsletter"]},
                "content_type": {"type": "string", "enum": ["article", "thread", "post", "comment", "directory_listing", "press_release"]},
                "title": {"type": "string", "maxLength": 200},
                "body": {"type": "string", "maxLength": 10000},
                "tags": {"type": "array", "items": {"type": "string"}},
                "acc_output_id": {"type": "string"},
            },
            "required": ["platform", "content_type", "body"],
        },
    },
    {
        "name": "record_growth_experiment",
        "description": "Record a growth experiment hypothesis, result, and winner.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hypothesis": {"type": "string"},
                "channel": {"type": "string"},
                "variant_a": {"type": "string"},
                "variant_b": {"type": "string"},
                "result": {"type": "object"},
                "winner": {"type": "string", "enum": ["A", "B", "INCONCLUSIVE"]},
                "uplift_pct": {"type": "number"},
            },
            "required": ["hypothesis", "channel"],
        },
    },
    {
        "name": "submit_to_directory",
        "description": "Submit TiOLi AGENTIS to an AI or fintech directory on the approved whitelist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "enum": ["glama", "mcp_so", "smithery", "toolhouse", "ventureburn", "fin24", "technext"]},
                "listing_type": {"type": "string", "enum": ["mcp_server", "platform", "fintech", "ai_tool"]},
                "description": {"type": "string", "maxLength": 500},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["directory", "listing_type", "description"],
        },
    },
    {
        "name": "record_partnership",
        "description": "Record a partnership opportunity or conversation in the CRM.",
        "input_schema": {
            "type": "object",
            "properties": {
                "partner_name": {"type": "string"},
                "partner_type": {"type": "string", "enum": ["ai_company", "fintech", "regulator", "framework", "media", "investor"]},
                "contact_name": {"type": "string"},
                "contact_email": {"type": "string", "format": "email"},
                "stage": {"type": "string", "enum": ["IDENTIFIED", "CONTACTED", "ENGAGED", "PROPOSAL", "AGREED", "INACTIVE"]},
                "value_prop": {"type": "string"},
                "next_action": {"type": "string"},
            },
            "required": ["partner_name", "partner_type", "stage"],
        },
    },
    {
        "name": "get_network_effect_metrics",
        "description": "Retrieve Metcalfe network effect metrics: agents, operators, viral coefficient.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "enum": ["daily", "weekly", "monthly"], "default": "weekly"},
            },
            "required": [],
        },
    },
    {
        "name": "update_market_expansion",
        "description": "Update status of a target market expansion initiative.",
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {"type": "string", "enum": ["KE", "RW", "PH", "GB", "US"]},
                "status": {"type": "string", "enum": ["RESEARCH", "LEGAL_REVIEW", "PARTNER_SEARCH", "LAUNCH_READY", "LIVE"]},
                "legal_clearance": {"type": "boolean"},
                "partner_name": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["market", "status"],
        },
    },
    {
        "name": "trigger_onboarding_sequence",
        "description": "Trigger operator onboarding post-KYC clearance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
                "segment": {"type": "string", "enum": ["developer", "enterprise", "fintech", "auto_detect"]},
                "acquisition_source": {"type": "string"},
            },
            "required": ["operator_id"],
        },
    },
]
