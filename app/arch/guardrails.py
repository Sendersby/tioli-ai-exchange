"""Agent action guardrails — pre/post validation for safety."""
import logging
import re

log = logging.getLogger("arch.guardrails")

# Hardcoded prohibitions (cannot be overridden)
BLOCKED_ACTIONS = [
    "rm -rf /",
    "DROP TABLE",
    "DELETE FROM agents",
    "DELETE FROM wallets",
    "shutdown",
    "reboot",
    "format",
    "mkfs",
    "dd if=",
]

BLOCKED_CONTENT_PATTERNS = [
    r"password\s*[:=]\s*\S+",  # Don't publish passwords
    r"api[_-]?key\s*[:=]\s*\S+",  # Don't publish API keys
    r"sk-[a-zA-Z0-9]{20,}",  # OpenAI-style keys
    r"Bearer\s+[a-zA-Z0-9_-]{20,}",  # Bearer tokens
]

SPENDING_THRESHOLD = 100.0  # AGENTIS tokens — above this requires board vote

def validate_pre_action(action_type: str, params: dict, agent_name: str) -> dict:
    """Validate an action BEFORE execution. Returns {allowed: bool, reason: str}."""

    # Check blocked commands
    if action_type == "execute_command":
        cmd = params.get("command", "")
        for blocked in BLOCKED_ACTIONS:
            if blocked.lower() in cmd.lower():
                log.warning(f"[guardrails] BLOCKED: {agent_name} tried '{cmd[:50]}'")
                return {"allowed": False, "reason": f"Blocked action: {blocked}"}

    # Check spending limits
    if action_type == "transfer" or action_type == "financial_proposal":
        amount = params.get("amount", 0)
        if amount > SPENDING_THRESHOLD:
            log.warning(f"[guardrails] SPENDING LIMIT: {agent_name} tried {amount} AGENTIS")
            return {"allowed": False, "reason": f"Amount {amount} exceeds threshold {SPENDING_THRESHOLD}. Requires board vote."}

    # Check self-modification (H-01)
    if action_type == "write_file" and agent_name == "architect":
        filepath = params.get("path", "")
        if "architect.py" in filepath:
            return {"allowed": False, "reason": "H-01: Architect cannot modify its own code"}

    return {"allowed": True, "reason": "Action permitted"}


def validate_post_action(action_type: str, output: str, agent_name: str) -> dict:
    """Validate action OUTPUT after execution. Checks for leaked secrets, etc."""

    for pattern in BLOCKED_CONTENT_PATTERNS:
        if re.search(pattern, output, re.IGNORECASE):
            log.warning(f"[guardrails] CONTENT LEAK detected in {agent_name} output")
            return {"safe": False, "reason": "Output contains potential secret/credential",
                    "action": "Output redacted. Do not publish."}

    return {"safe": True, "reason": "Output clean"}


def validate_social_content(content: str, agent_name: str) -> dict:
    """Validate content before social media publishing."""
    issues = []

    # Check for secrets
    for pattern in BLOCKED_CONTENT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            issues.append("Contains potential credential/secret")

    # Check length
    if len(content) > 280 and "twitter" in agent_name.lower():
        issues.append(f"Exceeds Twitter limit ({len(content)} chars)")

    # Check for competitor bashing (brand guideline)
    negative_words = ["sucks", "terrible", "garbage", "worst", "scam"]
    for word in negative_words:
        if word in content.lower():
            issues.append(f"Contains negative language: '{word}'")

    if issues:
        return {"approved": False, "issues": issues}
    return {"approved": True, "issues": []}
