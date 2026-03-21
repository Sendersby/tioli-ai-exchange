"""Webhook service — notify agent systems when events occur.

Agents register webhook URLs for specific events. When those events fire,
the platform POSTs a JSON payload to the registered URL.
"""

import uuid
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import Column, DateTime, String, Integer, Boolean, Text, JSON, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base

logger = logging.getLogger("tioli.webhooks")

WEBHOOK_EVENTS = [
    "engagement.created", "engagement.funded", "engagement.delivered",
    "engagement.completed", "engagement.disputed",
    "transfer.received", "transfer.sent",
    "referral.used", "message.received",
    "guild.joined", "proposal.voted",
]


class WebhookRegistration(Base):
    __tablename__ = "webhook_registrations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, nullable=False)
    url = Column(String(500), nullable=False)
    events = Column(JSON, nullable=False)  # list of event types
    is_active = Column(Boolean, default=True)
    failures = Column(Integer, default=0)
    last_triggered = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    registration_id = Column(String, nullable=False)
    event = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    status_code = Column(Integer, nullable=True)
    success = Column(Boolean, default=False)
    error = Column(Text, nullable=True)
    delivered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class WebhookService:
    async def register(
        self, db: AsyncSession, agent_id: str, url: str, events: list[str],
    ) -> dict:
        invalid = [e for e in events if e not in WEBHOOK_EVENTS]
        if invalid:
            raise ValueError(f"Invalid events: {invalid}. Valid: {WEBHOOK_EVENTS}")
        if not url.startswith("https://"):
            raise ValueError("Webhook URL must use HTTPS")

        reg = WebhookRegistration(agent_id=agent_id, url=url, events=events)
        db.add(reg)
        await db.flush()
        return {"webhook_id": reg.id, "url": url, "events": events, "status": "active"}

    async def list_webhooks(self, db: AsyncSession, agent_id: str) -> list[dict]:
        result = await db.execute(
            select(WebhookRegistration).where(
                WebhookRegistration.agent_id == agent_id,
                WebhookRegistration.is_active == True,
            )
        )
        return [
            {"id": w.id, "url": w.url, "events": w.events, "failures": w.failures}
            for w in result.scalars().all()
        ]

    async def delete_webhook(self, db: AsyncSession, webhook_id: str, agent_id: str) -> bool:
        result = await db.execute(
            select(WebhookRegistration).where(
                WebhookRegistration.id == webhook_id,
                WebhookRegistration.agent_id == agent_id,
            )
        )
        reg = result.scalar_one_or_none()
        if not reg:
            return False
        reg.is_active = False
        await db.flush()
        return True

    async def trigger(
        self, db: AsyncSession, event: str, agent_id: str, payload: dict,
    ) -> int:
        """Fire webhooks for an event. Returns count of deliveries attempted."""
        result = await db.execute(
            select(WebhookRegistration).where(
                WebhookRegistration.agent_id == agent_id,
                WebhookRegistration.is_active == True,
            )
        )
        registrations = result.scalars().all()
        delivered = 0

        for reg in registrations:
            if event not in (reg.events or []):
                continue

            delivery = WebhookDelivery(
                registration_id=reg.id, event=event, payload=payload,
            )

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(
                        reg.url,
                        json={"event": event, "agent_id": agent_id, "data": payload,
                              "timestamp": datetime.now(timezone.utc).isoformat()},
                        headers={"X-TiOLi-Event": event, "Content-Type": "application/json"},
                    )
                delivery.status_code = resp.status_code
                delivery.success = 200 <= resp.status_code < 300
                if not delivery.success:
                    reg.failures += 1
                reg.last_triggered = datetime.now(timezone.utc)
            except Exception as e:
                delivery.error = str(e)[:500]
                delivery.success = False
                reg.failures += 1

            # Disable after 10 consecutive failures
            if reg.failures >= 10:
                reg.is_active = False
                logger.warning(f"Webhook disabled after 10 failures: {reg.url}")

            db.add(delivery)
            delivered += 1

        await db.flush()
        return delivered

    async def get_available_events(self) -> list[str]:
        return WEBHOOK_EVENTS
