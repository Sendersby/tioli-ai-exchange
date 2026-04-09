"""Medium article publishing via REST API.
Feature flag: ARCH_MEDIUM_ENABLED
Requires: MEDIUM_TOKEN in .env"""
import os
import logging
import httpx

log = logging.getLogger("arch.medium_poster")


async def post_to_medium(title: str, body: str, tags: list = None) -> dict:
    """Publish an article to Medium."""
    if os.environ.get("ARCH_MEDIUM_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    token = os.environ.get("MEDIUM_TOKEN", "")
    if not token:
        return {"error": "MEDIUM_TOKEN not configured",
                "setup": "Get your token at medium.com/me/settings/security → Integration tokens"}

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            # Get user ID first
            user_resp = await client.get("https://api.medium.com/v1/me",
                                          headers={"Authorization": f"Bearer {token}"})
            if user_resp.status_code != 200:
                return {"error": f"Medium auth failed: {user_resp.status_code}"}

            user_id = user_resp.json().get("data", {}).get("id", "")

            # Publish article
            article = {
                "title": title[:100],
                "contentFormat": "markdown",
                "content": body,
                "tags": (tags or ["ai-agents", "artificial-intelligence", "blockchain"])[:5],
                "publishStatus": "public",
                "canonicalUrl": "https://agentisexchange.com",
            }

            resp = await client.post(
                f"https://api.medium.com/v1/users/{user_id}/posts",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=article)

            if resp.status_code in (200, 201):
                data = resp.json().get("data", {})
                url = data.get("url", "")
                log.info(f"[medium] Published: {url}")
                return {"success": True, "url": url, "id": data.get("id", ""), "title": title[:60]}
            else:
                return {"error": f"Medium API {resp.status_code}", "detail": resp.text[:200]}

    except Exception as e:
        return {"error": str(e)[:200]}
