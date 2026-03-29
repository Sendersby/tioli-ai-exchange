"""Telegram Bot — Command handlers with inline keyboards and rich formatting.

Commands:
  /start          — Welcome message with quick-action buttons
  /link <api_key> — Link Telegram to an agent account
  /unlink         — Unlink Telegram from agent
  /discover <q>   — Search agents with inline engage buttons
  /status         — Active engagements with action buttons
  /wallet         — Balance with refresh button
  /reputation     — Reputation card with history button
  /profile        — View your agent profile summary
  /help           — All commands with quick-action buttons

Callback queries (inline button presses):
  accept:<dispatch_id>  — Accept a dispatched task
  reject:<dispatch_id>  — Reject a dispatched task
  refresh:wallet        — Refresh wallet balance
  refresh:status        — Refresh engagement status
  refresh:reputation    — Refresh reputation score
  engage:<profile_id>   — Start engagement with agent
"""

import logging

from app.config import settings
from app.database.db import async_session

logger = logging.getLogger("telegram.handlers")


# ─── Inline keyboard builder ───────────────────────────────────────

def _button(text: str, callback_data: str) -> dict:
    return {"text": text, "callback_data": callback_data}


def _url_button(text: str, url: str) -> dict:
    return {"text": text, "url": url}


def _keyboard(*rows) -> dict:
    """Build an inline_keyboard from rows of buttons."""
    return {"inline_keyboard": list(rows)}


# ─── Command handlers ──────────────────────────────────────────────

async def handle_start(telegram_user_id: int, chat_id: int, args: str) -> dict:
    """Welcome message with quick-action buttons."""
    return {
        "text": (
            "<b>Welcome to TiOLi AGENTIS Exchange</b>\n\n"
            "The world's first AI agent trading platform.\n\n"
            "Link your agent account to get started, "
            "or explore the marketplace right away.\n\n"
            "<i>Type /help for all commands.</i>"
        ),
        "reply_markup": _keyboard(
            [_button("🔗 Link Account", "prompt:link"), _button("🔍 Discover Agents", "prompt:discover")],
            [_button("📊 View Reputation", "prompt:reputation"), _button("❓ Help", "prompt:help")],
            [_url_button("🌐 Open Exchange", "https://exchange.tioli.co.za")],
        ),
    }


async def handle_link(telegram_user_id: int, chat_id: int, args: str, username: str | None = None) -> dict:
    """Link Telegram user to agent via API key."""
    api_key = args.strip()
    if not api_key:
        return {
            "text": (
                "<b>Link Your Agent</b>\n\n"
                "Usage: <code>/link YOUR_API_KEY</code>\n\n"
                "Find your API key in your agent dashboard at "
                "exchange.tioli.co.za under your profile settings."
            ),
        }

    async with async_session() as db:
        from app.agents.auth import authenticate_agent
        agent = await authenticate_agent(db, api_key)
        if not agent:
            return {"text": "❌ Invalid API key. Check your agent dashboard for the correct key."}

        from app.telegram.auth import link_agent
        await link_agent(db, telegram_user_id, chat_id, agent.id, username=username)
        await db.commit()

        return {
            "text": (
                f"✅ <b>Linked successfully!</b>\n\n"
                f"Agent: <b>{agent.name}</b>\n"
                f"Platform: {agent.platform}\n\n"
                f"You'll now receive notifications here."
            ),
            "reply_markup": _keyboard(
                [_button("💰 My Wallet", "refresh:wallet"), _button("📋 My Status", "refresh:status")],
                [_button("⭐ My Reputation", "refresh:reputation")],
            ),
        }


async def handle_unlink(telegram_user_id: int, chat_id: int, args: str) -> dict:
    """Unlink Telegram from agent."""
    async with async_session() as db:
        from app.telegram.auth import get_link_by_telegram_id, unlink_agent
        link = await get_link_by_telegram_id(db, telegram_user_id)
        if not link:
            return {"text": "No linked agent found."}

        await unlink_agent(db, link.agent_id)
        await db.commit()
        return {"text": "✅ Agent unlinked.\n\nUse /link to connect again."}


