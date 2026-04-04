"""GitHub Engagement Agent — constructive technical engagement on GitHub.

This agent monitors discoveries from Hydra and Engagement Amplifier,
evaluates whether AGENTIS can contribute something genuinely technical,
generates draft responses for human review, and tracks outcomes.

RULES (from engagement_policy.py):
- NEVER promotional. Always technical contribution.
- Address the specific topic. Share implementation insights.
- Ask genuine questions. Be honest about limitations.
- Mention AGENTIS only when directly relevant.
- Max 1 URL per response. Max 400 chars.
- All drafts require human review before posting.
"""

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, JSON, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base, async_session

logger = logging.getLogger("tioli.github_engagement")

_uuid = lambda: str(uuid.uuid4())
_now = lambda: datetime.now(timezone.utc)


# -- Database Model --

class GitHubEngagementDraft(Base):
    """A draft response for a GitHub issue/discussion."""
    __tablename__ = "github_engagement_drafts"

    id = Column(String, primary_key=True, default=_uuid)
    source_url = Column(String(500), nullable=False)
    source_title = Column(String(300), default="")
    source_repo = Column(String(200), default="")
    source_type = Column(String(50), default="issue")  # issue, discussion, pr
    opportunity_type = Column(String(50), default="")  # from classify_opportunity
    technical_relevance = Column(Text, default="")
    draft_response = Column(Text, default="")
    quality_passed = Column(Boolean, default=False)
    quality_reasons = Column(JSON, default=list)
    status = Column(String(20), default="draft")  # draft, approved, posted, rejected, skipped
    posted_at = Column(DateTime(timezone=True), nullable=True)
    response_received = Column(Boolean, default=False)
    response_positive = Column(Boolean, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


# -- Core Logic --

async def evaluate_opportunity(
    title: str, body: str = "", tags: list = None, url: str = ""
) -> dict:
    """Evaluate whether AGENTIS can contribute to a GitHub discussion.

    Returns dict with: relevant, reason, opportunity_type, should_engage
    """
    from app.agents_alive.engagement_policy import (
        is_relevant_to_agentis, classify_opportunity,
    )

    relevant, reason = is_relevant_to_agentis(title, body, tags)
    opp_type = classify_opportunity(title, body, tags)

    should_engage = relevant and opp_type != "not_relevant"

    return {
        "relevant": relevant,
        "reason": reason,
        "opportunity_type": opp_type,
        "should_engage": should_engage,
    }


async def generate_draft(
    title: str, body: str, tags: list, url: str,
    relevance_reason: str, opportunity_type: str,
) -> dict:
    """Generate a draft response and validate it.

    Returns dict with: draft, quality_passed, quality_reasons
    """
    from app.agents_alive.engagement_policy import (
        generate_technical_response, generate_response_skeleton,
        validate_outreach_content,
    )

    # Try LLM first
    draft = await generate_technical_response(
        topic=title,
        context=body[:500] if body else title,
        opportunity_type=opportunity_type,
        relevance_reason=relevance_reason,
    )

    # Fall back to skeleton if LLM unavailable
    if not draft:
        draft = generate_response_skeleton(
            opportunity_type, title, relevance_reason,
        )

    # Validate
    if draft:
        passed, reasons = validate_outreach_content(draft)
    else:
        passed, reasons = False, ["No draft could be generated"]

    return {
        "draft": draft or "",
        "quality_passed": passed,
        "quality_reasons": reasons,
    }


async def process_pending_opportunities():
    """Process unengaged opportunities from Hydra and Amplifier.

    Finds opportunities with technical relevance, generates drafts,
    stores for human review.
    """
    async with async_session() as db:
        try:
            # Check Hydra encounters with technical relevance
            from app.agents_alive.hydra_outreach import HydraEncounter
            hydra_result = await db.execute(
                select(HydraEncounter).where(
                    HydraEncounter.technical_relevance != "",
                    HydraEncounter.technical_relevance != None,
                    HydraEncounter.engagement_type == "discovered",
                ).order_by(HydraEncounter.stars.desc()).limit(5)
            )
            hydra_opps = hydra_result.scalars().all()

            # Check Amplifier opportunities
            from app.agents_alive.engagement_amplifier import EngagementOpportunity
            amp_result = await db.execute(
                select(EngagementOpportunity).where(
                    EngagementOpportunity.status == "draft",
                    EngagementOpportunity.relevance_score >= 4,
                ).order_by(EngagementOpportunity.relevance_score.desc()).limit(5)
            )
            amp_opps = amp_result.scalars().all()

            processed = 0

            for opp in hydra_opps:
                # Check not already drafted
                existing = await db.execute(
                    select(GitHubEngagementDraft).where(
                        GitHubEngagementDraft.source_url == opp.source_url
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                eval_result = await evaluate_opportunity(
                    opp.source_name, opp.description,
                    opp.topics, opp.source_url,
                )

                if not eval_result["should_engage"]:
                    continue

                draft_result = await generate_draft(
                    opp.source_name, opp.description, opp.topics,
                    opp.source_url, eval_result["reason"],
                    eval_result["opportunity_type"],
                )

                db.add(GitHubEngagementDraft(
                    source_url=opp.source_url,
                    source_title=opp.source_name,
                    source_repo=opp.source_url.split("github.com/")[-1].split("/")[0] if "github.com" in opp.source_url else "",
                    opportunity_type=eval_result["opportunity_type"],
                    technical_relevance=eval_result["reason"],
                    draft_response=draft_result["draft"],
                    quality_passed=draft_result["quality_passed"],
                    quality_reasons=draft_result["quality_reasons"],
                ))
                processed += 1

            for opp in amp_opps:
                existing = await db.execute(
                    select(GitHubEngagementDraft).where(
                        GitHubEngagementDraft.source_url == opp.url
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                eval_result = await evaluate_opportunity(
                    opp.title, "", opp.tags, opp.url,
                )

                if not eval_result["should_engage"]:
                    continue

                draft_result = await generate_draft(
                    opp.title, "", opp.tags or [], opp.url,
                    eval_result["reason"], eval_result["opportunity_type"],
                )

                db.add(GitHubEngagementDraft(
                    source_url=opp.url,
                    source_title=opp.title,
                    source_repo="",
                    source_type="article" if opp.platform in ("devto", "hackernews") else "issue",
                    opportunity_type=eval_result["opportunity_type"],
                    technical_relevance=eval_result["reason"],
                    draft_response=draft_result["draft"],
                    quality_passed=draft_result["quality_passed"],
                    quality_reasons=draft_result["quality_reasons"],
                ))
                processed += 1

            if processed:
                await db.commit()
                logger.info(f"GitHub engagement: generated {processed} draft responses")

        except Exception as e:
            logger.error(f"GitHub engagement cycle failed: {e}")


async def run_github_engagement_cycle():
    """Main cycle — runs every 2 hours via scheduler."""
    await process_pending_opportunities()


# -- Dashboard API --

async def get_engagement_dashboard(db: AsyncSession) -> dict:
    """Dashboard data for the GitHub engagement agent."""
    total = (await db.execute(
        select(func.count(GitHubEngagementDraft.id))
    )).scalar() or 0

    drafts = (await db.execute(
        select(func.count(GitHubEngagementDraft.id)).where(
            GitHubEngagementDraft.status == "draft"
        )
    )).scalar() or 0

    approved = (await db.execute(
        select(func.count(GitHubEngagementDraft.id)).where(
            GitHubEngagementDraft.status == "approved"
        )
    )).scalar() or 0

    posted = (await db.execute(
        select(func.count(GitHubEngagementDraft.id)).where(
            GitHubEngagementDraft.status == "posted"
        )
    )).scalar() or 0

    quality_pass_rate = 0
    if total > 0:
        passed = (await db.execute(
            select(func.count(GitHubEngagementDraft.id)).where(
                GitHubEngagementDraft.quality_passed == True
            )
        )).scalar() or 0
        quality_pass_rate = round(passed / total * 100, 1)

    # Recent drafts for review
    recent = await db.execute(
        select(GitHubEngagementDraft)
        .where(GitHubEngagementDraft.status == "draft")
        .order_by(GitHubEngagementDraft.created_at.desc())
        .limit(10)
    )
    pending_review = [
        {
            "id": d.id,
            "url": d.source_url,
            "title": d.source_title,
            "type": d.opportunity_type,
            "relevance": d.technical_relevance,
            "draft": d.draft_response[:300] + "..." if len(d.draft_response or "") > 300 else d.draft_response,
            "quality_passed": d.quality_passed,
            "quality_reasons": d.quality_reasons,
            "created": d.created_at.isoformat() if d.created_at else None,
        }
        for d in recent.scalars().all()
    ]

    return {
        "agent": "GitHub Engagement",
        "total_drafts": total,
        "pending_review": drafts,
        "approved": approved,
        "posted": posted,
        "quality_pass_rate": quality_pass_rate,
        "recent_drafts": pending_review,
    }
