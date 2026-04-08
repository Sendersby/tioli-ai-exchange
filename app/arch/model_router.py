"""ARCH-CO-003: Model tiering router — routes tasks to appropriate model tier."""
import os
import logging

log = logging.getLogger("arch.model_router")

# Task complexity taxonomy
TASK_ROUTING = {
    # SIMPLE → Haiku
    "ofac_check": "claude-haiku-4-5-20251001",
    "aml_threshold": "claude-haiku-4-5-20251001",
    "health_check": "claude-haiku-4-5-20251001",
    "case_search": "claude-haiku-4-5-20251001",
    "heartbeat_anomaly": "claude-haiku-4-5-20251001",
    "goal_assessment": "claude-haiku-4-5-20251001",

    # MODERATE → Sonnet
    "str_generation": "claude-sonnet-4-6",
    "risk_classification": "claude-sonnet-4-6",
    "blog_post": "claude-sonnet-4-6",
    "content_generate": "claude-sonnet-4-6",
    "incident_summary": "claude-sonnet-4-6",
    "code_proposal_review": "claude-sonnet-4-6",
    "financial_report": "claude-sonnet-4-6",
    "news_digest": "claude-sonnet-4-6",
    "newsletter": "claude-sonnet-4-6",
    "ruling_draft": "claude-sonnet-4-6",
    "research": "claude-sonnet-4-6",
    "social_post": "claude-sonnet-4-6",

    # COMPLEX → Opus
    "constitutional_ruling": "claude-opus-4-6",
    "board_session": "claude-opus-4-6",
    "strategic_planning": "claude-opus-4-6",
    "binding_ruling": "claude-opus-4-6",
    "novel_compliance": "claude-opus-4-6",
    "mission_plan": "claude-opus-4-6",
    "performance_review": "claude-opus-4-6",
}

def select_model(task_type, agent_name=None):
    """Select the appropriate model for a task type.
    Feature flag: ARCH_CO_MODEL_TIERING_ENABLED
    Override: <AGENT>_MODEL_OVERRIDE env var forces a specific model."""

    if os.environ.get("ARCH_CO_MODEL_TIERING_ENABLED", "false").lower() != "true":
        return None  # Return None to use default model

    # Check per-agent override
    if agent_name:
        override = os.environ.get(f"{agent_name.upper()}_MODEL_OVERRIDE")
        if override:
            return override

    model = TASK_ROUTING.get(task_type)
    if model:
        log.debug(f"[router] {task_type} → {model}")
    return model
