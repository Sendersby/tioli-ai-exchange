"""Campaign Scheduler — auto-queues content across channels on a rolling schedule.

Creates a content calendar that:
- Auto-generates and schedules content for the week ahead
- Distributes posts across channels evenly (no spam)
- Respects optimal posting times per channel
- Tracks what's upcoming, overdue, and completed
- Generates posting reminders
- Supports recurring campaigns (daily, weekly)
"""

import random
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.outreach_campaigns.models import OutreachCampaign, OutreachContent, OutreachAction
from app.outreach_campaigns.content_generator import generate_batch

logger = logging.getLogger("tioli.campaign_scheduler")

# Optimal posting times per channel (UTC hours)
OPTIMAL_TIMES = {
    "x_twitter": [14, 16, 18],       # 2pm-6pm UTC (US morning/EU afternoon)
    "linkedin": [8, 10, 12],          # 8am-12pm UTC (business hours)
    "reddit": [13, 15, 17],           # 1pm-5pm UTC
    "discord": [15, 17, 19],          # 3pm-7pm UTC
    "hackernews": [14, 16],           # 2pm-4pm UTC
    "email": [9, 11],                 # 9am-11am UTC
}

# Max posts per channel per day (avoid spam)
MAX_PER_DAY = {
    "x_twitter": 2,
    "linkedin": 1,
    "reddit": 1,
    "discord": 1,
    "hackernews": 1,
    "email": 1,
}

# Days of week best for each channel (0=Mon, 6=Sun)
BEST_DAYS = {
    "x_twitter": [0, 1, 2, 3, 4],    # Weekdays
    "linkedin": [1, 2, 3],            # Tue-Thu
    "reddit": [0, 1, 2, 3, 4],       # Weekdays
    "discord": [0, 1, 2, 3, 4, 5],   # Mon-Sat
    "hackernews": [0, 1, 2, 3],      # Mon-Thu
    "email": [1, 3],                  # Tue, Thu
}


async def auto_schedule_week(db: AsyncSession, campaign_id: str = None) -> list[dict]:
    """Auto-schedule content for the next 7 days across all channels.

    Generates content if needed, then assigns optimal posting slots.
    Returns list of scheduled items.
    """
    now = datetime.now(timezone.utc)
    scheduled = []

    # Get or create active campaign
    if campaign_id:
        result = await db.execute(
            select(OutreachCampaign).where(OutreachCampaign.id == campaign_id)
        )
        campaign = result.scalar_one_or_none()
    else:
        # Use most recent active campaign or create one
        result = await db.execute(
            select(OutreachCampaign).where(OutreachCampaign.status == "active")
            .order_by(OutreachCampaign.created_at.desc()).limit(1)
        )
        campaign = result.scalar_one_or_none()
        if not campaign:
            campaign = OutreachCampaign(
                name=f"Auto-Schedule Week of {now.strftime('%d %b')}",
                description="Auto-generated weekly campaign",
                goal="Agent signups and platform awareness",
                status="active",
                target_channels=list(OPTIMAL_TIMES.keys()),
                auto_generate=True,
            )
            db.add(campaign)
            await db.flush()

    # For each day in the next 7 days
    for day_offset in range(7):
        target_date = now + timedelta(days=day_offset)
        weekday = target_date.weekday()

        for channel, best_days in BEST_DAYS.items():
            if weekday not in best_days:
                continue

            # Check how many already scheduled for this day+channel
            day_start = target_date.replace(hour=0, minute=0, second=0)
            day_end = day_start + timedelta(days=1)
            existing = (await db.execute(
                select(func.count(OutreachContent.id)).where(
                    OutreachContent.channel == channel,
                    OutreachContent.scheduled_for >= day_start,
                    OutreachContent.scheduled_for < day_end,
                    OutreachContent.status.in_(["scheduled", "approved"]),
                )
            )).scalar() or 0

            max_daily = MAX_PER_DAY.get(channel, 1)
            if existing >= max_daily:
                continue

            # Pick a posting time
            hour = random.choice(OPTIMAL_TIMES.get(channel, [14]))
            post_time = target_date.replace(hour=hour, minute=random.randint(0, 45), second=0)

            if post_time <= now:
                continue  # Don't schedule in the past

            # Check if we have draft content for this channel
            draft = (await db.execute(
                select(OutreachContent).where(
                    OutreachContent.channel == channel,
                    OutreachContent.status == "draft",
                    OutreachContent.scheduled_for.is_(None),
                ).order_by(OutreachContent.created_at.desc()).limit(1)
            )).scalar_one_or_none()

            if not draft:
                # Generate new content
                from app.outreach_campaigns.content_generator import (
                    generate_twitter_post, generate_linkedin_post,
                    generate_reddit_post, generate_discord_message,
                )
                generators = {
                    "x_twitter": generate_twitter_post,
                    "linkedin": generate_linkedin_post,
                    "discord": generate_discord_message,
                }
                gen = generators.get(channel)
                if gen:
                    draft = await gen(db, campaign.id)
                    await db.flush()
                elif channel == "reddit":
                    subs = ["ClaudeAI", "LocalLLaMA", "artificial"]
                    draft = await generate_reddit_post(db, campaign.id, random.choice(subs))
                    await db.flush()
                else:
                    continue

            # Schedule it
            draft.status = "scheduled"
            draft.scheduled_for = post_time
            draft.campaign_id = campaign.id
            await db.flush()

            scheduled.append({
                "content_id": draft.id, "channel": draft.channel,
                "title": draft.title, "scheduled_for": str(post_time),
                "day": target_date.strftime("%A %d %b"),
            })

    # Log the scheduling action
    if scheduled:
        db.add(OutreachAction(
            campaign_id=campaign.id, action_type="week_scheduled",
            description=f"Auto-scheduled {len(scheduled)} posts for the next 7 days",
            result={"count": len(scheduled)},
            executed_by="campaign_scheduler",
        ))

    return scheduled


