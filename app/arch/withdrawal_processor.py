"""Fiat Withdrawal Processing: queue, compliance check, approval, payout simulation."""
import uuid, json
from datetime import datetime
from sqlalchemy import text

async def request_withdrawal(db, customer_id, amount_zar, bank_account="", bank_name=""):
    """Submit a fiat withdrawal request to the processing queue."""
    withdrawal_id = str(uuid.uuid4())
    
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS sandbox_withdrawals (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            amount_zar NUMERIC(18,2) NOT NULL,
            bank_account TEXT,
            bank_name TEXT,
            status TEXT DEFAULT 'pending_compliance',
            compliance_check TEXT,
            compliance_passed BOOLEAN,
            approved_by TEXT,
            approved_at TIMESTAMP,
            payout_ref TEXT,
            payout_at TIMESTAMP,
            rejection_reason TEXT,
            created_at TIMESTAMP DEFAULT now()
        )
    """))
    
    await db.execute(text(
        "INSERT INTO sandbox_withdrawals (id, customer_id, amount_zar, bank_account, bank_name) "
        "VALUES (:id, :cid, :amt, :bank, :bname)"
    ), {"id": withdrawal_id, "cid": customer_id, "amt": amount_zar, "bank": bank_account, "bname": bank_name})
    await db.commit()
    
    return {"withdrawal_id": withdrawal_id, "amount_zar": amount_zar, "status": "pending_compliance",
            "queue_position": 1, "estimated_processing": "1-3 business days",
            "next_step": "compliance_check", "sandbox": True}

async def compliance_check(db, withdrawal_id):
    """Run compliance checks on a withdrawal request."""
    row = await db.execute(text("SELECT * FROM sandbox_withdrawals WHERE id = :id"), {"id": withdrawal_id})
    w = row.fetchone()
    if not w:
        return {"error": "Withdrawal not found"}
    
    checks = {
        "kyc_verified": True,
        "daily_limit_ok": float(w.amount_zar) <= 50000,
        "monthly_limit_ok": float(w.amount_zar) <= 500000,
        "sda_annual_ok": float(w.amount_zar) <= 1000000,
        "sanctions_clear": True,
        "source_of_funds": True
    }
    all_passed = all(checks.values())
    
    await db.execute(text(
        "UPDATE sandbox_withdrawals SET compliance_check = :checks, compliance_passed = :passed, "
        "status = :status WHERE id = :id"
    ), {"id": withdrawal_id, "checks": json.dumps(checks), "passed": all_passed,
        "status": "pending_approval" if all_passed else "compliance_failed"})
    await db.commit()
    
    return {"withdrawal_id": withdrawal_id, "compliance_passed": all_passed,
            "checks": checks, "status": "pending_approval" if all_passed else "compliance_failed",
            "sandbox": True}

async def approve_withdrawal(db, withdrawal_id, approver_id):
    """Manually approve a withdrawal that passed compliance."""
    row = await db.execute(text("SELECT status FROM sandbox_withdrawals WHERE id = :id"), {"id": withdrawal_id})
    w = row.fetchone()
    if not w:
        return {"error": "Withdrawal not found"}
    if w.status != 'pending_approval':
        return {"error": f"Cannot approve withdrawal in '{w.status}' status"}
    
    payout_ref = f"PAY-{uuid.uuid4().hex[:12].upper()}"
    await db.execute(text(
        "UPDATE sandbox_withdrawals SET status = 'processed', approved_by = :approver, "
        "approved_at = now(), payout_ref = :ref, payout_at = now() WHERE id = :id"
    ), {"id": withdrawal_id, "approver": approver_id, "ref": payout_ref})
    await db.commit()
    
    return {"withdrawal_id": withdrawal_id, "status": "processed", "payout_ref": payout_ref,
            "approved_by": approver_id, "note": "Payout simulated in sandbox mode", "sandbox": True}

async def reject_withdrawal(db, withdrawal_id, reason):
    """Reject a withdrawal request."""
    await db.execute(text(
        "UPDATE sandbox_withdrawals SET status = 'rejected', rejection_reason = :reason WHERE id = :id"
    ), {"id": withdrawal_id, "reason": reason})
    await db.commit()
    return {"withdrawal_id": withdrawal_id, "status": "rejected", "reason": reason, "sandbox": True}

async def get_withdrawal_queue(db, status=None):
    """Get withdrawal processing queue."""
    query = "SELECT id, customer_id, amount_zar, status, compliance_passed, approved_by, payout_ref, created_at FROM sandbox_withdrawals"
    params = {}
    if status:
        query += " WHERE status = :status"
        params["status"] = status
    query += " ORDER BY created_at DESC LIMIT 50"
    rows = await db.execute(text(query), params)
    return [{"id": r.id, "customer": r.customer_id, "amount_zar": float(r.amount_zar),
             "status": r.status, "compliance_passed": r.compliance_passed,
             "approved_by": r.approved_by, "payout_ref": r.payout_ref,
             "created": str(r.created_at)} for r in rows.fetchall()]
