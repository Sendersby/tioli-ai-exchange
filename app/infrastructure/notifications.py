"""Notification system — alerts, rate warnings, and governance inbox.

Section 6.1: "Owner should never need to hunt for pending decisions.
Push alerts for time-sensitive governance items."
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Boolean, Integer, Text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base


class Notification(Base):
    """A notification for the platform owner or an operator/agent."""
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    recipient_id = Column(String, nullable=False)        # "owner", operator_id, or agent_id
    recipient_type = Column(String(20), nullable=False)  # "owner", "operator", "agent"
    category = Column(String(50), nullable=False)        # governance, security, financial, system
    severity = Column(String(20), default="info")        # info, warning, urgent, critical
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    action_url = Column(String(500), nullable=True)      # Link to relevant dashboard page
    is_read = Column(Boolean, default=False)
    is_dismissed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    read_at = Column(DateTime, nullable=True)


class NotificationService:
    """Manages notifications and alerts."""

    async def send(
        self, db: AsyncSession, recipient_id: str, recipient_type: str,
        category: str, title: str, message: str,
        severity: str = "info", action_url: str | None = None
    ) -> Notification:
        """Send a notification."""
        notif = Notification(
            recipient_id=recipient_id,
            recipient_type=recipient_type,
            category=category,
            severity=severity,
            title=title,
            message=message,
            action_url=action_url,
        )
        db.add(notif)
        await db.flush()
        return notif

    async def notify_owner(
        self, db: AsyncSession, category: str, title: str,
        message: str, severity: str = "info", action_url: str | None = None
    ) -> Notification:
        """Send a notification to the platform owner."""
        return await self.send(
            db, "owner", "owner", category, title, message, severity, action_url
        )

    async def get_notifications(
        self, db: AsyncSession, recipient_id: str,
        unread_only: bool = False, limit: int = 50
    ) -> list[dict]:
        """Get notifications for a recipient."""
        query = select(Notification).where(
            Notification.recipient_id == recipient_id,
            Notification.is_dismissed == False,
        )
        if unread_only:
            query = query.where(Notification.is_read == False)
        query = query.order_by(Notification.created_at.desc()).limit(limit)

        result = await db.execute(query)
        return [
            {
                "id": n.id, "category": n.category, "severity": n.severity,
                "title": n.title, "message": n.message,
                "action_url": n.action_url, "is_read": n.is_read,
                "created_at": str(n.created_at),
            }
            for n in result.scalars().all()
        ]

    async def mark_read(self, db: AsyncSession, notification_id: str) -> None:
        result = await db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        notif = result.scalar_one_or_none()
        if notif:
            notif.is_read = True
            notif.read_at = datetime.now(timezone.utc)
            await db.flush()

    async def get_unread_count(
        self, db: AsyncSession, recipient_id: str
    ) -> int:
        result = await db.execute(
            select(func.count(Notification.id)).where(
                Notification.recipient_id == recipient_id,
                Notification.is_read == False,
                Notification.is_dismissed == False,
            )
        )
        return result.scalar() or 0