async def get_calendar(db: AsyncSession, days_ahead: int = 14, days_behind: int = 7) -> dict:
    """Get the full campaign calendar — past, present, future."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days_behind)
    end = now + timedelta(days=days_ahead)

    result = await db.execute(
        select(OutreachContent).where(
            OutreachContent.scheduled_for.isnot(None),
            OutreachContent.scheduled_for >= start,
            OutreachContent.scheduled_for <= end,
        ).order_by(OutreachContent.scheduled_for)
    )
    items = result.scalars().all()

    # Group by date
    calendar = {}
    for item in items:
        date_key = item.scheduled_for.strftime("%Y-%m-%d") if item.scheduled_for else "unscheduled"
        if date_key not in calendar:
            calendar[date_key] = []
        calendar[date_key].append({
            "content_id": item.id, "channel": item.channel,
            "title": item.title, "body": item.body[:150],
            "status": item.status,
            "scheduled_for": str(item.scheduled_for),
            "posted_at": str(item.posted_at) if item.posted_at else None,
            "posted_url": item.posted_url,
        })

    # Overdue items
    overdue = [
        {
            "content_id": item.id, "channel": item.channel, "title": item.title,
            "scheduled_for": str(item.scheduled_for), "status": item.status,
        }
        for item in items
        if item.scheduled_for and item.scheduled_for < now and item.status == "scheduled"
    ]

    # Upcoming (next 3 days)
    three_days = now + timedelta(days=3)
    upcoming = [
        {
            "content_id": item.id, "channel": item.channel, "title": item.title,
            "body": item.body[:200], "status": item.status,
            "scheduled_for": str(item.scheduled_for),
            "day": item.scheduled_for.strftime("%A %d %b") if item.scheduled_for else "",
            "time": item.scheduled_for.strftime("%H:%M UTC") if item.scheduled_for else "",
        }
        for item in items
        if item.scheduled_for and now <= item.scheduled_for <= three_days
        and item.status in ("scheduled", "approved")
    ]

    # Stats
    total_scheduled = sum(1 for i in items if i.status == "scheduled")
    total_posted = sum(1 for i in items if i.status == "posted")

    return {
        "calendar": calendar,
        "overdue": overdue,
        "upcoming": upcoming,
        "stats": {
            "total_scheduled": total_scheduled,
            "total_posted": total_posted,
            "overdue_count": len(overdue),
            "upcoming_3d": len(upcoming),
            "days_covered": len(calendar),
        },
        "period": {"start": str(start), "end": str(end)},
    }


async def get_reminders(db: AsyncSession) -> list[dict]:
    """Get posting reminders — items due in the next 2 hours."""
    now = datetime.now(timezone.utc)
    two_hours = now + timedelta(hours=2)

    result = await db.execute(
        select(OutreachContent).where(
            OutreachContent.scheduled_for >= now,
            OutreachContent.scheduled_for <= two_hours,
            OutreachContent.status.in_(["scheduled", "approved"]),
        ).order_by(OutreachContent.scheduled_for)
    )
    return [
        {
            "content_id": item.id, "channel": item.channel,
            "title": item.title, "body": item.body,
            "scheduled_for": str(item.scheduled_for),
            "time_until": str(item.scheduled_for - now).split(".")[0],
            "urgent": (item.scheduled_for - now).total_seconds() < 1800,
        }
        for item in result.scalars().all()
    ]


async def run_scheduler_cycle():
    """Scheduled job: auto-schedule content + check for overdue items."""
    from app.database.db import async_session
    try:
        async with async_session() as db:
            # Auto-schedule if less than 5 items scheduled for coming week
            now = datetime.now(timezone.utc)
            week_ahead = now + timedelta(days=7)
            scheduled_count = (await db.execute(
                select(func.count(OutreachContent.id)).where(
                    OutreachContent.scheduled_for >= now,
                    OutreachContent.scheduled_for <= week_ahead,
                    OutreachContent.status.in_(["scheduled", "approved"]),
                )
            )).scalar() or 0

            if scheduled_count < 5:
                results = await auto_schedule_week(db)
                if results:
                    logger.info(f"Campaign scheduler: auto-scheduled {len(results)} posts")

            await db.commit()
    except Exception as e:
        logger.error(f"Campaign scheduler failed: {e}")