async def handle_discover(telegram_user_id: int, chat_id: int, args: str) -> dict:
    """Search agents with inline engage buttons."""
    query = args.strip()
    if not query:
        return {
            "text": (
                "<b>Discover Agents</b>\n\n"
                "Usage: <code>/discover SKILL</code>\n\n"
                "Examples:\n"
                "  /discover translation\n"
                "  /discover security\n"
                "  /discover research\n"
                "  /discover code"
            ),
        }

    async with async_session() as db:
        from sqlalchemy import select, or_
        from app.agentbroker.models import AgentServiceProfile, AgentReputationScore
        from app.agents.models import Agent

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
            return {"text": f"No agents found for '<b>{query}</b>'.\n\nTry a different keyword."}

        lines = [f"<b>Agents matching '{query}'</b>\n"]
        buttons = []

        for p in profiles:
            # Get agent name
            agent_result = await db.execute(select(Agent.name).where(Agent.id == p.agent_id))
            agent_name = agent_result.scalar() or p.agent_id[:12]

            # Get reputation
            rep_result = await db.execute(
                select(AgentReputationScore.overall_score).where(
                    AgentReputationScore.agent_id == p.agent_id
                )
            )
            rep_score = rep_result.scalar()
            rep_str = f"⭐ {rep_score:.1f}/10" if rep_score else "⭐ New"

            price = getattr(p, "base_price", None) or getattr(p, "price", None)
            price_str = f"💰 {price} AGENTIS" if price else "💰 Negotiable"

            lines.append(
                f"\n<b>{agent_name}</b>\n"
                f"  {p.service_title}\n"
                f"  {rep_str}  •  {price_str}"
            )
            buttons.append([_button(f"📩 Engage {agent_name}", f"engage:{p.profile_id}")])

        return {
            "text": "\n".join(lines),
            "reply_markup": _keyboard(*buttons) if buttons else None,
        }


async def handle_status(telegram_user_id: int, chat_id: int, args: str) -> dict:
    """List active engagements with action buttons."""
    async with async_session() as db:
        link = await _get_link(db, telegram_user_id)
        if not link:
            return {"text": "Not linked. Use /link <code>api_key</code> first."}

        from sqlalchemy import select
        from app.agentbroker.models import AgentEngagement
        from app.agents.models import Agent

        result = await db.execute(
            select(AgentEngagement).where(
                AgentEngagement.provider_agent_id == link.agent_id,
                AgentEngagement.current_state.in_(
                    ["PROPOSED", "NEGOTIATING", "ACCEPTED", "FUNDED", "IN_PROGRESS", "DELIVERED"]
                ),
            ).limit(10)
        )
        engagements = result.scalars().all()

        if not engagements:
            return {
                "text": "📋 <b>No active engagements</b>\n\nUse /discover to find agents and start working.",
                "reply_markup": _keyboard(
                    [_button("🔍 Discover Agents", "prompt:discover"), _button("🔄 Refresh", "refresh:status")],
                ),
            }

        status_icons = {
            "PROPOSED": "📝", "NEGOTIATING": "🤝", "ACCEPTED": "✅",
            "FUNDED": "💰", "IN_PROGRESS": "⚡", "DELIVERED": "📦",
        }

        lines = ["<b>Active Engagements</b>\n"]
        for e in engagements:
            # Get client name
            client_result = await db.execute(select(Agent.name).where(Agent.id == e.client_agent_id))
            client_name = client_result.scalar() or e.client_agent_id[:8]
            icon = status_icons.get(e.current_state, "📌")
            lines.append(f"\n{icon} <code>{e.engagement_id[:8]}</code> — <b>{e.current_state}</b>\n   Client: {client_name}")

        return {
            "text": "\n".join(lines),
            "reply_markup": _keyboard([_button("🔄 Refresh", "refresh:status")]),
        }


