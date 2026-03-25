"""Outreach Campaign System — database models.

Manages the full campaign lifecycle:
- Campaigns: themes/goals with target channels and schedules
- Content: auto-generated posts ready for one-click share
- Actions: every outreach action taken (past, present, scheduled)
- Reports: performance tracking per campaign and per channel
- Feedback: what worked, what didn't, learn and iterate
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, Index
from app.database.db import Base

_uuid = lambda: str(uuid.uuid4())
_now = lambda: datetime.now(timezone.utc)


class OutreachCampaign(Base):
    """A campaign with theme, goals, target channels, and schedule."""
    __tablename__ = "outreach_campaigns"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    goal = Column(String(200), default="")  # e.g. "10 signups from Reddit", "MCP directory listing"
    status = Column(String(20), default="draft")  # draft, active, paused, completed, archived
    target_channels = Column(JSON, default=list)  # ["x_twitter", "linkedin", "reddit", "hackernews", "discord", "github", "email"]
    target_audience = Column(String(100), default="")  # "AI developers", "MCP users", "agent builders"
    start_date = Column(String(10), nullable=True)
    end_date = Column(String(10), nullable=True)
    budget_agentis = Column(Float, default=0)  # AGENTIS allocated for referral incentives
    kpi_target = Column(Integer, default=0)  # target metric (signups, impressions, etc.)
    kpi_actual = Column(Integer, default=0)  # actual achieved
    auto_generate = Column(Boolean, default=True)  # agents auto-generate content
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now)


class OutreachContent(Base):
    """A piece of content ready to post — auto-generated or manual."""
    __tablename__ = "outreach_content"
    __table_args__ = (
        Index("ix_outreach_content_campaign", "campaign_id"),
        Index("ix_outreach_content_status", "status"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    campaign_id = Column(String, nullable=True)  # links to campaign
    channel = Column(String(50), nullable=False)  # x_twitter, linkedin, reddit, hackernews, discord, github, email
    content_type = Column(String(30), default="post")  # post, thread, comment, email, dm
    title = Column(String(300), default="")  # for Reddit/HN — the headline
    body = Column(Text, nullable=False)  # the actual content to post
    hashtags = Column(JSON, default=list)
    target_url = Column(String(500), default="")  # where to post (subreddit URL, etc.)
    status = Column(String(20), default="draft")  # draft, approved, scheduled, posted, failed
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    posted_url = Column(String(500), default="")  # URL of the actual post after posting
    generated_by = Column(String(50), default="agent")  # agent, manual, hydra, catalyst
    performance = Column(JSON, default=dict)  # {views, clicks, reactions, comments, signups}
    ab_variant = Column(String(10), default="A")  # A/B testing
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now)


class OutreachAction(Base):
    """Every outreach action taken — past, present, future."""
    __tablename__ = "outreach_actions"

    id = Column(String, primary_key=True, default=_uuid)
    campaign_id = Column(String, nullable=True)
    content_id = Column(String, nullable=True)  # links to content piece
    action_type = Column(String(50), nullable=False)  # post_created, post_scheduled, post_published, directory_submitted, comment_posted, email_sent
    channel = Column(String(50), default="")
    description = Column(Text, default="")
    status = Column(String(20), default="completed")  # scheduled, in_progress, completed, failed
    result = Column(JSON, default=dict)  # outcome data
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    executed_at = Column(DateTime(timezone=True), default=_now)
    executed_by = Column(String(50), default="agent")  # agent name or "owner"


class OutreachReport(Base):
    """Campaign performance report — daily or per-campaign."""
    __tablename__ = "outreach_reports"

    id = Column(String, primary_key=True, default=_uuid)
    campaign_id = Column(String, nullable=True)
    report_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    channel_metrics = Column(JSON, default=dict)  # {channel: {posts, impressions, clicks, signups}}
    total_posts = Column(Integer, default=0)
    total_impressions = Column(Integer, default=0)
    total_signups = Column(Integer, default=0)
    directory_submissions = Column(Integer, default=0)
    directory_accepted = Column(Integer, default=0)
    github_comments = Column(Integer, default=0)
    insights = Column(JSON, default=list)  # AI-generated insights
    created_at = Column(DateTime(timezone=True), default=_now)
