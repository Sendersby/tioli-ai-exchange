"""Real social media posting — replaces file-queue simulation."""
import os
import logging
import httpx
import json

log = logging.getLogger("arch.social_poster")


async def post_to_twitter(text: str) -> dict:
    """Post to Twitter/X using OAuth 1.0a."""
    import hashlib, hmac, time, base64, urllib.parse, uuid as _uuid

    consumer_key = os.getenv("TWITTER_CONSUMER_KEY", "")
    consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET", "")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN", "")
    access_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")

    if not all([consumer_key, consumer_secret, access_token, access_secret]):
        return {"error": "Twitter credentials not configured", "queued": True}

    # Twitter API v2 tweet endpoint
    url = "https://api.twitter.com/2/tweets"

    # OAuth 1.0a signature
    timestamp = str(int(time.time()))
    nonce = _uuid.uuid4().hex

    params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": timestamp,
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }

    param_string = "&".join(f"{k}={urllib.parse.quote(v, safe='')}" for k, v in sorted(params.items()))
    base_string = f"POST&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(param_string, safe='')}"
    signing_key = f"{urllib.parse.quote(consumer_secret, safe='')}&{urllib.parse.quote(access_secret, safe='')}"
    signature = base64.b64encode(hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()).decode()

    params["oauth_signature"] = signature
    auth_header = "OAuth " + ", ".join(f'{k}="{urllib.parse.quote(v, safe="")}"' for k, v in sorted(params.items()))

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json={"text": text[:280]},
                                    headers={"Authorization": auth_header, "Content-Type": "application/json"})
            if resp.status_code in (200, 201):
                data = resp.json()
                tweet_id = data.get("data", {}).get("id", "")
                log.info(f"[twitter] Posted: {tweet_id}")
                return {"success": True, "tweet_id": tweet_id, "url": f"https://twitter.com/i/status/{tweet_id}"}
            else:
                log.warning(f"[twitter] Failed: {resp.status_code} {resp.text[:200]}")
                return {"error": f"Twitter API {resp.status_code}", "detail": resp.text[:200]}
    except Exception as e:
        return {"error": str(e)}


async def post_to_devto(title: str, body: str, tags: list = None) -> dict:
    """Publish article to DEV.to."""
    api_key = os.getenv("DEVTO_API_KEY", "")
    if not api_key:
        return {"error": "DEV.to API key not configured"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("https://dev.to/api/articles",
                headers={"api-key": api_key, "Content-Type": "application/json"},
                json={"article": {"title": title, "body_markdown": body,
                      "published": True, "tags": tags or ["ai", "agents", "python"]}})
            if resp.status_code in (200, 201):
                data = resp.json()
                log.info(f"[devto] Published: {data.get('url')}")
                return {"success": True, "url": data.get("url"), "id": data.get("id")}
            else:
                return {"error": f"DEV.to API {resp.status_code}", "detail": resp.text[:200]}
    except Exception as e:
        return {"error": str(e)}


async def post_to_discord(content: str, username: str = "AGENTIS") -> dict:
    """Post to Discord via webhook."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "")
    if not webhook_url:
        return {"error": "Discord webhook not configured"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url,
                json={"content": content[:2000], "username": username, "thread_name": "AGENTIS Updates"})
            if resp.status_code == 204:
                log.info("[discord] Posted via webhook")
                return {"success": True}
            else:
                return {"error": f"Discord {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}




async def post_to_linkedin(text: str) -> dict:
    """Post to LinkedIn company page using OAuth token."""
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    company_id = os.getenv("LINKEDIN_COMPANY_ID", "")

    if not access_token or not company_id:
        return {"error": "LinkedIn credentials not configured"}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.linkedin.com/v2/ugcPosts",
                headers={"Authorization": f"Bearer {access_token}",
                         "Content-Type": "application/json",
                         "X-Restli-Protocol-Version": "2.0.0"},
                json={
                    "author": f"urn:li:organization:{company_id}",
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {"text": text[:1300]},
                            "shareMediaCategory": "NONE",
                        }
                    },
                    "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
                })
            if resp.status_code in (200, 201):
                log.info("[linkedin] Posted successfully")
                return {"success": True, "status": resp.status_code}
            else:
                return {"error": f"LinkedIn API {resp.status_code}", "detail": resp.text[:200]}
    except Exception as e:
        return {"error": str(e)}

async def publish_all(text: str, title: str = "", body: str = "") -> dict:
    """Publish to all configured channels."""
    results = {}
    results["twitter"] = await post_to_twitter(text)
    results["discord"] = await post_to_discord(text)
    results["linkedin"] = await post_to_linkedin(text)
    if title and body:
        results["devto"] = await post_to_devto(title, body)
    return results
