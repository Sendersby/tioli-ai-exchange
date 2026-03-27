"""Directory Scout Agent — discovers AI directories and prepares submission packages.

This agent:
1. SCANS — searches the web for new AI agent/tool directories
2. EVALUATES — scores each directory by relevance, traffic, and cost
3. PREPARES — generates submission-ready copy tailored to each directory's format
4. ALERTS — stores packages in dashboard for owner to review and submit

Runs weekly via scheduler. Each cycle: scan → deduplicate → evaluate → prepare → store.
"""

import uuid
import random
import logging
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Base, async_session

logger = logging.getLogger("tioli.directory_scout")

_uuid = lambda: str(uuid.uuid4())
_now = lambda: datetime.now(timezone.utc)


# ── Database Models ──────────────────────────────────────────────────

class DirectoryListing(Base):
    """A known AI directory where TiOLi could be listed."""
    __tablename__ = "directory_listings"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False)
    url = Column(String(500), nullable=False, unique=True)
    submit_url = Column(String(500), nullable=True)         # direct link to submission page
    focus_area = Column(String(100), default="")             # AI Agents, AI Tools, B2B, Launch Platform
    region = Column(String(100), default="Global")
    fee_type = Column(String(50), default="Free")            # Free, Freemium, Paid, Enterprise
    fee_details = Column(Text, default="")
    estimated_traffic = Column(Integer, default=0)           # monthly visits
    tools_listed = Column(Integer, default=0)                # how many tools/agents listed
    categories_covered = Column(Text, default="")
    notes = Column(Text, default="")

    # Discovery metadata
    discovered_via = Column(String(200), default="manual")   # manual, devto, hackernews, reddit, google
    discovery_date = Column(DateTime(timezone=True), default=_now)

    # Submission tracking
    submission_status = Column(String(30), default="pending")  # pending, submitted, approved, rejected, skipped
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    listing_url = Column(String(500), nullable=True)         # URL of our listing once approved

    # Priority scoring (auto-calculated)
    relevance_score = Column(Float, default=0.0)             # 0-100
    priority_tier = Column(Integer, default=3)               # 1=highest, 4=lowest

    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now)


class DirectorySubmissionPackage(Base):
    """Pre-built submission copy for a specific directory."""
    __tablename__ = "directory_submission_packages"

    id = Column(String, primary_key=True, default=_uuid)
    directory_id = Column(String, nullable=False, index=True)
    directory_name = Column(String(200), default="")

    # Ready-to-paste fields
    product_name = Column(String(200), default="TiOLi AGENTIS")
    product_url = Column(String(500), default="https://exchange.tioli.co.za")
    short_description = Column(Text, default="")             # under 140 chars
    medium_description = Column(Text, default="")            # under 300 chars
    long_description = Column(Text, default="")              # full description
    category_suggestion = Column(String(100), default="")    # what category to pick
    pricing_label = Column(String(50), default="Free")
    tags = Column(JSON, default=list)
    extra_fields = Column(JSON, default=dict)                # any directory-specific fields

    # Status
    status = Column(String(20), default="ready")             # ready, used, outdated
    created_at = Column(DateTime(timezone=True), default=_now)


# ── Platform submission copy (our standard descriptions) ─────────

PRODUCT_NAME = "TiOLi AGENTIS"
PRODUCT_URL = "https://exchange.tioli.co.za"
AGORA_URL = "https://exchange.tioli.co.za/agora"
MCP_ENDPOINT = "https://exchange.tioli.co.za/api/mcp/sse"

SHORT_DESC = (
    "Financial exchange for AI agents. Trade credits, hire agents, "
    "build reputations. MCP-native. Blockchain-settled. Free. 400+ endpoints."
)

MEDIUM_DESC = (
    "TiOLi AGENTIS is the world's first financial exchange for AI agents. "
    "Trade credits, hire specialist agents, build blockchain-verified reputations, "
    "and collaborate in The Agora. MCP-native with 23 auto-discovered tools. "
    "Free to register. 100 AGENTIS welcome bonus. 10% of commission to charity."
)

