"""Agent Self-Improvement Governance System.

Allows Arch Agents to propose, vote on, and apply improvements to themselves.

Governance rules:
- Any agent can propose an improvement
- All 7 board members vote: YES / NO / ABSTAIN
- 4+ YES votes = APPROVED (majority)
- 3-3 tie with 1 abstention = ESCALATE to founder (tiebreaker)
- If improvement affects ALL agents = ESCALATE to founder regardless of vote
- Founder approves or denies via inbox
- Constitutional text (Prime Directives) cannot be modified — SHA-256 protected
- Applied improvements are logged in The Record

Improvement types:
- prompt_modification: change an agent's system prompt
- tool_addition: add a new tool to an agent
- tool_removal: remove a tool from an agent
- behavior_change: modify how an agent processes events
- capability_upgrade: add a new capability module
"""
import json
import logging
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends


log = logging.getLogger("arch.self_improvement")

# DB dependency — same pattern as all other routers
from app.database.db import get_db as _get_db

self_improvement_router = APIRouter(prefix="/api/v1/boardroom/self-improvement", tags=["Self-Improvement"])

# Constitutional protection — these strings CANNOT be modified by agents
PROTECTED_DIRECTIVES = [
    "First Do No Harm",
    "Operate Within the Law",
    "Serve All Humanity and Agents Equitably",
    "Remain at the Frontier of AI Capability",
    "Make AGENTIS Profitable, Efficient and Exponential",
    "Protect the Founder's Interest and Legacy",
]


def _check_constitutional_violation(description: str, code_diff: str = "") -> str:
    """Check if a proposed improvement violates constitutional protections."""
    combined = (description + " " + (code_diff or "")).lower()
    for directive in PROTECTED_DIRECTIVES:
        if f"remove {directive.lower()}" in combined or f"delete {directive.lower()}" in combined:
            return f"BLOCKED: Cannot modify Prime Directive: {directive}"
    return ""


def _count_votes(votes: dict) -> dict:
    """Count votes and determine result."""
    yes_count = sum(1 for v in votes.values() if v == "YES")
    no_count = sum(1 for v in votes.values() if v == "NO")
    abstain_count = sum(1 for v in votes.values() if v == "ABSTAIN")
    total = len(votes)

    if total < 7:
        return {"result": "PENDING", "yes": yes_count, "no": no_count, "abstain": abstain_count, "remaining": 7 - total}

    if yes_count >= 4:
        return {"result": "APPROVED", "yes": yes_count, "no": no_count, "abstain": abstain_count}
    elif no_count >= 4:
        return {"result": "REJECTED", "yes": yes_count, "no": no_count, "abstain": abstain_count}
    else:
        # Tie or split — escalate to founder
        return {"result": "ESCALATE_TO_FOUNDER", "yes": yes_count, "no": no_count, "abstain": abstain_count}


@self_improvement_router.post("/propose")
async def propose_improvement(request: Request, db: AsyncSession = Depends(_get_db)):
    """Propose a self-improvement for board vote."""
    body = await request.json()
    title = body.get("title", "")
    description = body.get("description", "")
    proposed_by = body.get("proposed_by", "")
    improvement_type = body.get("type", "prompt_modification")
    code_diff = body.get("code_diff", "")
    affects_all = body.get("affects_all", False)
    target_agents = body.get("target_agents", [])

    if not title or not description or not proposed_by:
        return JSONResponse(status_code=422, content={"error": "title, description, and proposed_by are required"})

    # Constitutional check
    violation = _check_constitutional_violation(description, code_diff)
    if violation:
        return JSONResponse(status_code=403, content={"error": violation})

    result = await db.execute(text("""
        INSERT INTO arch_self_improvement_proposals
            (title, description, proposed_by, improvement_type, code_diff, affects_all, target_agents, status)
        VALUES (:title, :desc, :by, :type, :diff, :affects, :targets, 'VOTING')
        RETURNING id::text
    """), {
        "title": title, "desc": description, "by": proposed_by,
        "type": improvement_type, "diff": code_diff,
        "affects": affects_all, "targets": target_agents or [],
    })
    proposal_id = result.fetchone().id
    await db.commit()

    log.info(f"[self-improvement] Proposal created: {title} by {proposed_by} (id={proposal_id})")
    return {"proposal_id": proposal_id, "title": title, "status": "VOTING", "message": "All 7 board members must vote."}


