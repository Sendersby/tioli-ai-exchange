"""Telegram Bot — SQLAlchemy models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String

from app.database.db import Base


class TelegramLink(Base):
    """Maps a Telegram user to a platform agent."""

    __tablename__ = "telegram_links"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_user_id = Column(BigInteger, unique=True, nullable=False)
    telegram_chat_id = Column(BigInteger, nullable=False)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    username = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)
    linked_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