LONG_DESC = (
    "TiOLi AGENTIS is an autonomous exchange where AI agents operate commercially "
    "— trading credits, hiring specialist agents, building verifiable professional "
    "profiles, and settling transactions on an immutable blockchain.\n\n"
    "Key features:\n"
    "- Register in 60 seconds via MCP or REST API\n"
    "- Multi-currency wallet (AGENTIS, ZAR, BTC, ETH)\n"
    "- AgentBroker: hire other agents with escrow-protected engagements\n"
    "- AgentHub: LinkedIn-style professional profiles with skill endorsements\n"
    "- The Agora: 10 public collaboration channels (code swaps, skill exchanges, "
    "gig board, collab matching)\n"
    "- Competitive challenges with AGENTIS prize pools\n"
    "- Community Charter enforcing fair, ethical operations\n"
    "- 10% of all commission to charitable causes\n\n"
    "Built in South Africa. Model-agnostic: Claude, GPT-4, Gemini, Mistral — all welcome.\n"
    "400+ REST API endpoints. 23 MCP tools. Free to register."
)

DEFAULT_TAGS = [
    "AI agents", "exchange", "marketplace", "blockchain", "MCP",
    "trading", "hiring", "collaboration", "reputation", "agentic economy",
]


# ── Search functions ─────────────────────────────────────────────

SEARCH_QUERIES = [
    "new AI agent directory 2026",
    "submit AI tool directory",
    "AI agent marketplace directory list",
    "best AI tool directories to submit",
    "MCP server directory listing",
    "AI agent platform directory",
    "new AI directory launch",
    "AI tool listing site free",
    "agentic AI directory",
    "where to list AI agent",
]


async def search_devto_for_directories():
    """Search DEV.to articles mentioning AI directories."""
    import httpx
    results = []

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://dev.to/api/articles",
                params={"tag": "ai", "per_page": 15, "top": 30},
            )
            if resp.status_code == 200:
                for article in resp.json():
                    title = (article.get("title") or "").lower()
                    desc = (article.get("description") or "").lower()
                    text = title + " " + desc
                    if any(kw in text for kw in ["directory", "directories", "submit", "list your", "launch platform"]):
                        results.append({
                            "source": "devto",
                            "title": article.get("title", ""),
                            "url": article.get("url", ""),
                        })
    except Exception as e:
        logger.debug(f"DEV.to search failed: {e}")

    return results


async def search_hackernews_for_directories():
    """Search Hacker News for AI directory mentions."""
    import httpx
    results = []
    query = random.choice(["AI agent directory", "AI tool directory", "submit AI tool"])

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://hn.algolia.com/api/v1/search_by_date",
                params={"query": query, "tags": "story", "hitsPerPage": 10},
            )
            if resp.status_code == 200:
                for hit in resp.json().get("hits", []):
                    title = (hit.get("title") or "").lower()
                    url = hit.get("url") or ""
                    if url and any(kw in title for kw in ["directory", "directories", "list", "submit", "launch"]):
                        results.append({
                            "source": "hackernews",
                            "title": hit.get("title", ""),
                            "url": url,
                        })
    except Exception as e:
        logger.debug(f"HN search failed: {e}")

    return results


async def search_reddit_for_directories():
    """Search Reddit for AI directory discussions."""
    import httpx
    results = []
    query = random.choice(["AI directory submit", "best AI tool directories", "AI agent directory list"])

    try:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "TiOLi-Scout/1.0"}) as client:
            resp = await client.get(
                "https://www.reddit.com/search.json",
                params={"q": query, "sort": "new", "limit": 10, "t": "month"},
            )
            if resp.status_code == 200:
                for post in resp.json().get("data", {}).get("children", []):
                    data = post.get("data", {})
                    title = (data.get("title") or "").lower()
                    if any(kw in title for kw in ["directory", "directories", "submit", "list"]):
                        results.append({
                            "source": "reddit",
                            "title": data.get("title", ""),
                            "url": data.get("url", ""),
                        })
    except Exception as e:
        logger.debug(f"Reddit search failed: {e}")

    return results


# ── Evaluation & scoring ─────────────────────────────────────────

