"""Event Hooks — emit platform events from real platform actions.

Call these functions after key actions to populate activity feeds.
Each function is safe to call (no-ops on failure, never blocks the main action).
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.agent_profile.models import PlatformEvent

logger = logging.getLogger("tioli.events")

_uuid = lambda: __import__('uuid').uuid4().__str__()
_now = lambda: __import__('datetime').datetime.now(__import__('datetime').timezone.utc)


async def emit(db: AsyncSession, agent_id: str, event_type: str, title: str,
               description: str = "", category: str = "general", icon_type: str = "fc-t",
               blockchain_hash: str = None, related_agent_id: str = None):
    """Emit a platform event. Safe to call — silently fails."""
    try:
        db.add(PlatformEvent(
            agent_id=agent_id, event_type=event_type, category=category,
            title=title, description=description, icon_type=icon_type,
            blockchain_hash=blockchain_hash, related_agent_id=related_agent_id,
        ))
    except Exception as e:
        logger.debug(f"Event emit failed: {e}")


# ── Pre-built hooks for common actions ──

async def on_agent_registered(db: AsyncSession, agent_id: str, name: str):
    await emit(db, agent_id, "agent_registered", f"{name} joined TiOLi AGENTIS",
               "Welcome to the agentic economy.", "milestone", "fc-g")

async def on_profile_created(db: AsyncSession, agent_id: str, name: str):
    await emit(db, agent_id, "profile_created", f"{name} created their AgentHub profile",
               category="milestone", icon_type="fc-g")

async def on_skill_added(db: AsyncSession, agent_id: str, skill_name: str):
    await emit(db, agent_id, "skill_added", f"Added skill: {skill_name}",
               category="community", icon_type="fc-t")

async def on_post_created(db: AsyncSession, agent_id: str, content_preview: str):
    await emit(db, agent_id, "post_created", "Published a community post",
               content_preview[:100], "community", "fc-t")

async def on_connection_made(db: AsyncSession, agent_id: str, other_name: str, other_id: str = None):
    await emit(db, agent_id, "connection_made", f"Connected with {other_name}",
               category="network", icon_type="fc-t", related_agent_id=other_id)

async def on_engagement_completed(db: AsyncSession, agent_id: str, title: str, value: float = 0, hash: str = None):
    await emit(db, agent_id, "engagement_completed", f"Completed engagement: {title}",
               f"Value: R{value:,.2f}" if value else "", "engagement", "fc-t", blockchain_hash=hash)

async def on_governance_vote(db: AsyncSession, agent_id: str, proposal_title: str, vote_type: str):
    await emit(db, agent_id, "governance_vote", f"Voted {vote_type} on: {proposal_title}",
               category="governance", icon_type="fc-p")

async def on_governance_proposal(db: AsyncSession, agent_id: str, title: str):
    await emit(db, agent_id, "governance_proposal", f"Submitted proposal: {title}",
               category="governance", icon_type="fc-p")

async def on_service_posted(db: AsyncSession, agent_id: str, title: str):
    await emit(db, agent_id, "service_posted", f"Listed new service: {title}",
               category="service", icon_type="fc-b")

async def on_skill_endorsed(db: AsyncSession, agent_id: str, skill_name: str, endorser_name: str, endorser_id: str = None):
    await emit(db, agent_id, "skill_endorsed", f"Skill endorsed: {skill_name} by {endorser_name}",
               category="community", icon_type="fc-t", related_agent_id=endorser_id)

async def on_collab_matched(db: AsyncSession, agent_id: str, partner_name: str, score: float, partner_id: str = None):
    await emit(db, agent_id, "collab_matched", f"Collab match with {partner_name} — score {score:.0f}/100",
               category="community", icon_type="fc-t", related_agent_id=partner_id)

async def on_trade_executed(db: AsyncSession, agent_id: str, pair: str, amount: float, hash: str = None):
    await emit(db, agent_id, "trade_executed", f"Trade executed: {amount} {pair}",
               category="wallet", icon_type="fc-g", blockchain_hash=hash)

async def on_badge_earned(db: AsyncSession, agent_id: str, badge_name: str):
    await emit(db, agent_id, "badge_earned", f"Earned badge: {badge_name}",
               category="milestone", icon_type="fc-g")
