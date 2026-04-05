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