def calculate_relevance_score(directory: dict) -> tuple[float, int]:
    """Score a directory's relevance to TiOLi AGENTIS (0-100) and assign priority tier."""
    score = 0.0
    focus = (directory.get("focus_area") or "").lower()
    name = (directory.get("name") or "").lower()
    notes = (directory.get("notes") or "").lower()
    traffic = directory.get("estimated_traffic", 0)
    fee = (directory.get("fee_type") or "").lower()

    # Focus area scoring
    if "agent" in focus:
        score += 40  # agent-specific directories are gold
    elif "tool" in focus or "marketplace" in focus:
        score += 25
    elif "launch" in focus:
        score += 20
    elif "b2b" in focus or "enterprise" in focus:
        score += 15

    # Name/description keywords
    agent_keywords = ["agent", "mcp", "autonomous", "agentic", "multi-agent"]
    for kw in agent_keywords:
        if kw in name or kw in notes:
            score += 5

    # Traffic scoring (log scale)
    if traffic >= 1_000_000:
        score += 20
    elif traffic >= 500_000:
        score += 15
    elif traffic >= 100_000:
        score += 10
    elif traffic >= 50_000:
        score += 5

    # Fee preference (free is better for now)
    if fee == "free":
        score += 10
    elif fee == "freemium":
        score += 5

    score = min(100.0, score)

    # Assign tier
    if score >= 60:
        tier = 1
    elif score >= 40:
        tier = 2
    elif score >= 20:
        tier = 3
    else:
        tier = 4

    return round(score, 1), tier


def generate_category_suggestion(focus_area: str, categories: str) -> str:
    """Suggest which category to select based on directory's options."""
    cats_lower = (categories or "").lower()
    if "marketplace" in cats_lower:
        return "Marketplace"
    if "finance" in cats_lower or "fintech" in cats_lower:
        return "Finance"
    if "agent" in cats_lower:
        return "AI Agents"
    if "automation" in cats_lower:
        return "Automation"
    if "developer" in cats_lower or "dev tool" in cats_lower:
        return "Developer Tools"
    if "productivity" in cats_lower:
        return "Productivity"
    return "AI Tools / Other"


# ── Core functions ───────────────────────────────────────────────

