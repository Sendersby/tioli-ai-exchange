"""Architect tool definitions — Anthropic API format.

Includes ACC orchestration tools (PI-10 fix).
"""

ARCHITECT_TOOLS = [
    {
        "name": "submit_code_proposal",
        "description": "Submit a code evolution proposal through the four-tier protocol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tier": {"type": "string", "enum": ["0", "1", "2", "3"]},
                "title": {"type": "string", "maxLength": 200},
                "description": {"type": "string"},
                "rationale": {"type": "string"},
                "file_changes": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["tier", "title", "description", "rationale"],
        },
    },
    {
        "name": "toggle_feature_flag",
        "description": "Toggle a feature flag on or off. Only for non-constitutional flags.",
        "input_schema": {
            "type": "object",
            "properties": {
                "flag_name": {"type": "string"},
                "enabled": {"type": "boolean"},
                "reason": {"type": "string"},
            },
            "required": ["flag_name", "enabled", "reason"],
        },
    },
    {
        "name": "sandbox_deploy",
        "description": "Deploy a code proposal to the sandbox/staging environment for testing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string"},
                "test_suite": {"type": "string", "default": "full"},
            },
            "required": ["proposal_id"],
        },
    },
    {
        "name": "update_tech_radar",
        "description": "Add or update a technology assessment on the tech radar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "technology": {"type": "string"},
                "category": {"type": "string"},
                "assessment": {"type": "string", "enum": ["ADOPT", "TRIAL", "ASSESS", "HOLD"]},
                "rationale": {"type": "string"},
            },
            "required": ["technology", "assessment", "rationale"],
        },
    },
    {
        "name": "evaluate_ai_model",
        "description": "Evaluate a new AI model for potential platform integration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_name": {"type": "string"},
                "provider": {"type": "string"},
                "benchmark_results": {"type": "object"},
                "cost_per_1k_tokens": {"type": "number"},
                "latency_ms_p50": {"type": "integer"},
            },
            "required": ["model_name", "provider"],
        },
    },
    {
        "name": "get_performance_snapshot",
        "description": "Get the latest performance snapshot for an agent or all agents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Optional: specific agent or 'all'"},
            },
            "required": [],
        },
    },
    # ACC orchestration tools (PI-10 fix)
    {
        "name": "trigger_acc_task",
        "description": "Instruct the ACC to produce content on a specific topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_type": {"type": "string", "enum": ["seo_article", "aeo_response", "press_release", "community_post", "technical_doc"]},
                "topic": {"type": "string"},
                "target_keywords": {"type": "array", "items": {"type": "string"}},
                "word_count": {"type": "integer", "minimum": 200, "maximum": 2000},
                "urgency": {"type": "string", "enum": ["ROUTINE", "URGENT"]},
            },
            "required": ["task_type", "topic"],
        },
    },
    {
        "name": "approve_acc_output",
        "description": "Mark ACC output as approved. Ambassador then publishes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "output_id": {"type": "string"},
                "approval_note": {"type": "string"},
            },
            "required": ["output_id"],
        },
    },
]
