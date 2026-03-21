"""ARM service — campaign management, directory tracking, and metrics."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.arm.models import OutreachCampaign, DirectoryListing

logger = logging.getLogger(__name__)


class ARMService:
    async def create_campaign(
        self, db: AsyncSession, campaign_name: str, campaign_type: str,
        channel: str, description: str = "", target_audience: str = "",
        content: str = "", url: str = None, tracking_code: str = None,
        status: str = "active",
    ) -> dict:
        campaign = OutreachCampaign(
            campaign_name=campaign_name, campaign_type=campaign_type,
            channel=channel, status=status, description=description,
            target_audience=target_audience, content=content, url=url,
            tracking_code=tracking_code,
            launched_at=datetime.now(timezone.utc) if status == "active" else None,
        )
        db.add(campaign)
        await db.flush()
        return {"campaign_id": campaign.id, "name": campaign_name, "status": status}

    async def update_metrics(
        self, db: AsyncSession, campaign_id: str,
        impressions: int = 0, clicks: int = 0, registrations: int = 0,
        conversions: int = 0, revenue: float = 0,
    ) -> dict:
        result = await db.execute(select(OutreachCampaign).where(OutreachCampaign.id == campaign_id))
        c = result.scalar_one_or_none()
        if not c:
            raise ValueError("Campaign not found")
        c.impressions += impressions
        c.clicks += clicks
        c.registrations += registrations
        c.conversions += conversions
        c.revenue_attributed += revenue
        c.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return {"campaign_id": c.id, "impressions": c.impressions, "clicks": c.clicks}

    async def add_directory_listing(
        self, db: AsyncSession, directory_name: str, directory_url: str,
        listing_type: str, status: str = "pending", listing_url: str = None,
        notes: str = "",
    ) -> dict:
        listing = DirectoryListing(
            directory_name=directory_name, directory_url=directory_url,
            listing_type=listing_type, status=status, listing_url=listing_url,
            notes=notes,
            submission_date=datetime.now(timezone.utc) if status != "pending" else None,
            approval_date=datetime.now(timezone.utc) if status == "active" else None,
        )
        db.add(listing)
        await db.flush()
        return {"listing_id": listing.id, "directory": directory_name, "status": status}

    async def get_dashboard_data(self, db: AsyncSession) -> dict:
        # Campaigns
        campaigns = (await db.execute(
            select(OutreachCampaign).order_by(OutreachCampaign.created_at.desc())
        )).scalars().all()

        total_impressions = sum(c.impressions for c in campaigns)
        total_clicks = sum(c.clicks for c in campaigns)
        total_registrations = sum(c.registrations for c in campaigns)
        total_revenue = sum(c.revenue_attributed for c in campaigns)
        active_campaigns = sum(1 for c in campaigns if c.status == "active")

        # Directories
        directories = (await db.execute(
            select(DirectoryListing).order_by(DirectoryListing.created_at.desc())
        )).scalars().all()
        active_listings = sum(1 for d in directories if d.status == "active")

        return {
            "campaigns": [{
                "id": c.id, "name": c.campaign_name, "type": c.campaign_type,
                "channel": c.channel, "status": c.status, "description": c.description,
                "impressions": c.impressions, "clicks": c.clicks,
                "registrations": c.registrations, "conversions": c.conversions,
                "spend": c.spend, "revenue": c.revenue_attributed, "url": c.url,
                "tracking_code": c.tracking_code,
                "ctr": round(c.clicks / max(c.impressions, 1) * 100, 1),
                "launched_at": str(c.launched_at) if c.launched_at else None,
            } for c in campaigns],
            "directories": [{
                "id": d.id, "name": d.directory_name, "url": d.directory_url,
                "type": d.listing_type, "status": d.status,
                "listing_url": d.listing_url, "notes": d.notes,
            } for d in directories],
            "totals": {
                "campaigns": len(campaigns), "active_campaigns": active_campaigns,
                "impressions": total_impressions, "clicks": total_clicks,
                "registrations": total_registrations, "revenue": total_revenue,
                "directories": len(directories), "active_listings": active_listings,
                "ctr": round(total_clicks / max(total_impressions, 1) * 100, 1),
            },
        }