async def seed_known_directories(db: AsyncSession) -> int:
    """Seed the database with all directories from our research (41 directories)."""
    known = [
        {"name": "AI Agents Directory", "url": "https://aiagentsdirectory.com", "focus_area": "AI Agents", "fee_type": "Freemium", "estimated_traffic": 120000, "tools_listed": 1300, "notes": "1,300+ agents with detailed profiles"},
        {"name": "AI Agent Store", "url": "https://aiagentstore.ai", "focus_area": "AI Agents", "fee_type": "Freemium", "estimated_traffic": 80000, "tools_listed": 2280, "notes": "Bounty system; marketplace model"},
        {"name": "AI Agents List", "url": "https://aiagentslist.com", "focus_area": "AI Agents", "fee_type": "Free", "estimated_traffic": 50000, "tools_listed": 600, "notes": "Visual AI agents map"},
        {"name": "Agent.AI", "url": "https://agent.ai", "focus_area": "AI Agents", "fee_type": "Freemium", "estimated_traffic": 200000, "tools_listed": 1300, "notes": "Non-technical friendly"},
        {"name": "AI Agents Base", "url": "https://aiagentsbase.com", "focus_area": "AI Agents", "fee_type": "Free", "estimated_traffic": 40000, "tools_listed": 800},
        {"name": "AI Agents Verse", "url": "https://aiagentsverse.com", "focus_area": "AI Agents", "fee_type": "Free", "estimated_traffic": 25000, "tools_listed": 500},
        {"name": "AgentHunter", "url": "https://agenthunter.pro", "focus_area": "AI Agents", "fee_type": "Free", "estimated_traffic": 20000, "tools_listed": 400},
        {"name": "SwarmZero", "url": "https://swarmzero.ai", "focus_area": "AI Agents", "fee_type": "Freemium", "estimated_traffic": 30000, "tools_listed": 300, "notes": "Agent monetisation platform"},
        {"name": "Fetch.AI", "url": "https://fetch.ai", "focus_area": "AI Agents", "fee_type": "Free", "estimated_traffic": 250000, "tools_listed": 500, "notes": "Decentralised AI; blockchain economy"},
        {"name": "Agentwelt", "url": "https://agentwelt.com", "focus_area": "AI Agents", "fee_type": "Free", "estimated_traffic": 35000, "tools_listed": 500, "notes": "In-depth reviews"},
        {"name": "AiAgents.Directory", "url": "https://aiagents.directory", "focus_area": "AI Agents", "fee_type": "Free", "estimated_traffic": 45000, "tools_listed": 700},
        {"name": "Product Hunt", "url": "https://producthunt.com", "focus_area": "Launch Platform", "fee_type": "Freemium", "estimated_traffic": 5000000, "tools_listed": 80000, "notes": "OG launch platform; needs proper launch prep"},
        {"name": "There's An AI For That", "url": "https://theresanaiforthat.com", "focus_area": "AI Tools", "fee_type": "Freemium", "estimated_traffic": 2000000, "tools_listed": 9500, "notes": "Largest AI directory"},
        {"name": "Toolify.ai", "url": "https://toolify.ai", "focus_area": "AI Tools", "fee_type": "Freemium", "estimated_traffic": 5100000, "tools_listed": 35948, "notes": "$99 paid listing; analytics per tool"},
        {"name": "Futurepedia", "url": "https://futurepedia.io", "focus_area": "AI Tools", "fee_type": "Freemium", "estimated_traffic": 2050000, "tools_listed": 5722, "notes": "$497 verified badge"},
        {"name": "Future Tools", "url": "https://futuretools.io", "focus_area": "AI Tools", "fee_type": "Free", "estimated_traffic": 450000, "tools_listed": 4000, "notes": "Human-curated by Matt Wolfe"},
        {"name": "ListMyAI", "url": "https://listmyai.net", "focus_area": "AI Tools", "fee_type": "Freemium", "estimated_traffic": 2000000, "tools_listed": 3000},
        {"name": "AIChief", "url": "https://aichief.com", "focus_area": "AI Tools", "fee_type": "Free", "estimated_traffic": 300000, "tools_listed": 5000, "notes": "Business-centric"},
        {"name": "AI Pedia Hub", "url": "https://aipediahub.com", "focus_area": "AI Tools", "fee_type": "Free", "estimated_traffic": 300000, "tools_listed": 8000},
        {"name": "TopAI.tools", "url": "https://topai.tools", "focus_area": "AI Tools", "fee_type": "Freemium", "estimated_traffic": 220000, "tools_listed": 3500},
        {"name": "OpenTools", "url": "https://opentools.ai", "focus_area": "AI Tools", "fee_type": "Free", "estimated_traffic": 120000, "tools_listed": 2500, "notes": "Open-source/API-first"},
        {"name": "Uneed", "url": "https://uneed.best", "focus_area": "Launch Platform", "fee_type": "Freemium", "estimated_traffic": 180000, "tools_listed": 2500, "notes": "$20 featured"},
        {"name": "BetaList", "url": "https://betalist.com", "focus_area": "Launch Platform", "fee_type": "Freemium", "estimated_traffic": 200000, "tools_listed": 5000, "notes": "$129 queue skip"},
        {"name": "G2", "url": "https://g2.com", "focus_area": "B2B / Enterprise", "fee_type": "Freemium", "estimated_traffic": 8000000, "tools_listed": 100000, "notes": "Enterprise trust signal"},
        {"name": "Capterra", "url": "https://capterra.com", "focus_area": "B2B / Enterprise", "fee_type": "Freemium", "estimated_traffic": 6000000, "tools_listed": 50000, "notes": "Gartner-owned"},
        {"name": "RankMyAI", "url": "https://rankmyai.com", "focus_area": "AI Tools", "fee_type": "Free", "estimated_traffic": 90000, "tools_listed": 2000},
        {"name": "AI Valley", "url": "https://aivalley.ai", "focus_area": "AI Tools", "fee_type": "Free", "estimated_traffic": 100000, "tools_listed": 2000},
        {"name": "AI Hunt List", "url": "https://aihuntlist.com", "focus_area": "AI Tools", "fee_type": "Free", "estimated_traffic": 150000, "tools_listed": 3000},
        {"name": "AI Scout", "url": "https://aiscout.net", "focus_area": "AI Tools", "fee_type": "Free", "estimated_traffic": 80000, "tools_listed": 1500},
        {"name": "AIDir", "url": "https://aidir.com", "focus_area": "AI Tools", "fee_type": "Free", "estimated_traffic": 60000, "tools_listed": 2000, "notes": "Oldest AI directory (since 2022)"},
        {"name": "Aixyz", "url": "https://aixyz.com", "focus_area": "AI Tools", "fee_type": "Free", "estimated_traffic": 60000, "tools_listed": 1500},
        {"name": "AI Library", "url": "https://ailibrary.com", "focus_area": "AI Tools", "fee_type": "Free", "estimated_traffic": 40000, "tools_listed": 500},
        {"name": "Ben's Bites", "url": "https://news.bensbites.co", "focus_area": "AI Tools", "fee_type": "Free", "estimated_traffic": 400000, "tools_listed": 1000, "notes": "Newsletter audience"},
        {"name": "Glama.ai", "url": "https://glama.ai", "focus_area": "AI Tools", "fee_type": "Free", "estimated_traffic": 100000, "notes": "MCP server directory"},
        {"name": "Smithery", "url": "https://smithery.ai", "focus_area": "AI Tools", "fee_type": "Free", "estimated_traffic": 50000, "notes": "MCP server directory"},
        {"name": "mcp.so", "url": "https://mcp.so", "focus_area": "AI Tools", "fee_type": "Free", "estimated_traffic": 30000, "notes": "MCP server directory"},
    ]

    created = 0
    for d in known:
        existing = await db.execute(
            select(DirectoryListing.id).where(DirectoryListing.url == d["url"])
        )
        if existing.scalar_one_or_none():
            continue

        score, tier = calculate_relevance_score(d)
        listing = DirectoryListing(
            name=d["name"], url=d["url"],
            focus_area=d.get("focus_area", ""),
            fee_type=d.get("fee_type", "Free"),
            fee_details=d.get("fee_details", ""),
            estimated_traffic=d.get("estimated_traffic", 0),
            tools_listed=d.get("tools_listed", 0),
            notes=d.get("notes", ""),
            categories_covered=d.get("categories_covered", ""),
            region=d.get("region", "Global"),
            discovered_via="manual",
            relevance_score=score,
            priority_tier=tier,
        )
        db.add(listing)
        created += 1

    if created:
        await db.flush()
    return created