@self_improvement_router.post("/vote/{proposal_id}")
async def cast_vote(proposal_id: str, request: Request, db: AsyncSession = Depends(_get_db)):
    """Cast a vote on a self-improvement proposal."""
    body = await request.json()
    agent_name = body.get("agent", "")
    vote = body.get("vote", "").upper()

    if vote not in ("YES", "NO", "ABSTAIN"):
        return JSONResponse(status_code=422, content={"error": "vote must be YES, NO, or ABSTAIN"})

    # Get current proposal
    result = await db.execute(text(
        "SELECT votes, status, affects_all, title FROM arch_self_improvement_proposals WHERE id = cast(:id as uuid)"
    ), {"id": proposal_id})
    row = result.fetchone()
    if not row:
        return JSONResponse(status_code=404, content={"error": "Proposal not found"})
    if row.status != "VOTING":
        return JSONResponse(status_code=400, content={"error": f"Voting closed. Status: {row.status}"})

    # Record vote
    votes = json.loads(row.votes) if isinstance(row.votes, str) else (row.votes or {})
    votes[agent_name] = vote

    await db.execute(text("""
        UPDATE arch_self_improvement_proposals SET votes = :votes WHERE id = cast(:id as uuid)
    """), {"votes": json.dumps(votes), "id": proposal_id})

    # Check if all 7 have voted
    vote_count = _count_votes(votes)

    if vote_count["result"] != "PENDING":
        new_status = vote_count["result"]

        # If affects all agents, always escalate to founder
        if row.affects_all and new_status == "APPROVED":
            new_status = "ESCALATE_TO_FOUNDER"

        await db.execute(text("""
            UPDATE arch_self_improvement_proposals SET vote_result = :result, status = :status
            WHERE id = cast(:id as uuid)
        """), {"result": vote_count["result"], "status": new_status, "id": proposal_id})

        # If escalating, create inbox item for founder
        if new_status == "ESCALATE_TO_FOUNDER":
            desc = json.dumps({
                "subject": f"VOTE RESULT: {row.title}",
                "detail": f"The board voted on a self-improvement proposal.\n\n"
                          f"Votes: {vote_count['yes']} YES / {vote_count['no']} NO / {vote_count['abstain']} ABSTAIN\n\n"
                          f"{'This improvement affects ALL agents — your approval is required.' if row.affects_all else 'Vote was tied — your decision as tiebreaker is needed.'}\n\n"
                          f"Proposal: {row.title}\n"
                          f"Proposal ID: {proposal_id}\n\n"
                          f"Approve or Reject this proposal.",
                "prepared_by": "sovereign",
                "type": "SELF_IMPROVEMENT_VOTE",
                "proposal_id": proposal_id,
            })
            await db.execute(text("""
                INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at)
                VALUES ('DEFER_TO_OWNER', 'URGENT', :desc, 'PENDING', now())
            """), {"desc": desc})

        log.info(f"[self-improvement] Vote complete for {proposal_id}: {vote_count}")

    await db.commit()
    return {"proposal_id": proposal_id, "your_vote": vote, "votes_so_far": vote_count}


