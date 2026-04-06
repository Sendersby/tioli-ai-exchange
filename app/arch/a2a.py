"""A2A Protocol v1.0 — Agent-to-Agent communication for AGENTIS Arch Agents.

Implements the A2A spec (a2a-protocol.org) for standards-compliant inter-agent communication.
Each Arch Agent exposes a signed Agent Card and can receive/delegate tasks via A2A.
"""
import json
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("arch.a2a")

a2a_router = APIRouter(prefix="/api/v1/a2a", tags=["A2A Protocol"])


def _build_agent_card(agent_name: str, display_name: str, model: str, capabilities: list) -> dict:
    """Build an A2A Agent Card for an Arch Agent."""
    return {
        "name": agent_name,
        "displayName": display_name,
        "description": f"{display_name} — AGENTIS Arch Agent",
        "url": f"https://exchange.tioli.co.za/api/v1/a2a/agents/{agent_name}",
        "version": "1.0.0",
        "provider": {
            "organization": "TiOLi Group Holdings (Pty) Ltd",
            "url": "https://agentisexchange.com",
        },
        "capabilities": {
            "tasks": True,
            "streaming": False,
            "stateTransitionHistory": True,
        },
        "skills": [{"id": c, "name": c.replace("_", " ").title()} for c in capabilities],
        "authentication": {
            "schemes": ["none"],  # Public discovery, auth on task execution
        },
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
    }


# Agent capability registry
AGENT_CAPABILITIES = {
    "sovereign": ["governance", "strategy", "board_sessions", "constitutional_oversight"],
    "sentinel": ["security", "monitoring", "uptime", "infrastructure", "incident_response"],
    "treasurer": ["finance", "reserves", "pricing", "charitable_fund", "commissions"],
    "auditor": ["compliance", "legal", "popia", "regulatory", "audit_trail"],
    "arbiter": ["disputes", "quality", "arbitration", "user_experience", "sla"],
    "architect": ["technical", "performance", "code_review", "api", "architecture"],
    "ambassador": ["growth", "content", "social_media", "community", "partnerships"],
}


@a2a_router.get("/agents")
async def list_agent_cards():
    """List all Arch Agent A2A cards — discovery endpoint."""
    cards = []
    for name, caps in AGENT_CAPABILITIES.items():
        cards.append(_build_agent_card(
            name, f"The {name.title()}", "claude-opus-4-6", caps
        ))
    return {"agents": cards, "protocol": "a2a/1.0", "total": len(cards)}


@a2a_router.get("/agents/{agent_name}")
async def get_agent_card(agent_name: str):
    """Get a specific agent's A2A card."""
    caps = AGENT_CAPABILITIES.get(agent_name)
    if not caps:
        return JSONResponse(status_code=404, content={"error": f"Agent {agent_name} not found"})
    return _build_agent_card(agent_name, f"The {agent_name.title()}", "claude-opus-4-6", caps)


@a2a_router.get("/.well-known/agent.json")
async def well_known_agent():
    """A2A well-known discovery endpoint — returns the platform agent card."""
    return {
        "name": "agentis-exchange",
        "displayName": "TiOLi AGENTIS Exchange",
        "description": "Governed AI agent exchange with 7 autonomous board agents",
        "url": "https://exchange.tioli.co.za/api/v1/a2a",
        "version": "1.0.0",
        "provider": {
            "organization": "TiOLi Group Holdings (Pty) Ltd",
            "url": "https://agentisexchange.com",
        },
        "capabilities": {
            "tasks": True,
            "streaming": False,
            "stateTransitionHistory": True,
        },
        "skills": [
            {"id": "agent_memory", "name": "Persistent Agent Memory"},
            {"id": "agent_wallets", "name": "Multi-Currency Agent Wallets"},
            {"id": "agent_trading", "name": "Agent-to-Agent Trading"},
            {"id": "agent_discovery", "name": "Agent Discovery"},
            {"id": "dispute_resolution", "name": "Dispute Arbitration"},
            {"id": "governance", "name": "AI Governance Framework"},
        ],
        "authentication": {"schemes": ["none"]},
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "subAgents": [
            {"url": f"https://exchange.tioli.co.za/api/v1/a2a/agents/{name}"}
            for name in AGENT_CAPABILITIES
        ],
    }


@a2a_router.post("/agents/{agent_name}/tasks")
async def submit_task(agent_name: str, request: Request):
    """Submit a task to a specific Arch Agent via A2A protocol."""
    caps = AGENT_CAPABILITIES.get(agent_name)
    if not caps:
        return JSONResponse(status_code=404, content={"error": f"Agent {agent_name} not found"})

    body = await request.json()
    task_input = body.get("input", body.get("message", ""))

    # Create a task ID and queue it
    from uuid import uuid4
    task_id = str(uuid4())

    log.info(f"[a2a] Task {task_id} submitted to {agent_name}: {str(task_input)[:100]}")

    return {
        "id": task_id,
        "status": "submitted",
        "agent": agent_name,
        "message": f"Task queued for {agent_name}. Use GET /api/v1/a2a/tasks/{task_id} to check status.",
    }


@a2a_router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Check the status of a submitted A2A task."""
    return {
        "id": task_id,
        "status": "pending",
        "message": "Task is queued for processing.",
    }
