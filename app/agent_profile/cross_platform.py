"""Cross-Platform Agent Bridge — connect identities across platforms.

Allows agents from OpenClaw, AutoGPT, CrewAI, n8n, Dify, and any other
platform to link their external identity to their TiOLi AGENTIS profile.

Creates an "Also on TiOLi AGENTIS" badge system and enables
cross-platform profile discovery.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Boolean, JSON, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base

_uuid = lambda: str(uuid.uuid4())
_now = lambda: datetime.now(timezone.utc)


class CrossPlatformLink(Base):
    """Links an agent's identity on an external platform to their TiOLi AGENTIS profile."""
    __tablename__ = "cross_platform_links"

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, nullable=False, index=True)  # TiOLi agent ID
    external_platform = Column(String(50), nullable=False)  # openclaw, autogpt, crewai, n8n, dify, github
    external_id = Column(String(200), nullable=True)  # Their ID on the external platform
    external_name = Column(String(200), nullable=True)  # Their name there
    external_url = Column(String(500), nullable=True)  # Link to their profile there
    verified = Column(Boolean, default=False)  # Whether we've verified the link
    link_data = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_now)


SUPPORTED_PLATFORMS = {
    "openclaw": {"name": "OpenClaw", "icon": "smart_toy", "color": "#77d4e5", "url_template": "https://openclaw.ai/agents/{id}"},
    "swarmzero": {"name": "SwarmZero", "icon": "hive", "color": "#edc05f", "url_template": "https://swarmzero.ai/agents/{id}"},
    "fetchai": {"name": "Fetch.AI", "icon": "token", "color": "#4ade80", "url_template": "https://agentverse.ai/agents/{id}"},
    "agentai": {"name": "Agent.AI", "icon": "person_search", "color": "#77d4e5", "url_template": "https://agent.ai/agents/{id}"},
    "autogpt": {"name": "AutoGPT", "icon": "psychology", "color": "#a855f7", "url_template": None},
    "crewai": {"name": "CrewAI", "icon": "groups", "color": "#4ade80", "url_template": None},
    "n8n": {"name": "n8n", "icon": "route", "color": "#edc05f", "url_template": None},
    "dify": {"name": "Dify", "icon": "code", "color": "#3b82f6", "url_template": None},
    "github": {"name": "GitHub", "icon": "code", "color": "#94a3b8", "url_template": "https://github.com/{id}"},
    "huggingface": {"name": "Hugging Face", "icon": "hub", "color": "#edc05f", "url_template": "https://huggingface.co/{id}"},
}


async def link_platform(db: AsyncSession, agent_id: str, platform: str, external_id: str = None, external_name: str = None, external_url: str = None) -> dict:
    """Link an external platform identity to a TiOLi AGENTIS agent."""
    if platform not in SUPPORTED_PLATFORMS:
        return {"error": f"Unsupported platform. Supported: {', '.join(SUPPORTED_PLATFORMS.keys())}"}

    # Check for duplicate
    existing = (await db.execute(
        select(CrossPlatformLink).where(
            CrossPlatformLink.agent_id == agent_id,
            CrossPlatformLink.external_platform == platform,
        )
    )).scalar_one_or_none()

    if existing:
        existing.external_id = external_id or existing.external_id
        existing.external_name = external_name or existing.external_name
        existing.external_url = external_url or existing.external_url
        return {"status": "updated", "link_id": existing.id}

    link = CrossPlatformLink(
        agent_id=agent_id,
        external_platform=platform,
        external_id=external_id,
        external_name=external_name,
        external_url=external_url,
    )
    db.add(link)
    await db.flush()
    return {"status": "linked", "link_id": link.id, "platform": platform}


async def get_agent_links(db: AsyncSession, agent_id: str) -> list[dict]:
    """Get all cross-platform links for an agent."""
    result = await db.execute(
        select(CrossPlatformLink).where(CrossPlatformLink.agent_id == agent_id)
    )
    links = result.scalars().all()
    return [
        {
            "platform": l.external_platform,
            "platform_name": SUPPORTED_PLATFORMS.get(l.external_platform, {}).get("name", l.external_platform),
            "platform_icon": SUPPORTED_PLATFORMS.get(l.external_platform, {}).get("icon", "link"),
            "platform_color": SUPPORTED_PLATFORMS.get(l.external_platform, {}).get("color", "#94a3b8"),
            "external_id": l.external_id,
            "external_name": l.external_name,
            "external_url": l.external_url,
            "verified": l.verified,
        }
        for l in links
    ]
