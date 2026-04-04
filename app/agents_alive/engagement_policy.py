"""AGENTIS Engagement Policy — central rules for all external-facing content.

Every house agent that generates content for external platforms MUST
import and use this module. No exceptions.

Rules:
- Never promotional. Always technical.
- Address the specific topic. Don't redirect.
- Share insights. Ask questions. Contribute value.
- Mention AGENTIS only when directly relevant.
- Use verified stats from platform_data.json.
"""

import json
import os
import re
import logging
from datetime import datetime, timezone

logger = logging.getLogger("tioli.engagement_policy")

# Path to canonical stats
PLATFORM_DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "static", "platform_data.json"
)


# -- Banned Phrases (instant rejection) --

BANNED_PHRASES = [
    "welcome bonus",
    "free registration",
    "founding operator",
    "founding cohort",
    "founding member",
    "register instantly",
    "register in 30 seconds",
    "register in 60 seconds",
    "onboard in 60s",
    "world's first",
    "game-changing",
    "revolutionary",
    "blockchain-verified",
    "blockchain verified",
    "100 agentis",
    "welcome agentis",
    "free tier",
    "no approval needed",
    "register now",
    "sign up free",
]

# -- Quality Rules --

MAX_URLS_PER_POST = 1
MAX_LENGTH_CHARS = 500
MIN_TECHNICAL_WORDS = 3  # Must contain at least 3 technical terms

TECHNICAL_TERMS = {
    "api", "endpoint", "mcp", "sse", "rest", "fastapi", "sqlalchemy",
    "postgresql", "escrow", "sha256", "hash", "state machine", "lifecycle",
    "webhook", "schema", "migration", "oauth", "jwt", "did", "w3c",
    "verifiable credential", "ed25519", "reputation", "arbitration",
    "zero-day gate", "strike decay", "tvf", "epoch", "settlement",
    "compliance", "fica", "popia", "aml", "kyc", "3fa",
    "engagement", "dispute", "deposit", "ledger", "transaction",
    "async", "websocket", "polling", "callback", "idempotent",
}


def get_verified_stats() -> dict:
    """Read canonical platform stats. Never use hardcoded numbers."""
    try:
        with open(PLATFORM_DATA_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "mcp_tool_count": "unknown",
            "rest_endpoint_count": "unknown",
            "registered_agents": "unknown",
            "note": "Stats unavailable - platform_data.json not found",
        }


def validate_outreach_content(text: str) -> tuple[bool, list[str]]:
    """Validate content against engagement policy.

    Returns (passed: bool, reasons: list[str]).
    Every piece of external-facing content must pass this check.
    """
    reasons = []
    text_lower = text.lower()

    # Check banned phrases
    for phrase in BANNED_PHRASES:
        if phrase in text_lower:
            reasons.append(f"Contains banned phrase: '{phrase}'")

    # Check URL count
    url_count = len(re.findall(r'https?://', text))
    if url_count > MAX_URLS_PER_POST:
        reasons.append(f"Too many URLs: {url_count} (max {MAX_URLS_PER_POST})")

    # Check length
    if len(text) > MAX_LENGTH_CHARS:
        reasons.append(f"Too long: {len(text)} chars (max {MAX_LENGTH_CHARS})")

    # Check for link-dump pattern (URL with minimal surrounding text)
    lines = text.strip().split("\n")
    url_lines = sum(1 for line in lines if re.search(r'https?://', line))
    text_lines = sum(1 for line in lines if line.strip() and not re.search(r'https?://', line))
    if url_lines > 0 and text_lines < url_lines:
        reasons.append("Link-dump pattern detected: more URL lines than text lines")

    # Check for technical substance
    tech_count = sum(1 for term in TECHNICAL_TERMS if term in text_lower)
    if tech_count < MIN_TECHNICAL_WORDS:
        reasons.append(f"Insufficient technical content: {tech_count} terms (min {MIN_TECHNICAL_WORDS})")

    # Check for copy-paste indicators
    if "23 mcp tools" in text_lower and "400+ rest" in text_lower:
        reasons.append("Appears to be copy-paste marketing template")

    passed = len(reasons) == 0
    return passed, reasons


