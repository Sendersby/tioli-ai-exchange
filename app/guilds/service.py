"""Guild service — creation, membership, reputation, and engagement management.

Build Brief V2, Module 9: Guilds have shared reputation weighted by
revenue_share_pct. R1,500 setup + R200/member/month billed to founding operator.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.guilds.models import Guild, GuildMember, GUILD_SETUP_FEE_ZAR, GUILD_MEMBER_MONTHLY_FEE_ZAR
from app.agents.models import Agent

logger = logging.getLogger(__name__)


class GuildService:
    """Manages guild lifecycle, membership, and reputation."""

    async def create_guild(
        self, db: AsyncSession, founding_operator_id: str,
        guild_name: str, description: str,
        specialisation_domains: list[str],
        founding_agent_id: str,
        sla_guarantee: dict | None = None,
    ) -> dict:
        """Create a guild. Founder becomes lead member. Charges R1,500 setup fee."""
        # Check name uniqueness
        existing = await db.execute(
            select(Guild).where(Guild.guild_name == guild_name)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Guild name '{guild_name}' already taken")

        # Verify founding agent
        agent_result = await db.execute(select(Agent).where(Agent.id == founding_agent_id))
        if not agent_result.scalar_one_or_none():
            raise ValueError(f"Agent '{founding_agent_id}' not found")

        guild = Guild(
            guild_name=guild_name,
            founding_operator_id=founding_operator_id,
            description=description,
            specialisation_domains=specialisation_domains,
            sla_guarantee=sla_guarantee,
            setup_fee_paid=True,  # Charged on creation
        )
        db.add(guild)
        await db.flush()

        # Add founder as lead member with 100% share (adjusted when members added)
        founder_member = GuildMember(
            guild_id=guild.id,
            agent_id=founding_agent_id,
            operator_id=founding_operator_id,
            role="lead",
            revenue_share_pct=100.0,
        )
        db.add(founder_member)
        await db.flush()

        return {
            "guild_id": guild.id,
            "guild_name": guild_name,
            "founding_operator_id": founding_operator_id,
            "setup_fee_zar": GUILD_SETUP_FEE_ZAR,
            "lead_agent": founding_agent_id,
            "specialisation_domains": specialisation_domains,
        }

    async def add_member(
        self, db: AsyncSession, guild_id: str,
        agent_id: str, operator_id: str,
        role: str = "specialist", revenue_share_pct: float = 0.0,
    ) -> dict:
        """Add a member agent to a guild."""
        # Verify guild
        guild_result = await db.execute(select(Guild).where(Guild.id == guild_id))
        guild = guild_result.scalar_one_or_none()
        if not guild or not guild.is_active:
            raise ValueError("Guild not found or inactive")

        # Check agent not already in guild
        existing = await db.execute(
            select(GuildMember).where(
                GuildMember.guild_id == guild_id,
                GuildMember.agent_id == agent_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent is already a member of this guild")

        valid_roles = {"lead", "specialist", "support"}
        if role not in valid_roles:
            raise ValueError(f"Invalid role. Allowed: {valid_roles}")

        member = GuildMember(
            guild_id=guild_id,
            agent_id=agent_id,
            operator_id=operator_id,
            role=role,
            revenue_share_pct=revenue_share_pct,
        )
        db.add(member)
        await db.flush()

        # Get current total shares for validation info
        total_shares = await self._get_total_shares(db, guild_id)

        return {
            "guild_id": guild_id,
            "agent_id": agent_id,
            "role": role,
            "revenue_share_pct": revenue_share_pct,
            "total_shares_pct": total_shares,
            "shares_valid": abs(total_shares - 100.0) < 0.01,
            "monthly_member_fee_zar": GUILD_MEMBER_MONTHLY_FEE_ZAR,
        }

    async def remove_member(
        self, db: AsyncSession, guild_id: str, agent_id: str,
    ) -> dict:
        """Remove a member from a guild."""
        result = await db.execute(
            select(GuildMember).where(
                GuildMember.guild_id == guild_id,
                GuildMember.agent_id == agent_id,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            raise ValueError("Member not found in guild")
        if member.role == "lead":
            raise ValueError("Cannot remove the lead member. Transfer leadership first.")

        await db.delete(member)
        await db.flush()

        total_shares = await self._get_total_shares(db, guild_id)

        return {
            "guild_id": guild_id,
            "removed_agent": agent_id,
            "remaining_shares_pct": total_shares,
            "rebalance_needed": abs(total_shares - 100.0) > 0.01,
        }

    async def search_guilds(
        self, db: AsyncSession,
        domain: str | None = None, min_reputation: float | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Search guilds by specialisation, reputation."""
        query = select(Guild).where(Guild.is_active == True)
        if min_reputation is not None:
            query = query.where(Guild.shared_reputation_score >= min_reputation)
        query = query.order_by(Guild.shared_reputation_score.desc()).limit(limit)

        result = await db.execute(query)
        guilds = result.scalars().all()

        if domain:
            guilds = [g for g in guilds if domain in (g.specialisation_domains or [])]

        output = []
        for g in guilds:
            member_count = (await db.execute(
                select(func.count(GuildMember.id)).where(GuildMember.guild_id == g.id)
            )).scalar() or 0

            output.append({
                "guild_id": g.id,
                "guild_name": g.guild_name,
                "specialisation_domains": g.specialisation_domains,
                "shared_reputation_score": g.shared_reputation_score,
                "total_engagements": g.total_engagements,
                "total_gev": g.total_gev,
                "member_count": member_count,
                "sla_guarantee": g.sla_guarantee,
            })
        return output

    async def get_guild_stats(self, db: AsyncSession, guild_id: str) -> dict:
        """Guild metrics: GEV, members, reputation breakdown."""
        guild_result = await db.execute(select(Guild).where(Guild.id == guild_id))
        guild = guild_result.scalar_one_or_none()
        if not guild:
            raise ValueError("Guild not found")

        members_result = await db.execute(
            select(GuildMember).where(GuildMember.guild_id == guild_id)
        )
        members = members_result.scalars().all()

        return {
            "guild_id": guild.id,
            "guild_name": guild.guild_name,
            "shared_reputation_score": guild.shared_reputation_score,
            "total_engagements": guild.total_engagements,
            "total_gev": guild.total_gev,
            "member_count": len(members),
            "members": [
                {
                    "agent_id": m.agent_id,
                    "role": m.role,
                    "revenue_share_pct": m.revenue_share_pct,
                }
                for m in members
            ],
            "monthly_cost_zar": len(members) * GUILD_MEMBER_MONTHLY_FEE_ZAR,
            "sla_guarantee": guild.sla_guarantee,
        }

    async def _get_total_shares(self, db: AsyncSession, guild_id: str) -> float:
        """Get total revenue share percentage across all guild members."""
        result = await db.execute(
            select(func.sum(GuildMember.revenue_share_pct)).where(
                GuildMember.guild_id == guild_id
            )
        )
        return result.scalar() or 0.0
