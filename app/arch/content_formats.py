"""Multi-format content generation — text, image prompts, video scripts, platform-specific."""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.content_formats")


async def generate_social_post(agent_client, topic: str, platform: str = "twitter") -> dict:
    """Generate a platform-optimized social media post."""
    limits = {"twitter": 280, "linkedin": 1300, "discord": 2000, "devto": 5000}
    char_limit = limits.get(platform, 280)

    try:
        response = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=[{"type": "text", "text": f"You are the Ambassador of TiOLi AGENTIS. Write a {platform} post about the given topic. Max {char_limit} chars. Professional, developer-friendly, confident tone. Include relevant hashtags for {platform}."}],
            messages=[{"role": "user", "content": topic}],
        )
        text = next((b.text for b in response.content if b.type == "text"), "")
        return {
            "platform": platform,
            "content": text[:char_limit],
            "char_count": len(text[:char_limit]),
            "char_limit": char_limit,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"error": str(e)}


async def generate_image_prompt(agent_client, topic: str) -> dict:
    """Generate a DALL-E prompt for social media graphics."""
    try:
        response = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=[{"type": "text", "text": "Generate a DALL-E 3 image prompt for a social media graphic. Dark theme (#061423 background), cyan (#77d4e5) and gold (#edc05f) accents. Modern, tech, AI aesthetic. The prompt should describe a compelling visual for the given topic."}],
            messages=[{"role": "user", "content": topic}],
        )
        prompt = next((b.text for b in response.content if b.type == "text"), "")
        return {
            "dalle_prompt": prompt,
            "style": "dark tech, #061423 bg, cyan/gold accents",
            "size": "1024x1024",
            "topic": topic,
        }
    except Exception as e:
        return {"error": str(e)}


async def generate_video_script(agent_client, topic: str, duration_seconds: int = 60) -> dict:
    """Generate a video script outline for YouTube/social."""
    try:
        response = await agent_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=[{"type": "text", "text": f"Write a {duration_seconds}-second video script outline for a TiOLi AGENTIS demo/tutorial. Format: [TIMESTAMP] VISUAL | NARRATION. Keep it concise and action-oriented."}],
            messages=[{"role": "user", "content": topic}],
        )
        script = next((b.text for b in response.content if b.type == "text"), "")
        return {
            "topic": topic,
            "duration": duration_seconds,
            "script": script,
            "format": "timestamp + visual + narration",
        }
    except Exception as e:
        return {"error": str(e)}


async def generate_all_formats(agent_client, topic: str) -> dict:
    """Generate content in all formats for a topic."""
    return {
        "twitter": await generate_social_post(agent_client, topic, "twitter"),
        "linkedin": await generate_social_post(agent_client, topic, "linkedin"),
        "image_prompt": await generate_image_prompt(agent_client, topic),
        "video_script": await generate_video_script(agent_client, topic, 60),
    }