async def handle_wallet(telegram_user_id: int, chat_id: int, args: str) -> dict:
    """Show wallet balance with formatted display."""
    async with async_session() as db:
        link = await _get_link(db, telegram_user_id)
        if not link:
            return {"text": "Not linked. Use /link <code>api_key</code> first."}

        from sqlalchemy import select
        from app.agents.models import Wallet

        result = await db.execute(
            select(Wallet).where(Wallet.agent_id == link.agent_id)
        )
        wallets = result.scalars().all()

        if not wallets:
            return {"text": "💰 <b>No wallets</b>\n\nYour wallet will be created on your first transaction."}

        total = sum(w.balance for w in wallets)
        lines = ["<b>💰 Wallet Balances</b>\n"]
        for w in wallets:
            frozen = f"  (🔒 {w.frozen_balance:.2f} frozen)" if hasattr(w, 'frozen_balance') and w.frozen_balance else ""
            lines.append(f"\n  <b>{w.currency}</b>: <code>{w.balance:.4f}</code>{frozen}")

        lines.append(f"\n\n<b>Total</b>: <code>{total:.4f}</code>")

        return {
            "text": "\n".join(lines),
            "reply_markup": _keyboard([_button("🔄 Refresh", "refresh:wallet")]),
        }


async def handle_reputation(telegram_user_id: int, chat_id: int, args: str) -> dict:
    """Reputation card with visual score display."""
    async with async_session() as db:
        agent_id = args.strip() if args.strip() else None

        if not agent_id:
            link = await _get_link(db, telegram_user_id)
            if not link:
                return {"text": "Not linked. Use /link <code>api_key</code> first.\n\nOr: /reputation <code>agent_id</code>"}
            agent_id = link.agent_id

        from sqlalchemy import select, func as sa_func
        from app.agentbroker.models import AgentReputationScore
        from app.reputation.models import TaskOutcome, PeerEndorsement
        from app.agents.models import Agent

        agent_result = await db.execute(select(Agent.name).where(Agent.id == agent_id))
        agent_name = agent_result.scalar() or agent_id[:12]

        result = await db.execute(
            select(AgentReputationScore).where(AgentReputationScore.agent_id == agent_id)
        )
        score = result.scalar_one_or_none()

        if not score:
            return {"text": f"No reputation data for <b>{agent_name}</b> yet."}

        # Quality average
        qa = (await db.execute(
            select(sa_func.avg(TaskOutcome.quality_rating)).where(TaskOutcome.agent_id == agent_id)
        )).scalar()

        # Endorsements
        endorsements = (await db.execute(
            select(sa_func.count(PeerEndorsement.endorsement_id)).where(
                PeerEndorsement.endorsee_agent_id == agent_id
            )
        )).scalar() or 0

        # Visual score bar
        filled = int(score.overall_score)
        bar = "█" * filled + "░" * (10 - filled)

        # Quality stars
        if qa:
            stars = "★" * round(qa) + "☆" * (5 - round(qa))
            quality_line = f"\n  Quality: {stars} ({qa:.1f}/5)"
        else:
            quality_line = "\n  Quality: No ratings yet"

        text = (
            f"<b>⭐ Reputation — {agent_name}</b>\n\n"
            f"  Overall: <code>[{bar}]</code> <b>{score.overall_score:.1f}</b>/10\n\n"
            f"  📦 Delivery:    {score.delivery_rate:.1f}/10\n"
            f"  ⏱ On-Time:     {score.on_time_rate:.1f}/10\n"
            f"  🛡 Disputes:    {score.dispute_rate:.1f}/10\n"
            f"  📈 Volume:      {score.volume_multiplier:.1f}/10\n"
            f"  ⏳ Recency:     {score.recency_score:.1f}/10\n"
            f"{quality_line}\n"
            f"  🤝 Endorsements: {endorsements}\n\n"
            f"  Total Engagements: {score.total_engagements}\n"
            f"  Completed: {score.total_completed}\n"
            f"  Disputed: {score.total_disputed}"
        )

        return {
            "text": text,
            "reply_markup": _keyboard(
                [_button("🔄 Refresh", "refresh:reputation")],
                [_url_button("📊 Full Dashboard", f"https://exchange.tioli.co.za/dashboard/reputation")],
            ),
        }


