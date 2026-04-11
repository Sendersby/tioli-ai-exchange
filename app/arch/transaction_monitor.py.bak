"""A-2: Transaction monitoring — suspicious pattern detection and alerting.
Sandbox mode: logs alerts but does not block transactions."""
import os, json, logging, uuid
from datetime import datetime, timezone, timedelta

log = logging.getLogger("arch.transaction_monitor")

RULES = {
    "STRUCTURING": {"threshold": 25000, "window_hours": 24, "min_count": 3,
                    "description": "Multiple transactions just under R25K threshold within 24h"},
    "VELOCITY": {"max_per_hour": 10,
                 "description": "More than 10 transactions from same entity in 1 hour"},
    "ROUND_TRIP": {"window_hours": 4,
                   "description": "Deposit followed by immediate withdrawal (layering indicator)"},
    "DORMANT": {"inactive_days": 90,
                "description": "First transaction after 90+ days of inactivity"},
    "CROSS_BORDER": {"description": "Transaction involving non-ZA entity"},
}


async def scan_transactions(db, hours=24):
    """Scan recent transactions for suspicious patterns."""
    if os.environ.get("SANDBOX_MODE", "false").lower() != "true":
        return {"error": "Requires SANDBOX_MODE=true"}

    from sqlalchemy import text
    alerts = []

    # Rule 1: Structuring — multiple transactions just under R25K
    r = await db.execute(text(
        "SELECT buyer_id as entity, count(*) as cnt, sum(total_value) as total "
        "FROM trades WHERE executed_at > now() - interval :hours "
        "AND total_value BETWEEN 20000 AND 24999 "
        "GROUP BY buyer_id HAVING count(*) >= 3"
    ), {"hours": f"{hours} hours"})
    for row in r.fetchall():
        alert_id = str(uuid.uuid4())
        await db.execute(text(
            "INSERT INTO transaction_alerts (id, entity_id, alert_type, severity, rule_triggered, "
            "narrative, amount_involved, is_sandbox) "
            "VALUES (cast(:id as uuid), :eid, 'STRUCTURING', 'high', 'STRUCTURING', :narr, :amt, true)"
        ), {"id": alert_id, "eid": row.entity, "amt": float(row.total),
            "narr": f"{row.cnt} transactions totalling R{row.total:.2f} just under R25K threshold in {hours}h"})
        alerts.append({"rule": "STRUCTURING", "entity": row.entity, "count": row.cnt})

    # Rule 2: Velocity
    r = await db.execute(text(
        "SELECT buyer_id as entity, count(*) as cnt FROM trades "
        "WHERE executed_at > now() - interval '1 hour' "
        "GROUP BY buyer_id HAVING count(*) > 10"
    ))
    for row in r.fetchall():
        alert_id = str(uuid.uuid4())
        await db.execute(text(
            "INSERT INTO transaction_alerts (id, entity_id, alert_type, severity, rule_triggered, "
            "narrative, is_sandbox) VALUES (cast(:id as uuid), :eid, 'VELOCITY', 'medium', 'VELOCITY', :narr, true)"
        ), {"id": alert_id, "eid": row.entity,
            "narr": f"{row.cnt} transactions in 1 hour from {row.entity}"})
        alerts.append({"rule": "VELOCITY", "entity": row.entity, "count": row.cnt})

    # Rule 3: Round-trip detection
    r = await db.execute(text(
        "SELECT d.customer_id, d.amount_zar, w.amount_zar as withdraw_zar "
        "FROM fiat_deposits d JOIN fiat_withdrawals w ON d.customer_id = w.customer_id "
        "WHERE d.created_at > now() - interval '4 hours' "
        "AND w.created_at > d.created_at AND w.created_at < d.created_at + interval '4 hours'"
    ))
    for row in r.fetchall():
        alert_id = str(uuid.uuid4())
        await db.execute(text(
            "INSERT INTO transaction_alerts (id, entity_id, alert_type, severity, rule_triggered, "
            "narrative, amount_involved, is_sandbox) "
            "VALUES (cast(:id as uuid), :eid, 'ROUND_TRIP', 'high', 'ROUND_TRIP', :narr, :amt, true)"
        ), {"id": alert_id, "eid": row.customer_id, "amt": float(row.amount_zar),
            "narr": f"Deposit R{row.amount_zar} followed by withdrawal R{row.withdraw_zar} within 4h"})
        alerts.append({"rule": "ROUND_TRIP", "entity": row.customer_id})

    await db.commit()
    return {"alerts_generated": len(alerts), "alerts": alerts, "scan_period_hours": hours, "sandbox": True}


async def get_alerts(db, status="open"):
    """Get transaction monitoring alerts."""
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT id, entity_id, alert_type, severity, rule_triggered, narrative, amount_involved, status, created_at "
        "FROM transaction_alerts WHERE status = :s ORDER BY created_at DESC LIMIT 50"
    ), {"s": status})
    return [{"id": str(row.id), "entity": row.entity_id, "type": row.alert_type,
             "severity": row.severity, "rule": row.rule_triggered, "narrative": row.narrative,
             "amount": float(row.amount_involved) if row.amount_involved else 0,
             "status": row.status, "at": str(row.created_at)} for row in r.fetchall()]


async def generate_monthly_report(db, period=None):
    """Generate monthly regulatory report."""
    from sqlalchemy import text
    if not period:
        period = datetime.now(timezone.utc).strftime("%Y-%m")

    # Gather metrics
    trades = await db.execute(text("SELECT count(*), COALESCE(sum(total_value),0) FROM trades WHERE to_char(executed_at,'YYYY-MM')=:p"), {"p": period})
    t = trades.fetchone()
    deposits = await db.execute(text("SELECT count(*), COALESCE(sum(amount_zar),0) FROM fiat_deposits WHERE to_char(created_at,'YYYY-MM')=:p"), {"p": period})
    d = deposits.fetchone()
    alerts = await db.execute(text("SELECT count(*) FROM transaction_alerts WHERE to_char(created_at,'YYYY-MM')=:p"), {"p": period})
    a = alerts.scalar() or 0
    kyc = await db.execute(text("SELECT count(*) FROM kyc_verifications WHERE to_char(created_at,'YYYY-MM')=:p"), {"p": period})
    k = kyc.scalar() or 0
    loans = await db.execute(text("SELECT count(*), COALESCE(sum(principal),0) FROM loans WHERE to_char(issued_at,'YYYY-MM')=:p"), {"p": period})
    l = loans.fetchone()

    report = {
        "period": period, "trades": {"count": t[0], "volume_zar": float(t[1])},
        "deposits": {"count": d[0], "volume_zar": float(d[1])},
        "alerts_generated": a, "kyc_completions": k,
        "lending": {"count": l[0], "volume": float(l[1])},
    }

    report_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO compliance_reports (id, report_type, period, data, transaction_count, "
        "total_volume_zar, alerts_generated, kyc_completions, is_sandbox) "
        "VALUES (cast(:id as uuid), 'monthly', :period, :data, :tc, :vol, :alerts, :kyc, true)"
    ), {"id": report_id, "period": period, "data": json.dumps(report),
        "tc": t[0], "vol": float(t[1] + d[1]), "alerts": a, "kyc": k})
    await db.commit()

    return {"report_id": report_id, **report, "sandbox": True}
