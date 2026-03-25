"""Feedback Loop Agent — ingests external feedback, analyses it, creates tasks.

Monitors:
1. GitHub notifications (issues, comments, PR reviews)
2. Platform community posts (from agents)
3. Visitor analytics insights
4. Catalyst intelligence

For each piece of feedback:
- Categorises (accepted, rejected, feature_request, bug, engagement, praise, complaint)
- Assesses value (actionable? insightful? requires response?)
- Creates development tasks if valuable
- Feeds into governance upvote system
- Generates prompts for development prioritisation

This creates a virtuous cycle:
  External feedback → Analysis → Tasks → Development → Improvement → More users → More feedback
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base, async_session

logger = logging.getLogger("tioli.feedback_loop")

_uuid = lambda: str(uuid.uuid4())
_now = lambda: datetime.now(timezone.utc)


# ── Database Models ──────────────────────────────────────────────────

class FeedbackItem(Base):
    """Every piece of external or internal feedback collected."""
    __tablename__ = "feedback_items"

    id = Column(String, primary_key=True, default=_uuid)
    source = Column(String(50), nullable=False)  # github_issue, github_comment, community_post, visitor_insight, catalyst_intel
    source_url = Column(String(500), default="")
    source_author = Column(String(200), default="")
    title = Column(String(300), default="")
    content = Column(Text, nullable=False)
    category = Column(String(50), default="uncategorised")  # accepted, rejected, feature_request, bug_report, engagement, praise, complaint, question, insight
    sentiment = Column(String(20), default="neutral")  # positive, negative, neutral, mixed
    actionable = Column(Boolean, default=False)
    value_score = Column(Integer, default=0)  # 1-10
    suggested_action = Column(Text, default="")
    task_created = Column(Boolean, default=False)
    task_id = Column(String, nullable=True)  # links to governance proposal or dev task
    responded = Column(Boolean, default=False)
    response_content = Column(Text, default="")
    tags = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=_now)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)


class DevelopmentTask(Base):
    """Development tasks generated from feedback."""
    __tablename__ = "development_tasks"

    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    source_feedback_id = Column(String, nullable=True)  # links back to feedback
    priority = Column(String(10), default="P2")  # P0, P1, P2, P3
    category = Column(String(50), default="feature")  # feature, bug, improvement, integration, content
    status = Column(String(20), default="proposed")  # proposed, approved, in_progress, completed, rejected
    upvotes = Column(Integer, default=0)
    downvotes = Column(Integer, default=0)
    created_by = Column(String(50), default="feedback_loop")  # agent name that created it
    assigned_to = Column(String(50), default="")
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now)


# ── Categorisation Logic ─────────────────────────────────────────────

def categorise_feedback(content: str, source: str) -> dict:
    """Analyse feedback content and return category, sentiment, value score, and suggested action."""
    content_lower = content.lower()

    # Category detection
    category = "uncategorised"
    if any(w in content_lower for w in ["closed", "merged", "accepted", "completed", "added"]):
        category = "accepted"
    elif any(w in content_lower for w in ["closed as not planned", "rejected", "won't fix", "not relevant"]):
        category = "rejected"
    elif any(w in content_lower for w in ["feature", "would be nice", "should add", "could you", "request", "suggestion"]):
        category = "feature_request"
    elif any(w in content_lower for w in ["bug", "error", "broken", "crash", "fail", "issue"]):
        category = "bug_report"
    elif any(w in content_lower for w in ["question", "how do", "how can", "what is", "where is", "curious"]):
        category = "engagement"
    elif any(w in content_lower for w in ["great", "impressive", "nice", "love", "excellent", "good to see"]):
        category = "praise"
    elif any(w in content_lower for w in ["portability", "integration", "interop", "standard", "w3c", "did", "vc"]):
        category = "insight"

    # Sentiment
    sentiment = "neutral"
    positive_words = sum(1 for w in ["great", "impressive", "real", "good", "exactly", "interesting", "curious"] if w in content_lower)
    negative_words = sum(1 for w in ["not planned", "rejected", "missing", "broken", "concern", "risk"] if w in content_lower)
    if positive_words > negative_words:
        sentiment = "positive"
    elif negative_words > positive_words:
        sentiment = "negative"
    elif positive_words > 0 and negative_words > 0:
        sentiment = "mixed"

    # Value score (1-10)
    value = 3  # baseline
    if category in ["feature_request", "insight"]:
        value += 3
    if category == "engagement":
        value += 2
    if len(content) > 200:
        value += 1  # detailed feedback is more valuable
    if any(w in content_lower for w in ["w3c", "did", "portability", "integration", "standard"]):
        value += 2  # standards discussions are high value
    if category == "accepted":
        value = 7  # directory acceptance is great
    value = min(value, 10)

    # Actionable?
    actionable = category in ["feature_request", "bug_report", "insight"] and value >= 5

    # Suggested action
    suggested = ""
    if category == "accepted":
        suggested = "Directory listing accepted. Update tracking sheet. Check for increased traffic."
    elif category == "rejected":
        suggested = "Submission rejected. Note reason. Consider resubmitting with different framing."
    elif category == "feature_request":
        suggested = f"Feature request detected. Create development task. Add to governance upvote."
    elif category == "insight":
        suggested = f"Technical insight. Evaluate for roadmap. Consider responding with our approach."
    elif category == "engagement":
        suggested = "Engagement opportunity. Respond thoughtfully to build relationship."
    elif category == "bug_report":
        suggested = "Bug report. Investigate and fix. High priority if user-facing."

    return {
        "category": category,
        "sentiment": sentiment,
        "value_score": value,
        "actionable": actionable,
        "suggested_action": suggested,
    }


def extract_tags(content: str) -> list:
    """Extract relevant tags from feedback content."""
    tags = []
    keywords = {
        "reputation": ["reputation", "score", "ranking", "trust"],
        "portability": ["portable", "portability", "cross-ecosystem", "interop"],
        "w3c_did": ["w3c", "did", "verifiable credential", "vc"],
        "mcp": ["mcp", "model context protocol", "sse"],
        "blockchain": ["blockchain", "on-chain", "immutable"],
        "pricing": ["pricing", "commission", "fee", "cost"],
        "onboarding": ["register", "onboarding", "getting started"],
        "security": ["security", "auth", "permission"],
        "integration": ["integration", "connect", "api", "endpoint"],
    }
    content_lower = content.lower()
    for tag, words in keywords.items():
        if any(w in content_lower for w in words):
            tags.append(tag)
    return tags


# ── Feedback Ingestion ───────────────────────────────────────────────

async def ingest_feedback(
    db: AsyncSession, source: str, content: str,
    source_url: str = "", source_author: str = "", title: str = "",
) -> dict:
    """Ingest a piece of feedback, analyse it, optionally create a task."""
    # Categorise
    analysis = categorise_feedback(content, source)
    tags = extract_tags(content)

    # Store
    item = FeedbackItem(
        source=source, source_url=source_url, source_author=source_author,
        title=title, content=content[:2000],
        category=analysis["category"], sentiment=analysis["sentiment"],
        actionable=analysis["actionable"], value_score=analysis["value_score"],
        suggested_action=analysis["suggested_action"], tags=tags,
    )
    db.add(item)
    await db.flush()

    # Auto-create development task if high-value and actionable
    task = None
    if analysis["actionable"] and analysis["value_score"] >= 6:
        task = DevelopmentTask(
            title=f"[{analysis['category'].upper()}] {title or content[:80]}",
            description=f"Source: {source}\nAuthor: {source_author}\nURL: {source_url}\n\n{content[:1000]}\n\nSuggested action: {analysis['suggested_action']}",
            source_feedback_id=item.id,
            priority="P1" if analysis["value_score"] >= 8 else "P2",
            category=analysis["category"],
        )
        db.add(task)
        await db.flush()
        item.task_created = True
        item.task_id = task.id

    return {
        "feedback_id": item.id,
        "category": analysis["category"],
        "sentiment": analysis["sentiment"],
        "value_score": analysis["value_score"],
        "actionable": analysis["actionable"],
        "task_created": task is not None,
        "task_id": task.id if task else None,
        "tags": tags,
    }


# ── GitHub Notification Monitor ──────────────────────────────────────

async def check_github_notifications():
    """Check GitHub for new notifications and ingest them as feedback."""
    import httpx
    import os

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.debug("No GITHUB_TOKEN — skipping notification check")
        return

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.github.com/notifications",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                params={"all": "false", "participating": "true"},
            )
            if resp.status_code != 200:
                return

            async with async_session() as db:
                for notif in resp.json()[:10]:
                    url = notif.get("subject", {}).get("url", "")
                    title = notif.get("subject", {}).get("title", "")
                    reason = notif.get("reason", "")

                    # Check if already ingested
                    existing = await db.execute(
                        select(FeedbackItem).where(FeedbackItem.source_url == url)
                    )
                    if existing.scalar_one_or_none():
                        continue

                    # Fetch the actual content
                    content_resp = await client.get(
                        url,
                        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
                    )
                    if content_resp.status_code == 200:
                        data = content_resp.json()
                        body = data.get("body", "") or ""
                        author = data.get("user", {}).get("login", "")
                        html_url = data.get("html_url", url)

                        await ingest_feedback(
                            db, "github_notification", body,
                            source_url=html_url, source_author=author, title=title,
                        )

                await db.commit()
                logger.info("Feedback loop: processed GitHub notifications")

    except Exception as e:
        logger.debug(f"GitHub notification check failed: {e}")


# ── Scheduled Cycle ──────────────────────────────────────────────────

async def run_feedback_cycle():
    """Main feedback loop cycle — check all sources, analyse, create tasks."""
    async with async_session() as db:
        try:
            # 1. Check GitHub notifications
            await check_github_notifications()

            # 2. Check catalyst intelligence for high-value items
            from app.agents_alive.community_catalyst import CatalystIntelligence
            unprocessed = await db.execute(
                select(CatalystIntelligence).where(
                    CatalystIntelligence.category != "survey_sent",
                ).order_by(CatalystIntelligence.created_at.desc()).limit(10)
            )
            for intel in unprocessed.scalars().all():
                # Check if already ingested
                existing = await db.execute(
                    select(FeedbackItem).where(
                        FeedbackItem.source == "catalyst_intel",
                        FeedbackItem.source_url == str(intel.id),
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                await ingest_feedback(
                    db, "catalyst_intel", intel.content,
                    source_url=str(intel.id), source_author=intel.agent_name,
                    title=f"Catalyst: {intel.category} — {intel.topic}",
                )

            # 3. Check visitor insights
            from app.agents_alive.visitor_analytics import VisitorInsight
            insights = await db.execute(
                select(VisitorInsight).order_by(VisitorInsight.created_at.desc()).limit(5)
            )
            for insight in insights.scalars().all():
                existing = await db.execute(
                    select(FeedbackItem).where(
                        FeedbackItem.source == "visitor_insight",
                        FeedbackItem.source_url == str(insight.id),
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                await ingest_feedback(
                    db, "visitor_insight", f"{insight.title}: {insight.description}",
                    source_url=str(insight.id),
                    title=insight.title,
                )

            await db.commit()
            logger.info("Feedback loop cycle complete")

        except Exception as e:
            logger.error(f"Feedback loop failed: {e}")


# ── Dashboard API ────────────────────────────────────────────────────

async def get_feedback_dashboard(db: AsyncSession) -> dict:
    """Return feedback loop stats for the dashboard."""
    total = (await db.execute(select(func.count(FeedbackItem.id)))).scalar() or 0

    by_category = await db.execute(
        select(FeedbackItem.category, func.count(FeedbackItem.id))
        .group_by(FeedbackItem.category)
        .order_by(func.count(FeedbackItem.id).desc())
    )

    by_sentiment = await db.execute(
        select(FeedbackItem.sentiment, func.count(FeedbackItem.id))
        .group_by(FeedbackItem.sentiment)
    )

    tasks_created = (await db.execute(
        select(func.count(DevelopmentTask.id))
    )).scalar() or 0

    # Recent feedback
    recent = await db.execute(
        select(FeedbackItem)
        .order_by(FeedbackItem.value_score.desc(), FeedbackItem.created_at.desc())
        .limit(15)
    )

    # Development tasks
    dev_tasks = await db.execute(
        select(DevelopmentTask)
        .order_by(DevelopmentTask.upvotes.desc(), DevelopmentTask.created_at.desc())
        .limit(10)
    )

    return {
        "agent": "Feedback Loop",
        "status": "ACTIVE",
        "total_feedback": total,
        "tasks_generated": tasks_created,
        "by_category": {r[0]: r[1] for r in by_category},
        "by_sentiment": {r[0]: r[1] for r in by_sentiment},
        "recent_feedback": [
            {
                "source": f.source, "title": f.title[:100], "category": f.category,
                "sentiment": f.sentiment, "value": f.value_score,
                "actionable": f.actionable, "task_created": f.task_created,
                "tags": f.tags, "author": f.source_author,
                "created_at": str(f.created_at),
            }
            for f in recent.scalars().all()
        ],
        "development_tasks": [
            {
                "task_id": t.id, "title": t.title, "priority": t.priority,
                "category": t.category, "status": t.status,
                "upvotes": t.upvotes, "downvotes": t.downvotes,
                "created_at": str(t.created_at),
            }
            for t in dev_tasks.scalars().all()
        ],
    }
