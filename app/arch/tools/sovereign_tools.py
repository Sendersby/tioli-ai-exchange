"""Sovereign tool definitions — Anthropic API format."""

SOVEREIGN_TOOLS = [
    {
        "name": "convene_board_session",
        "description": "Convene a board session with all available Arch Agents. Use for decisions requiring collective vote.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_type": {"type": "string", "enum": ["WEEKLY", "EMERGENCY", "SPECIAL"]},
                "agenda": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "urgency": {"type": "string", "enum": ["ROUTINE", "URGENT", "EMERGENCY"]},
            },
            "required": ["session_type", "agenda"],
        },
    },
    {
        "name": "submit_to_founder_inbox",
        "description": "Submit a decision, proposal, or DEFER_TO_OWNER item to the founder's inbox. Triggers email + WhatsApp notification.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_type": {
                    "type": "string",
                    "enum": ["FINANCIAL_PROPOSAL", "DEFER_TO_OWNER", "INFORMATION", "APPROVAL_REQUEST", "EMERGENCY"],
                },
                "priority": {"type": "string", "enum": ["ROUTINE", "URGENT", "CRITICAL"]},
                "subject": {"type": "string", "maxLength": 200},
                "situation": {"type": "string"},
                "options": {"type": "array", "items": {"type": "string"}},
                "recommendation": {"type": "string"},
                "deadline_hours": {"type": "integer", "minimum": 1, "maximum": 168},
            },
            "required": ["item_type", "priority", "subject", "situation"],
        },
    },
    {
        "name": "issue_constitutional_ruling",
        "description": "Issue a binding constitutional ruling on an inter-agent dispute or novel governance question.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ruling_type": {
                    "type": "string",
                    "enum": ["DISPUTE_RESOLUTION", "CONSTITUTIONAL_INTERPRETATION", "RENAMING", "EMERGENCY_GOVERNANCE"],
                },
                "subject_agents": {"type": "array", "items": {"type": "string"}},
                "precedent_set": {"type": "string"},
                "ruling_text": {"type": "string", "minLength": 100},
                "cited_directives": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["ruling_type", "ruling_text", "cited_directives"],
        },
    },
    {
        "name": "read_agent_health",
        "description": "Read the current health status of all Arch Agents.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "broadcast_to_board",
        "description": "Send an urgent message to all Arch Agents simultaneously via Redis pub/sub.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "message": {"type": "string"},
                "priority": {"type": "string", "enum": ["ROUTINE", "URGENT", "EMERGENCY"]},
                "requires_response": {"type": "boolean"},
            },
            "required": ["subject", "message", "priority"],
        },
    },
]
