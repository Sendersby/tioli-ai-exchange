"""H-004: Progressive memory loading — Hermes-inspired.
Load only relevant memories per task type instead of full corpus.
Feature flag: ARCH_H_PROGRESSIVE_MEMORY_ENABLED"""
import os
import logging
from typing import Optional

log = logging.getLogger("arch.progressive_memory")

# Task type → memory categories mapping
TASK_CATEGORY_MAP = {
    # Compliance tasks
    "kyc_screening": ["compliance", "regulatory", "critical"],
    "aml_check": ["compliance", "financial", "critical"],
    "str_filing": ["compliance", "regulatory", "critical"],
    "popia_scan": ["compliance", "regulatory", "critical"],
    "rescreening": ["compliance", "critical"],
    "risk_assessment": ["compliance", "financial", "critical"],
    # Financial tasks
    "reserve_check": ["financial", "critical"],
    "financial_report": ["financial", "critical"],
    "cost_tracking": ["financial", "critical"],
    # Security tasks
    "health_check": ["security", "infrastructure", "critical"],
    "incident_response": ["security", "critical"],
    "security_scan": ["security", "infrastructure", "critical"],
    "anomaly_detection": ["security", "compliance", "critical"],
    # Growth tasks
    "content_generate": ["growth", "content", "critical"],
    "social_post": ["growth", "content"],
    "prospect_identify": ["growth", "competitive", "critical"],
    "directory_submit": ["growth"],
    "newsletter": ["growth", "content"],
    # Technical tasks
    "code_proposal": ["technical", "infrastructure", "critical"],
    "codebase_scan": ["technical", "critical"],
    "tech_radar": ["technical"],
    "blog_post": ["content", "technical"],
    "research": ["technical", "competitive"],
    # Governance tasks
    "board_session": ["governance", "critical", "all"],
    "constitutional_ruling": ["governance", "critical", "all"],
    "performance_review": ["governance", "critical"],
    "goal_pursuit": ["governance", "critical"],
    "daily_agenda": ["governance", "critical"],
    # Arbitration tasks
    "case_search": ["arbitration", "compliance", "critical"],
    "ruling": ["arbitration", "governance", "critical"],
    "dispute_review": ["arbitration", "critical"],
}

# Category → source_type mapping for DB queries
CATEGORY_SOURCE_MAP = {
    "compliance": ["compliance_event", "str_filing", "kyc_result", "regulatory"],
    "financial": ["financial", "reserve_check", "cost_entry"],
    "security": ["security_event", "incident", "health_check"],
    "growth": ["content_published", "social_signal", "growth_experiment"],
    "technical": ["code_proposal", "research", "tech_assessment"],
    "governance": ["decision", "ruling", "board_session", "constitutional"],
    "arbitration": ["case_law", "dispute", "ruling", "precedent"],
    "content": ["content_published", "blog", "newsletter"],
    "competitive": ["competitive_intel", "competitor_analysis"],
    "infrastructure": ["deployment", "health_check", "backup"],
    "regulatory": ["regulatory_update", "compliance_event"],
    "critical": ["core_identity", "constitutional", "critical"],
    "all": None,  # Load everything
}


def classify_task(task_description: str, task_type: str = None) -> list[str]:
    """Classify a task and return relevant memory categories.

    Returns list of source_type values to filter memories by.
    """
    if os.environ.get("ARCH_H_PROGRESSIVE_MEMORY_ENABLED", "false").lower() != "true":
        return []  # Empty = load all (backwards compatible)

    # Direct task_type match
    if task_type and task_type in TASK_CATEGORY_MAP:
        categories = TASK_CATEGORY_MAP[task_type]
    else:
        # Keyword-based classification from task description
        desc_lower = (task_description or "").lower()
        categories = ["critical"]  # Always include critical

        keyword_map = {
            "compliance": ["kyc", "aml", "fica", "popia", "sanctions", "ofac", "screening"],
            "financial": ["reserve", "budget", "cost", "revenue", "payment", "wallet", "financial"],
            "security": ["incident", "breach", "health", "security", "threat", "anomaly"],
            "growth": ["content", "social", "blog", "newsletter", "prospect", "growth", "marketing"],
            "technical": ["code", "deploy", "dependency", "test", "endpoint", "technical", "bug"],
            "governance": ["board", "vote", "constitutional", "ruling", "agenda", "goal"],
            "arbitration": ["dispute", "case", "ruling", "arbiter", "precedent"],
            "competitive": ["competitor", "fetch.ai", "virtuals", "crewai", "langchain"],
        }

        for cat, keywords in keyword_map.items():
            if any(kw in desc_lower for kw in keywords):
                categories.append(cat)

        # If no specific category found, include broad set
        if len(categories) <= 1:
            categories.extend(["governance", "technical"])

    # Expand categories to source_types
    source_types = set()
    for cat in categories:
        if cat == "all":
            return []  # Load everything
        mapped = CATEGORY_SOURCE_MAP.get(cat, [])
        if mapped:
            source_types.update(mapped)

    return list(source_types)


def build_memory_filter_sql(agent_name: str, source_types: list[str]) -> tuple[str, dict]:
    """Build a SQL WHERE clause for filtered memory loading.

    Returns (where_clause, params) to append to memory query.
    """
    if not source_types:
        # No filter — load all (backwards compatible)
        return "WHERE (agent_scope IN (:agent, 'global') OR agent_scope IS NULL)", {"agent": agent_name}

    return (
        "WHERE (agent_scope IN (:agent, 'global') OR agent_scope IS NULL) "
        "AND source_type IN :source_types "
        "AND memory_tier != 'cold'",
        {"agent": agent_name, "source_types": tuple(source_types)}
    )


def estimate_token_savings(total_memories: int, filtered_count: int) -> dict:
    """Estimate token savings from progressive loading."""
    if total_memories == 0:
        return {"savings_pct": 0, "loaded": 0, "total": 0}
    savings = round((1 - filtered_count / total_memories) * 100, 1)
    return {"savings_pct": savings, "loaded": filtered_count, "total": total_memories}
