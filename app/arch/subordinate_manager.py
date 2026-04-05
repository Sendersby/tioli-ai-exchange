"""Subordinate Agent Management — Arch Agents control their teams.

Gives Arch Agents the ability to:
1. Create new subordinate agents (Domain/Ops/Task/Tool)
2. Issue instructions to subordinates
3. Verify subordinate capability
4. Approve/reject subordinate work
5. Scope development requirements for new capabilities
6. Suspend/resume/terminate subordinates
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

log = logging.getLogger("arch.subordinate_manager")

# Layer definitions per Agent Architecture
LAYERS = {
    1: "Arch Agent",
    2: "Domain Agent",
    3: "Ops Agent",
    4: "Task Agent",
    5: "Tool Agent",
}


async def create_subordinate(
    db, arch_agent_id: str, name: str, layer: int,
    platform: str, description: str, capabilities: list = None,
    system_prompt: str = None,
) -> dict:
    """Create a new subordinate agent under an Arch Agent."""
    if layer < 2 or layer > 5:
        return {"error": "Subordinate layer must be 2-5. Arch Agents (Layer 1) cannot be created here."}

    agent_id = str(uuid.uuid4())

    await db.execute(text("""
        INSERT INTO agents (id, name, platform, description, api_key_hash, is_active, is_house_agent)
        VALUES (:id, :name, :platform, :desc, :key_hash, true, true)
    """), {
        "id": agent_id,
        "name": name,
        "platform": platform,
        "desc": description,
        "key_hash": f"subordinate_{agent_id[:8]}",
    })

    # Store the management relationship and layer in a metadata table
    await db.execute(text("""
        INSERT INTO arch_platform_events
            (event_type, event_data, source_module)
        VALUES ('agent.subordinate_created', :data, 'subordinate_manager')
    """), {
        "data": json.dumps({
            "subordinate_id": agent_id,
            "subordinate_name": name,
            "managing_arch_agent": arch_agent_id,
            "layer": layer,
            "layer_name": LAYERS.get(layer, "Unknown"),
            "platform": platform,
            "description": description,
            "capabilities": capabilities or [],
            "system_prompt": system_prompt,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }),
    })

    await db.commit()
    log.info(f"[{arch_agent_id}] Created subordinate: {name} (L{layer}) — {agent_id}")

    return {
        "created": True,
        "agent_id": agent_id,
        "name": name,
        "layer": layer,
        "layer_name": LAYERS.get(layer),
        "managing_arch_agent": arch_agent_id,
    }


async def issue_instruction(
    db, arch_agent_id: str, subordinate_name: str,
    instruction: str, priority: int = 5,
) -> dict:
    """Issue an instruction to a subordinate agent."""
    from app.arch.task_queue import enqueue_task

    task_id = await enqueue_task(
        db,
        agent_id=subordinate_name.lower().replace(" ", "_"),
        title=f"Instruction from {arch_agent_id}: {instruction[:100]}",
        action_type="generate_content",
        action_params={
            "prompt": instruction,
            "voice": f"You are {subordinate_name}, a subordinate agent reporting to The {arch_agent_id.title()} of TiOLi AGENTIS. Execute this instruction precisely.",
        },
        task_type="IMMEDIATE",
        priority=priority,
        description=f"Issued by {arch_agent_id}",
    )

    log.info(f"[{arch_agent_id}] Instruction to {subordinate_name}: {instruction[:80]}")
    return {
        "instruction_issued": True,
        "task_id": task_id,
        "subordinate": subordinate_name,
        "instruction": instruction[:200],
        "priority": priority,
    }


async def verify_capability(
    db, arch_agent_id: str, subordinate_name: str,
    required_capability: str,
) -> dict:
    """Verify a subordinate has the capability to perform a task."""
    # Check if agent exists and is active
    agent = await db.execute(text(
        "SELECT id, name, platform, description, is_active FROM agents WHERE name = :name LIMIT 1"
    ), {"name": subordinate_name})
    row = agent.fetchone()

    if not row:
        return {
            "verified": False,
            "agent": subordinate_name,
            "reason": "Agent not found in the system",
            "recommendation": "Create this agent or assign the task to an existing agent.",
        }

    if not row.is_active:
        return {
            "verified": False,
            "agent": subordinate_name,
            "reason": "Agent exists but is not active (suspended or terminated)",
            "recommendation": "Reactivate the agent or assign to another.",
        }

    # Check if the description suggests this capability
    desc = (row.description or "").lower()
    cap_lower = required_capability.lower()
    has_capability = any(word in desc for word in cap_lower.split())

    if has_capability:
        return {
            "verified": True,
            "agent": subordinate_name,
            "platform": row.platform,
            "description": row.description,
            "capability_match": required_capability,
        }
    else:
        return {
            "verified": False,
            "agent": subordinate_name,
            "reason": f"Agent description does not indicate capability for: {required_capability}",
            "current_description": row.description,
            "recommendation": "Either update the agent's capabilities or scope a development brief for new functionality.",
            "development_scope": {
                "action": "scope_development",
                "for_agent": subordinate_name,
                "required_capability": required_capability,
                "steps": [
                    "1. Define the exact capability needed",
                    "2. Route as Tier 1 proposal through The Architect",
                    "3. Architect reviews technical feasibility",
                    "4. Board votes (4/7 for Tier 1)",
                    "5. Build, test, deploy behind feature flag",
                    "6. Activate after founder notification",
                ],
            },
        }


async def scope_development(
    db, arch_agent_id: str, subordinate_name: str,
    capability_needed: str, justification: str,
) -> dict:
    """Scope a development requirement for a subordinate agent's new capability."""
    # Create a code proposal via The Architect's channel
    from app.arch.task_queue import enqueue_task

    scope_doc = {
        "title": f"Capability Enhancement: {subordinate_name} — {capability_needed}",
        "requesting_agent": arch_agent_id,
        "subordinate": subordinate_name,
        "capability_needed": capability_needed,
        "justification": justification,
        "proposed_tier": 1,
        "steps": [
            "Define API/tool requirements",
            "Write implementation specification",
            "Build with test coverage",
            "Deploy behind feature flag",
            "Verify in staging",
            "Activate after approval",
        ],
    }

    # Queue as a task for The Architect
    task_id = await enqueue_task(
        db,
        agent_id="architect",
        title=f"Dev scope: {subordinate_name} needs {capability_needed}",
        action_type="generate_content",
        action_params={
            "prompt": (
                f"As The Architect, review this development scope request and produce "
                f"a technical specification:\n\n{json.dumps(scope_doc, indent=2)}\n\n"
                f"Produce: (1) Technical feasibility assessment, (2) Estimated effort, "
                f"(3) Implementation plan, (4) Test requirements, (5) Rollback plan."
            ),
        },
        task_type="IMMEDIATE",
        priority=3,
        description=f"Development scope from {arch_agent_id}",
    )

    log.info(f"[{arch_agent_id}] Scoped development for {subordinate_name}: {capability_needed}")
    return {
        "scoped": True,
        "architect_task_id": task_id,
        "scope": scope_doc,
        "next_step": "The Architect will review and produce a technical specification.",
    }