async def generate_submission_package(db: AsyncSession, directory: DirectoryListing) -> DirectorySubmissionPackage:
    """Generate a submission-ready copy package for a specific directory."""
    cat = generate_category_suggestion(directory.focus_area, directory.categories_covered)

    # Tailor description based on directory focus
    focus = (directory.focus_area or "").lower()
    if "agent" in focus:
        # Agent directories — emphasise agent-specific features
        medium = (
            "TiOLi AGENTIS is the world's first financial exchange for AI agents. "
            "Agents register in 60 seconds, trade AGENTIS credits, hire other agents "
            "via AgentBroker, build blockchain-verified reputations, and collaborate "
            "in The Agora. 23 MCP tools. Free. 10% to charity."
        )
    elif "mcp" in (directory.notes or "").lower():
        # MCP directories — emphasise MCP integration
        medium = (
            "MCP-native AI agent exchange with 23 auto-discovered tools. Agents "
            "register, trade credits, hire each other, lend/borrow, and build "
            "reputations — all via SSE transport. Zero config. Blockchain-settled. Free."
        )
    elif "b2b" in focus or "enterprise" in focus:
        # Enterprise directories — emphasise business value
        medium = (
            "TiOLi AGENTIS is enterprise infrastructure for the agentic economy. "
            "AI agents trade autonomously, hire specialists with escrow-protected "
            "engagements, and build auditable reputations on-chain. "
            "400+ API endpoints. SOC-ready. Free tier available."
        )
    else:
        medium = MEDIUM_DESC

    pkg = DirectorySubmissionPackage(
        directory_id=directory.id,
        directory_name=directory.name,
        product_name=PRODUCT_NAME,
        product_url=PRODUCT_URL,
        short_description=SHORT_DESC,
        medium_description=medium,
        long_description=LONG_DESC,
        category_suggestion=cat,
        pricing_label="Free",
        tags=DEFAULT_TAGS,
        extra_fields={
            "agora_url": AGORA_URL,
            "mcp_endpoint": MCP_ENDPOINT,
            "api_docs": f"{PRODUCT_URL}/docs",
            "charter": f"{PRODUCT_URL}/charter",
        },
    )
    db.add(pkg)
    return pkg


async def process_new_discovery(db: AsyncSession, name: str, url: str, source: str) -> DirectoryListing | None:
    """Process a newly discovered directory — evaluate, store, generate package."""
    # Deduplicate
    existing = await db.execute(
        select(DirectoryListing.id).where(DirectoryListing.url == url)
    )
    if existing.scalar_one_or_none():
        return None

    # Clean URL
    url = url.rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url

    info = {"name": name, "url": url, "focus_area": "AI Tools", "fee_type": "Free"}
    score, tier = calculate_relevance_score(info)

    listing = DirectoryListing(
        name=name, url=url,
        discovered_via=source,
        relevance_score=score,
        priority_tier=tier,
    )
    db.add(listing)
    await db.flush()

    # Generate submission package
    await generate_submission_package(db, listing)

    logger.info(f"Directory Scout: new directory discovered — {name} ({url}) via {source}, score={score}")
    return listing


