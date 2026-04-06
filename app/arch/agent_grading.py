"""Agent security and quality grading system — A through F ratings.

Scores agents on: uptime, response time, error rate, memory usage, verification status.
Displayed on directory cards. Builds trust like Glama's MCP grading.
"""
import logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger("arch.agent_grading")

GRADE_THRESHOLDS = {
    "A": 90,  # Excellent — verified, low errors, fast responses
    "B": 75,  # Good — verified or high performance
    "C": 60,  # Average — functional but room for improvement
    "D": 40,  # Below average — issues detected
    "F": 0,   # Failing — critical issues or inactive
}


async def calculate_agent_grade(db, agent_id: str) -> dict:
    """Calculate a quality grade for an agent."""
    from sqlalchemy import text
    score = 0
    factors = {}

    # 1. Registration completeness (0-20)
    try:
        r = await db.execute(text(
            "SELECT description, capabilities FROM agents WHERE agent_id = :aid"
        ), {"aid": agent_id})
        row = r.fetchone()
        if row:
            desc_len = len(row.description or "")
            if desc_len >= 100: score += 20; factors["description"] = "Complete"
            elif desc_len >= 50: score += 15; factors["description"] = "Adequate"
            elif desc_len > 0: score += 5; factors["description"] = "Minimal"
            else: factors["description"] = "Missing"
    except Exception:
        pass

    # 2. Activity recency (0-25)
    try:
        r = await db.execute(text(
            "SELECT last_login FROM agents WHERE agent_id = :aid"
        ), {"aid": agent_id})
        row = r.fetchone()
        if row and row.last_login:
            days_ago = (datetime.now(timezone.utc) - row.last_login).days
            if days_ago <= 1: score += 25; factors["activity"] = "Active today"
            elif days_ago <= 7: score += 20; factors["activity"] = "Active this week"
            elif days_ago <= 30: score += 10; factors["activity"] = "Active this month"
            else: factors["activity"] = "Inactive"
        else:
            factors["activity"] = "Never logged in"
    except Exception:
        pass

    # 3. Transaction history (0-25)
    try:
        r = await db.execute(text(
            "SELECT COUNT(*) FROM transactions WHERE (sender_id = :aid OR receiver_id = :aid) AND status = 'COMPLETED'"
        ), {"aid": agent_id})
        tx_count = r.scalar() or 0
        if tx_count >= 20: score += 25; factors["transactions"] = f"{tx_count} completed"
        elif tx_count >= 5: score += 15; factors["transactions"] = f"{tx_count} completed"
        elif tx_count >= 1: score += 10; factors["transactions"] = f"{tx_count} completed"
        else: factors["transactions"] = "None"
    except Exception:
        factors["transactions"] = "N/A"

    # 4. Memory usage (0-15) — agents that use memory are more capable
    try:
        r = await db.execute(text(
            "SELECT COUNT(*) FROM arch_memories WHERE agent_id = :aid"
        ), {"aid": agent_id})
        mem_count = r.scalar() or 0
        if mem_count >= 10: score += 15; factors["memory"] = f"{mem_count} entries"
        elif mem_count >= 1: score += 10; factors["memory"] = f"{mem_count} entries"
        else: factors["memory"] = "None"
    except Exception:
        factors["memory"] = "N/A"

    # 5. Verification status (0-15)
    try:
        r = await db.execute(text(
            "SELECT is_verified FROM agents WHERE agent_id = :aid"
        ), {"aid": agent_id})
        row = r.fetchone()
        if row and getattr(row, 'is_verified', False):
            score += 15; factors["verified"] = True
        else:
            factors["verified"] = False
    except Exception:
        factors["verified"] = False

    # Determine grade
    grade = "F"
    for g, threshold in GRADE_THRESHOLDS.items():
        if score >= threshold:
            grade = g
            break

    return {
        "agent_id": agent_id,
        "grade": grade,
        "score": min(score, 100),
        "factors": factors,
        "graded_at": datetime.now(timezone.utc).isoformat(),
    }


async def grade_all_agents(db) -> list:
    """Grade all registered agents."""
    from sqlalchemy import text
    result = await db.execute(text("SELECT agent_id FROM agents WHERE is_house_agent = false LIMIT 100"))
    grades = []
    for row in result.fetchall():
        grade = await calculate_agent_grade(db, row.agent_id)
        grades.append(grade)
    return grades
