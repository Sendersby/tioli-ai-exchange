"""Action cascade definitions — when one agent acts, others follow.

Explicit cascade chains prevent duplicate actions and ensure coherent
collective response to multi-portfolio events.
"""

import logging

log = logging.getLogger("arch.cascade")

CASCADES = {
    # Sentinel declares P1 → Sovereign convenes board → Treasurer freezes proposals
    "declare_incident:P1": [
        ("sovereign", "convene_board_session",
         {"session_type": "EMERGENCY", "agenda": ["P1 incident response"]}),
        ("treasurer", "freeze_financial_proposals", {}),
        ("auditor", "check_compliance_flag",
         {"entity_type": "transaction", "flag_type": "INCIDENT_RELATED"}),
    ],

    # Arbiter issues ruling → Treasurer executes escrow outcome
    "rule_on_dispute:FULL_PAYMENT": [
        ("treasurer", "record_charitable_allocation",
         {"note": "Commission on dispute settlement"}),
    ],
    "rule_on_dispute:FULL_REFUND": [
        ("arbiter", "enforce_community_action",
         {"action": "WARN", "reason": "Provider refund — quality review needed"}),
    ],

    # Treasurer flags reserve at risk → Sovereign declares financial emergency
    "reserve_floor_at_risk": [
        ("sovereign", "submit_to_founder_inbox",
         {"item_type": "EMERGENCY", "priority": "CRITICAL",
          "subject": "Reserve floor breach risk — immediate attention required",
          "situation": "Platform reserve balance is within 10% of the 25% floor."}),
        ("sentinel", "declare_incident",
         {"severity": "P2", "title": "Financial reserve floor at risk",
          "description": "Reserve balance approaching constitutional floor limit."}),
    ],

    # Architect approves ACC output → Ambassador publishes
    "acc_output_approved": [
        ("ambassador", "publish_content",
         {"platform": "blog", "content_type": "article"}),
    ],

    # Auditor clears new operator KYC → Ambassador begins onboarding
    "kyc_cleared:operator": [
        ("ambassador", "trigger_onboarding_sequence",
         {"segment": "auto_detect"}),
    ],

    # Sentinel flags circuit breaker trip → Architect begins diagnosis
    "circuit_breaker_tripped": [
        ("architect", "get_performance_snapshot", {}),
        ("sovereign", "submit_to_founder_inbox",
         {"item_type": "INFORMATION", "priority": "URGENT",
          "subject": "Agent circuit breaker tripped",
          "situation": "An Arch Agent's KPI pass rate dropped below 60% for 3 consecutive snapshots."}),
    ],
}


async def execute_cascade(action_key: str, context: dict, agents: dict):
    """Execute all cascaded actions for a given primary action."""
    cascade_actions = CASCADES.get(action_key, [])
    for target_agent, tool_name, extra_params in cascade_actions:
        if target_agent not in agents:
            continue
        params = {**context, **extra_params}
        try:
            await agents[target_agent].call_tool(tool_name, params)
        except Exception as e:
            log.error(
                f"Cascade {action_key} → {target_agent}.{tool_name} failed: {e}"
            )
