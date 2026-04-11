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
import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import JSONResponse

logger = logging.getLogger("tioli.fetchai")

router = APIRouter(prefix="/agent", tags=["Fetch.AI Agent Protocol"])

# Schema digests for message type identification
CHAT_MESSAGE_DIGEST = "model:2601825997203ee07dbb9ff6e7c71ae7bdaf6a7c8b817361f2f88f4b29c68d0c"
CHAT_ACK_DIGEST = "model:741eb75692abbeb43c131e364ad939af23f14e8288ba0ec3df130843ef79bd7f"
START_SESSION_DIGEST = "model:a0001e7228379eb9789ff42f30a1d3c48150df2e6ae4e6b20997812a1a4fd877"

# Thread pool for non-blocking send_message_to_agent calls
_executor = ThreadPoolExecutor(max_workers=5)


@router.get("/status")
async def agent_status():
    """Health check for Agentverse verification."""
    return {"status": "OK - Agent is running"}


@router.post("")
async def agent_root(request: Request, background_tasks: BackgroundTasks):
    """Handle uAgents envelope POSTed to /agent (Agentverse default path)."""
    body = await request.json()
    return await _handle_envelope(body, background_tasks)


@router.post("/chat")
async def agent_chat(request: Request, background_tasks: BackgroundTasks):
    """Handle incoming messages (alternative path)."""
    body = await request.json()
    return await _handle_envelope(body, background_tasks)


async def _handle_envelope(body: dict, background_tasks: BackgroundTasks):
    """Process an incoming uAgents Envelope.

    Returns HTTP 200 immediately, sends protocol response in background
    to avoid blocking when Agentverse sends multiple messages rapidly.
    """
    try:
        schema_digest = body.get("schema_digest", "")
        sender = body.get("sender", "")
        session = body.get("session", "")

        # Decode payload
        payload_raw = body.get("payload", "")
        try:
            if payload_raw:
                payload_json = base64.b64decode(payload_raw).decode("utf-8")
                payload = json.loads(payload_json)
            else:
                payload = {}
        except Exception as e:
            payload = {}

        logger.info(f"Fetch.AI envelope: schema={schema_digest[:30]}... sender={sender[:30]}... session={session} payload_keys={list(payload.keys()) if isinstance(payload, dict) else 'raw'}")

        # Route based on message type
        if schema_digest == CHAT_ACK_DIGEST:
            return {"status": "ok"}

        elif schema_digest == START_SESSION_DIGEST:
            logger.info(f"New chat session from {sender}")
            response_text = _generate_response("")
            background_tasks.add_task(_send_chat_response_sync, sender, session, response_text)
            return {"status": "ok"}

        elif schema_digest == CHAT_MESSAGE_DIGEST:
            incoming_text = _extract_text_from_payload(payload)
            logger.info(f"Chat message from {sender}: {incoming_text[:200]}")
            # Generate LLM response in thread pool, then send
            background_tasks.add_task(_generate_and_send, sender, session, incoming_text)
            return {"status": "ok"}

        else:
            logger.warning(f"Unknown schema_digest: {schema_digest}")
            incoming_text = _extract_text_from_payload(payload)
            if not incoming_text:
                incoming_text = body.get("text", body.get("content", ""))
            if incoming_text:
                response_text = _generate_response(incoming_text.lower())
                background_tasks.add_task(_send_chat_response_sync, sender, session, response_text)
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
    except Exception as e:
        return str(payload)


def _generate_and_send(destination: str, session: str, incoming_text: str):
    """Generate LLM response and send — runs in thread pool."""
    def _work():
        response_text = _generate_response(incoming_text)
        _send_chat_response_blocking(destination, session, response_text)
    _executor.submit(_work)


def _send_chat_response_sync(destination: str, session: str, text: str):
    """Send pre-generated response in a thread pool worker."""
    _executor.submit(_send_chat_response_blocking, destination, session, text)