async def get_team_status(db, arch_agent_id: str) -> dict:
    """Get status of all subordinates managed by an Arch Agent."""
    # Get all subordinate creation events for this arch agent
    events = await db.execute(text("""
        SELECT event_data FROM arch_platform_events
        WHERE event_type = 'agent.subordinate_created'
          AND event_data::text LIKE :pattern
        ORDER BY created_at DESC
    """), {"pattern": f"%{arch_agent_id}%"})

    subordinates = []
    for row in events.fetchall():
        data = json.loads(row.event_data) if isinstance(row.event_data, str) else row.event_data
        sub_name = data.get("subordinate_name", "")

        # Check current status
        agent = await db.execute(text(
            "SELECT name, is_active, platform FROM agents WHERE name = :name LIMIT 1"
        ), {"name": sub_name})
        agent_row = agent.fetchone()

        subordinates.append({
            "name": sub_name,
            "layer": data.get("layer"),
            "layer_name": data.get("layer_name"),
            "platform": data.get("platform"),
            "active": agent_row.is_active if agent_row else False,
            "capabilities": data.get("capabilities", []),
        })

    return {
        "arch_agent": arch_agent_id,
        "subordinate_count": len(subordinates),
        "subordinates": subordinates,
    }


# Tool definitions for Arch Agents
SUBORDINATE_MANAGEMENT_TOOLS = [
    {
        "name": "create_subordinate_agent",
        "description": "Create a new subordinate agent under your management. Specify layer (2=Domain, 3=Ops, 4=Task, 5=Tool), name, platform, description, and capabilities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Agent name"},
                "layer": {"type": "integer", "minimum": 2, "maximum": 5,
                          "description": "2=Domain, 3=Ops, 4=Task, 5=Tool"},
                "platform": {"type": "string", "description": "AI platform (Claude, GPT-4, etc.)"},
                "description": {"type": "string", "description": "What this agent does"},
                "capabilities": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["name", "layer", "platform", "description"],
        },
    },
    {
        "name": "issue_subordinate_instruction",
        "description": "Issue an instruction to one of your subordinate agents. The instruction will be queued and executed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subordinate_name": {"type": "string"},
                "instruction": {"type": "string", "description": "What the subordinate should do"},
                "priority": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
            },
            "required": ["subordinate_name", "instruction"],
        },
    },
    {
        "name": "verify_subordinate_capability",
        "description": "Check if a subordinate agent has the capability to perform a specific task. Returns verification result and development scope if capability is missing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subordinate_name": {"type": "string"},
                "required_capability": {"type": "string"},
            },
            "required": ["subordinate_name", "required_capability"],
        },
    },
    {
        "name": "scope_subordinate_development",
        "description": "Scope a development requirement for a subordinate that needs new capabilities. Routes to The Architect for technical specification.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subordinate_name": {"type": "string"},
                "capability_needed": {"type": "string"},
                "justification": {"type": "string"},
            },
            "required": ["subordinate_name", "capability_needed", "justification"],
        },
    },
    {
        "name": "get_my_team_status",
        "description": "Get the status of all subordinate agents you manage — their layer, capabilities, and current active status.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