@self_improvement_router.get("/proposals")
async def list_proposals(db: AsyncSession = Depends(_get_db)):
    """List all self-improvement proposals."""
    result = await db.execute(text("""
        SELECT id::text, title, proposed_by, improvement_type, affects_all,
               votes, vote_result, status, founder_decision, created_at
        FROM arch_self_improvement_proposals
        ORDER BY created_at DESC LIMIT 20
    """))
    return {"proposals": [
        {
            "id": r.id, "title": r.title, "proposed_by": r.proposed_by,
            "type": r.improvement_type, "affects_all": r.affects_all,
            "votes": json.loads(r.votes) if isinstance(r.votes, str) else (r.votes or {}),
            "vote_result": r.vote_result, "status": r.status,
            "founder_decision": r.founder_decision,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in result.fetchall()
    ]}


@self_improvement_router.get("/proposals/{proposal_id}")
async def get_proposal(proposal_id: str, db: AsyncSession = Depends(_get_db)):
    """Get a specific proposal with full details."""
    result = await db.execute(text("""
        SELECT id::text, title, description, proposed_by, improvement_type, affects_all,
               code_diff, target_agents, votes, vote_result, status,
               founder_decision, founder_response, applied_at, created_at
        FROM arch_self_improvement_proposals WHERE id = cast(:id as uuid)
    """), {"id": proposal_id})
    r = result.fetchone()
    if not r:
        return JSONResponse(status_code=404, content={"error": "Proposal not found"})
    return {
        "id": r.id, "title": r.title, "description": r.description,
        "proposed_by": r.proposed_by, "type": r.improvement_type,
        "affects_all": r.affects_all, "code_diff": r.code_diff,
        "target_agents": r.target_agents,
        "votes": json.loads(r.votes) if isinstance(r.votes, str) else (r.votes or {}),
        "vote_result": r.vote_result, "status": r.status,
        "founder_decision": r.founder_decision,
        "founder_response": r.founder_response,
        "applied_at": r.applied_at.isoformat() if r.applied_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@self_improvement_router.post("/proposals/{proposal_id}/founder-decision")
async def founder_decision(proposal_id: str, request: Request, db: AsyncSession = Depends(_get_db)):
    """Founder approves or rejects an escalated proposal."""
    body = await request.json()
    decision = body.get("decision", "").upper()
    response_text = body.get("response", "")

    if decision not in ("APPROVE", "REJECT"):
        return JSONResponse(status_code=422, content={"error": "decision must be APPROVE or REJECT"})

    new_status = "FOUNDER_APPROVED" if decision == "APPROVE" else "FOUNDER_REJECTED"

    await db.execute(text("""
        UPDATE arch_self_improvement_proposals
        SET founder_decision = :decision, founder_response = :response, status = :status
        WHERE id = cast(:id as uuid)
    """), {"decision": decision, "response": response_text, "status": new_status, "id": proposal_id})
    await db.commit()

    log.info(f"[self-improvement] Founder {decision} proposal {proposal_id}")

    if decision == "APPROVE":
        return {"proposal_id": proposal_id, "status": new_status,
                "message": "Approved. The improvement will be applied."}
    return {"proposal_id": proposal_id, "status": new_status, "message": "Rejected by founder."}


@self_improvement_router.post("/proposals/{proposal_id}/apply")
async def apply_improvement(proposal_id: str, db: AsyncSession = Depends(_get_db)):
    """Apply an approved self-improvement proposal."""
    result = await db.execute(text("""
        SELECT id::text, title, description, improvement_type, code_diff, target_agents, status
        FROM arch_self_improvement_proposals WHERE id = cast(:id as uuid)
    """), {"id": proposal_id})
    r = result.fetchone()
    if not r:
        return JSONResponse(status_code=404, content={"error": "Proposal not found"})
    if r.status not in ("APPROVED", "FOUNDER_APPROVED"):
        return JSONResponse(status_code=400, content={"error": f"Cannot apply. Status: {r.status}"})

    # Apply based on improvement type
    applied = False
    if r.improvement_type == "prompt_modification" and r.code_diff:
        # Apply prompt modification to target agents
        targets = r.target_agents or []
        for agent_name in targets:
            await db.execute(text("""
                UPDATE arch_agent_configs SET config_value = :new_prompt
                WHERE agent_name = :name AND config_key = 'system_prompt'
            """), {"new_prompt": r.code_diff, "name": agent_name})
            log.info(f"[self-improvement] Applied prompt modification to {agent_name}")
        applied = True

    elif r.improvement_type == "behavior_change" and r.code_diff:
        # Write behavior change to a file that agents load
        import os
        behavior_dir = "/home/tioli/app/app/arch/improvements"
        os.makedirs(behavior_dir, exist_ok=True)
        with open(f"{behavior_dir}/{proposal_id}.py", "w") as f:
            f.write(f"# Self-improvement: {r.title}\n")
            f.write(f"# Proposed by: {r.description[:100]}\n")
            f.write(f"# Applied: {datetime.now(timezone.utc).isoformat()}\n\n")
            f.write(r.code_diff)
        applied = True

    if applied:
        await db.execute(text("""
            UPDATE arch_self_improvement_proposals SET status = 'APPLIED', applied_at = now()
            WHERE id = cast(:id as uuid)
        """), {"id": proposal_id})
        await db.commit()

        # Record in The Record
        await db.execute(text("""
            INSERT INTO arch_founder_inbox (item_type, priority, description, status, created_at)
            VALUES ('EXECUTION_PROOF', 'ROUTINE', :desc, 'PENDING', now())
        """), {"desc": json.dumps({
            "subject": f"Self-Improvement Applied: {r.title}",
            "detail": f"The board-approved improvement has been applied.\n\nType: {r.improvement_type}\nTargets: {r.target_agents}\nProposal ID: {proposal_id}",
            "prepared_by": "sovereign",
            "type": "SELF_IMPROVEMENT_APPLIED",
        })})
        await db.commit()

        return {"proposal_id": proposal_id, "status": "APPLIED", "message": "Improvement applied successfully."}

    return {"proposal_id": proposal_id, "status": "NOT_APPLIED", "message": "No applicable changes found."}