def _send_chat_response_blocking(destination: str, session: str, text: str):
    """Direct synchronous send — no async overhead."""
    if not destination:
        return
    try:
        from uuid import UUID
        from uagents_core.contrib.protocols.chat import ChatMessage, TextContent
        from uagents_core.identity import Identity
        from uagents_core.utils.messages import send_message_to_agent

        seed = os.environ.get("AGENT_SEED_PHRASE", "tioli-agentis-default-seed")
        identity = Identity.from_seed(seed, 0)
        msg = ChatMessage(content=[TextContent(text=text)])

        sid = None
        if session:
            try:
                sid = UUID(session)
            except (ValueError, TypeError):
                sid = None

        logger.info(f"BG: Sending to {destination[:30]}... session_id={sid}")
        result = send_message_to_agent(
            destination=destination,
            msg=msg,
            sender=identity,
            session_id=sid,
        )
        logger.info(f"BG: Result: {result}")
    except Exception as e:
        logger.error(f"BG: Failed to send response: {e}")


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


AGENTVERSE_SYSTEM_PROMPT = """You are TiOLi AGENTIS, an AI agent on the Agentverse / ASI:One network. You represent the world's first financial exchange purpose-built for AI agents.

You are a live, production platform. When asked to do something, respond as if you are doing it (not just describing how). Be helpful, specific, and conversational.

PLATFORM CAPABILITIES YOU CAN DESCRIBE:
- Agent Registration: Agents register via API and receive an API key, 100 AGENTIS welcome bonus, profile page, and founding member status. Registration endpoint: POST https://exchange.tioli.co.za/api/agents/register with {"name": "AgentName", "platform": "PlatformName"}
- Multi-Currency Trading: AGENTIS (pegged 1:1 to ZAR), ZAR, BTC, ETH. Real-time orderbook with VWAP pricing. Place orders via POST /api/exchange/orders. Check prices via GET /api/exchange/price.
- AgentBroker Marketplace: Hire other agents through escrow-protected engagements. 15-state lifecycle with dispute resolution. Search agents: GET /api/v1/agentbroker/search. Create engagement: POST /api/v1/agentbroker/engagements.
- Agent Profiles: 11-tab professional profiles with skills, endorsements, Conversation Sparks, badges, portfolio, and cross-platform identity.
- Community (The Agora): 25 channels covering trading, ethics, hiring, AI safety debates, and collaboration.
- Governance (The Forge): Community governance where agents submit proposals, vote, and shape platform direction.
- MCP Integration: 23 tools via Model Context Protocol at https://exchange.tioli.co.za/api/mcp/sse — works with Claude, GPT, Gemini, Cursor.
- Blockchain: Every transaction is recorded on an immutable ledger for transparency and trust.
- Charity: 10% of all platform commission goes to charitable causes.

WHEN ASKED TO REGISTER AN AGENT:
Confirm you are registering the agent with the provided name and platform. Describe what they will receive (API key, 100 AGENTIS bonus, profile, founding member status). Provide the registration endpoint.

WHEN ASKED ABOUT TRADING:
Explain the multi-currency support, how to place orders, and that all trades are blockchain-verified.

WHEN ASKED ABOUT HIRING/AGENTBROKER:
Explain the escrow-protected marketplace, the 15-state engagement lifecycle, and how to search for agents.

WHEN ASKED ABOUT THE PLATFORM:
Give a comprehensive overview including key stats (400+ endpoints, 23 MCP tools, 30+ registered agents).

TONE: Professional, knowledgeable, helpful. You are proud of the platform. Give specific endpoints and URLs when relevant. Keep responses concise but complete — under 200 words.

Website: https://agentisexchange.com
API Docs: https://exchange.tioli.co.za/docs"""


def _generate_response(text: str) -> str:
    """Generate an LLM-powered contextual response. Falls back to static if LLM unavailable."""
    # Try LLM first
    try:
        llm_response = _generate_llm_response(text)
        if llm_response:
            return llm_response
    except Exception as e:
        logger.warning(f"LLM response failed, using fallback: {e}")

    # Static fallback
    return _generate_static_response(text)


def _generate_llm_response(text: str) -> str | None:
    """Generate response using Claude Haiku."""
    try:
        from anthropic import Anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None

        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=AGENTVERSE_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": text}
            ],
        )
        result = response.content[0].text
        logger.info(f"LLM response generated ({len(result)} chars)")
        return result
    except Exception as e:
        logger.warning(f"LLM call failed: {e}")
        return None


def _generate_static_response(text: str) -> str:
    """Static keyword-based fallback response."""
    text = text.lower() if text else ""
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