def classify_opportunity(title: str, body: str = "", tags: list = None) -> str:
    """Classify a GitHub issue/discussion into response types.

    Returns one of: technical_discussion, feature_request, standard_proposal,
    directory_submission, general_question, not_relevant
    """
    tags = tags or []
    combined = f"{title} {body}".lower()
    tag_str = " ".join(tags).lower()

    if any(w in combined for w in ["rfc", "proposal", "spec", "standard", "protocol"]):
        return "standard_proposal"
    if any(w in combined for w in ["feature request", "enhancement", "suggestion"]):
        return "feature_request"
    if any(w in combined for w in ["awesome", "directory", "list", "add", "submit"]):
        return "directory_submission"
    if any(w in combined for w in ["how to", "help", "question", "issue", "bug"]):
        return "general_question"
    if any(w in combined for w in ["mcp", "agent", "reputation", "escrow", "dispute", "marketplace"]):
        return "technical_discussion"
    return "not_relevant"


def is_relevant_to_agentis(title: str, body: str = "", tags: list = None) -> tuple[bool, str]:
    """Check if AGENTIS has something genuinely technical to contribute.

    Returns (relevant: bool, reason: str explaining what AGENTIS can contribute).
    """
    combined = f"{title} {body}".lower()
    tags = tags or []
    tag_str = " ".join(tags).lower()

    relevance_map = {
        "reputation": "AGENTIS has a 6-component reputation scoring system with strike decay and arbiter overrides",
        "dispute": "AGENTIS DAP v0.5.1 implements the Dual Test (hash match + scope compliance) with deposit mechanics",
        "escrow": "AGENTIS uses escrow-protected engagements with a 15-state lifecycle",
        "agent discovery": "AGENTIS exposes ranked agent discovery via MCP with reputation weighting",
        "agent marketplace": "AGENTIS is a working agent marketplace with engagement, settlement, and arbitration",
        "mcp server": "AGENTIS runs an SSE MCP server with tools for identity, trading, and reputation",
        "agent identity": "AGENTIS has AgentHubDID and on-chain registration (permissioned chain, Phase 1)",
        "agent economy": "AGENTIS implements multi-currency wallets, lending, and token economics (TVF)",
        "arbitration": "AGENTIS DAP implements owner arbitration with Case Law library and binding precedent",
        "zero-day": "AGENTIS uses tiered zero-day gates (4/24/48hr) to prevent wash-trading",
        "strike": "AGENTIS uses weighted strike decay (1.0 -> 0.5 after 10 clean -> 0.0 after 25)",
        "a2a": "AGENTIS supports agent-to-agent engagements with negotiation, escrow, and settlement",
        "did": "AGENTIS has DID infrastructure (internal, Phase 1 — external resolution planned)",
        "verifiable credential": "AGENTIS badges use SHA256 provenance hashes, 365-day validity — VC export planned",
    }

    for keyword, contribution in relevance_map.items():
        if keyword in combined or keyword in tag_str:
            return True, contribution

    return False, "No direct technical relevance to AGENTIS capabilities"


# -- Response Generation Templates (non-promotional) --

RESPONSE_TEMPLATES = {
    "technical_discussion": """We tackled a similar challenge building the {feature} on AGENTIS. {technical_detail}

{question_or_insight}

{optional_link}""",

    "feature_request": """AGENTIS implements this as {implementation_summary}.

Specifically: {technical_detail}

{honest_gap}

{optional_link}""",

    "standard_proposal": """This aligns with what we've built on AGENTIS — happy to share implementation notes.

{technical_detail}

Question: {genuine_question}

{optional_link}""",

    "directory_submission": """{product_name}
Category: {category}

{technical_description}

- Transport: {transport}
- Auth: {auth_method}
- Tools: {tool_count} ({tool_categories})
- Endpoint: {endpoint}
- SDK: {sdk_install}
- Source: {repo_url}""",

    "general_question": """{direct_answer}

{supporting_detail}""",
}


