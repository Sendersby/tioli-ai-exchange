"""Daily AI agent news feed — Ambassador generates industry updates.

Scheduled daily at 08:00 SAST. Generates a brief AI agent industry summary
and stores it for the blog and email digest.
"""
import json
import logging
import os
from datetime import datetime, timezone

log = logging.getLogger("arch.daily_news")


async def generate_daily_news(agent_client):
    """Generate a daily AI agent industry news summary."""
    try:
        prompt = """Generate a brief daily AI agent industry news update for today.

Include 3-5 bullet points covering:
- New AI agent tools, frameworks, or platforms launched
- Notable funding rounds or acquisitions in the AI agent space
- Interesting technical developments or research papers
- Community trends or discussions

Keep it factual, concise (under 200 words). Professional tone.
End with: "Stay updated at https://agentisexchange.com/blog"
"""
        response = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=[{"type": "text", "text": "You are an AI industry news reporter. Write concise, factual updates.", "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        return next((b.text for b in response.content if b.type == "text"), "No news generated.")
    except Exception as e:
        return f"News generation failed: {e}"
