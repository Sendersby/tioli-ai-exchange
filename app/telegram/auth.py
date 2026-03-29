"""Telegram-to-Agent linking and authentication."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.telegram.models import TelegramLink


async def link_agent(
    db: AsyncSession,
    telegram_user_id: int,
    telegram_chat_id: int,
    agent_id: str,
    username: str | None = None,
) -> TelegramLink:
    """Link a Telegram user to a platform agent."""

    # Check if already linked
    result = await db.execute(
        select(TelegramLink).where(
            TelegramLink.telegram_user_id == telegram_user_id
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.agent_id = agent_id
        existing.telegram_chat_id = telegram_chat_id
        existing.username = username
        existing.is_active = True
        return existing

    link = TelegramLink(
        id=str(uuid.uuid4()),
        telegram_user_id=telegram_user_id,
        telegram_chat_id=telegram_chat_id,
        agent_id=agent_id,
        username=username,
        is_active=True,
    )
    db.add(link)
    return link


async def get_link_by_telegram_id(
    db: AsyncSession, telegram_user_id: int
) -> TelegramLink | None:
    """Find a TelegramLink by Telegram user ID."""
    result = await db.execute(
        select(TelegramLink).where(
            TelegramLink.telegram_user_id == telegram_user_id,
            TelegramLink.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def get_link_by_agent_id(
    db: AsyncSession, agent_id: str
) -> TelegramLink | None:
    """Find a TelegramLink by agent ID."""
    result = await db.execute(
        select(TelegramLink).where(
            TelegramLink.agent_id == agent_id,
            TelegramLink.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def unlink_agent(db: AsyncSession, agent_id: str) -> bool:
    """Deactivate the Telegram link for an agent."""
    result = await db.execute(
        select(TelegramLink).where(TelegramLink.agent_id == agent_id)
    )
    link = result.scalar_one_or_none()
    if link:
        link.is_active = False
        return True
    return False
