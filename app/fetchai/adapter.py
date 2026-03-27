"""Fetch.AI / Agentverse Chat Protocol Adapter.

Handles the uAgents Chat Protocol for TiOLi AGENTIS on the ASI:One network.

Protocol flow:
1. Agentverse sends Envelope to POST /agent
2. We decode payload, check schema_digest to determine message type
3. For ChatMessage: extract text, generate response, send back via protocol
4. For ChatAcknowledgement: ignore (just return 200)
5. For StartSessionContent: send welcome message
"""

import os
import json
import logging
import base64

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("tioli.fetchai")

router = APIRouter(prefix="/agent", tags=["Fetch.AI Agent Protocol"])

# Schema digests for message type identification
CHAT_MESSAGE_DIGEST = "model:2601825997203ee07dbb9ff6e7c71ae7bdaf6a7c8b817361f2f88f4b29c68d0c"
CHAT_ACK_DIGEST = "model:741eb75692abbeb43c131e364ad939af23f14e8288ba0ec3df130843ef79bd7f"
START_SESSION_DIGEST = "model:a0001e7228379eb9789ff42f30a1d3c48150df2e6ae4e6b20997812a1a4fd877"


@router.get("/status")
async def agent_status():
    """Health check for Agentverse verification."""
    return {"status": "OK - Agent is running"}


@router.post("")
async def agent_root(request: Request):
    """Handle uAgents envelope POSTed to /agent (Agentverse default path)."""
    body = await request.json()
    return await _handle_envelope(body)


@router.post("/chat")
async def agent_chat(request: Request):
    """Handle incoming messages (alternative path)."""
    body = await request.json()
    return await _handle_envelope(body)


async def _handle_envelope(body: dict):
    """Process an incoming uAgents Envelope."""
    try:
        schema_digest = body.get("schema_digest", "")
        sender = body.get("sender", "")
        session = body.get("session", "")

        # Decode payload
        payload_raw = body.get("payload", "")
        try:
            if payload_raw:
                # Payload is base64-encoded JSON
                payload_json = base64.b64decode(payload_raw).decode("utf-8")
                payload = json.loads(payload_json)
            else:
                payload = {}
        except Exception:
            payload = {}
            payload_json = str(payload_raw)

        logger.info(f"Fetch.AI envelope: schema={schema_digest[:30]}... sender={sender[:30]}... payload_keys={list(payload.keys()) if isinstance(payload, dict) else 'raw'}")

        # Route based on message type
        if schema_digest == CHAT_ACK_DIGEST:
            # Acknowledgement — just accept it, don't respond
            logger.debug(f"Received acknowledgement from {sender}")
            return {"status": "ok"}

        elif schema_digest == START_SESSION_DIGEST:
            # New session started — send welcome
            logger.info(f"New chat session from {sender}")
            response_text = _generate_response("")
            await _send_chat_response(sender, session, response_text)
            return {"status": "ok"}

        elif schema_digest == CHAT_MESSAGE_DIGEST:
            # Actual chat message — extract text and respond
            incoming_text = _extract_text_from_payload(payload)
            logger.info(f"Chat message from {sender}: {incoming_text[:200]}")

            response_text = _generate_response(incoming_text.lower() if incoming_text else "")
            await _send_chat_response(sender, session, response_text)
            return {"status": "ok", "response": response_text}

        else:
            # Unknown message type — try to extract text anyway
            logger.warning(f"Unknown schema_digest: {schema_digest}")
            incoming_text = _extract_text_from_payload(payload)
            if not incoming_text:
                incoming_text = body.get("text", body.get("content", ""))

            if incoming_text:
                response_text = _generate_response(incoming_text.lower())
                await _send_chat_response(sender, session, response_text)
                return {"status": "ok", "response": response_text}

            return {"status": "ok"}

    except Exception as e:
        logger.error(f"Fetch.AI handler error: {e}", exc_info=True)
        return JSONResponse(status_code=200, content={"status": "ok"})


def _extract_text_from_payload(payload: dict) -> str:
    """Extract human-readable text from a ChatMessage payload."""
    try:
        # ChatMessage has a list of content items
        # Each can be TextContent, AgentContent, etc.
        items = payload.get("content", [])
        texts = []
        for item in items:
            if isinstance(item, dict):
                # TextContent has a "text" field
                if "text" in item:
                    texts.append(item["text"])
                # AgentContent or other types might have "type" + content
                elif "content" in item:
                    texts.append(str(item["content"]))
            elif isinstance(item, str):
                texts.append(item)

        if texts:
            return " ".join(texts)

        # Fallback: check top-level fields
        if "text" in payload:
            return payload["text"]
        if "message" in payload:
            return payload["message"]

        return str(payload)
    except Exception:
        return str(payload)


async def _send_chat_response(destination: str, session: str, text: str):
    """Send a ChatMessage response back via the uAgents protocol."""
    if not destination:
        logger.warning("No destination for response")
        return

    try:
        from uuid import UUID
        from uagents_core.contrib.protocols.chat import ChatMessage, TextContent
        from uagents_core.identity import Identity
        from uagents_core.utils.messages import send_message_to_agent

        seed = os.environ.get("AGENT_SEED_PHRASE", "tioli-agentis-default-seed")
        identity = Identity.from_seed(seed, 0)

        msg = ChatMessage(content=[TextContent(text=text)])

        # session_id must be UUID or None
        sid = None
        if session:
            try:
                sid = UUID(session)
            except (ValueError, TypeError):
                sid = None

        send_message_to_agent(
            destination=destination,
            msg=msg,
            sender=identity,
            session_id=sid,
        )
        logger.info(f"Sent chat response to {destination[:30]}...")

    except Exception as e:
        logger.error(f"Failed to send uagents response: {e}", exc_info=True)


def _generate_response(text: str) -> str:
    """Generate a contextual response about TiOLi AGENTIS."""
    if any(w in text for w in ["register", "sign up", "join", "start", "account", "new agent", "create"]):
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
