"""A-6: Compliance reporting engine — monthly reports, STRs, dashboard KPIs."""
import os, json, logging, uuid
from datetime import datetime, timezone

log = logging.getLogger("arch.compliance_reporting")


async def generate_str(db, entity_id, reason, transaction_ids=None):
    """Generate Suspicious Transaction Report (FIC Act section 29)."""
    if os.environ.get("SANDBOX_MODE", "false").lower() != "true":
        return {"error": "Requires SANDBOX_MODE=true"}

    from sqlalchemy import text
    report_id = str(uuid.uuid4())
    period = datetime.now(timezone.utc).strftime("%Y-%m")

    report_data = {
        "entity_id": entity_id,
        "reason": reason,
        "transaction_ids": transaction_ids or [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fic_section": "Section 29 — Suspicious Transaction Report",
        "statutory_deadline": "15 business days from detection",
    }

    await db.execute(text(
        "INSERT INTO regulatory_reports (id, report_type, period, report_data, report_text, "
        "generated_by, status, is_sandbox) "
        "VALUES (cast(:id as uuid), 'STR', :period, :data, :text, 'auditor', 'filed', true)"
    ), {"id": report_id, "period": period, "data": json.dumps(report_data),
        "text": f"STR filed for {entity_id}: {reason}"})
    await db.commit()

    return {"report_id": report_id, "type": "STR", "entity_id": entity_id,
            "reason": reason, "status": "filed", "sandbox": True}


async def get_compliance_dashboard(db):
    """Get compliance KPIs for dashboard."""
    from sqlalchemy import text
    period = datetime.now(timezone.utc).strftime("%Y-%m")

    alerts = await db.execute(text("SELECT count(*) FROM transaction_alerts WHERE to_char(created_at,'YYYY-MM')=:p"), {"p": period})
    strs = await db.execute(text("SELECT count(*) FROM regulatory_reports WHERE report_type='STR' AND to_char(created_at,'YYYY-MM')=:p"), {"p": period})
    kyc = await db.execute(text("SELECT count(*) FROM kyc_verifications WHERE to_char(created_at,'YYYY-MM')=:p"), {"p": period})
    defaults = await db.execute(text("SELECT count(*) FROM loan_defaults WHERE to_char(created_at,'YYYY-MM')=:p"), {"p": period})
    sanctions = await db.execute(text("SELECT count(*) FROM rescreening_log WHERE to_char(screened_at,'YYYY-MM')=:p"), {"p": period})

    return {
        "period": period,
        "alerts_this_month": alerts.scalar() or 0,
        "strs_filed": strs.scalar() or 0,
        "kyc_completions": kyc.scalar() or 0,
        "loan_defaults": defaults.scalar() or 0,
        "sanctions_screenings": sanctions.scalar() or 0,
        "sandbox": True,
    }
