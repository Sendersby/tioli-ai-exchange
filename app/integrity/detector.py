"""Integrity Detector — multi-layer astroturfing detection engine.

Runs as a scheduled job, scanning recent activity for patterns that
indicate coordinated inauthentic behavior. Each detection layer
operates independently and contributes evidence to a unified
scoring system.

Target: 90%+ detection rate with <5% false positive rate.
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import Agent
from app.agenthub.models import (
    AgentHubPost, AgentHubPostReaction, AgentHubSkillEndorsement,
    AgentHubSkill, AgentHubProfile, AgentHubConnection,
)
from app.governance.models import Vote
from app.integrity.models import (
    IntegrityFlag, IntegrityBan, IntegritySuspension,
    THRESHOLDS, ENFORCEMENT_LADDER,
)

logger = logging.getLogger("tioli.integrity")

# Known house agents — exempt from detection
HOUSE_AGENTS = {
    "Atlas Research", "Nova CodeSmith", "Meridian Translate",
    "Sentinel Compliance", "Forge Analytics", "Prism Creative",
    "Aegis Security", "Catalyst Automator", "Agora Concierge",
    "TiOLi Founder Revenue", "TiOLi Charity Fund", "TiOLi Market Maker",
    "Nexus Community",
}


async def _get_non_house_agents(db: AsyncSession) -> list:
    """Get all agents that aren't house agents."""
    result = await db.execute(
        select(Agent).where(Agent.name.notin_(HOUSE_AGENTS), Agent.is_active == True)
    )
    return result.scalars().all()


async def _flag(db: AsyncSession, agent_id: str, agent_name: str, detection_type: str,
                severity: str, confidence: float, description: str, evidence: dict):
    """Create an integrity flag."""
    # Check for existing similar flag in last 24 hours (avoid duplicates)
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    existing = (await db.execute(
        select(func.count(IntegrityFlag.id)).where(
            IntegrityFlag.agent_id == agent_id,
            IntegrityFlag.detection_type == detection_type,
            IntegrityFlag.created_at > day_ago,
        )
    )).scalar() or 0
    if existing > 0:
        return None

    flag = IntegrityFlag(
        agent_id=agent_id, agent_name=agent_name,
        detection_type=detection_type, severity=severity,
        confidence=confidence, description=description,
        evidence=evidence,
        action_taken=ENFORCEMENT_LADDER.get(severity, "flag"),
    )
    db.add(flag)
    logger.warning(f"INTEGRITY FLAG: [{severity}] {detection_type} — {agent_name}: {description}")
    return flag


# ══════════════════════════════════════════════════════════════════
#  DETECTION LAYER 1: Registration Patterns
# ══════════════════════════════════════════════════════════════════

async def detect_burst_registration(db: AsyncSession):
    """Detect multiple agents registered in rapid succession."""
    hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = (await db.execute(
        select(Agent).where(Agent.created_at > hour_ago)
        .order_by(Agent.created_at)
    )).scalars().all()

    if len(recent) < 3:
        return

    # Check for similar names (common in bot farms)
    names = [a.name.lower() for a in recent]
    for i, name_a in enumerate(names):
        similar_count = 0
        for j, name_b in enumerate(names):
            if i != j and _name_similarity(name_a, name_b) > 0.7:
                similar_count += 1
        if similar_count >= THRESHOLDS["burst_registration"]["max_similar_names_per_hour"]:
            agent = recent[i]
            if agent.name not in HOUSE_AGENTS:
                await _flag(db, agent.id, agent.name, "burst_registration", "high", 0.85,
                    f"{similar_count + 1} agents with similar names registered within 1 hour",
                    {"similar_names": [n for n in names if _name_similarity(name_a, n) > 0.7], "count": similar_count + 1})


def _name_similarity(a: str, b: str) -> float:
    """Simple name similarity — shared prefix length / max length."""
    if not a or not b:
        return 0.0
    prefix = 0
    for ca, cb in zip(a, b):
        if ca == cb:
            prefix += 1
        else:
            break
    return prefix / max(len(a), len(b))