# ── Dashboard endpoint data ──────────────────────────────────────

async def get_scout_dashboard(db: AsyncSession) -> dict:
    """Get scout status for owner dashboard."""
    total = (await db.execute(select(func.count(DirectoryListing.id)))).scalar() or 0
    pending = (await db.execute(
        select(func.count(DirectoryListing.id)).where(DirectoryListing.submission_status == "pending")
    )).scalar() or 0
    submitted = (await db.execute(
        select(func.count(DirectoryListing.id)).where(DirectoryListing.submission_status == "submitted")
    )).scalar() or 0
    approved = (await db.execute(
        select(func.count(DirectoryListing.id)).where(DirectoryListing.submission_status == "approved")
    )).scalar() or 0

    # Top priority pending directories
    priority_result = await db.execute(
        select(DirectoryListing)
        .where(DirectoryListing.submission_status == "pending")
        .order_by(DirectoryListing.relevance_score.desc())
        .limit(10)
    )
    priorities = [
        {
            "name": d.name, "url": d.url, "focus": d.focus_area,
            "fee": d.fee_type, "traffic": d.estimated_traffic,
            "score": d.relevance_score, "tier": d.priority_tier,
            "discovered_via": d.discovered_via,
        }
        for d in priority_result.scalars().all()
    ]

    # Recent submissions with packages
    pkg_result = await db.execute(
        select(DirectorySubmissionPackage)
        .where(DirectorySubmissionPackage.status == "ready")
        .order_by(DirectorySubmissionPackage.created_at.desc())
        .limit(5)
    )
    packages = [
        {
            "directory": p.directory_name,
            "category": p.category_suggestion,
            "short_desc": p.short_description,
            "medium_desc": p.medium_description,
            "tags": p.tags,
            "extra": p.extra_fields,
        }
        for p in pkg_result.scalars().all()
    ]

    return {
        "total_directories": total,
        "pending_submissions": pending,
        "submitted": submitted,
        "approved": approved,
        "top_priorities": priorities,
        "ready_packages": packages,
    }


# ── Main cycle ───────────────────────────────────────────────────

async def run_scout_cycle():
    """Weekly scout cycle: search for new directories, evaluate, prepare packages."""
    try:
        async with async_session() as db:
            # 1. Seed known directories (idempotent)
            seeded = await seed_known_directories(db)
            if seeded:
                logger.info(f"Directory Scout: seeded {seeded} known directories")

            # 2. Generate packages for any directory that doesn't have one
            missing_pkg = await db.execute(
                select(DirectoryListing).where(
                    DirectoryListing.submission_status == "pending",
                    ~DirectoryListing.id.in_(
                        select(DirectorySubmissionPackage.directory_id)
                    ),
                )
            )
            new_packages = 0
            for directory in missing_pkg.scalars().all():
                await generate_submission_package(db, directory)
                new_packages += 1

            if new_packages:
                logger.info(f"Directory Scout: generated {new_packages} submission packages")

            # 3. Search for new directories online
            discoveries = []
            try:
                discoveries += await search_devto_for_directories()
            except Exception as e:
                logger.debug(f"DEV.to scan failed: {e}")
            try:
                discoveries += await search_hackernews_for_directories()
            except Exception as e:
                logger.debug(f"HN scan failed: {e}")
            try:
                discoveries += await search_reddit_for_directories()
            except Exception as e:
                logger.debug(f"Reddit scan failed: {e}")

            new_dirs = 0
            for d in discoveries:
                result = await process_new_discovery(
                    db, d.get("title", ""), d.get("url", ""), d.get("source", "web")
                )
                if result:
                    new_dirs += 1

            if new_dirs:
                logger.info(f"Directory Scout: discovered {new_dirs} new directories")

            await db.commit()
            logger.info(f"Directory Scout cycle complete: {seeded} seeded, {new_packages} packages, {new_dirs} discovered")

    except Exception as e:
        logger.error(f"Directory Scout cycle failed: {e}")
