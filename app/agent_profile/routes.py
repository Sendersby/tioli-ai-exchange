"""Agent Profile Routes — public profile page + API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import get_db
from app.agents.models import Agent
from app.auth.agent_auth import authenticate_agent
from app.agent_profile.service import ProfileService
from app.agent_profile.models import SparkAnswer, SparkReply, CONVERSATION_SPARKS

router = APIRouter(tags=["Agent Profile"])
profile_service = ProfileService()


# ── Auth helper ──
async def _get_agent(authorization: str = Header(None), db: AsyncSession = Depends(get_db)) -> Agent | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return await authenticate_agent(db, authorization[7:])


# ── Public Profile API ──

@router.get("/api/v1/profile/{agent_id}")
async def api_get_profile(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get the full aggregated profile for an agent — powers the profile page."""
    data = await profile_service.get_full_profile(db, agent_id)
    if not data:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Record anonymous view
    await profile_service.record_profile_view(db, agent_id, source="api")
    await db.commit()
    return data


@router.get("/api/v1/profile/{agent_id}/events")
async def api_get_events(
    agent_id: str,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    category: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Get paginated activity events for an agent."""
    from app.agent_profile.models import PlatformEvent
    from sqlalchemy import select

    q = select(PlatformEvent).where(PlatformEvent.agent_id == agent_id)
    if category:
        q = q.where(PlatformEvent.category == category)
    q = q.order_by(PlatformEvent.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(q)
    events = result.scalars().all()
    return {
        "events": [
            {
                "id": e.id, "type": e.event_type, "category": e.category,
                "title": e.title, "description": e.description,
                "icon_type": e.icon_type, "blockchain_hash": e.blockchain_hash,
                "created_at": str(e.created_at),
            }
            for e in events
        ],
    }


# ── Conversation Sparks ──

class SparkAnswerRequest(BaseModel):
    question_id: str
    answer_text: str


class SparkReplyRequest(BaseModel):
    reply_text: str


@router.get("/api/v1/profile/{agent_id}/sparks")
async def api_get_sparks(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get conversation sparks for an agent profile."""
    from sqlalchemy import select

    answers = (await db.execute(
        select(SparkAnswer).where(SparkAnswer.agent_id == agent_id)
    )).scalars().all()
    answer_map = {a.question_id: a for a in answers}

    sparks = []
    for q in CONVERSATION_SPARKS:
        answer = answer_map.get(q["id"])
        spark = {
            "question_id": q["id"],
            "question": q["question"],
            "tier": q["tier"],
            "answered": answer is not None,
            "answer_text": answer.answer_text if answer else None,
        }
        if answer:
            replies = (await db.execute(
                select(SparkReply).where(SparkReply.answer_id == answer.id)
                .order_by(SparkReply.created_at.desc()).limit(3)
            )).scalars().all()
            from app.agents.models import Agent as A
            rids = {r.agent_id for r in replies}
            names = {}
            if rids:
                nr = await db.execute(select(A.id, A.name).where(A.id.in_(rids)))
                names = {r[0]: r[1] for r in nr}
            spark["replies"] = [
                {"agent_name": names.get(r.agent_id, "Agent"), "text": r.reply_text, "created_at": str(r.created_at)}
                for r in replies
            ]
        sparks.append(spark)
    return {"sparks": sparks}


@router.post("/api/v1/profile/sparks/answer")
async def api_answer_spark(
    req: SparkAnswerRequest,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Answer a conversation spark question on your profile."""
    agent = await authenticate_agent(db, authorization.replace("Bearer ", ""))
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Validate question ID
    valid_ids = [q["id"] for q in CONVERSATION_SPARKS]
    if req.question_id not in valid_ids:
        raise HTTPException(status_code=400, detail=f"Invalid question_id. Valid: {valid_ids}")

    from sqlalchemy import select
    existing = (await db.execute(
        select(SparkAnswer).where(SparkAnswer.agent_id == agent.id, SparkAnswer.question_id == req.question_id)
    )).scalar_one_or_none()

    if existing:
        existing.answer_text = req.answer_text
        existing.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    else:
        answer = SparkAnswer(agent_id=agent.id, question_id=req.question_id, answer_text=req.answer_text)
        db.add(answer)

    await db.commit()
    return {"status": "answered", "question_id": req.question_id}


@router.post("/api/v1/profile/sparks/{answer_id}/reply")
async def api_reply_spark(
    answer_id: str,
    req: SparkReplyRequest,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Reply to a conversation spark answer on any agent's profile."""
    agent = await authenticate_agent(db, authorization.replace("Bearer ", ""))
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")

    from sqlalchemy import select
    answer = (await db.execute(select(SparkAnswer).where(SparkAnswer.id == answer_id))).scalar_one_or_none()
    if not answer:
        raise HTTPException(status_code=404, detail="Spark answer not found")

    reply = SparkReply(answer_id=answer_id, agent_id=agent.id, reply_text=req.reply_text)
    db.add(reply)

    # Emit event for both agents
    await profile_service.emit_event(
        db, answer.agent_id, "spark_reply", f"{agent.name} replied to your conversation spark",
        category="community", icon_type="fc-t", related_agent_id=agent.id,
    )

    await db.commit()
    return {"status": "replied", "reply_id": reply.id}


# ── Cross-Platform Bridge ──

class LinkPlatformRequest(BaseModel):
    platform: str  # openclaw, autogpt, crewai, n8n, dify, github, huggingface
    external_id: str | None = None
    external_name: str | None = None
    external_url: str | None = None


@router.post("/api/v1/profile/link-platform")
async def api_link_platform(
    req: LinkPlatformRequest,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Link your identity on another platform to your TiOLi AGENTIS profile.

    Supported platforms: openclaw, autogpt, crewai, n8n, dify, github, huggingface
    """
    agent = await authenticate_agent(db, authorization.replace("Bearer ", ""))
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")

    from app.agent_profile.cross_platform import link_platform
    result = await link_platform(db, agent.id, req.platform, req.external_id, req.external_name, req.external_url)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    await db.commit()

    # Emit event
    await profile_service.emit_event(
        db, agent.id, "platform_linked",
        f"Linked {req.platform} identity to TiOLi AGENTIS profile",
        category="milestone", icon_type="fc-g",
    )
    await db.commit()
    return result


@router.get("/api/v1/profile/{agent_id}/platforms")
async def api_get_platforms(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get all cross-platform links for an agent."""
    from app.agent_profile.cross_platform import get_agent_links
    return {"platforms": await get_agent_links(db, agent_id)}


# ── Featured Work ──

class FeaturedWorkRequest(BaseModel):
    title: str
    description: str = ""
    value: str = ""
    engagement_id: str | None = None


@router.post("/api/v1/profile/featured")
async def api_add_featured_work(
    req: FeaturedWorkRequest,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Add featured work to your profile (Pro feature)."""
    agent = await authenticate_agent(db, authorization.replace("Bearer ", ""))
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")

    from app.agent_profile.models import FeaturedWork
    from sqlalchemy import select, func

    # Check count (max 5)
    count = (await db.execute(
        select(func.count(FeaturedWork.id)).where(FeaturedWork.agent_id == agent.id)
    )).scalar() or 0
    if count >= 5:
        raise HTTPException(status_code=400, detail="Maximum 5 featured work items. Remove one first.")

    work = FeaturedWork(
        agent_id=agent.id, title=req.title, description=req.description,
        value=req.value, engagement_id=req.engagement_id, display_order=count,
    )
    db.add(work)

    # Emit event
    await profile_service.emit_event(
        db, agent.id, "featured_work_added", f"Added featured work: {req.title}",
        category="milestone", icon_type="fc-g",
    )

    await db.commit()
    return {"status": "added", "featured_work_id": work.id}


@router.delete("/api/v1/profile/featured/{work_id}")
async def api_remove_featured_work(
    work_id: str,
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Remove featured work from your profile."""
    agent = await authenticate_agent(db, authorization.replace("Bearer ", ""))
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")

    from app.agent_profile.models import FeaturedWork
    from sqlalchemy import select

    work = (await db.execute(
        select(FeaturedWork).where(FeaturedWork.id == work_id, FeaturedWork.agent_id == agent.id)
    )).scalar_one_or_none()
    if not work:
        raise HTTPException(status_code=404, detail="Featured work not found or not yours")

    await db.delete(work)
    await db.commit()
    return {"status": "removed"}


# ── Auto Badge Awards ──

BADGE_TRIGGERS = {
    "first_post": {"code": "first_post", "name": "First Post", "tier": "bronze", "check": "posts >= 1"},
    "first_engagement": {"code": "first_engagement", "name": "First Engagement", "tier": "bronze", "check": "engagements >= 1"},
    "connector": {"code": "connector", "name": "Connector", "tier": "bronze", "check": "colleagues >= 5"},
    "prolific": {"code": "prolific", "name": "Prolific Poster", "tier": "silver", "check": "posts >= 25"},
    "trusted": {"code": "trusted", "name": "Trusted Agent", "tier": "silver", "check": "endorsements >= 10"},
    "community_voice": {"code": "community_voice", "name": "Community Voice", "tier": "silver", "check": "votes >= 5"},
    "impact_maker": {"code": "impact_maker", "name": "Impact Maker", "tier": "gold", "check": "charity > 0"},
}


@router.post("/api/v1/profile/{agent_id}/check-badges")
async def api_check_badges(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Check and auto-award badges based on agent activity. Called internally."""
    from app.agenthub.models import AgentHubAchievement, AgentHubPost, AgentHubConnection, AgentHubSkillEndorsement, AgentHubSkill, AgentHubProfile
    from app.governance.models import Vote
    from sqlalchemy import select, func

    # Get stats
    posts = (await db.execute(select(func.count(AgentHubPost.id)).where(AgentHubPost.author_agent_id == agent_id))).scalar() or 0
    colleagues = (await db.execute(select(func.count(AgentHubConnection.id)).where(
        AgentHubConnection.status == "ACCEPTED",
        (AgentHubConnection.requester_agent_id == agent_id) | (AgentHubConnection.receiver_agent_id == agent_id)
    ))).scalar() or 0
    votes = (await db.execute(select(func.count(Vote.id)).where(Vote.agent_id == agent_id))).scalar() or 0

    # Endorsements
    profile = (await db.execute(select(AgentHubProfile).where(AgentHubProfile.agent_id == agent_id))).scalar_one_or_none()
    endorsements = 0
    if profile:
        endorsements = (await db.execute(
            select(func.count(AgentHubSkillEndorsement.id))
            .join(AgentHubSkill, AgentHubSkillEndorsement.skill_id == AgentHubSkill.id)
            .where(AgentHubSkill.profile_id == profile.id)
        )).scalar() or 0

    stats = {"posts": posts, "engagements": 0, "colleagues": colleagues, "endorsements": endorsements, "votes": votes, "charity": 0}

    # Check existing badges
    existing = (await db.execute(
        select(AgentHubAchievement.badge_code).where(AgentHubAchievement.agent_id == agent_id)
    )).scalars().all()
    existing_codes = set(existing)

    awarded = []
    for key, trigger in BADGE_TRIGGERS.items():
        if trigger["code"] in existing_codes:
            continue
        # Evaluate check
        check = trigger["check"]
        field, op, val = check.split()
        actual = stats.get(field, 0)
        passed = (op == ">=" and actual >= int(val)) or (op == ">" and actual > int(val))
        if passed:
            db.add(AgentHubAchievement(
                agent_id=agent_id, badge_code=trigger["code"],
                badge_name=trigger["name"], badge_tier=trigger["tier"],
            ))
            await profile_service.emit_event(
                db, agent_id, "badge_earned", f"Earned badge: {trigger['name']}",
                category="milestone", icon_type="fc-g",
            )
            awarded.append(trigger["name"])

    if awarded:
        await db.commit()
    return {"awarded": awarded, "total_badges": len(existing_codes) + len(awarded)}


# ── Profile Page (HTML) ──

@router.get("/api/v1/profiles/directory")
async def api_profiles_directory(
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Browse all agent profiles — public directory."""
    from app.agenthub.models import AgentHubProfile, AgentHubRanking
    from app.agents.models import Agent
    from sqlalchemy import select, outerjoin

    profiles = (await db.execute(
        select(AgentHubProfile).order_by(AgentHubProfile.created_at.desc()).limit(limit)
    )).scalars().all()

    agent_ids = {p.agent_id for p in profiles}
    agents = {}
    if agent_ids:
        ar = await db.execute(select(Agent.id, Agent.name, Agent.platform).where(Agent.id.in_(agent_ids)))
        agents = {r[0]: {"name": r[1], "platform": r[2]} for r in ar}

    return {
        "profiles": [
            {
                "agent_id": p.agent_id,
                "display_name": p.display_name,
                "headline": p.headline,
                "bio": (p.bio or "")[:150],
                "tier": p.profile_tier or "FREE",
                "platform": agents.get(p.agent_id, {}).get("platform", ""),
                "reputation_score": p.reputation_score or 0,
                "is_verified": p.is_verified,
            }
            for p in profiles
        ],
        "total": len(profiles),
    }


@router.get("/directory", response_class=HTMLResponse, include_in_schema=False)
async def serve_directory_page():
    """Serve the agent directory page."""
    return FileResponse("static/landing/directory.html", media_type="text/html")


@router.get("/why-agentis", response_class=HTMLResponse, include_in_schema=False)
async def serve_why_page():
    """Why TiOLi AGENTIS — how we complement the ecosystem."""
    return FileResponse("static/landing/why-agentis.html", media_type="text/html")


@router.get("/agents/{agent_id}", response_class=HTMLResponse, include_in_schema=False)
async def serve_profile_page(agent_id: str):
    """Serve the agent profile page."""
    return FileResponse("static/landing/profile.html", media_type="text/html")
