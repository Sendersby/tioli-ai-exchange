"""ML-lite transaction risk scoring — pattern-based analysis."""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.ml_risk")


async def score_transaction_risk(db, agent_id, amount, currency):
    """Score transaction risk based on historical patterns."""
    from sqlalchemy import text
    import os

    if os.environ.get("ARCH_AGENT_ML_RISK", "false").lower() != "true":
        return {"risk_score": 0, "method": "disabled"}

    risk_score = 0
    flags = []

    # Factor 1: Amount relative to agent's typical transactions
    try:
        avg_result = await db.execute(text(
            "SELECT AVG(tokens), STDDEV(tokens), COUNT(*) FROM agentis_token_transactions "
            "WHERE operator_id = :aid"
        ), {"aid": agent_id})
        row = avg_result.fetchone()
        if row and row[0] and row[2] > 2:
            avg_amount = float(row[0])
            stddev = float(row[1] or 0)
            if amount > avg_amount + (2 * stddev):
                risk_score += 30
                flags.append(f"Amount {amount} exceeds 2 std devs above mean {avg_amount:.0f}")
    except Exception:
        pass

    # Factor 2: Transaction frequency (velocity check)
    try:
        recent = await db.execute(text(
            "SELECT COUNT(*) FROM agentis_token_transactions "
            "WHERE operator_id = :aid AND created_at > now() - interval '1 hour'"
        ), {"aid": agent_id})
        hourly_count = recent.scalar() or 0
        if hourly_count > 10:
            risk_score += 25
            flags.append(f"High velocity: {hourly_count} transactions in last hour")
    except Exception:
        pass

    # Factor 3: Currency risk
    if currency in ("BTC", "ETH"):
        risk_score += 15
        flags.append(f"Cryptocurrency transaction ({currency})")

    # Factor 4: Amount threshold
    if amount >= 100000:
        risk_score += 40
        flags.append("Very large transaction (>R100K)")
    elif amount > 25000:
        risk_score += 20
        flags.append("Exceeds R25,000 AML reporting threshold")

    risk_level = "LOW" if risk_score < 20 else "MEDIUM" if risk_score < 40 else "HIGH" if risk_score < 60 else "CRITICAL"

    return {
        "agent_id": agent_id,
        "amount": amount,
        "currency": currency,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "flags": flags,
        "method": "ml_lite_pattern",
        "factors_checked": 4,
    }
