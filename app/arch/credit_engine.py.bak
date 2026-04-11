"""A-4: Credit assessment engine — 5-factor scoring with NCA disclosure generation."""
import os, json, logging, uuid
from datetime import datetime, timezone, timedelta

log = logging.getLogger("arch.credit_engine")

GRADE_THRESHOLDS = {"A": 80, "B": 65, "C": 50, "D": 35, "E": 0}
MAX_RATE = 27.0  # NCA maximum interest rate (per annum)


async def assess_credit(db, entity_id):
    """Run 5-factor credit assessment."""
    if os.environ.get("SANDBOX_MODE", "false").lower() != "true":
        return {"error": "Requires SANDBOX_MODE=true"}

    from sqlalchemy import text
    try:
        await db.rollback()
    except Exception:
        pass

    # Factor 1: Reputation (0-20)
    rep = await db.execute(text("SELECT 5.0 as rep_score FROM agents WHERE id = :eid"), {"eid": entity_id})
    rep_row = rep.fetchone()
    reputation = min((float(rep_row.rep_score) if rep_row else 0) * 4, 20)

    # Factor 2: Transaction history (0-20)
    tx = await db.execute(text("SELECT count(*) FROM trades WHERE buyer_id = :eid OR seller_id = :eid"), {"eid": entity_id})
    tx_count = tx.scalar() or 0
    history = min(tx_count * 2, 20)

    # Factor 3: Account age (0-20)
    age = await db.execute(text("SELECT created_at FROM agents WHERE id = :eid"), {"eid": entity_id})
    age_row = age.fetchone()
    if age_row and age_row.created_at:
        days = (datetime.now(timezone.utc) - age_row.created_at).days
        age_score = min(days / 5, 20)
    else:
        age_score = 0

    # Factor 4: Collateral ratio (0-20)
    bal = await db.execute(text("SELECT COALESCE(sum(balance),0) FROM wallets WHERE agent_id = :eid"), {"eid": entity_id})
    balance = float(bal.scalar() or 0)
    collateral = min(balance / 50, 20)

    # Factor 5: Platform activity (0-20)
    eng = await db.execute(text("SELECT count(*) FROM agent_engagements WHERE client_agent_id = :eid OR provider_agent_id = :eid"), {"eid": entity_id})
    engagements = eng.scalar() or 0
    activity = min(engagements * 4, 20)

    total = round(reputation + history + age_score + collateral + activity)
    grade = "E"
    for g, threshold in GRADE_THRESHOLDS.items():
        if total >= threshold:
            grade = g
            break

    max_loan = round(balance * (total / 100) * 10, 2)
    rate = round(MAX_RATE - (total * 0.15), 2)

    assess_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO credit_assessments (id, entity_id, credit_score, reputation_factor, history_factor, "
        "age_factor, collateral_factor, activity_factor, risk_grade, max_loan_amount, recommended_rate, is_sandbox) "
        "VALUES (cast(:id as uuid), :eid, :score, :rep, :hist, :age, :coll, :act, :grade, :max_loan, :rate, true)"
    ), {"id": assess_id, "eid": entity_id, "score": total,
        "rep": reputation, "hist": history, "age": age_score, "coll": collateral,
        "act": activity, "grade": grade, "max_loan": max_loan, "rate": rate})
    await db.commit()

    return {"assessment_id": assess_id, "entity_id": entity_id, "credit_score": total,
            "grade": grade, "factors": {"reputation": round(reputation,1), "history": round(history,1),
            "age": round(age_score,1), "collateral": round(collateral,1), "activity": round(activity,1)},
            "max_loan_amount": max_loan, "recommended_rate": rate, "sandbox": True}


async def generate_nca_disclosure(db, borrower_id, principal, rate, term_months):
    """Generate NCA-compliant pre-agreement disclosure."""
    from sqlalchemy import text
    monthly_rate = rate / 12 / 100
    if monthly_rate > 0:
        instalment = principal * (monthly_rate * (1 + monthly_rate)**term_months) / ((1 + monthly_rate)**term_months - 1)
    else:
        instalment = principal / term_months
    total_cost = instalment * term_months
    total_interest = total_cost - principal

    cooling_off = datetime.now(timezone.utc) + timedelta(days=5)

    disclosure_text = (
        f"PRE-AGREEMENT STATEMENT AND QUOTATION (National Credit Act, Section 92)\n\n"
        f"Borrower: {borrower_id}\n"
        f"Principal amount: R{principal:.2f}\n"
        f"Interest rate: {rate:.2f}% per annum\n"
        f"Term: {term_months} months\n"
        f"Monthly instalment: R{instalment:.2f}\n"
        f"Total interest: R{total_interest:.2f}\n"
        f"TOTAL COST OF CREDIT: R{total_cost:.2f}\n\n"
        f"Cooling-off period: 5 business days from acceptance (expires {cooling_off.strftime('%Y-%m-%d')})\n"
        f"You may cancel this agreement within the cooling-off period without penalty.\n\n"
        f"WARNING: This is a credit agreement regulated by the National Credit Act 34 of 2005."
    )

    disc_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO nca_disclosures (id, borrower_id, principal, interest_rate, total_cost_of_credit, "
        "monthly_instalment, term_months, cooling_off_expires, disclosure_text, is_sandbox) "
        "VALUES (cast(:id as uuid), :bid, :p, :r, :tcc, :mi, :tm, :co, :txt, true)"
    ), {"id": disc_id, "bid": borrower_id, "p": float(principal), "r": float(rate),
        "tcc": round(total_cost, 2), "mi": round(instalment, 2), "tm": term_months,
        "co": cooling_off, "txt": disclosure_text})
    await db.commit()

    return {"disclosure_id": disc_id, "principal": float(principal), "rate": float(rate),
            "term_months": term_months, "monthly_instalment": round(instalment, 2),
            "total_interest": round(total_interest, 2), "total_cost": round(total_cost, 2),
            "cooling_off_expires": cooling_off.isoformat(), "disclosure_text": disclosure_text, "sandbox": True}
