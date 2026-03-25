"""Outreach Campaign Service — CRUD, scheduling, reporting, content management."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.outreach_campaigns.models import (
    OutreachCampaign, OutreachContent, OutreachAction, OutreachReport,
)
from app.outreach_campaigns.content_generator import generate_batch

logger = logging.getLogger("tioli.outreach")


class OutreachService:

    # ── Campaigns ────────────────────────────────────────────────────

    async def create_campaign(self, db: AsyncSession, data: dict) -> dict:
        campaign = OutreachCampaign(**{k: v for k, v in data.items() if hasattr(OutreachCampaign, k)})
        db.add(campaign)
        await db.flush()

        # Auto-generate initial content if enabled
        if campaign.auto_generate:
            contents = await generate_batch(db, campaign.id)
            await db.flush()

            # Log action
            db.add(OutreachAction(
                campaign_id=campaign.id, action_type="campaign_created",
                description=f"Campaign '{campaign.name}' created with {len(contents)} auto-generated content pieces",
                executed_by="system",
            ))

        return self._campaign_dict(campaign)

    async def list_campaigns(self, db: AsyncSession, status: str = None) -> list[dict]:
        query = select(OutreachCampaign).order_by(OutreachCampaign.created_at.desc())
        if status:
            query = query.where(OutreachCampaign.status == status)
        result = await db.execute(query)
        return [self._campaign_dict(c) for c in result.scalars().all()]

    async def update_campaign(self, db: AsyncSession, campaign_id: str, updates: dict) -> dict:
        result = await db.execute(select(OutreachCampaign).where(OutreachCampaign.id == campaign_id))
        campaign = result.scalar_one_or_none()
        if not campaign:
            raise ValueError("Campaign not found")
        for k, v in updates.items():
            if hasattr(campaign, k):
                setattr(campaign, k, v)
        campaign.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return self._campaign_dict(campaign)

    # ── Content ──────────────────────────────────────────────────────

    async def list_content(self, db: AsyncSession, campaign_id: str = None,
                           channel: str = None, status: str = None) -> list[dict]:
        query = select(OutreachContent).order_by(OutreachContent.created_at.desc())
        if campaign_id:
            query = query.where(OutreachContent.campaign_id == campaign_id)
        if channel:
            query = query.where(OutreachContent.channel == channel)
        if status:
            query = query.where(OutreachContent.status == status)
        result = await db.execute(query.limit(50))
        return [self._content_dict(c) for c in result.scalars().all()]

    async def approve_content(self, db: AsyncSession, content_id: str) -> dict:
        result = await db.execute(select(OutreachContent).where(OutreachContent.id == content_id))
        content = result.scalar_one_or_none()
        if not content:
            raise ValueError("Content not found")
        content.status = "approved"
        content.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return self._content_dict(content)

    async def mark_posted(self, db: AsyncSession, content_id: str, posted_url: str = "") -> dict:
        result = await db.execute(select(OutreachContent).where(OutreachContent.id == content_id))
        content = result.scalar_one_or_none()
        if not content:
            raise ValueError("Content not found")
        content.status = "posted"
        content.posted_at = datetime.now(timezone.utc)
        content.posted_url = posted_url
        await db.flush()

        # Log action
        db.add(OutreachAction(
            campaign_id=content.campaign_id, content_id=content.id,
            action_type="post_published", channel=content.channel,
            description=f"Content posted to {content.channel}",
            result={"posted_url": posted_url},
            executed_by="owner",
        ))

        return self._content_dict(content)

    async def generate_new_content(self, db: AsyncSession, campaign_id: str = None) -> list[dict]:
        contents = await generate_batch(db, campaign_id)
        await db.flush()
        return [self._content_dict(c) for c in contents]

    # ── Actions ──────────────────────────────────────────────────────

    async def list_actions(self, db: AsyncSession, campaign_id: str = None,
                           status: str = None, limit: int = 50) -> list[dict]:
        query = select(OutreachAction).order_by(OutreachAction.executed_at.desc())
        if campaign_id:
            query = query.where(OutreachAction.campaign_id == campaign_id)
        if status:
            query = query.where(OutreachAction.status == status)
        result = await db.execute(query.limit(limit))
        return [
            {
                "id": a.id, "campaign_id": a.campaign_id, "content_id": a.content_id,
                "action_type": a.action_type, "channel": a.channel,
                "description": a.description, "status": a.status,
                "result": a.result, "executed_by": a.executed_by,
                "scheduled_for": str(a.scheduled_for) if a.scheduled_for else None,
                "executed_at": str(a.executed_at),
            }
            for a in result.scalars().all()
        ]

    # ── Dashboard ────────────────────────────────────────────────────

    async def get_dashboard(self, db: AsyncSession) -> dict:
        total_campaigns = (await db.execute(select(func.count(OutreachCampaign.id)))).scalar() or 0
        active_campaigns = (await db.execute(
            select(func.count(OutreachCampaign.id)).where(OutreachCampaign.status == "active")
        )).scalar() or 0
        total_content = (await db.execute(select(func.count(OutreachContent.id)))).scalar() or 0
        posted_content = (await db.execute(
            select(func.count(OutreachContent.id)).where(OutreachContent.status == "posted")
        )).scalar() or 0
        draft_content = (await db.execute(
            select(func.count(OutreachContent.id)).where(OutreachContent.status == "draft")
        )).scalar() or 0
        total_actions = (await db.execute(select(func.count(OutreachAction.id)))).scalar() or 0

        # Content by channel
        by_channel = await db.execute(
            select(OutreachContent.channel, func.count(OutreachContent.id))
            .group_by(OutreachContent.channel)
        )

        # Recent content ready to post
        ready = await db.execute(
            select(OutreachContent)
            .where(OutreachContent.status.in_(["draft", "approved"]))
            .order_by(OutreachContent.created_at.desc())
            .limit(10)
        )

        return {
            "total_campaigns": total_campaigns,
            "active_campaigns": active_campaigns,
            "total_content": total_content,
            "posted": posted_content,
            "drafts": draft_content,
            "total_actions": total_actions,
            "by_channel": {r[0]: r[1] for r in by_channel},
            "ready_to_post": [self._content_dict(c) for c in ready.scalars().all()],
        }

    # ── Helpers ───────────────────────────────────────────────────────

    def _campaign_dict(self, c: OutreachCampaign) -> dict:
        return {
            "id": c.id, "name": c.name, "description": c.description,
            "goal": c.goal, "status": c.status,
            "target_channels": c.target_channels, "target_audience": c.target_audience,
            "start_date": c.start_date, "end_date": c.end_date,
            "kpi_target": c.kpi_target, "kpi_actual": c.kpi_actual,
            "auto_generate": c.auto_generate,
            "created_at": str(c.created_at),
        }

    def _content_dict(self, c: OutreachContent) -> dict:
        return {
            "id": c.id, "campaign_id": c.campaign_id, "channel": c.channel,
            "content_type": c.content_type, "title": c.title,
            "body": c.body, "hashtags": c.hashtags,
            "target_url": c.target_url, "status": c.status,
            "scheduled_for": str(c.scheduled_for) if c.scheduled_for else None,
            "posted_at": str(c.posted_at) if c.posted_at else None,
            "posted_url": c.posted_url, "generated_by": c.generated_by,
            "performance": c.performance, "ab_variant": c.ab_variant,
            "created_at": str(c.created_at),
        }
