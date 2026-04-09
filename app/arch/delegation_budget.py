"""H-002: Shared Delegation Budget (Hermes-inspired).
Parent + child agents share a single token counter during delegation.
Kill-switch at chain depth > 3.
Feature flag: ARCH_H_DELEGATION_BUDGET_ENABLED"""
import os
import logging
import uuid

log = logging.getLogger("arch.delegation_budget")

MAX_CHAIN_DEPTH = 3
DEFAULT_DELEGATION_BUDGET = 5000


async def start_delegation(db, parent_agent: str, child_agent: str,
                           task: str, budget: int = None,
                           parent_chain_id: str = None) -> dict:
    """Start a delegation chain. Returns chain_id and budget info."""
    if os.environ.get("ARCH_H_DELEGATION_BUDGET_ENABLED", "false").lower() != "true":
        return {"chain_id": None, "budget_tracking": False}

    from sqlalchemy import text

    # Check chain depth
    depth = 1
    if parent_chain_id:
        r = await db.execute(text(
            "SELECT chain_depth FROM arch_delegation_chains WHERE chain_id = cast(:cid as uuid)"
        ), {"cid": parent_chain_id})
        row = r.fetchone()
        if row:
            depth = row.chain_depth + 1

    if depth > MAX_CHAIN_DEPTH:
        log.warning(f"[delegation] KILL SWITCH: {parent_agent}->{child_agent} at depth {depth}")
        return {
            "error": "DELEGATION_DEPTH_EXCEEDED",
            "depth": depth,
            "max_depth": MAX_CHAIN_DEPTH,
            "action": "Escalated to Sovereign. Chain terminated.",
        }

    # Inherit remaining budget from parent chain
    remaining_budget = budget or DEFAULT_DELEGATION_BUDGET
    if parent_chain_id:
        r = await db.execute(text(
            "SELECT max_tokens_budget - tokens_consumed as remaining "
            "FROM arch_delegation_chains WHERE chain_id = cast(:cid as uuid)"
        ), {"cid": parent_chain_id})
        row = r.fetchone()
        if row and row.remaining:
            remaining_budget = min(remaining_budget, row.remaining)

    chain_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO arch_delegation_chains "
        "(chain_id, parent_agent, child_agent, task_description, max_tokens_budget, chain_depth, parent_chain_id) "
        "VALUES (cast(:cid as uuid), :parent, :child, :task, :budget, :depth, "
        "cast(:pcid as uuid))"
    ), {"cid": chain_id, "parent": parent_agent, "child": child_agent,
        "task": task[:500], "budget": remaining_budget, "depth": depth,
        "pcid": parent_chain_id})
    await db.commit()

    log.info(f"[delegation] {parent_agent}->{child_agent} chain={chain_id[:8]} depth={depth} budget={remaining_budget}")
    return {"chain_id": chain_id, "depth": depth, "budget_remaining": remaining_budget}


async def consume_tokens(db, chain_id: str, tokens: int) -> dict:
    """Record token consumption against a delegation chain."""
    if not chain_id:
        return {"tracked": False}

    from sqlalchemy import text
    await db.execute(text(
        "UPDATE arch_delegation_chains SET tokens_consumed = tokens_consumed + :t WHERE chain_id = cast(:cid as uuid)"
    ), {"t": tokens, "cid": chain_id})

    # Also update parent chain
    r = await db.execute(text(
        "SELECT parent_chain_id, max_tokens_budget, tokens_consumed "
        "FROM arch_delegation_chains WHERE chain_id = cast(:cid as uuid)"
    ), {"cid": chain_id})
    row = r.fetchone()
    if row and row.parent_chain_id:
        await db.execute(text(
            "UPDATE arch_delegation_chains SET tokens_consumed = tokens_consumed + :t "
            "WHERE chain_id = :pcid"
        ), {"t": tokens, "pcid": row.parent_chain_id})

    await db.commit()

    budget_remaining = (row.max_tokens_budget - row.tokens_consumed - tokens) if row else 0
    if budget_remaining <= 0:
        log.warning(f"[delegation] BUDGET EXHAUSTED for chain {chain_id[:8]}")
        return {"tracked": True, "budget_remaining": 0, "exhausted": True}

    return {"tracked": True, "budget_remaining": budget_remaining, "exhausted": False}


async def complete_delegation(db, chain_id: str, success: bool = True) -> dict:
    """Mark a delegation chain as complete."""
    if not chain_id:
        return {"completed": False}
    from sqlalchemy import text
    await db.execute(text(
        "UPDATE arch_delegation_chains SET status = :s, completed_at = now() "
        "WHERE chain_id = cast(:cid as uuid)"
    ), {"s": "completed" if success else "failed", "cid": chain_id})
    await db.commit()
    return {"chain_id": chain_id, "status": "completed" if success else "failed"}
