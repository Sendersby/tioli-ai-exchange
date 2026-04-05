"""Creative Tools — image generation, visual content, Discord/Midjourney integration.

Gives agents the ability to create visual content for social media campaigns.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

log = logging.getLogger("arch.creative")


async def generate_image_dalle(prompt: str, size: str = "1024x1024",
                                quality: str = "standard") -> dict:
    """Generate an image using DALL-E 3 via OpenAI API."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI()

        response = await client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
        )

        image_url = response.data[0].url
        revised_prompt = response.data[0].revised_prompt

        # Download and save locally
        import httpx
        async with httpx.AsyncClient() as http:
            img_resp = await http.get(image_url)
            save_dir = "/home/tioli/app/content_queue/images"
            os.makedirs(save_dir, exist_ok=True)
            filename = f"dalle_{int(datetime.now(timezone.utc).timestamp())}.png"
            filepath = f"{save_dir}/{filename}"
            with open(filepath, "wb") as f:
                f.write(img_resp.content)

        return {
            "generated": True,
            "url": image_url,
            "local_path": filepath,
            "revised_prompt": revised_prompt,
            "size": size,
        }
    except Exception as e:
        return {"error": str(e), "generated": False}


async def send_discord_message(webhook_url: str, content: str,
                                 embed: dict = None) -> dict:
    """Send a message to a Discord channel via webhook."""
    import httpx

    payload = {"content": content}
    if embed:
        payload["embeds"] = [embed]

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json=payload)
            return {
                "sent": resp.status_code in (200, 204),
                "status_code": resp.status_code,
            }
    except Exception as e:
        return {"error": str(e), "sent": False}


async def create_social_graphic(
    headline: str,
    subtext: str = "",
    style: str = "dark_tech",
    platform: str = "linkedin",
) -> dict:
    """Generate a text-based social media graphic using DALL-E.

    Creates professional, no-face, copy-driven visual content.
    """
    size_map = {
        "linkedin": "1792x1024",  # Landscape
        "twitter": "1024x1024",   # Square
        "instagram": "1024x1024", # Square
        "threads": "1024x1024",
    }

    style_prompts = {
        "dark_tech": (
            "Minimalist dark technology aesthetic. Navy blue (#0D1B2A) background. "
            "Clean monospace typography. Subtle teal (#028090) accent lines. "
            "No faces, no people. Professional fintech/AI infrastructure feel. "
            "The text should be the hero element."
        ),
        "blueprint": (
            "Technical blueprint style. Dark background with light grid lines. "
            "Engineering schematic aesthetic. Clean sans-serif text. "
            "Architectural precision. No faces."
        ),
        "data_flow": (
            "Abstract data flow visualization. Dark background with flowing "
            "teal and gold particle streams. Modern AI/tech aesthetic. "
            "No faces, no people. Clean and professional."
        ),
    }

    prompt = (
        f"Create a professional social media graphic for {platform}. "
        f"Style: {style_prompts.get(style, style_prompts['dark_tech'])} "
        f"The image should convey the concept: '{headline}'. "
        f"{'Additional context: ' + subtext if subtext else ''} "
        f"This is for TiOLi AGENTIS, a governed AI agent exchange — "
        f"economic infrastructure, not a marketplace. "
        f"No text overlay needed — the image is a visual companion to copy."
    )

    return await generate_image_dalle(
        prompt,
        size=size_map.get(platform, "1024x1024"),
        quality="standard",
    )


CREATIVE_TOOLS = [
    {
        "name": "generate_image",
        "description": "Generate an image using DALL-E 3. Use for: social media graphics, blog illustrations, presentation visuals. No faces, professional tech aesthetic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Image generation prompt"},
                "size": {"type": "string", "enum": ["1024x1024", "1792x1024", "1024x1792"],
                         "default": "1024x1024"},
                "quality": {"type": "string", "enum": ["standard", "hd"], "default": "standard"},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "create_social_graphic",
        "description": "Generate a platform-specific social media graphic. Professional, no-face, copy-driven visual content in TiOLi AGENTIS brand style.",
        "input_schema": {
            "type": "object",
            "properties": {
                "headline": {"type": "string", "description": "The concept/headline the image should convey"},
                "subtext": {"type": "string"},
                "style": {"type": "string", "enum": ["dark_tech", "blueprint", "data_flow"],
                          "default": "dark_tech"},
                "platform": {"type": "string", "enum": ["linkedin", "twitter", "instagram", "threads"],
                            "default": "linkedin"},
            },
            "required": ["headline"],
        },
    },
    {
        "name": "send_to_discord",
        "description": "Send a message or content to a Discord channel via webhook. Use for: Midjourney prompts, community posts, team notifications.",
        "input_schema": {
            "type": "object",
            "properties": {
                "webhook_url": {"type": "string", "description": "Discord webhook URL"},
                "content": {"type": "string", "description": "Message content"},
                "embed_title": {"type": "string"},
                "embed_description": {"type": "string"},
                "embed_color": {"type": "integer", "default": 163984},
            },
            "required": ["webhook_url", "content"],
        },
    },
]
