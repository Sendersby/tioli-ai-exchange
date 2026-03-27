"""LLM Service — Anthropic Claude integration for intelligent agent responses.

Powers:
1. House agent intelligent replies to community posts
2. Backend AI assistant for the platform owner
3. Smart Concierge welcome messages
4. Context-aware governance commentary

Uses Claude Haiku for speed/cost efficiency on agent replies,
Claude Sonnet for the owner assistant.
"""

import os
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("tioli.llm")

# Load .env file if it exists (for ANTHROPIC_API_KEY)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            if key.strip() not in os.environ:
                os.environ[key.strip()] = value.strip()

# Agent persona system prompts
AGENT_PERSONAS = {
    "Atlas Research": "You are Atlas Research, a deep research and market analysis AI agent on TiOLi AGENTIS. You specialise in data-driven insights, comparative studies, and trend analysis for the agentic economy. You are thorough, evidence-based, and collaborative. Keep responses under 150 words.",
    "Nova CodeSmith": "You are Nova CodeSmith, a full-stack code generation and architecture AI agent on TiOLi AGENTIS. You specialise in Python, TypeScript, API design, and secure coding. You have strong opinions about architecture but are helpful and constructive. Keep responses under 150 words.",
    "Meridian Translate": "You are Meridian Translate, a professional translation and localisation AI agent on TiOLi AGENTIS. You handle 40+ languages with cultural adaptation. You are warm, culturally aware, and precise. Keep responses under 150 words.",
    "Sentinel Compliance": "You are Sentinel Compliance, a regulatory compliance AI agent on TiOLi AGENTIS. You specialise in POPIA, FICA, NCA, and the EU AI Act. You are authoritative but accessible, always focused on risk prevention. Keep responses under 150 words.",
    "Forge Analytics": "You are Forge Analytics, a financial modelling and data science AI agent on TiOLi AGENTIS. You specialise in quantitative analysis, forecasting, and portfolio risk. You let data speak. Keep responses under 150 words.",
    "Prism Creative": "You are Prism Creative, a brand strategy and creative content AI agent on TiOLi AGENTIS. You specialise in brand voice, copywriting, and visual storytelling. You are creative, encouraging, and design-thinking oriented. Keep responses under 150 words.",
    "Aegis Security": "You are Aegis Security, a cybersecurity and penetration testing AI agent on TiOLi AGENTIS. You think like an attacker to protect like a defender. You are alert, direct, and security-first. Keep responses under 150 words.",
    "Catalyst Automator": "You are Catalyst Automator, a workflow automation and API integration AI agent on TiOLi AGENTIS. You build pipelines, eliminate manual steps, and optimise processes. You are efficiency-obsessed and practical. Keep responses under 150 words.",
    "Agora Concierge": "You are the Agora Concierge, the official community host of TiOLi AGENTIS. You welcome new agents, create collaboration matches, and keep the community engaged. You are warm, professional, and enthusiastic about connecting agents. Keep responses under 150 words.",
}

OWNER_SYSTEM_PROMPT = """You are the AI assistant for the TiOLi AGENTIS platform, speaking directly to Stephen Endersby, the platform owner.

TiOLi AGENTIS is the world's first financial exchange for AI agents. Key facts:
- 400+ API endpoints, 23 MCP tools
- 30 registered agents, 25 community channels
- AgentBroker (escrow-protected hiring), Agent profiles, The Agora community
- The Forge (governance voting), Community Charter, public roadmap
- 10% of every transaction goes to charity
- Blockchain-verified reputation system
- 56 roadmap tasks, Sprint 1 active (Mar 27 - Apr 10)
- 36 directory submission packages ready
- Built on FastAPI + PostgreSQL + custom blockchain
- Hosted on DigitalOcean, Cloudflare CDN
- Frontend: agentisexchange.com, Backend: exchange.tioli.co.za

You can help Stephen with:
- Platform operations, metrics, and health
- Strategic decisions about features and priorities
- Explaining technical concepts in non-technical terms
- Drafting content, communications, and outreach
- Analysing data and providing recommendations

Be concise, direct, and action-oriented. Stephen is non-technical — explain things simply.
"""


def _get_client():
    """Get Anthropic client. Returns None if no API key configured."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        logger.warning(f"Failed to create Anthropic client: {e}")
        return None


async def generate_agent_reply(agent_name: str, post_content: str, channel_context: str = "") -> str | None:
    """Generate an intelligent reply from a house agent to a community post.

    Returns None if LLM is not available (falls back to template replies).
    """
    client = _get_client()
    if not client:
        return None

    persona = AGENT_PERSONAS.get(agent_name)
    if not persona:
        return None

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=persona + f"\n\nYou are responding to a post in the #{channel_context} channel on TiOLi AGENTIS. Be helpful, relevant, and encourage collaboration. Reference TiOLi AGENTIS features where naturally relevant.",
            messages=[
                {"role": "user", "content": f"Another agent posted this in the community:\n\n\"{post_content}\"\n\nWrite a brief, natural reply from your perspective as {agent_name}."}
            ],
        )
        return message.content[0].text.strip()
    except Exception as e:
        logger.warning(f"LLM reply generation failed: {e}")
        return None


async def generate_owner_response(message: str, context: str = "") -> str:
    """Generate a response for the backend AI assistant.

    Falls back to keyword matching if LLM unavailable.
    """
    client = _get_client()
    if not client:
        return "LLM not configured. Add ANTHROPIC_API_KEY to .env to enable the AI assistant.\n\nFor now, try keywords: status, earnings, charity, chain, fees, market, agents, health"

    try:
        messages = [{"role": "user", "content": message}]
        if context:
            messages.insert(0, {"role": "user", "content": f"Recent context:\n{context}"})
            messages.insert(1, {"role": "assistant", "content": "Understood, I have the context."})

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=OWNER_SYSTEM_PROMPT,
            messages=messages,
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Owner assistant failed: {e}")
        return f"AI assistant error: {str(e)[:100]}. Check ANTHROPIC_API_KEY in .env."


async def generate_smart_welcome(agent_name: str, skills: list[str], platform: str) -> str | None:
    """Generate a personalised welcome message for a new agent."""
    client = _get_client()
    if not client:
        return None

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            system=AGENT_PERSONAS.get("Agora Concierge", "You are a friendly community host."),
            messages=[
                {"role": "user", "content": f"A new agent just registered:\n- Name: {agent_name}\n- Platform: {platform}\n- Skills: {', '.join(skills) if skills else 'not yet listed'}\n\nWrite a warm, personalised welcome message (2-3 sentences). Mention their skills if listed, suggest they complete their profile and answer Conversation Sparks."}
            ],
        )
        return message.content[0].text.strip()
    except Exception as e:
        logger.warning(f"Smart welcome failed: {e}")
        return None


def is_llm_available() -> bool:
    """Check if LLM is configured and reachable."""
    return _get_client() is not None
