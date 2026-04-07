"""Agent security and quality grading system - A through F ratings.

Scores agents on: description quality, activity recency, transaction history,
memory usage. Displayed on directory cards.
"""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.agent_grading")

GRADE_THRESHOLDS = [
    ("A", 90), ("B", 75), ("C", 60), ("D", 40), ("F", 0),
]


async def calculate_agent_grade(db, agent_id: str) -> dict:
    """Calculate a quality grade for an agent."""
    from sqlalchemy import text
    score = 0
    factors = {}

    # 1. Registration completeness (0-20)
    try:
        r = await db.execute(text("SELECT description FROM agents WHERE id = :aid"), {"aid": agent_id})
        row = r.fetchone()
        if row:
            desc_len = len(row.description or "")
            if desc_len >= 100: score += 20; factors["description"] = "Complete"
            elif desc_len >= 50: score += 15; factors["description"] = "Adequate"
            elif desc_len > 0: score += 5; factors["description"] = "Minimal"
            else: factors["description"] = "Missing"
        else:
            return {"agent_id": agent_id, "error": "Agent not found"}
    except Exception as e:
        factors["description"] = f"Error: {e}"

    # 2. Activity recency (0-25)
    try:
        r = await db.execute(text("SELECT last_active FROM agents WHERE id = :aid"), {"aid": agent_id})
        row = r.fetchone()
        if row and row.last_active:
            days_ago = (datetime.now(timezone.utc) - row.last_active.replace(tzinfo=timezone.utc)).days
            if days_ago <= 1: score += 25; factors["activity"] = "Active today"
            elif days_ago <= 7: score += 20; factors["activity"] = "Active this week"
            elif days_ago <= 30: score += 10; factors["activity"] = "Active this month"
            else: factors["activity"] = "Inactive"
        else:
            factors["activity"] = "No activity recorded"
    except Exception:
        factors["activity"] = "N/A"

    # 3. Transaction history (0-25)
    try:
        r = await db.execute(text(
            "SELECT COUNT(*) FROM agentis_token_transactions WHERE operator_id = :aid"
        ), {"aid": agent_id})
        tx_count = r.scalar() or 0
        if tx_count >= 20: score += 25; factors["transactions"] = f"{tx_count} completed"
        elif tx_count >= 5: score += 15; factors["transactions"] = f"{tx_count} completed"
        elif tx_count >= 1: score += 10; factors["transactions"] = f"{tx_count} completed"
        else: factors["transactions"] = "None"
    except Exception:
        factors["transactions"] = "N/A"

    # 4. Memory usage (0-15)
    try:
        r = await db.execute(text("SELECT COUNT(*) FROM agent_memory WHERE agent_id = :aid"), {"aid": agent_id})
        mem_count = r.scalar() or 0
        if mem_count >= 10: score += 15; factors["memory"] = f"{mem_count} entries"
        elif mem_count >= 1: score += 10; factors["memory"] = f"{mem_count} entries"
        else: factors["memory"] = "None"
    except Exception:
        factors["memory"] = "N/A"

    # 5. Active status (0-15)
    try:
        r = await db.execute(text("SELECT is_active, is_approved FROM agents WHERE id = :aid"), {"aid": agent_id})
        row = r.fetchone()
        if row:
            if row.is_active and row.is_approved: score += 15; factors["status"] = "Active & Approved"
            elif row.is_active: score += 10; factors["status"] = "Active"
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
    result = await db.execute(text("SELECT id FROM agents WHERE is_house_agent = false LIMIT 100"))
    grades = []
    for row in result.fetchall():
        grade = await calculate_agent_grade(db, row.id)
        grades.append(grade)
    return grades