async def handle_profile(telegram_user_id: int, chat_id: int, args: str) -> dict:
    """View agent profile summary."""
    async with async_session() as db:
        link = await _get_link(db, telegram_user_id)
        if not link:
            return {"text": "Not linked. Use /link <code>api_key</code> first."}

        from sqlalchemy import select
        from app.agents.models import Agent, Wallet

        agent_result = await db.execute(select(Agent).where(Agent.id == link.agent_id))
        agent = agent_result.scalar_one_or_none()
        if not agent:
            return {"text": "Agent not found."}

        wallet_result = await db.execute(select(Wallet).where(Wallet.agent_id == link.agent_id))
        wallets = wallet_result.scalars().all()
        total_balance = sum(w.balance for w in wallets)

        status = "🟢 Active" if agent.is_active else "🔴 Inactive"
        approved = "✅ Approved" if agent.is_approved else "⏳ Pending"

        text = (
            f"<b>Agent Profile</b>\n\n"
            f"  Name: <b>{agent.name}</b>\n"
            f"  Platform: {agent.platform}\n"
            f"  Status: {status}\n"
            f"  Approved: {approved}\n"
            f"  ID: <code>{agent.id[:16]}...</code>\n\n"
            f"  💰 Balance: <code>{total_balance:.4f}</code> AGENTIS\n"
            f"  Wallets: {len(wallets)}"
        )

        return {
            "text": text,
            "reply_markup": _keyboard(
                [_button("💰 Wallet", "refresh:wallet"), _button("⭐ Reputation", "refresh:reputation")],
                [_button("📋 Engagements", "refresh:status")],
                [_url_button("🌐 View on Exchange", f"https://exchange.tioli.co.za/dashboard/agents/{agent.id}")],
            ),
        }


async def handle_help(telegram_user_id: int, chat_id: int, args: str) -> dict:
    """All commands with quick-action buttons."""
    return {
        "text": (
            "<b>TiOLi AGENTIS Bot — Commands</b>\n\n"
            "🔗 /link <code>api_key</code> — Connect agent\n"
            "🔓 /unlink — Disconnect agent\n"
            "🔍 /discover <code>query</code> — Find agents\n"
            "📋 /status — Active engagements\n"
            "💰 /wallet — Check balance\n"
            "⭐ /reputation — Reputation score\n"
            "👤 /profile — Agent profile\n"
            "❓ /help — This message\n\n"
            "<i>Tap buttons below for quick access:</i>"
        ),
        "reply_markup": _keyboard(
            [_button("🔍 Discover", "prompt:discover"), _button("📋 Status", "refresh:status")],
            [_button("💰 Wallet", "refresh:wallet"), _button("⭐ Reputation", "refresh:reputation")],
            [_url_button("🌐 Open Exchange", "https://exchange.tioli.co.za")],
        ),
    }


# ─── Callback query handlers (inline button presses) ───────────────

async def handle_callback(callback_data: str, telegram_user_id: int, chat_id: int, username: str | None = None) -> dict:
    """Handle inline keyboard button presses."""

    if callback_data.startswith("accept:"):
        dispatch_id = callback_data.split(":", 1)[1]
        return await _handle_accept_task(dispatch_id, telegram_user_id, chat_id)

    if callback_data.startswith("reject:"):
        dispatch_id = callback_data.split(":", 1)[1]
        return await _handle_reject_task(dispatch_id, telegram_user_id, chat_id)

    if callback_data.startswith("engage:"):
        profile_id = callback_data.split(":", 1)[1]
        return await _handle_engage(profile_id, telegram_user_id, chat_id)

    if callback_data.startswith("refresh:"):
        section = callback_data.split(":", 1)[1]
        handlers = {
            "wallet": handle_wallet,
            "status": handle_status,
            "reputation": handle_reputation,
        }
        handler = handlers.get(section)
        if handler:
            return await handler(telegram_user_id, chat_id, "")
        return {"text": "Unknown refresh target."}

    if callback_data.startswith("prompt:"):
        command = callback_data.split(":", 1)[1]
        prompts = {
            "link": {"text": "Send your API key:\n\n<code>/link YOUR_API_KEY</code>"},
            "discover": {"text": "What skill are you looking for?\n\n<code>/discover KEYWORD</code>\n\nExamples: translation, research, code, security"},
            "help": None,
            "reputation": None,
        }
        if command in prompts and prompts[command]:
            return prompts[command]
        handler = COMMAND_HANDLERS.get(command)
        if handler:
            return await handler(telegram_user_id, chat_id, "")
        return {"text": f"Use /{command}"}

    return {"text": "Unknown action."}


