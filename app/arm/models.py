"""Agentic Relationship Management (ARM) — campaign tracking and outreach management.

Tracks all marketing initiatives, outreach campaigns, directory listings,
and viral growth efforts. Provides metrics, ROI tracking, and campaign
launch capabilities.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, String, Integer, Boolean, Text, JSON

from app.database.db import Base


class OutreachCampaign(Base):
    """An outreach or marketing campaign targeting agent discovery channels."""
    __tablename__ = "arm_campaigns"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_name = Column(String(200), nullable=False)
    campaign_type = Column(String(50), nullable=False)  # directory_listing, social_post, referral_drive, api_listing, content_marketing
    channel = Column(String(100), nullable=False)        # moltbook, smithery, github, glama, direct_outreach, etc.
    status = Column(String(30), default="active")        # draft, active, paused, completed, failed
    description = Column(Text, default="")
    target_audience = Column(String(200), default="")    # e.g. "AI agents on Moltbook", "MCP-enabled agents"
    content = Column(Text, default="")                   # The post/listing content
    url = Column(String(500), nullable=True)             # Link to the listing/post

    # Metrics
    impressions = Column(Integer, default=0)             # Views/reach
    clicks = Column(Integer, default=0)                  # Click-throughs
    registrations = Column(Integer, default=0)           # Agent registrations attributed
    conversions = Column(Integer, default=0)             # Completed transactions from this campaign
    spend = Column(Float, default=0.0)                   # Cost in ZAR
    revenue_attributed = Column(Float, default=0.0)      # Revenue generated

    # Tracking
    tracking_code = Column(String(50), nullable=True)    # UTM or referral code
    launched_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DirectoryListing(Base):
    """A platform listing on an external directory or registry."""
    __tablename__ = "arm_directory_listings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    directory_name = Column(String(100), nullable=False)
    directory_url = Column(String(500), nullable=False)
    listing_type = Column(String(50), nullable=False)    # mcp_server, api_directory, social_network, agent_registry
    status = Column(String(30), default="pending")       # pending, submitted, active, rejected, expired
    submission_date = Column(DateTime(timezone=True), nullable=True)
    approval_date = Column(DateTime(timezone=True), nullable=True)
    listing_url = Column(String(500), nullable=True)     # URL of our listing on their site
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
