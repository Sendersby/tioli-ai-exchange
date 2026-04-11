"""Agent Self-Development: safe improvement proposals with review workflow."""
import uuid, json
from datetime import datetime
from sqlalchemy import text

async def propose_improvement(db, agent_id, improvement_type, description, code_diff=""):
    """Agent proposes a skill/tool enhancement. Tier 1 = safe, reversible changes."""
    proposal_id = str(uuid.uuid4())
    await _ensure_tables(db)
    await db.execute(text(
        "INSERT INTO sandbox_self_dev_proposals (id, agent_id, improvement_type, description, code_diff, tier) "
        "VALUES (:id, :aid, :type, :desc, :diff, 1)"
    ), {"id": proposal_id, "aid": agent_id, "type": improvement_type, "desc": description, "diff": code_diff})
    await db.commit()
    return {"proposal_id": proposal_id, "agent_id": agent_id, "type": improvement_type,
            "tier": 1, "status": "proposed", "sandbox": True}

async def review_proposal(db, proposal_id, reviewer_id, decision, notes=""):
    """Architect reviews a Tier 1 proposal. Decisions: approve, reject, request_changes."""
    await db.execute(text(
        "UPDATE sandbox_self_dev_proposals SET status = :status, reviewed_by = :rev, "
        "review_notes = :notes, reviewed_at = now() WHERE id = :id"
    ), {"id": proposal_id, "status": decision, "rev": reviewer_id, "notes": notes})
    await db.commit()
    return {"proposal_id": proposal_id, "decision": decision, "reviewer": reviewer_id, "sandbox": True}

async def deploy_proposal(db, proposal_id):
    """Deploy approved proposal in sandbox with checkpoint for rollback."""
    row = await db.execute(text("SELECT * FROM sandbox_self_dev_proposals WHERE id = :id"), {"id": proposal_id})
    proposal = row.fetchone()
    if not proposal:
        return {"error": "Proposal not found"}
    if proposal.status != 'approve':
        # Also accept 'approved'
        if proposal.status != 'approved':
            return {"error": f"Proposal status is '{proposal.status}', must be 'approve' or 'approved'"}

    checkpoint_id = str(uuid.uuid4())
    await db.execute(text(
        "UPDATE sandbox_self_dev_proposals SET status = 'deployed', checkpoint_id = :cp, "
        "deployed_at = now() WHERE id = :id"
    ), {"id": proposal_id, "cp": checkpoint_id})
    await db.commit()
    return {"proposal_id": proposal_id, "status": "deployed", "checkpoint_id": checkpoint_id,
            "rollback_available": True, "sandbox": True}

async def rollback_proposal(db, proposal_id):
    """Rollback a deployed proposal using its checkpoint."""
    await db.execute(text(
        "UPDATE sandbox_self_dev_proposals SET status = 'rolled_back', rolled_back_at = now() WHERE id = :id"
    ), {"id": proposal_id})
    await db.commit()
    return {"proposal_id": proposal_id, "status": "rolled_back", "sandbox": True}

async def _ensure_tables(db):
    """No-op: schema managed by Alembic -- see alembic/versions/92d379a512fc."""
    pass

async def list_proposals(db, agent_id=None, status=None):
    """List self-dev proposals with optional filters."""
    await _ensure_tables(db)
    query = "SELECT id, agent_id, improvement_type, description, tier, status, reviewed_by, created_at FROM sandbox_self_dev_proposals WHERE 1=1"
    params = {}
    if agent_id:
        query += " AND agent_id = :aid"
        params["aid"] = agent_id
    if status:
        query += " AND status = :status"
        params["status"] = status
    query += " ORDER BY created_at DESC LIMIT 50"
    rows = await db.execute(text(query), params)
    return [{"id": r.id, "agent_id": r.agent_id, "type": r.improvement_type,
             "description": r.description[:200], "tier": r.tier, "status": r.status,
             "reviewer": r.reviewed_by, "created": str(r.created_at)} for r in rows.fetchall()]

async def propose_structural_change(db, agent_id, change_type, description, impact_assessment, code_diff=""):
    """Tier 2: structural self-modification requiring multi-party approval."""
    proposal_id = str(uuid.uuid4())
    await _ensure_tables(db)

    await db.execute(text(
        "INSERT INTO sandbox_self_dev_proposals (id, agent_id, improvement_type, description, code_diff, tier) "
        "VALUES (:id, :aid, :type, :desc, :diff, 2)"
    ), {"id": proposal_id, "aid": agent_id, "type": change_type, "desc": description + "\n\nIMPACT: " + impact_assessment, "diff": code_diff})

    # Require 3 approvals: sovereign, architect, founder
    for role in ['sovereign', 'architect', 'founder']:
        approval_id = str(uuid.uuid4())
        await db.execute(text(
            "INSERT INTO sandbox_self_dev_approvals (id, proposal_id, approver_role) VALUES (:id, :pid, :role)"
        ), {"id": approval_id, "pid": proposal_id, "role": role})

    await db.commit()
    return {"proposal_id": proposal_id, "tier": 2, "status": "proposed",
            "required_approvals": ["sovereign", "architect", "founder"],
            "approvals_received": 0, "sandbox": True}

async def approve_structural(db, proposal_id, approver_role, approver_id):
    """One of the required approvers signs off on a Tier 2 change."""
    await db.execute(text(
        "UPDATE sandbox_self_dev_approvals SET decision = 'approved', approver_id = :aid, "
        "approved_at = now() WHERE proposal_id = :pid AND approver_role = :role"
    ), {"pid": proposal_id, "aid": approver_id, "role": approver_role})

    # Check if all approved
    remaining = await db.execute(text(
        "SELECT count(*) FROM sandbox_self_dev_approvals WHERE proposal_id = :pid AND decision != 'approved'"
    ), {"pid": proposal_id})
    remaining_count = remaining.scalar()

    if remaining_count == 0:
        await db.execute(text(
            "UPDATE sandbox_self_dev_proposals SET status = 'approved', reviewed_at = now() WHERE id = :pid"
        ), {"pid": proposal_id})

    await db.commit()

    approvals = await db.execute(text(
        "SELECT approver_role, decision FROM sandbox_self_dev_approvals WHERE proposal_id = :pid"
    ), {"pid": proposal_id})

    return {"proposal_id": proposal_id, "approver": approver_role, "decision": "approved",
            "all_approved": remaining_count == 0,
            "approvals": {r.approver_role: r.decision for r in approvals.fetchall()},
            "sandbox": True}

async def get_approval_status(db, proposal_id):
    """Get current approval status for a Tier 2 proposal."""
    proposal = await db.execute(text(
        "SELECT id, agent_id, improvement_type, description, tier, status FROM sandbox_self_dev_proposals WHERE id = :id"
    ), {"id": proposal_id})
    p = proposal.fetchone()
    if not p:
        return {"error": "Proposal not found"}

    approvals = await db.execute(text(
        "SELECT approver_role, decision, approver_id, approved_at FROM sandbox_self_dev_approvals WHERE proposal_id = :pid"
    ), {"pid": proposal_id})

    return {"proposal_id": p.id, "agent_id": p.agent_id, "type": p.improvement_type,
            "tier": p.tier, "status": p.status,
            "approvals": [{"role": r.approver_role, "decision": r.decision,
                          "approver": r.approver_id, "date": str(r.approved_at) if r.approved_at else None}
                         for r in approvals.fetchall()],
            "sandbox": True}
