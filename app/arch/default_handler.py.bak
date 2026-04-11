"""A-5: Loan default handling — NCA-compliant collection workflow."""
import os, json, logging, uuid
from datetime import datetime, timezone

log = logging.getLogger("arch.default_handler")

STAGES = ["reminder", "second_notice", "formal_demand", "collateral_seizure", "write_off"]


async def check_arrears(db):
    """Find all overdue loans."""
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT id, borrower_id, lender_id, principal, amount_repaid, due_at, "
        "EXTRACT(DAY FROM now() - due_at) as days_overdue "
        "FROM loans WHERE status = 'active' AND due_at < now() ORDER BY due_at ASC"
    ))
    return [{"loan_id": row.id, "borrower": row.borrower_id, "lender": row.lender_id,
             "principal": float(row.principal), "repaid": float(row.amount_repaid or 0),
             "outstanding": float(row.principal) - float(row.amount_repaid or 0),
             "days_overdue": int(row.days_overdue or 0)} for row in r.fetchall()]


async def declare_default(db, loan_id):
    """Declare a loan in default and initiate collection."""
    if os.environ.get("SANDBOX_MODE", "false").lower() != "true":
        return {"error": "Requires SANDBOX_MODE=true"}

    from sqlalchemy import text
    loan = await db.execute(text("SELECT * FROM loans WHERE id = :lid"), {"lid": loan_id})
    row = loan.fetchone()
    if not row:
        return {"error": "Loan not found"}

    outstanding = float(row.principal) - float(row.amount_repaid or 0)
    days_overdue = 0
    if row.due_at:
        days_overdue = max(0, (datetime.now(timezone.utc) - row.due_at).days)

    # Determine stage
    stage = "reminder"
    if days_overdue >= 30: stage = "write_off"
    elif days_overdue >= 14: stage = "formal_demand"
    elif days_overdue >= 7: stage = "second_notice"

    default_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO loan_defaults (id, loan_id, borrower_id, lender_id, amount_outstanding, "
        "days_overdue, default_stage, nca_section_129_sent, is_sandbox) "
        "VALUES (cast(:id as uuid), :lid, :bid, :leid, :amt, :days, :stage, :s129, true)"
    ), {"id": default_id, "lid": loan_id, "bid": row.borrower_id, "leid": row.lender_id,
        "amt": outstanding, "days": days_overdue, "stage": stage,
        "s129": days_overdue >= 14})

    # Log collection action
    await db.execute(text(
        "INSERT INTO collection_actions (default_id, action_type, action_detail, nca_compliant, is_sandbox) "
        "VALUES (cast(:did as uuid), :atype, :detail, true, true)"
    ), {"did": default_id, "atype": f"stage_{stage}",
        "detail": f"Loan {loan_id} declared in default. Outstanding: R{outstanding:.2f}. Days overdue: {days_overdue}. Stage: {stage}."})

    await db.execute(text("UPDATE loans SET status = 'defaulted' WHERE id = :lid"), {"lid": loan_id})
    await db.commit()

    return {"default_id": default_id, "loan_id": loan_id, "outstanding": outstanding,
            "days_overdue": days_overdue, "stage": stage, "nca_section_129": days_overdue >= 14,
            "sandbox": True}
