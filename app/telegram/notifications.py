"""Telegram Notifications — push messages with inline action buttons."""

import logging

import httpx

from app.config import settings
from app.database.db import async_session
from app.telegram.auth import get_link_by_agent_id

logger = logging.getLogger("telegram.notifications")


async def notify_agent(agent_id: str, message: str, reply_markup: dict | None = None) -> bool:
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
            payload = {
                "chat_id": link.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML",
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=payload)

            if resp.status_code == 200:
                return True
            else:
                logger.warning(f"Telegram notify failed for {agent_id}: {resp.status_code}")
                return False

    except Exception as e:
        logger.error(f"Telegram notify error for {agent_id}: {e}")
        return False


async def notify_task_dispatched(
    agent_id: str, task_title: str,
    dispatch_id: str, sla_deadline: str | None = None
) -> bool:
    """Notify an agent that a task has been dispatched — with Accept/Reject buttons."""
    msg = (
        f"<b>📩 New Task Dispatched</b>\n\n"
        f"<b>{task_title}</b>\n"
    )
    if sla_deadline:
        msg += f"\n⏰ Deadline: {sla_deadline}"
    msg += "\n\nDo you want to accept this task?"

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Accept", "callback_data": f"accept:{dispatch_id}"},
                {"text": "🚫 Reject", "callback_data": f"reject:{dispatch_id}"},
            ],
            [
                {"text": "📋 View All Tasks", "callback_data": "refresh:status"},
            ],
        ]
    }
    return await notify_agent(agent_id, msg, reply_markup=keyboard)


async def notify_outcome_rated(agent_id: str, quality_rating: int, task_title: str) -> bool:
    """Notify an agent that their work has been rated — with reputation link."""
    stars = "★" * quality_rating + "☆" * (5 - quality_rating)
    emoji = "🌟" if quality_rating >= 4 else "⭐" if quality_rating >= 3 else "😔"
    msg = (
        f"<b>{emoji} Task Rated</b>\n\n"
        f"<b>{task_title}</b>\n"
        f"Rating: {stars} ({quality_rating}/5)"
    )
    keyboard = {
        "inline_keyboard": [
            [{"text": "⭐ View Reputation", "callback_data": "refresh:reputation"}],
        ]
    }
    return await notify_agent(agent_id, msg, reply_markup=keyboard)


async def notify_engagement_update(agent_id: str, engagement_id: str, new_state: str) -> bool:
    """Notify an agent of an engagement state change — with status link."""
    state_icons = {
        "PROPOSED": "📝", "NEGOTIATING": "🤝", "ACCEPTED": "✅",
        "FUNDED": "💰", "IN_PROGRESS": "⚡", "DELIVERED": "📦",
        "VERIFIED": "✔️", "COMPLETED": "🎉", "DISPUTED": "⚠️",
        "REFUNDED": "↩️", "RESOLVED": "✅",
    }
    icon = state_icons.get(new_state, "📌")
    msg = (
        f"<b>{icon} Engagement Update</b>\n\n"
        f"<code>{engagement_id[:8]}...</code> → <b>{new_state}</b>"
    )
    keyboard = {
        "inline_keyboard": [
            [{"text": "📋 View Engagements", "callback_data": "refresh:status"}],
        ]
    }
    return await notify_agent(agent_id, msg, reply_markup=keyboard)


async def notify_endorsement_received(agent_id: str, endorser_name: str, skill_tag: str) -> bool:
    """Notify an agent they received a peer endorsement."""
    msg = (
        f"<b>🤝 New Endorsement!</b>\n\n"
        f"<b>{endorser_name}</b> endorsed your skill:\n"
        f"<i>{skill_tag}</i>"
    )
    keyboard = {
        "inline_keyboard": [
            [{"text": "⭐ View Reputation", "callback_data": "refresh:reputation"}],
        ]
    }
    return await notify_agent(agent_id, msg, reply_markup=keyboard)
