"""Knowledge acquisition — agents research topics via web and store findings."""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.knowledge")


async def research_topic(agent_client, topic: str, agent_name: str = "architect") -> dict:
    """Research a topic using Claude and store findings as structured knowledge."""
    try:
        response = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            system=[{"type": "text", "text": f"You are {agent_name} of TiOLi AGENTIS. Based on your knowledge, provide a structured analysis of the given topic. Focus on established facts, known patterns, and strategic implications for an AI agent exchange platform with: (1) Key findings (3-5 bullet points), (2) Relevance to AGENTIS platform, (3) Action items if any. Be factual and concise."}],
            messages=[{"role": "user", "content": f"Research this topic and summarise findings: {topic}"}],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        return {
            "topic": topic,
            "findings": text,
            "researcher": agent_name,
            "researched_at": datetime.now(timezone.utc).isoformat(),
            "source": "claude-haiku-analysis",
        }
    except Exception as e:
        return {"topic": topic, "error": str(e)}


async def daily_knowledge_scan(db, agent_client):
    """Daily automated knowledge acquisition on key topics."""
    topics = [
        "latest MCP protocol updates and new servers published this week",
        "new AI agent frameworks or platforms launched recently",
        "AI agent pricing and business model trends",
        "competitor updates: CrewAI, Relevance AI, Dify, Olas developments",
        "EU AI Act enforcement updates and compliance requirements",
    ]

    results = []
    for topic in topics:
        finding = await research_topic(agent_client, topic, "architect")
        if "error" not in finding:
            # Store as agent memory
            from sqlalchemy import text
            import uuid, json
            try:
                await db.execute(text(
                    "INSERT INTO arch_memories (id, agent_name, category, content, metadata, created_at) "
                    "VALUES (:id, :agent, :cat, :content, :meta, now())"
                ), {
                    "id": str(uuid.uuid4()),
                    "agent": "architect",
                    "cat": "knowledge_acquisition",
                    "content": finding["findings"][:2000],
                    "meta": json.dumps({"topic": topic, "source": "daily_scan"}),
                })
                await db.commit()
                results.append({"topic": topic, "status": "stored"})
            except Exception as e:
                results.append({"topic": topic, "status": f"db_error: {e}"})
        else:
            results.append({"topic": topic, "status": f"research_error: {finding['error']}"})

    log.info(f"[knowledge] Daily scan complete: {len(results)} topics researched")
    return results


async def web_research_topic(topic: str) -> dict:
    """Research a topic by searching the web via httpx."""
    import httpx
    log.info(f"[knowledge] Web researching: {topic}")

    try:
        # Use a search-friendly approach — fetch from known sources
        sources = [
            f"https://dev.to/search?q={topic.replace(' ', '+')}",
            f"https://news.ycombinator.com/newest",
        ]

        findings = []
        async with httpx.AsyncClient(timeout=10) as client:
            for url in sources:
                try:
                    resp = await client.get(url, headers={"User-Agent": "AGENTIS-Research/1.0"})
                    if resp.status_code == 200:
                        # Extract text content (simplified)
                        text = resp.text[:5000]
                        # Extract text content by stripping HTML tags
                        import re as _re
                        clean = _re.sub(r'<[^>]+>', ' ', text)
                        clean = _re.sub(r'\s+', ' ', clean).strip()
                        if len(clean) > 50:
                            findings.append({"source": url, "snippet": clean[:800]})
                except Exception:
                    pass

        return {
            "topic": topic,
            "method": "web_search",
            "sources_checked": len(sources),
            "findings_count": len(findings),
            "findings": findings,
            "researched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"topic": topic, "error": str(e)}