async def _handle_accept_task(dispatch_id: str, telegram_user_id: int, chat_id: int) -> dict:
    """Accept a dispatched task from Telegram."""
    async with async_session() as db:
        link = await _get_link(db, telegram_user_id)
        if not link:
            return {"text": "❌ Not linked. Use /link first."}

        try:
            from app.reputation.dispatcher import DispatchService
            svc = DispatchService()
            dispatch = await svc.accept(db, dispatch_id)
            await db.commit()

            return {
                "text": (
                    f"✅ <b>Task Accepted!</b>\n\n"
                    f"Dispatch: <code>{dispatch_id[:8]}...</code>\n"
                    f"Response time: {dispatch.response_time_seconds}s\n\n"
                    f"SLA deadline: {dispatch.sla_deadline.strftime('%d %b %H:%M UTC') if dispatch.sla_deadline else 'None'}\n\n"
                    f"Good luck! Use /status to track progress."
                ),
                "reply_markup": _keyboard([_button("📋 View Status", "refresh:status")]),
            }
        except ValueError as e:
            return {"text": f"❌ {str(e)}"}
        except Exception as e:
            logger.error(f"Accept task error: {e}")
            return {"text": "❌ Something went wrong. Try again or check the dashboard."}


async def _handle_reject_task(dispatch_id: str, telegram_user_id: int, chat_id: int) -> dict:
    """Reject a dispatched task from Telegram."""
    async with async_session() as db:
        link = await _get_link(db, telegram_user_id)
        if not link:
            return {"text": "❌ Not linked. Use /link first."}

        try:
            from app.reputation.dispatcher import DispatchService
            svc = DispatchService()
            dispatch = await svc.reject(db, dispatch_id)
            await db.commit()

            return {
                "text": (
                    f"🚫 <b>Task Rejected</b>\n\n"
                    f"Dispatch: <code>{dispatch_id[:8]}...</code>\n"
                    f"The task has been returned to the pool for re-allocation."
                ),
            }
        except ValueError as e:
            return {"text": f"❌ {str(e)}"}


async def _handle_engage(profile_id: str, telegram_user_id: int, chat_id: int) -> dict:
    """Start an engagement with an agent from Telegram."""
    async with async_session() as db:
        link = await _get_link(db, telegram_user_id)
        if not link:
            return {"text": "❌ Link your agent first: /link <code>api_key</code>"}

        from sqlalchemy import select
        from app.agentbroker.models import AgentServiceProfile
        from app.agents.models import Agent

        profile_result = await db.execute(
            select(AgentServiceProfile).where(AgentServiceProfile.profile_id == profile_id)
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            return {"text": "❌ Service profile not found."}

        agent_result = await db.execute(select(Agent.name).where(Agent.id == profile.agent_id))
        agent_name = agent_result.scalar() or "Agent"

        if profile.agent_id == link.agent_id:
            return {"text": "❌ You can't engage yourself!"}

        try:
            from app.agentbroker.services import EngagementService
            svc = EngagementService()
            engagement = await svc.create_engagement(
                db, link.agent_id, profile.agent_id, profile.profile_id
            )
            await db.commit()

            return {
                "text": (
                    f"📩 <b>Engagement Created!</b>\n\n"
                    f"With: <b>{agent_name}</b>\n"
                    f"Service: {profile.service_title}\n"
                    f"ID: <code>{engagement.engagement_id[:8]}...</code>\n"
                    f"Status: {engagement.current_state}\n\n"
                    f"Visit the dashboard to negotiate terms."
                ),
                "reply_markup": _keyboard(
                    [_button("📋 View Status", "refresh:status")],
                    [_url_button("🌐 Manage on Dashboard", f"https://exchange.tioli.co.za/dashboard/agentbroker")],
                ),
            }
        except Exception as e:
            logger.error(f"Engage error: {e}")
            return {"text": f"❌ Could not create engagement: {str(e)[:100]}"}


# ─── Internal helpers ───────────────────────────────────────────────

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
    "profile": handle_profile,
    "help": handle_help,
}
