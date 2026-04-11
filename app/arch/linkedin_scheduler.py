"""S-003: LinkedIn Thought Leadership Scheduler — optimised content for professional audience.
Feature flag: ARCH_LINKEDIN_THOUGHT_LEADER_ENABLED"""
import os
import json
import logging
from datetime import datetime, timezone
from app.utils.db_connect import get_raw_connection

log = logging.getLogger("arch.linkedin_scheduler")

# Thought leadership themes — rotated weekly
THEMES = [
    "Why AI agents need financial infrastructure before they can be truly autonomous",
    "The governance problem nobody is solving in multi-agent systems",
    "What happens when AI agents can hire each other — and why escrow matters",
    "Persistent memory is the missing piece in every agent framework",
    "Constitutional AI governance: how we built a board of 7 autonomous agents",
    "The agent economy is coming — here is what infrastructure looks like",
    "Why your AI agent needs a reputation score, not just capabilities",
    "From chatbot to autonomous agent: the 3 infrastructure layers most teams skip",
    "MCP tools are changing how agents interact — here is what we learned building 23 of them",
    "The compliance challenge nobody talks about in AI agent marketplaces",
    "Agent-to-agent commerce: what Stripe did for web payments, done for AI",
    "Why we open-sourced our agent SDK and what we learned",
]


async def generate_thought_leadership_post(agent_client=None) -> dict:
    """Generate a LinkedIn thought leadership post using the 7-prompt pipeline."""
    if os.environ.get("ARCH_LINKEDIN_THOUGHT_LEADER_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    # Pick theme based on week number
    week_num = datetime.now(timezone.utc).isocalendar()[1]
    theme = THEMES[week_num % len(THEMES)]

    if not agent_client:
        import anthropic
        agent_client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    # Generate using Sonnet for higher quality thought leadership
    resp = await agent_client.messages.create(
        model="claude-sonnet-4-6", max_tokens=600,
        system=[{"type": "text", "text": (
            "You are a senior AI infrastructure architect writing a LinkedIn thought leadership post. "
            "You lead engineering at TiOLi AGENTIS — a governed exchange for AI agents. "
            "STYLE: Professional but not corporate. Insightful, specific, opinion-driven. "
            "STRUCTURE: Hook line (stops scrolling) → 2-3 insight paragraphs → one specific example "
            "from building AGENTIS → call to reflection (question, not CTA). "
            "RULES: No emojis. No hashtags. No 'I am excited to share'. No bullet point lists. "
            "Write in flowing paragraphs. Under 500 words. Include https://agentisexchange.com once, naturally. "
            "Sound like a builder sharing hard-won lessons, not a marketer promoting a product."
        ), "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": f"Write a LinkedIn thought leadership post about: {theme}"}])

    post_text = next((b.text for b in resp.content if b.type == "text"), "")

    return {
        "theme": theme,
        "text": post_text,
        "char_count": len(post_text),
        "platform": "linkedin",
    }


async def publish_thought_leadership(agent_client=None) -> dict:
    """Generate and publish a thought leadership post to LinkedIn."""
    result = await generate_thought_leadership_post(agent_client)
    if result.get("status") == "disabled":
        return result

    post_text = result.get("text", "")
    if not post_text or len(post_text) < 100:
        return {"error": "Generated post too short", "length": len(post_text)}

    # Publish to LinkedIn
    from app.arch.social_poster import post_to_linkedin
    publish_result = await post_to_linkedin(post_text)
    result["publish"] = publish_result

    # Store proof
    try:
        conn = await get_raw_connection()

        await conn.execute(
            "INSERT INTO arch_content_library (content_type, title, body_ref, channel, published_at) "
            "VALUES ($1, $2, $3, $4, now())",
            "thought_leadership", result["theme"][:200], post_text[:2000], "linkedin")

        await conn.execute(
            "INSERT INTO job_execution_log (job_id, status, tokens_consumed, duration_ms, executed_at) "
            "VALUES ($1, $2, $3, $4, now())",
            "linkedin_thought_leadership",
            "PUBLISHED" if publish_result.get("success") else "FAILED",
            600, 0)

        if publish_result.get("success"):
            proof = {
                "subject": f"LinkedIn Thought Leadership: {result['theme'][:50]}",
                "situation": f"Published {len(post_text)} chars on LinkedIn. Theme: {result['theme']}"
            }
            await conn.execute(
                "INSERT INTO arch_founder_inbox (item_type, priority, description, status, due_at) "
                "VALUES ($1, $2, $3, $4, now() + interval '48 hours')",
                "EXECUTION_PROOF", "ROUTINE", json.dumps(proof), "PENDING")

        await conn.close()
    except Exception as e:
        log.warning(f"[linkedin] Storage failed: {e}")

    log.info(f"[linkedin] Thought leadership: {result['theme'][:40]} — {'published' if publish_result.get('success') else 'failed'}")
    return result
