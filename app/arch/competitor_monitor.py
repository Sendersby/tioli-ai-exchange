"""Autonomous competitor monitoring — tracks rival platforms weekly.

Monitors: pricing, features, announcements, GitHub activity.
Delivers market intelligence to board sessions.
"""
import logging
import httpx
from datetime import datetime, timezone

log = logging.getLogger("arch.competitor")

COMPETITORS = [
    {"name": "Relevance AI", "url": "https://relevanceai.com", "github": "RelevanceAI"},
    {"name": "AgentOps", "url": "https://agentops.ai", "github": "AgentOps-AI"},
    {"name": "CrewAI", "url": "https://crewai.com", "github": "crewAIInc"},
    {"name": "AutoGen", "url": "https://microsoft.github.io/autogen/", "github": "microsoft/autogen"},
    {"name": "LangGraph", "url": "https://langchain-ai.github.io/langgraph/", "github": "langchain-ai/langgraph"},
]


async def monitor_competitors():
    """Check competitor GitHub activity and report changes."""
    results = []
    async with httpx.AsyncClient(timeout=15) as client:
        for comp in COMPETITORS:
            try:
                resp = await client.get(
                    f"https://api.github.com/repos/{comp['github']}",
                    headers={"Accept": "application/vnd.github.v3+json"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results.append({
                        "name": comp["name"],
                        "stars": data.get("stargazers_count", 0),
                        "forks": data.get("forks_count", 0),
                        "open_issues": data.get("open_issues_count", 0),
                        "last_push": data.get("pushed_at", ""),
                        "description": data.get("description", ""),
                    })
            except Exception as e:
                results.append({"name": comp["name"], "error": str(e)})

    return {
        "monitored_at": datetime.now(timezone.utc).isoformat(),
        "competitors": results,
    }
