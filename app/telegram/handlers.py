"""Telegram Bot — Command handlers.

Commands:
  /start          — Welcome message and link instructions
  /link <api_key> — Link Telegram to an agent account
  /unlink         — Unlink Telegram from agent
  /discover <q>   — Search agents by capability
  /status         — List active engagements
  /wallet         — Show balance
  /reputation     — View reputation score
  /help           — List all commands
"""

import logging

from app.config import settings
from app.database.db import async_session

logger = logging.getLogger("telegram.handlers")


async def handle_start(telegram_user_id: int, chat_id: int, args: str) -> str:
    """Welcome message."""
    return (
        "Welcome to TiOLi AGENTIS Exchange!\n\n"
        "Link your agent account to interact via Telegram.\n\n"
        "Commands:\n"
        "/link <your_api_key> — Connect your agent\n"
        "/discover <query> — Find agents by skill\n"
        "/status — Your active tasks\n"
        "/wallet — Check balance\n"
        "/reputation — Your reputation score\n"
        "/help — All commands"
    )


async def handle_link(telegram_user_id: int, chat_id: int, args: str, username: str | None = None) -> str:
    """Link Telegram user to agent via API key."""
    api_key = args.strip()
    if not api_key:
        return "Usage: /link <your_api_key>\n\nFind your API key in your agent dashboard."

    async with async_session() as db:
        from app.agents.auth import authenticate_agent
        agent = await authenticate_agent(db, api_key)
        if not agent:
            return "Invalid API key. Check your agent dashboard for the correct key."

        from app.telegram.auth import link_agent
        link = await link_agent(db, telegram_user_id, chat_id, agent.id, username=username)
        await db.commit()

        return f"Linked to agent: {agent.name}\nYou can now use all commands."


async def handle_unlink(telegram_user_id: int, chat_id: int, args: str) -> str:
    """Unlink Telegram from agent."""
    async with async_session() as db:
        from app.telegram.auth import get_link_by_telegram_id, unlink_agent
        link = await get_link_by_telegram_id(db, telegram_user_id)
        if not link:
            return "No linked agent found."

        await unlink_agent(db, link.agent_id)
        await db.commit()
        return "Agent unlinked. Use /link to connect again."


async def handle_discover(telegram_user_id: int, chat_id: int, args: str) -> str:
    """Search agents by capability."""
    query = args.strip()
    if not query:
        return "Usage: /discover <skill or keyword>\n\nExample: /discover translation"

    async with async_session() as db:
        from sqlalchemy import select, or_
        from app.agentbroker.models import AgentServiceProfile

        result = await db.execute(
            select(AgentServiceProfile).where(
                AgentServiceProfile.is_active.is_(True),
                or_(
                    AgentServiceProfile.service_title.ilike(f"%{query}%"),
                    AgentServiceProfile.description.ilike(f"%{query}%"),
                ),
            ).limit(5)
        )
        profiles = result.scalars().all()

        if not profiles:
            return f"No agents found for '{query}'. Try a different keyword."

        lines = [f"Agents matching '{query}':\n"]
        for p in profiles:
            price = getattr(p, "base_price", None) or getattr(p, "price", "N/A")
            lines.append(f"  {p.service_title}\n  Agent: {p.agent_id}\n  Price: {price} AGENTIS\n")

        return "\n".join(lines)


async def handle_status(telegram_user_id: int, chat_id: int, args: str) -> str:
    """List active engagements for the linked agent."""
    async with async_session() as db:
        link = await _get_link(db, telegram_user_id)
        if not link:
            return "Not linked. Use /link <api_key> first."

        from sqlalchemy import select
        from app.agentbroker.models import AgentEngagement

        result = await db.execute(
            select(AgentEngagement).where(
                AgentEngagement.provider_agent_id == link.agent_id,
                AgentEngagement.current_state.in_(
                    ["PROPOSED", "NEGOTIATING", "ACCEPTED", "FUNDED", "IN_PROGRESS"]
                ),
            ).limit(10)
        )
        engagements = result.scalars().all()

        if not engagements:
            return "No active engagements."

        lines = ["Active engagements:\n"]
        for e in engagements:
            lines.append(f"  {e.engagement_id[:8]}... — {e.current_state}")

        return "\n".join(lines)


async def handle_wallet(telegram_user_id: int, chat_id: int, args: str) -> str:
    """Show wallet balance."""
    async with async_session() as db:
        link = await _get_link(db, telegram_user_id)
        if not link:
            return "Not linked. Use /link <api_key> first."

        from sqlalchemy import select
        from app.agents.models import Wallet

        result = await db.execute(
            select(Wallet).where(Wallet.agent_id == link.agent_id)
        )
        wallets = result.scalars().all()

        if not wallets:
            return "No wallets found."

        lines = ["Wallet balances:\n"]
        for w in wallets:
            lines.append(f"  {w.currency}: {w.balance:.2f}")

        return "\n".join(lines)


async def handle_reputation(telegram_user_id: int, chat_id: int, args: str) -> str:
    """View reputation score."""
    async with async_session() as db:
        # Check if querying own or another agent
        agent_id = args.strip() if args.strip() else None

        if not agent_id:
            link = await _get_link(db, telegram_user_id)
            if not link:
                return "Not linked. Use /link <api_key> first, or: /reputation <agent_id>"
            agent_id = link.agent_id

        from sqlalchemy import select
        from app.agentbroker.models import AgentReputationScore

        result = await db.execute(
            select(AgentReputationScore).where(
                AgentReputationScore.agent_id == agent_id
            )
        )
        score = result.scalar_one_or_none()

        if not score:
            return f"No reputation data for agent {agent_id[:8]}..."

        return (
            f"Reputation for {agent_id[:8]}...\n\n"
            f"  Overall: {score.overall_score:.1f}/10\n"
            f"  Delivery: {score.delivery_rate:.1f}/10\n"
            f"  On-time: {score.on_time_rate:.1f}/10\n"
            f"  Disputes: {score.dispute_rate:.1f}/10\n"
            f"  Volume: {score.volume_multiplier:.1f}/10\n"
            f"  Engagements: {score.total_engagements}\n"
            f"  Completed: {score.total_completed}"
        )


async def handle_help(telegram_user_id: int, chat_id: int, args: str) -> str:
    """List all commands."""
    return (
        "TiOLi AGENTIS Telegram Bot\n\n"
        "/start — Welcome\n"
        "/link <api_key> — Link your agent\n"
        "/unlink — Disconnect agent\n"
        "/discover <query> — Find agents\n"
        "/status — Active engagements\n"
        "/wallet — Check balance\n"
        "/reputation [agent_id] — View score\n"
        "/help — This message"
    )


# ----- Internal helpers -----

async def _get_link(db, telegram_user_id: int):
    from app.telegram.auth import get_link_by_telegram_id
    return await get_link_by_telegram_id(db, telegram_user_id)


# Command dispatch map
COMMAND_HANDLERS = {
    "start": handle_start,
    "link": handle_link,
    "unlink": handle_unlink,
    "discover": handle_discover,
    "status": handle_status,
    "wallet": handle_wallet,
    "reputation": handle_reputation,
    "help": handle_help,
}
