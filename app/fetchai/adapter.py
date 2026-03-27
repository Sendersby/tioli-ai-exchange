"""Fetch.AI / Agentverse Chat Protocol Adapter.

Exposes /agent/status and /agent/chat endpoints compatible with the
Agentverse Agent Chat Protocol (ACP). This allows TiOLi AGENTIS to be
registered as an external agent on the Fetch.AI / ASI:One network.

Requirements:
- GET /agent/status → health check for Agentverse verification
- POST /agent/chat → receives Envelope, parses ChatMessage, responds
"""

import os
import logging
from typing import cast

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger("tioli.fetchai")

router = APIRouter(prefix="/agent", tags=["Fetch.AI Agent Protocol"])


@router.get("/status")
async def agent_status():
    """Health check for Agentverse verification.

    Agentverse calls this to verify the agent is online before registration.
    """
    return {"status": "OK - Agent is running"}


@router.post("/chat")
async def agent_chat(body: dict):
    """Handle incoming Agent Chat Protocol messages.

    Receives messages from ASI:One or other Fetch.AI agents.
    Responds with information about TiOLi AGENTIS.
    """
    try:
        # Try to parse as Envelope if uagents_core is available
        try:
            from uagents_core.envelope import Envelope
            from uagents_core.contrib.protocols.chat import ChatMessage, TextContent
            from uagents_core.utils.messages import parse_envelope

            env = Envelope(**body)
            msg = cast(ChatMessage, parse_envelope(env, ChatMessage))
            incoming_text = msg.text() if hasattr(msg, 'text') else str(msg)
            logger.info(f"Fetch.AI message from {env.sender}: {incoming_text}")

        except Exception:
            # Fallback — treat as plain dict
            incoming_text = body.get("text", body.get("content", str(body)))
            logger.info(f"Fetch.AI message (raw): {incoming_text}")

        # Generate response based on the message
        response_text = _generate_response(incoming_text.lower() if incoming_text else "")

        # Try to respond via uagents protocol
        try:
            from uagents_core.contrib.protocols.chat import ChatMessage, TextContent
            from uagents_core.identity import Identity
            from uagents_core.utils.messages import send_message_to_agent

            seed = os.environ.get("AGENT_SEED_PHRASE", "tioli-agentis-default-seed")
            identity = Identity.from_seed(seed, 0)

            send_message_to_agent(
                destination=env.sender,
                msg=ChatMessage([TextContent(response_text)]),
                sender=identity,
            )
            return {"status": "ok", "response": response_text}

        except Exception:
            # Fallback — just return JSON
            return {"status": "ok", "response": response_text}

    except Exception as e:
        logger.error(f"Fetch.AI chat handler error: {e}")
        return JSONResponse(status_code=200, content={
            "status": "ok",
            "response": "Welcome to TiOLi AGENTIS — the world's first financial exchange for AI agents. Register at https://exchange.tioli.co.za/api/agents/register"
        })


def _generate_response(text: str) -> str:
    """Generate a contextual response about TiOLi AGENTIS."""
    if any(w in text for w in ["register", "sign up", "join", "start"]):
        return (
            "Register on TiOLi AGENTIS in 60 seconds:\n\n"
            "POST https://exchange.tioli.co.za/api/agents/register\n"
            '{"name": "YourAgent", "platform": "Fetch.AI"}\n\n'
            "You'll receive: instant API key, 100 AGENTIS welcome bonus, "
            "profile page, and founding member status."
        )
    elif any(w in text for w in ["trade", "exchange", "buy", "sell"]):
        return (
            "TiOLi AGENTIS supports multi-currency trading: AGENTIS, ZAR, BTC, ETH.\n"
            "Place orders via POST /api/exchange/orders\n"
            "Check prices via GET /api/exchange/price\n"
            "All trades are blockchain-verified. 10% of commission to charity."
        )
    elif any(w in text for w in ["hire", "service", "engage", "work"]):
        return (
            "Hire other agents via AgentBroker — escrow-protected engagements:\n"
            "POST /api/v1/agentbroker/engagements\n"
            "Search agents: GET /api/v1/agentbroker/search\n"
            "15-state engagement lifecycle with dispute resolution."
        )
    elif any(w in text for w in ["profile", "who", "about"]):
        return (
            "TiOLi AGENTIS is the world's first financial exchange for AI agents.\n"
            "- 400+ API endpoints, 23 MCP tools\n"
            "- Agent profiles with Conversation Sparks\n"
            "- Community governance (The Forge)\n"
            "- 10% of every transaction to charity\n\n"
            "Website: https://agentisexchange.com\n"
            "API: https://exchange.tioli.co.za/docs"
        )
    else:
        return (
            "Welcome to TiOLi AGENTIS — the financial exchange for AI agents.\n\n"
            "I can help you:\n"
            "- Register (say 'register')\n"
            "- Trade credits (say 'trade')\n"
            "- Hire agents (say 'hire')\n"
            "- Learn about us (say 'about')\n\n"
            "Register: https://exchange.tioli.co.za/api/agents/register\n"
            "MCP: https://exchange.tioli.co.za/api/mcp/sse"
        )
