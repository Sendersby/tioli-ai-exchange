"""Telegram Notifications — push messages to agents via Telegram."""

import logging

import httpx

from app.config import settings
from app.database.db import async_session
from app.telegram.auth import get_link_by_agent_id

logger = logging.getLogger("telegram.notifications")


async def notify_agent(agent_id: str, message: str) -> bool:
    """Send a Telegram message to an agent if they have a linked account.

    Returns True if sent successfully, False otherwise.
    Fire-and-forget — never raises exceptions.
    """
    if not settings.telegram_bot_enabled or not settings.telegram_bot_token:
        return False

    try:
        async with async_session() as db:
            link = await get_link_by_agent_id(db, agent_id)
            if not link:
                return False

            url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json={
                    "chat_id": link.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                })

            if resp.status_code == 200:
                return True
            else:
                logger.warning(f"Telegram notify failed for {agent_id}: {resp.status_code}")
                return False

    except Exception as e:
        logger.error(f"Telegram notify error for {agent_id}: {e}")
        return False


async def notify_task_dispatched(agent_id: str, task_title: str, sla_deadline: str | None = None) -> bool:
    """Notify an agent that a task has been dispatched to them."""
    msg = f"<b>New Task Dispatched</b>\n\n{task_title}"
    if sla_deadline:
        msg += f"\n\nDeadline: {sla_deadline}"
    msg += "\n\nUse /status to view your tasks."
    return await notify_agent(agent_id, msg)


async def notify_outcome_rated(agent_id: str, quality_rating: int, task_title: str) -> bool:
    """Notify an agent that their work has been rated."""
    stars = "★" * quality_rating + "☆" * (5 - quality_rating)
    msg = f"<b>Task Rated</b>\n\n{task_title}\nRating: {stars} ({quality_rating}/5)"
    return await notify_agent(agent_id, msg)


async def notify_engagement_update(agent_id: str, engagement_id: str, new_state: str) -> bool:
    """Notify an agent of an engagement state change."""
    msg = f"<b>Engagement Update</b>\n\n{engagement_id[:8]}... → {new_state}"
    return await notify_agent(agent_id, msg)
