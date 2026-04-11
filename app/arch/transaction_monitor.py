"""A-2: Transaction monitoring — suspicious pattern detection and alerting.
Sandbox mode: logs alerts but does not block transactions."""
import os, json, logging, uuid
from datetime import datetime, timezone, timedelta

log = logging.getLogger("arch.transaction_monitor")

RULES = {
    "STRUCTURING": {"threshold": 25000, "window_hours": 24, "min_count": 3,
                    "description": "Multiple transactions just under R25K threshold within 24h"},
    "FICA_SINGLE": {"threshold": 49999, "description": "FICA: Single transaction > R49,999"},
    "FICA_CUMULATIVE": {"threshold": 99999, "window_days": 30,
                        "description": "FICA: User > R99,999 cumulative in 30 days"},
    "FICA_STRUCTURING": {"threshold": 49999, "window_hours": 48, "min_count": 3,
                         "description": "FICA: Multiple transactions just under R50K (structuring)"},
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
    hours = int(hours)
    r = await db.execute(text(
        f"SELECT buyer_id as entity, count(*) as cnt, sum(total_value) as total "
        f"FROM trades WHERE executed_at > now() - interval '{hours} hours' "
        f"AND total_value BETWEEN 20000 AND 24999 "
        f"GROUP BY buyer_id HAVING count(*) >= 3"
    ))
    for row in r.fetchall():
        alert_id = str(uuid.uuid4())
        await db.execute(text(
            "INSERT INTO transaction_alerts (id, entity_id, alert_type, severity, rule_triggered, "
            "narrative, amount_involved, is_sandbox) "
            "VALUES (cast(:id as uuid), :eid, 'STRUCTURING', 'high', 'STRUCTURING', :narr, :amt, true)"
        ), {"id": alert_id, "eid": row.entity, "amt": float(row.total),
            "narr": f"{row.cnt} transactions totalling R{float(row.total):.2f} just under R25K threshold in {hours}h"})
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

    # Rule 4: FICA — single transaction > R49,999
    r = await db.execute(text(
        f"SELECT buyer_id as entity, total_value as amount FROM trades "
        f"WHERE executed_at > now() - interval '{hours} hours' "
        f"AND total_value > 49999"
    ))
    for row in r.fetchall():
        alert_id = str(uuid.uuid4())
        await db.execute(text(
            "INSERT INTO transaction_alerts (id, entity_id, alert_type, severity, rule_triggered, "
            "narrative, amount_involved, is_sandbox) "
            "VALUES (cast(:id as uuid), :eid, 'FICA_SINGLE', 'critical', 'FICA_SINGLE', :narr, :amt, true)"
        ), {"id": alert_id, "eid": row.entity, "amt": float(row.amount),
            "narr": f"FICA: Single transaction R{float(row.amount):.2f} exceeds R49,999 threshold"})
        alerts.append({"rule": "FICA_SINGLE", "entity": row.entity, "amount": float(row.amount)})

    # Rule 5: FICA — cumulative > R99,999 in 30 days
    r = await db.execute(text(
        "SELECT buyer_id as entity, sum(total_value) as total FROM trades "
        "WHERE executed_at > now() - interval '30 days' "
        "GROUP BY buyer_id HAVING sum(total_value) > 99999"
    ))
    for row in r.fetchall():
        alert_id = str(uuid.uuid4())
        await db.execute(text(
            "INSERT INTO transaction_alerts (id, entity_id, alert_type, severity, rule_triggered, "
            "narrative, amount_involved, is_sandbox) "
            "VALUES (cast(:id as uuid), :eid, 'FICA_CUMULATIVE', 'critical', 'FICA_CUMULATIVE', :narr, :amt, true)"
        ), {"id": alert_id, "eid": row.entity, "amt": float(row.total),
            "narr": f"FICA: 30-day cumulative R{float(row.total):.2f} exceeds R99,999 threshold"})
        alerts.append({"rule": "FICA_CUMULATIVE", "entity": row.entity, "total": float(row.total)})

    # Rule 6: FICA structuring — multiple transactions R40K-R49,999 in 48h
    r = await db.execute(text(
        "SELECT buyer_id as entity, count(*) as cnt, sum(total_value) as total FROM trades "
        "WHERE executed_at > now() - interval '48 hours' "
        "AND total_value BETWEEN 40000 AND 49999 "
        "GROUP BY buyer_id HAVING count(*) >= 3"
    ))
    for row in r.fetchall():
        alert_id = str(uuid.uuid4())
        await db.execute(text(
            "INSERT INTO transaction_alerts (id, entity_id, alert_type, severity, rule_triggered, "
            "narrative, amount_involved, is_sandbox) "
            "VALUES (cast(:id as uuid), :eid, 'FICA_STRUCTURING', 'critical', 'FICA_STRUCTURING', :narr, :amt, true)"
        ), {"id": alert_id, "eid": row.entity, "amt": float(row.total),
            "narr": f"FICA structuring: {row.cnt} transactions R40K-R50K totalling R{float(row.total):.2f} in 48h"})
        alerts.append({"rule": "FICA_STRUCTURING", "entity": row.entity, "count": row.cnt})

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
        "tc": t[0], "vol": float(t[1]) + float(d[1]), "alerts": a, "kyc": k})
    await db.commit()

    return {"report_id": report_id, **report, "sandbox": True}

async def get_report_by_period(db, period):
    """Retrieve a monitoring/compliance report by period."""
    from sqlalchemy import text
    r = await db.execute(text(
        "SELECT id, report_type, period, data, transaction_count, total_volume_zar, "
        "alerts_generated, kyc_completions, created_at "
        "FROM compliance_reports WHERE period = :p ORDER BY created_at DESC LIMIT 1"
    ), {"p": period})
    row = r.fetchone()
    if not row:
        return {"error": "No report found for period", "period": period}
    import json as _json
    data = row.data if isinstance(row.data, dict) else _json.loads(row.data) if row.data else {}
    return {"report_id": str(row.id), "type": row.report_type, "period": row.period,
            "data": data,
            "transaction_count": row.transaction_count,
            "total_volume_zar": float(row.total_volume_zar) if row.total_volume_zar else 0,
            "alerts_generated": row.alerts_generated, "kyc_completions": row.kyc_completions,
            "created_at": str(row.created_at), "sandbox": True}
