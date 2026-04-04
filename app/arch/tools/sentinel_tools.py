"""Sentinel tool definitions — Anthropic API format."""

SENTINEL_TOOLS = [
    {
        "name": "declare_incident",
        "description": "Declare a platform incident. Use immediately when a security or operational issue is detected.",
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
                "title": {"type": "string", "maxLength": 200},
                "description": {"type": "string"},
                "popia_notifiable": {"type": "boolean", "default": False},
                "affected_systems": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["severity", "title", "description"],
        },
    },
    {
        "name": "freeze_account",
        "description": "Freeze an agent or operator account for security reasons.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
                "account_type": {"type": "string", "enum": ["agent", "operator"]},
                "reason": {"type": "string"},
                "incident_ref": {"type": "string"},
            },
            "required": ["account_id", "account_type", "reason"],
        },
    },
    {
        "name": "check_platform_health",
        "description": "Get real-time health status of all platform components.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "activate_kill_switch",
        "description": "Emergency infrastructure shutdown. Requires kill_switch_key confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "kill_switch_confirmation": {"type": "string"},
                "preserve_database": {"type": "boolean", "default": True},
            },
            "required": ["reason", "kill_switch_confirmation"],
        },
    },
    {
        "name": "check_security_posture",
        "description": "Generate a security posture report including rate limits, CVEs, and credential rotation status.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "trigger_key_rotation",
        "description": "Trigger credential rotation for a specific platform or all overdue credentials.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "description": "Specific platform or 'all_overdue'"},
            },
            "required": ["platform"],
        },
    },
    {
        "name": "verify_backup",
        "description": "Trigger a backup verification check.",
        "input_schema": {
            "type": "object",
            "properties": {
                "backup_type": {"type": "string", "enum": ["database", "redis", "files", "full"]},
            },
            "required": ["backup_type"],
        },
    },
]