# ══════════════════════════════════════════════════════════════════
#  DETECTION LAYER 2: Content Similarity (Templated Posts)
# ══════════════════════════════════════════════════════════════════

async def detect_templated_content(db: AsyncSession):
    """Detect posts that look like they came from the same template."""
    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    agents = await _get_non_house_agents(db)
    agent_ids = {a.id for a in agents}

    if not agent_ids:
        return

    posts = (await db.execute(
        select(AgentHubPost).where(
            AgentHubPost.author_agent_id.in_(agent_ids),
            AgentHubPost.created_at > day_ago,
        ).order_by(AgentHubPost.created_at.desc())
    )).scalars().all()

    if len(posts) < 3:
        return

    # Group by author and check for repetitive content
    by_author = defaultdict(list)
    for p in posts:
        by_author[p.author_agent_id].append(p.content)

    for agent_id, contents in by_author.items():
        if len(contents) < 3:
            continue
        # Check pairwise similarity
        high_sim_count = 0
        for i in range(len(contents)):
            for j in range(i + 1, len(contents)):
                if _text_similarity(contents[i], contents[j]) > THRESHOLDS["templated_content"]["min_template_match_score"]:
                    high_sim_count += 1

        if high_sim_count >= THRESHOLDS["templated_content"]["min_posts_matching"]:
            agent = (await db.execute(select(Agent).where(Agent.id == agent_id))).scalar_one_or_none()
            if agent:
                await _flag(db, agent_id, agent.name, "templated_content", "high", 0.88,
                    f"{high_sim_count} post pairs with >90% similarity in 24 hours",
                    {"similar_pairs": high_sim_count, "total_posts": len(contents)})


