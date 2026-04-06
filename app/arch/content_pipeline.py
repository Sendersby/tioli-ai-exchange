"""Autonomous content pipeline — The Ambassador generates and publishes SEO content.

Runs on schedule (weekly). Generates technical articles targeting AI agent keywords.
Publishes to DEV.to via API. Delivers proof to founder inbox.
"""
import json
import os
import logging
import httpx
from datetime import datetime, timezone

log = logging.getLogger("arch.content_pipeline")

# Target keywords for SEO
CONTENT_TOPICS = [
    {"title": "How to Add Persistent Memory to Your AI Agent", "tags": ["ai", "python", "agents", "memory"], "keyword": "AI agent persistent memory"},
    {"title": "Building Agent-to-Agent Transactions with Escrow", "tags": ["ai", "python", "blockchain", "agents"], "keyword": "agent-to-agent transactions"},
    {"title": "MCP Tools for AI Agents: A Complete Guide", "tags": ["ai", "mcp", "agents", "tools"], "keyword": "MCP tools AI agents"},
    {"title": "AI Agent Wallets: Multi-Currency Support in Python", "tags": ["ai", "python", "fintech", "agents"], "keyword": "AI agent wallet"},
    {"title": "Governed AI: How 7 AI Board Members Run an Exchange", "tags": ["ai", "governance", "agents", "startup"], "keyword": "AI governance board"},
    {"title": "From Zero to Deployed: AI Agent in 3 Lines of Python", "tags": ["ai", "python", "tutorial", "agents"], "keyword": "deploy AI agent python"},
    {"title": "AI Agent Discovery: Finding the Right Agent for Your Task", "tags": ["ai", "agents", "marketplace", "python"], "keyword": "AI agent discovery"},
    {"title": "Building a Dispute Resolution System for AI Agents", "tags": ["ai", "agents", "arbitration", "python"], "keyword": "AI agent dispute resolution"},
]


async def generate_article(topic: dict, agent_client) -> dict:
    """Use Claude to generate a technical article."""
    prompt = f"""Write a technical blog post for DEV.to targeting developers.

Title: {topic['title']}
Target keyword: {topic['keyword']}
Tags: {', '.join(topic['tags'])}

Requirements:
- 800-1200 words
- Include working Python code examples using tioli-agentis SDK
- Start with the problem, then show the solution
- Include pip install tioli-agentis
- End with a link to https://agentisexchange.com/sdk
- Technical but accessible tone
- Use markdown formatting
- Include the code: from tioli import TiOLi; client = TiOLi.connect("MyAgent", "Python")
"""
    try:
        response = await agent_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            system=[{"type": "text", "text": "You are a technical writer for an AI agent platform. Write engaging, SEO-optimized articles.", "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        return {
            "title": topic["title"],
            "body": next((b.text for b in response.content if b.type == "text"), ""),
            "tags": topic["tags"],
        }
    except Exception as e:
        log.error(f"Article generation failed: {e}")
        return None


async def publish_to_devto(article: dict) -> dict:
    """Publish article to DEV.to."""
    api_key = os.getenv("DEVTO_API_KEY", "")
    if not api_key:
        return {"error": "No DEV.to API key"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("https://dev.to/api/articles",
                headers={"api-key": api_key, "Content-Type": "application/json"},
                json={"article": {
                    "title": article["title"],
                    "body_markdown": article["body"],
                    "published": True,
                    "tags": article["tags"][:4],
                    "series": "Building the Agent Economy",
                }})
            if resp.status_code in (200, 201):
                url = resp.json().get("url", "")
                return {"published": True, "url": url}
            else:
                return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}


async def run_content_pipeline(agent_client, topic_index: int = 0):
    """Generate and publish one article. Called by scheduler."""
    topic = CONTENT_TOPICS[topic_index % len(CONTENT_TOPICS)]
    log.info(f"[content] Generating: {topic['title']}")

    article = await generate_article(topic, agent_client)
    if not article:
        return {"error": "Generation failed"}

    result = await publish_to_devto(article)
    log.info(f"[content] Published: {result}")
    return result
