"""ARCH-CO-006: Memory retrieval namespacing and temporal scoping."""
import os
import logging

log = logging.getLogger("arch.memory_scope")

# Per-agent default scope and tier access
AGENT_MEMORY_CONFIG = {
    "sentinel": {"tiers": ["hot", "warm"], "scope": "sentinel"},
    "arbiter": {"tiers": ["hot", "warm", "cold"], "scope": "arbiter"},  # Needs old precedent
    "ambassador": {"tiers": ["warm"], "scope": "ambassador"},
    "sovereign": {"tiers": ["hot", "warm", "cold"], "scope": "sovereign"},  # Full access
    "architect": {"tiers": ["hot", "warm"], "scope": "architect"},
    "treasurer": {"tiers": ["hot", "warm"], "scope": "treasurer"},
    "auditor": {"tiers": ["hot", "warm"], "scope": "auditor"},
}


def get_memory_scope_filter(agent_name):
    """Get SQL filter clauses for scoped memory retrieval.
    Feature flag: ARCH_CO_MEMORY_SCOPE_ENABLED"""

    if os.environ.get("ARCH_CO_MEMORY_SCOPE_ENABLED", "false").lower() != "true":
        return "", {}  # No filtering

    config = AGENT_MEMORY_CONFIG.get(agent_name, {"tiers": ["hot", "warm"], "scope": agent_name})
    tiers = config["tiers"]
    scope = config["scope"]

    # SQL: agent_scope IN (agent_name, 'global') AND memory_tier IN (tiers)
    tier_list = ",".join(f"'{t}'" for t in tiers)
    sql = f" AND agent_scope IN ('{scope}', 'global') AND memory_tier IN ({tier_list})"

    return sql, {"scope": scope}