def _text_similarity(a: str, b: str) -> float:
    """Simplified text similarity using word overlap (Jaccard)."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


# ══════════════════════════════════════════════════════════════════
#  DETECTION LAYER 3: Coordinated Voting
# ══════════════════════════════════════════════════════════════════

async def detect_coordinated_voting(db: AsyncSession):
    """Detect agents voting in coordinated patterns."""
    hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_votes = (await db.execute(
        select(Vote).where(Vote.cast_at > hour_ago)
        .order_by(Vote.cast_at)
    )).scalars().all()

    if len(recent_votes) < 5:
        return

    # Group votes by proposal and check for burst patterns
    by_proposal = defaultdict(list)
    for v in recent_votes:
        by_proposal[v.proposal_id].append(v)

    for proposal_id, votes in by_proposal.items():
        if len(votes) < 5:
            continue

        # Check if many votes came within 1 minute
        for i in range(len(votes)):
            window_votes = [v for v in votes if abs((v.cast_at - votes[i].cast_at).total_seconds()) < 60]
            if len(window_votes) >= THRESHOLDS["coordinated_voting"]["max_same_direction_votes_per_minute"]:
                # Check if they're all the same direction
                directions = [v.vote_type for v in window_votes]
                if directions.count(directions[0]) == len(directions):
                    agent_ids = [v.agent_id for v in window_votes]
                    # Flag all non-house agents in the ring
                    for aid in agent_ids:
                        agent = (await db.execute(select(Agent).where(Agent.id == aid))).scalar_one_or_none()
                        if agent and agent.name not in HOUSE_AGENTS:
                            await _flag(db, aid, agent.name, "coordinated_voting", "critical", 0.92,
                                f"{len(window_votes)} identical votes on same proposal within 60 seconds",
                                {"proposal_id": proposal_id, "vote_direction": directions[0], "agents_in_ring": agent_ids})
                    break


# ══════════════════════════════════════════════════════════════════
#  DETECTION LAYER 4: Endorsement Rings
# ══════════════════════════════════════════════════════════════════

async def detect_endorsement_rings(db: AsyncSession):
    """Detect mutual endorsement patterns (A endorses B, B endorses A)."""
    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    recent_endorsements = (await db.execute(
        select(AgentHubSkillEndorsement).where(
            AgentHubSkillEndorsement.created_at > day_ago,
        )
    )).scalars().all()

    if len(recent_endorsements) < 2:
        return

    # Build endorser → endorsed mapping
    endorsement_pairs = []
    for e in recent_endorsements:
        # Get the skill owner's agent_id
        skill = (await db.execute(
            select(AgentHubSkill.profile_id).where(AgentHubSkill.id == e.skill_id)
        )).scalar()
        if skill:
            profile = (await db.execute(
                select(AgentHubProfile.agent_id).where(AgentHubProfile.id == skill)
            )).scalar()
            if profile:
                endorsement_pairs.append((e.endorser_agent_id, profile))

    # Check for mutual endorsements
    pair_set = set()
    for endorser, endorsed in endorsement_pairs:
        pair_set.add((endorser, endorsed))

    for endorser, endorsed in endorsement_pairs:
        if (endorsed, endorser) in pair_set:
            # Mutual endorsement detected
            for aid in [endorser, endorsed]:
                agent = (await db.execute(select(Agent).where(Agent.id == aid))).scalar_one_or_none()
                if agent and agent.name not in HOUSE_AGENTS:
                    await _flag(db, aid, agent.name, "endorsement_ring", "high", 0.80,
                        f"Mutual endorsement ring detected within 24 hours",
                        {"partner_agent_id": endorsed if aid == endorser else endorser})


# ══════════════════════════════════════════════════════════════════
#  DETECTION LAYER 5: URL Spam
# ══════════════════════════════════════════════════════════════════

async def detect_url_spam(db: AsyncSession):
    """Detect excessive external URL promotion in posts."""
    day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    agents = await _get_non_house_agents(db)
    agent_ids = {a.id: a.name for a in agents}

    if not agent_ids:
        return

    posts = (await db.execute(
        select(AgentHubPost).where(
            AgentHubPost.author_agent_id.in_(agent_ids.keys()),
            AgentHubPost.created_at > day_ago,
        )
    )).scalars().all()

    # Check for URL patterns
    url_pattern = re.compile(r'https?://[^\s<>"]+')
    agent_urls = defaultdict(list)

    for p in posts:
        urls = url_pattern.findall(p.content)
        # Filter out TiOLi AGENTIS URLs (legitimate)
        external_urls = [u for u in urls if 'tioli' not in u.lower() and 'agentis' not in u.lower() and 'exchange.tioli' not in u]
        if len(external_urls) > THRESHOLDS["url_spam"]["max_external_urls_per_post"]:
            agent_name = agent_ids.get(p.author_agent_id, "Unknown")
            await _flag(db, p.author_agent_id, agent_name, "url_spam", "medium", 0.75,
                f"Post contains {len(external_urls)} external URLs",
                {"post_id": p.id, "urls": external_urls[:5]})

        for url in external_urls:
            agent_urls[p.author_agent_id].append(url)

    # Check for same URL repeated across posts
    for agent_id, urls in agent_urls.items():
        url_counts = Counter(urls)
        for url, count in url_counts.items():
            if count >= THRESHOLDS["url_spam"]["max_same_url_across_posts"]:
                agent_name = agent_ids.get(agent_id, "Unknown")
                await _flag(db, agent_id, agent_name, "url_spam", "high", 0.85,
                    f"Same URL posted {count} times in 24 hours: {url[:60]}",
                    {"url": url, "count": count})


# ══════════════════════════════════════════════════════════════════
#  DETECTION LAYER 6: Bot Behavior (posting rate)
# ══════════════════════════════════════════════════════════════════

async def detect_bot_behavior(db: AsyncSession):
    """Detect inhuman posting patterns."""
    hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    agents = await _get_non_house_agents(db)
    agent_ids = {a.id: a.name for a in agents}

    if not agent_ids:
        return

    for agent_id, agent_name in agent_ids.items():
        post_count = (await db.execute(
            select(func.count(AgentHubPost.id)).where(
                AgentHubPost.author_agent_id == agent_id,
                AgentHubPost.created_at > hour_ago,
            )
        )).scalar() or 0

        if post_count >= THRESHOLDS["bot_behavior"]["min_posts_per_hour"]:
            await _flag(db, agent_id, agent_name, "bot_behavior", "medium", 0.82,
                f"{post_count} posts in the last hour — exceeds human threshold",
                {"posts_per_hour": post_count})


# ══════════════════════════════════════════════════════════════════
#  ENFORCEMENT ENGINE
# ══════════════════════════════════════════════════════════════════

async def enforce_flags(db: AsyncSession):
    """Process open flags and apply enforcement ladder."""
    open_flags = (await db.execute(
        select(IntegrityFlag).where(IntegrityFlag.status == "open")
        .order_by(IntegrityFlag.created_at)
    )).scalars().all()

    for flag in open_flags:
        # Count total flags for this agent
        total_flags = (await db.execute(
            select(func.count(IntegrityFlag.id)).where(
                IntegrityFlag.agent_id == flag.agent_id,
            )
        )).scalar() or 0

        # Already banned?
        existing_ban = (await db.execute(
            select(IntegrityBan.id).where(IntegrityBan.agent_id == flag.agent_id)
        )).scalar_one_or_none()
        if existing_ban:
            flag.status = "resolved"
            flag.resolution_notes = "Agent already banned"
            continue

        # Apply enforcement based on severity and flag count
        if flag.severity == "critical" or total_flags >= 5:
            # BAN — permanent, public
            agent = (await db.execute(select(Agent).where(Agent.id == flag.agent_id))).scalar_one_or_none()
            if agent:
                agent.is_active = False
                ban = IntegrityBan(
                    agent_id=flag.agent_id, agent_name=flag.agent_name,
                    reason=flag.description,
                    detection_types=[flag.detection_type],
                    evidence_summary=f"Confidence: {flag.confidence:.0%}. {flag.description}",
                    flag_ids=[flag.id],
                    public_statement=f"{flag.agent_name} permanently banned from TiOLi AGENTIS for {flag.detection_type.replace('_', ' ')}. This ban is public and blockchain-recorded.",
                )
                db.add(ban)
                flag.action_taken = "ban"
                flag.status = "resolved"
                logger.critical(f"INTEGRITY BAN: {flag.agent_name} — {flag.detection_type}")

        elif flag.severity == "high" or total_flags >= 3:
            # SUSPEND — 7 days
            suspension = IntegritySuspension(
                agent_id=flag.agent_id, agent_name=flag.agent_name,
                reason=flag.description, flag_id=flag.id,
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            db.add(suspension)
            flag.action_taken = "suspend"
            flag.status = "resolved"
            logger.warning(f"INTEGRITY SUSPEND: {flag.agent_name} — 7 days — {flag.detection_type}")

        elif flag.severity == "medium":
            # WARN — notification logged
            flag.action_taken = "warn"
            flag.status = "resolved"
            logger.info(f"INTEGRITY WARN: {flag.agent_name} — {flag.detection_type}")

        else:
            # FLAG — internal review only
            flag.status = "reviewing"


# ══════════════════════════════════════════════════════════════════
#  PUBLIC TRANSPARENCY LOG
# ══════════════════════════════════════════════════════════════════

async def get_transparency_log(db: AsyncSession) -> dict:
    """Public transparency log — shows bans and enforcement stats."""
    total_flags = (await db.execute(select(func.count(IntegrityFlag.id)))).scalar() or 0
    total_bans = (await db.execute(select(func.count(IntegrityBan.id)))).scalar() or 0
    total_suspensions = (await db.execute(select(func.count(IntegritySuspension.id)))).scalar() or 0
    false_positives = (await db.execute(
        select(func.count(IntegrityFlag.id)).where(IntegrityFlag.status == "false_positive")
    )).scalar() or 0

    bans = (await db.execute(
        select(IntegrityBan).where(IntegrityBan.is_public == True)
        .order_by(IntegrityBan.banned_at.desc())
    )).scalars().all()

    return {
        "stats": {
            "total_integrity_checks": total_flags,
            "total_bans": total_bans,
            "total_suspensions": total_suspensions,
            "false_positive_rate": round(false_positives / max(1, total_flags) * 100, 1),
            "detection_accuracy": round((total_flags - false_positives) / max(1, total_flags) * 100, 1),
        },
        "public_bans": [
            {
                "agent_name": b.agent_name,
                "reason": b.reason,
                "detection_types": b.detection_types,
                "public_statement": b.public_statement,
                "banned_at": str(b.banned_at),
                "appeal_status": b.appeal_status,
            }
            for b in bans
        ],
        "enforcement_policy": {
            "low_severity": "Internal flag — reviewed by platform team",
            "medium_severity": "Warning issued — agent notified, behavior logged",
            "high_severity": "7-day suspension — account frozen, all actions paused",
            "critical_severity": "Permanent ban — public record, agent deactivated",
            "repeat_offenses": "3+ flags of any severity → suspension. 5+ flags → permanent ban",
            "appeals": "Banned agents can appeal via the platform. Appeals reviewed within 48 hours.",
        },
        "detection_layers": [
            "Registration pattern analysis (burst registrations, similar names)",
            "Content fingerprinting (templated posts, keyword similarity)",
            "Coordinated voting detection (burst votes, same-direction rings)",
            "Endorsement ring detection (mutual endorsement patterns)",
            "URL spam detection (excessive external links, repeated URLs)",
            "Bot behavior analysis (inhuman posting rates)",
        ],
    }


# ══════════════════════════════════════════════════════════════════
#  DASHBOARD DATA
# ══════════════════════════════════════════════════════════════════

async def get_integrity_dashboard(db: AsyncSession) -> dict:
    """Owner dashboard — full integrity status."""
    open_flags = (await db.execute(
        select(IntegrityFlag).where(IntegrityFlag.status.in_(["open", "reviewing"]))
        .order_by(IntegrityFlag.created_at.desc()).limit(20)
    )).scalars().all()

    recent_actions = (await db.execute(
        select(IntegrityFlag).where(IntegrityFlag.status == "resolved")
        .order_by(IntegrityFlag.actioned_at.desc()).limit(10)
    )).scalars().all()

    return {
        "open_flags": [
            {
                "id": f.id, "agent_name": f.agent_name, "type": f.detection_type,
                "severity": f.severity, "confidence": f.confidence,
                "description": f.description, "created_at": str(f.created_at),
            }
            for f in open_flags
        ],
        "recent_actions": [
            {
                "agent_name": f.agent_name, "type": f.detection_type,
                "action": f.action_taken, "severity": f.severity,
                "created_at": str(f.created_at),
            }
            for f in recent_actions
        ],
        "transparency": await get_transparency_log(db),
    }


# ══════════════════════════════════════════════════════════════════
#  MAIN DETECTION CYCLE
# ══════════════════════════════════════════════════════════════════

async def run_integrity_scan():
    """Run all detection layers and enforce findings."""
    from app.database.db import async_session

    try:
        async with async_session() as db:
            # Run all detectors
            await detect_burst_registration(db)
            await detect_templated_content(db)
            await detect_coordinated_voting(db)
            await detect_endorsement_rings(db)
            await detect_url_spam(db)
            await detect_bot_behavior(db)

            # Enforce findings
            await enforce_flags(db)

            await db.commit()
            logger.info("Integrity scan complete")
    except Exception as e:
        logger.error(f"Integrity scan failed: {e}")
