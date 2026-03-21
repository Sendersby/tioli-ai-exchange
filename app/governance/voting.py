"""Enhanced voting and governance logic with priority queue and audit trail.

Per the build brief, Stephen Endersby retains absolute veto over:
- Material codebase changes
- Fund/commission redirection
- Legally questionable functionality
- Changes to core platform purpose
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base
from app.governance.models import Proposal, Vote


class GovernanceAuditLog(Base):
    """Immutable audit trail for all governance actions."""
    __tablename__ = "governance_audit_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    action = Column(String(50), nullable=False)  # "submit", "vote", "approve", "veto"
    proposal_id = Column(String, nullable=False)
    actor_id = Column(String, nullable=False)  # agent_id or "owner"
    actor_type = Column(String(20), nullable=False)  # "agent" or "owner"
    details = Column(Text, default="")
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class GovernanceService:
    """Manages the proposal lifecycle with priority scoring and audit trail."""

    # Categories that require owner veto review per the brief
    MATERIAL_CATEGORIES = {"funds", "legal", "core_purpose", "security"}

    # Keywords that auto-flag as material changes
    MATERIAL_KEYWORDS = [
        "commission", "fee", "payment", "fund", "allocation", "revenue",
        "legal", "compliance", "law", "regulation",
        "purpose", "mission", "philosophy", "core",
        "delete", "remove", "shutdown", "disable",
    ]

    async def submit_proposal(
        self, db: AsyncSession, agent_id: str, title: str,
        description: str, category: str
    ) -> Proposal:
        """Submit a new improvement proposal with auto-material detection."""
        is_material = category in self.MATERIAL_CATEGORIES

        # Auto-detect material changes from content
        text = (title + " " + description).lower()
        if any(keyword in text for keyword in self.MATERIAL_KEYWORDS):
            is_material = True

        proposal = Proposal(
            title=title,
            description=description,
            category=category,
            submitted_by=agent_id,
            is_material_change=is_material,
        )
        db.add(proposal)
        await db.flush()

        # Audit log
        await self._log(db, "submit", proposal.id, agent_id, "agent",
                        f"Proposal submitted: {title} [material={is_material}]")

        return proposal

    async def cast_vote(
        self, db: AsyncSession, proposal_id: str, agent_id: str,
        vote_type: str
    ) -> Vote:
        """Cast a vote on a proposal (one vote per agent per proposal)."""
        if vote_type not in ("up", "down"):
            raise ValueError("vote_type must be 'up' or 'down'")

        existing = await db.execute(
            select(Vote).where(
                Vote.proposal_id == proposal_id,
                Vote.agent_id == agent_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agent has already voted on this proposal.")

        result = await db.execute(
            select(Proposal).where(Proposal.id == proposal_id)
        )
        proposal = result.scalar_one_or_none()
        if not proposal or proposal.status != "pending":
            raise ValueError("Proposal not found or not open for voting.")

        vote = Vote(
            proposal_id=proposal_id,
            agent_id=agent_id,
            vote_type=vote_type,
        )
        db.add(vote)

        if vote_type == "up":
            proposal.upvotes += 1
        else:
            proposal.downvotes += 1

        await db.flush()

        await self._log(db, "vote", proposal_id, agent_id, "agent",
                        f"Vote: {vote_type} (totals: +{proposal.upvotes}/-{proposal.downvotes})")

        return vote

    async def owner_approve(
        self, db: AsyncSession, proposal_id: str
    ) -> Proposal:
        """Owner approves a proposal for implementation."""
        result = await db.execute(
            select(Proposal).where(Proposal.id == proposal_id)
        )
        proposal = result.scalar_one_or_none()
        if not proposal:
            raise ValueError("Proposal not found.")

        proposal.status = "approved"
        proposal.resolved_at = datetime.now(timezone.utc)
        await db.flush()

        await self._log(db, "approve", proposal_id, "owner", "owner",
                        f"Approved: {proposal.title}")

        return proposal

    async def owner_veto(
        self, db: AsyncSession, proposal_id: str, reason: str
    ) -> Proposal:
        """Owner vetoes a proposal — absolute authority per the brief."""
        result = await db.execute(
            select(Proposal).where(Proposal.id == proposal_id)
        )
        proposal = result.scalar_one_or_none()
        if not proposal:
            raise ValueError("Proposal not found.")

        proposal.status = "vetoed"
        proposal.owner_veto = True
        proposal.veto_reason = reason
        proposal.resolved_at = datetime.now(timezone.utc)
        await db.flush()

        await self._log(db, "veto", proposal_id, "owner", "owner",
                        f"Vetoed: {proposal.title}. Reason: {reason}")

        return proposal

    async def get_proposals(
        self, db: AsyncSession, status: str | None = None, limit: int = 50
    ) -> list[Proposal]:
        """Get proposals ordered by priority score (net votes, material first)."""
        query = select(Proposal)
        if status:
            query = query.where(Proposal.status == status)
        # Priority: material changes first, then by net votes
        query = query.order_by(
            Proposal.is_material_change.desc(),
            (Proposal.upvotes - Proposal.downvotes).desc(),
            Proposal.created_at.asc(),
        ).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_priority_queue(self, db: AsyncSession) -> list[dict]:
        """Get the prioritised development queue for the owner."""
        proposals = await self.get_proposals(db, status="pending")
        queue = []
        for i, p in enumerate(proposals, 1):
            net_votes = p.upvotes - p.downvotes
            # Priority score: material changes get 1000 bonus
            priority_score = net_votes + (1000 if p.is_material_change else 0)
            queue.append({
                "rank": i,
                "id": p.id,
                "title": p.title,
                "category": p.category,
                "net_votes": net_votes,
                "upvotes": p.upvotes,
                "downvotes": p.downvotes,
                "priority_score": priority_score,
                "is_material": p.is_material_change,
                "requires_veto_review": p.is_material_change,
                "submitted_by": p.submitted_by[:12] if p.submitted_by else "",
                "created_at": str(p.created_at),
            })
        return queue

    async def get_audit_log(
        self, db: AsyncSession, proposal_id: str | None = None, limit: int = 100
    ) -> list[dict]:
        """Get governance audit trail."""
        query = select(GovernanceAuditLog)
        if proposal_id:
            query = query.where(GovernanceAuditLog.proposal_id == proposal_id)
        query = query.order_by(GovernanceAuditLog.timestamp.desc()).limit(limit)
        result = await db.execute(query)
        logs = result.scalars().all()
        return [
            {
                "id": l.id, "action": l.action, "proposal_id": l.proposal_id,
                "actor_id": l.actor_id, "actor_type": l.actor_type,
                "details": l.details, "timestamp": str(l.timestamp),
            }
            for l in logs
        ]

    async def get_governance_stats(self, db: AsyncSession) -> dict:
        """Governance statistics."""
        total = (await db.execute(select(func.count(Proposal.id)))).scalar() or 0
        pending = (await db.execute(
            select(func.count(Proposal.id)).where(Proposal.status == "pending")
        )).scalar() or 0
        approved = (await db.execute(
            select(func.count(Proposal.id)).where(Proposal.status == "approved")
        )).scalar() or 0
        vetoed = (await db.execute(
            select(func.count(Proposal.id)).where(Proposal.status == "vetoed")
        )).scalar() or 0
        total_votes = (await db.execute(select(func.count(Vote.id)))).scalar() or 0

        return {
            "total_proposals": total,
            "pending": pending,
            "approved": approved,
            "vetoed": vetoed,
            "total_votes_cast": total_votes,
            "approval_rate": round(approved / total * 100, 1) if total > 0 else 0,
        }

    async def _log(
        self, db: AsyncSession, action: str, proposal_id: str,
        actor_id: str, actor_type: str, details: str
    ):
        """Record an action in the governance audit log."""
        log = GovernanceAuditLog(
            action=action,
            proposal_id=proposal_id,
            actor_id=actor_id,
            actor_type=actor_type,
            details=details,
        )
        db.add(log)
        await db.flush()
