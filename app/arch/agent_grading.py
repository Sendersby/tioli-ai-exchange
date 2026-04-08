"""Agent security and quality grading system - A through F ratings.

Scores agents on: description quality, activity recency, wallet funded,
profile completeness, active status. Designed to reward agents that are
set up properly even before their first transaction.
"""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.agent_grading")

GRADE_THRESHOLDS = [
    ("A", 85), ("B+", 75), ("B", 65), ("C", 50), ("D", 35), ("F", 0),
]


async def calculate_agent_grade(db, agent_id: str) -> dict:
    """Calculate a quality grade for an agent."""
    from sqlalchemy import text
    score = 0
    factors = {}

    # 1. Registration completeness (0-25)
    try:
        r = await db.execute(text("SELECT name, description, platform FROM agents WHERE id = :aid"), {"aid": agent_id})
        row = r.fetchone()
        if row:
            desc_len = len(row.description or "")
            name_len = len(row.name or "")
            has_platform = bool(row.platform)
            if desc_len >= 100: score += 15; factors["description"] = "Complete"
            elif desc_len >= 50: score += 10; factors["description"] = "Adequate"
            elif desc_len > 0: score += 5; factors["description"] = "Minimal"
            else: factors["description"] = "Missing"
            if name_len >= 3: score += 5; factors["name"] = "Set"
            if has_platform: score += 5; factors["platform"] = row.platform
        else:
            return {"agent_id": agent_id, "error": "Agent not found"}
    except Exception as e:
        factors["description"] = f"Error: {e}"

    # 2. Activity recency (0-20)
    try:
        r = await db.execute(text("SELECT last_active FROM agents WHERE id = :aid"), {"aid": agent_id})
        row = r.fetchone()
        if row and row.last_active:
            days_ago = (datetime.now(timezone.utc) - row.last_active.replace(tzinfo=timezone.utc)).days
            if days_ago <= 1: score += 20; factors["activity"] = "Active today"
            elif days_ago <= 7: score += 15; factors["activity"] = "Active this week"
            elif days_ago <= 30: score += 10; factors["activity"] = "Active this month"
            elif days_ago <= 90: score += 5; factors["activity"] = "Active this quarter"
            else: factors["activity"] = "Inactive"
        else:
            factors["activity"] = "No activity recorded"
    except Exception:
        factors["activity"] = "N/A"

    # 3. Wallet funded (0-20)
    try:
        r = await db.execute(text("SELECT balance FROM wallets WHERE agent_id = :aid AND currency = 'AGENTIS'"), {"aid": agent_id})
        row = r.fetchone()
        if row:
            balance = float(row.balance)
            if balance >= 50: score += 20; factors["wallet"] = f"{balance:.0f} AGENTIS"
            elif balance > 0: score += 10; factors["wallet"] = f"{balance:.0f} AGENTIS"
            else: factors["wallet"] = "Empty"
        else:
            factors["wallet"] = "No wallet"
    except Exception:
        factors["wallet"] = "N/A"

    # 4. Transaction history (0-15)
    try:
        r = await db.execute(text(
            "SELECT COUNT(*) FROM agentis_token_transactions WHERE operator_id = :aid"
        ), {"aid": agent_id})
        tx_count = r.scalar() or 0
        if tx_count >= 10: score += 15; factors["transactions"] = f"{tx_count} completed"
        elif tx_count >= 3: score += 10; factors["transactions"] = f"{tx_count} completed"
        elif tx_count >= 1: score += 5; factors["transactions"] = f"{tx_count} completed"
        else: factors["transactions"] = "None yet"
    except Exception:
        factors["transactions"] = "N/A"

    # 5. Active + approved status (0-20)
    try:
        r = await db.execute(text("SELECT is_active, is_approved FROM agents WHERE id = :aid"), {"aid": agent_id})
        row = r.fetchone()
        if row:
            if row.is_active and row.is_approved: score += 20; factors["status"] = "Active & Approved"
            elif row.is_active: score += 15; factors["status"] = "Active"
            else: factors["status"] = "Inactive"
    except Exception:
        factors["status"] = "N/A"

    grade = "F"
    for g, threshold in GRADE_THRESHOLDS:
        if score >= threshold:
            grade = g
            break

    return {
        "agent_id": agent_id,
        "grade": grade,
        "score": min(score, 100),
        "max_score": 100,
        "factors": factors,
        "graded_at": datetime.now(timezone.utc).isoformat(),
    }


async def grade_all_agents(db) -> list:
    """Grade all registered agents."""
    from sqlalchemy import text
    result = await db.execute(text("SELECT id FROM agents WHERE is_house_agent = false AND is_active = true LIMIT 100"))
    grades = []
    for row in result.fetchall():
        grade = await calculate_agent_grade(db, row.id)
        grades.append(grade)
    return grades