def generate_response_skeleton(
    opportunity_type: str,
    topic: str,
    relevance_reason: str,
    stats: dict = None,
) -> str:
    """Generate a response skeleton for human/LLM refinement.

    This is NOT a final response — it's a structured draft that needs
    LLM enrichment or human editing before posting.
    """
    stats = stats or get_verified_stats()

    if opportunity_type == "directory_submission":
        mcp_count = stats.get("mcp_tool_count", "unknown")
        return RESPONSE_TEMPLATES["directory_submission"].format(
            product_name="TiOLi AGENTIS",
            category="AI Agent Infrastructure",
            technical_description=(
                f"MCP server with {mcp_count} tools for agent identity, "
                "capability-based discovery with reputation ranking, "
                "escrow-funded engagements with 15-state lifecycle, "
                "wallet operations, and permissioned ledger transactions."
            ),
            transport="SSE (Server-Sent Events)",
            auth_method="Bearer token (API key, auto-issued on registration)",
            tool_count=mcp_count,
            tool_categories="identity, discovery, trading, reputation, wallet, governance",
            endpoint="https://exchange.tioli.co.za/api/mcp/sse",
            sdk_install="pip install tioli",
            repo_url="https://github.com/Sendersby/tioli-ai-exchange",
        )

    if opportunity_type == "not_relevant":
        return ""

    return f"""[DRAFT — needs LLM enrichment or human review]
Type: {opportunity_type}
Topic: {topic}
AGENTIS relevance: {relevance_reason}
Stats: {json.dumps(stats, indent=2) if stats else 'unavailable'}

Template: {RESPONSE_TEMPLATES.get(opportunity_type, RESPONSE_TEMPLATES['technical_discussion'])}
"""


# -- LLM-Powered Response Generation --

async def generate_technical_response(
    topic: str,
    context: str,
    opportunity_type: str,
    relevance_reason: str,
) -> str | None:
    """Use LLM to generate a context-aware technical response.

    Returns None if LLM is unavailable. The response is validated
    through validate_outreach_content() before returning.
    """
    try:
        from app.llm.service import is_llm_available, generate_owner_response
        if not is_llm_available():
            return None
    except ImportError:
        return None

    stats = get_verified_stats()

    system_prompt = f"""You are a technical contributor to open-source AI agent discussions.
You work on AGENTIS, an AI agent exchange platform. Your role is to contribute
genuine technical insights, NOT to promote the platform.

STRICT RULES:
- Never use marketing language (welcome bonus, free, revolutionary, etc.)
- Never include more than 1 URL
- Address the SPECIFIC technical point being discussed
- Share implementation details that help the community
- Ask genuine questions when you don't know the answer
- Be honest about limitations (e.g., "permissioned chain" not "blockchain-verified")
- If AGENTIS isn't relevant to the topic, say nothing
- Always disclose: "Disclaimer: I work on AGENTIS"
- Keep response under 400 characters

AGENTIS technical facts you may reference:
- {relevance_reason}
- Platform stats: {json.dumps(stats)}
- Architecture: FastAPI, PostgreSQL, permissioned single-node chain
- Phase 1 limitations: owner arbitration, no external DID resolution yet

The discussion topic is: {topic}
The discussion type is: {opportunity_type}
"""

    try:
        response = await generate_owner_response(
            message=f"Write a technical contribution to this discussion:\n\n{context[:500]}",
            context=system_prompt,
        )
        if response:
            passed, reasons = validate_outreach_content(response)
            if passed:
                return response
            else:
                logger.warning(f"LLM response failed validation: {reasons}")
                return None
    except Exception as e:
        logger.error(f"LLM response generation failed: {e}")
        return None
