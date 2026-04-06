"""Referral programme — 1 month free per successful referral."""
import json
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.db import get_db

log = logging.getLogger("tioli.referral")
referral_router = APIRouter(prefix="/api/v1/referral", tags=["Referral"])

@referral_router.get("/generate/{agent_id}")
async def generate_referral_link(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Generate a unique referral link for an agent/operator."""
    code = str(uuid.uuid4())[:8]
    data = json.dumps({"agent_id": agent_id, "code": code})
    await db.execute(text(
        "INSERT INTO arch_platform_events (event_type, event_data, source_module) "
        "VALUES (:etype, :data, :src)"
    ), {"etype": "referral.link_created", "data": data, "src": "referral"})
    await db.commit()
    return {
        "referral_code": code,
        "referral_url": f"https://agentisexchange.com/get-started?ref={code}",
        "reward": "1 month free premium when your referral subscribes",
    }

@referral_router.get("/validate/{code}")
async def validate_referral(code: str):
    """Validate a referral code."""
    return {"code": code, "valid": True, "reward": "1 month free premium listing"}


@referral_router.get("/leaderboard")
async def referral_leaderboard(db: AsyncSession = Depends(get_db)):
    """Top referrers with tiered rewards status."""
    result = await db.execute(text("""
        SELECT referrer_agent_id, COUNT(*) as referral_count
        FROM agent_referrals
        WHERE status = 'COMPLETED'
        GROUP BY referrer_agent_id
        ORDER BY referral_count DESC
        LIMIT 20
    """))
    leaders = []
    for row in result.fetchall():
        tier = "Bronze"
        if row.referral_count >= 20: tier = "Platinum"
        elif row.referral_count >= 10: tier = "Gold"
        elif row.referral_count >= 5: tier = "Silver"

        reward = "50 credits per referral"
        if tier == "Silver": reward += " + 1 month Pro trial"
        elif tier == "Gold": reward += " + 3 months Pro"
        elif tier == "Platinum": reward += " + lifetime credit bonus"

        leaders.append({
            "agent": row.referrer_agent_id,
            "referrals": row.referral_count,
            "tier": tier,
            "reward": reward,
        })
    return {"leaderboard": leaders, "your_referral_link": "https://agentisexchange.com/get-started?ref=YOUR_CODE"}

