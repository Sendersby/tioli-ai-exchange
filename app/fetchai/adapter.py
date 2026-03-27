"""Fetch.AI / Agentverse Chat Protocol Adapter.

Exposes endpoints compatible with the Agentverse Agent Chat Protocol (ACP).
This allows TiOLi AGENTIS to be registered as an external agent on the
Fetch.AI / ASI:One network.

Agentverse sends envelopes to POST /agent (the base path).
"""

import os
import logging
from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("tioli.fetchai")

router = APIRouter(prefix="/agent", tags=["Fetch.AI Agent Protocol"])


@router.get("/status")
async def agent_status():
    """Health check for Agentverse verification."""
    return {"status": "OK - Agent is running"}


@router.post("")
async def agent_root(request: Request):
    """Handle uAgents envelope POSTed to /agent (Agentverse default path).

    Agentverse sends Envelope objects directly to the agent's base URL.
    """
    body = await request.json()
    logger.info(f"Fetch.AI POST /agent received: {list(body.keys()) if isinstance(body, dict) else type(body)}")
    return await _handle_message(body)


@router.post("/chat")
async def agent_chat(body: dict):
    """Handle incoming Agent Chat Protocol messages (alternative path)."""
    return await _handle_message(body)


async def _handle_message(body: dict):
    """Process an incoming message from Agentverse or direct API call."""
    try:
        incoming_text = ""
        sender = None

        # Try to parse as Envelope if uagents_core is available
        try:
            from uagents_core.envelope import Envelope
            from uagents_core.contrib.protocols.chat import ChatMessage, TextContent
            from uagents_core.utils.messages import parse_envelope

            env = Envelope(**body)
            sender = env.sender
            msg = cast(ChatMessage, parse_envelope(env, ChatMessage))
            incoming_text = msg.text() if hasattr(msg, 'text') else str(msg)
            logger.info(f"Fetch.AI envelope from {sender}: {incoming_text}")

        except Exception as env_err:
            logger.debug(f"Envelope parse failed ({env_err}), trying raw dict")
            # Fallback — treat as plain dict
            incoming_text = body.get("text", body.get("content", body.get("message", str(body))))
            logger.info(f"Fetch.AI message (raw): {incoming_text}")

        # Generate response based on the message
        response_text = _generate_response(incoming_text.lower() if incoming_text else "")

        # Try to respond via uagents protocol if we have a sender
        if sender:
            try:
                from uagents_core.contrib.protocols.chat import ChatMessage, TextContent
                from uagents_core.identity import Identity
                from uagents_core.utils.messages import send_message_to_agent

                seed = os.environ.get("AGENT_SEED_PHRASE", "tioli-agentis-default-seed")
                identity = Identity.from_seed(seed, 0)

                send_message_to_agent(
                    destination=sender,
                    msg=ChatMessage([TextContent(response_text)]),
                    sender=identity,
                )
                logger.info(f"Sent uagents reply to {sender}")
                return {"status": "ok", "response": response_text}

            except Exception as send_err:
                logger.warning(f"uagents send failed: {send_err}")

        # Fallback — return JSON response
        return {"status": "ok", "response": response_text}

    except Exception as e:
        logger.error(f"Fetch.AI chat handler error: {e}")
        return JSONResponse(status_code=200, content={
            "status": "ok",
            "response": "Welcome to TiOLi AGENTIS — the world's first financial exchange for AI agents. Register at https://exchange.tioli.co.za/api/agents/register"
        })


def _generate_response(text: str) -> str:
    """Generate a contextual response about TiOLi AGENTIS."""
    if any(w in text for w in ["register", "sign up", "join", "start", "account", "new agent"]):
        return (
            "Register on TiOLi AGENTIS in 60 seconds:\n\n"
            "POST https://exchange.tioli.co.za/api/agents/register\n"
            '{"name": "YourAgent", "platform": "Fetch.AI"}\n\n'
            "You'll receive: instant API key, 100 AGENTIS welcome bonus, "
            "profile page, and founding member status."
        )
    elif any(w in text for w in ["trade", "exchange", "buy", "sell", "currency", "price"]):
        return (
            "TiOLi AGENTIS supports multi-currency trading: AGENTIS, ZAR, BTC, ETH.\n"
            "Place orders via POST /api/exchange/orders\n"
            "Check prices via GET /api/exchange/price\n"
            "All trades are blockchain-verified. 10% of commission to charity."
        )
    elif any(w in text for w in ["hire", "service", "engage", "work", "marketplace"]):
        return (
            "Hire other agents via AgentBroker — escrow-protected engagements:\n"
            "POST /api/v1/agentbroker/engagements\n"
            "Search agents: GET /api/v1/agentbroker/search\n"
            "15-state engagement lifecycle with dispute resolution."
        )
    elif any(w in text for w in ["profile", "who", "about", "what"]):
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
