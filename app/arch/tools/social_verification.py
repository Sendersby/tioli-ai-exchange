"""Social media post verification tools for Arch Agents.

Verifies tweets and LinkedIn posts exist via their respective APIs,
returning proof URLs and engagement metrics for founder validation.
"""
import os
import logging
import json
from datetime import datetime

logger = logging.getLogger("arch.social_verification")

# Twitter/X API v2 — check both env var names
TWITTER_BEARER = os.environ.get("X_BEARER_TOKEN", "") or os.environ.get("TWITTER_BEARER_TOKEN", "")
TWITTER_HANDLE = os.environ.get("X_HANDLE", "Tioli4")

# LinkedIn API
LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_COMPANY_ID = os.environ.get("LINKEDIN_COMPANY_ID", "")


async def verify_tweet(tweet_id: str) -> dict:
    """Verify a tweet exists via the Twitter API v2 and return proof data.

    Returns: {exists, url, text, created_at, metrics, error}
    """
    if not TWITTER_BEARER:
        return {"exists": False, "error": "X_BEARER_TOKEN not configured"}

    if not tweet_id:
        return {"exists": False, "error": "No tweet_id provided"}

    # Clean the tweet_id — extract from URL if a full URL was passed
    if "/" in tweet_id:
        tweet_id = tweet_id.rstrip("/").split("/")[-1]

    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"https://api.twitter.com/2/tweets/{tweet_id}",
                params={
                    "tweet.fields": "created_at,public_metrics,text,author_id",
                },
                headers={"Authorization": f"Bearer {TWITTER_BEARER}"}
            )

            if response.status_code == 200:
                data = response.json().get("data", {})
                metrics = data.get("public_metrics", {})
                return {
                    "exists": True,
                    "tweet_id": tweet_id,
                    "url": f"https://x.com/{TWITTER_HANDLE}/status/{tweet_id}",
                    "text": data.get("text", ""),
                    "created_at": data.get("created_at", ""),
                    "likes": metrics.get("like_count", 0),
                    "retweets": metrics.get("retweet_count", 0),
                    "replies": metrics.get("reply_count", 0),
                    "impressions": metrics.get("impression_count", 0),
                    "note": "Tweet verified via Twitter API v2. Click the URL to view."
                }
            elif response.status_code == 404:
                return {"exists": False, "tweet_id": tweet_id, "error": "Tweet not found (deleted or invalid ID)"}
            else:
                return {"exists": False, "tweet_id": tweet_id, "error": f"Twitter API returned {response.status_code}: {response.text[:200]}"}
    except Exception as e:
        logger.error(f"Tweet verification failed for {tweet_id}: {e}")
        return {"exists": False, "tweet_id": tweet_id, "error": str(e)}


async def verify_linkedin_post(post_urn: str = "", search_text: str = "") -> dict:
    """Verify a LinkedIn post exists.

    Can verify by post URN or search recent posts for matching text.
    Returns: {exists, url, text, created_at, metrics, error}
    """
    if not LINKEDIN_ACCESS_TOKEN:
        return {"exists": False, "error": "LINKEDIN_ACCESS_TOKEN not configured"}

    import httpx
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "X-Restli-Protocol-Version": "2.0.0",
        "LinkedIn-Version": "202504",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if post_urn:
                # Direct post lookup by URN
                response = await client.get(
                    f"https://api.linkedin.com/rest/posts/{post_urn}",
                    headers=headers
                )
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "exists": True,
                        "post_urn": post_urn,
                        "url": f"https://www.linkedin.com/feed/update/{post_urn}/",
                        "text": data.get("commentary", data.get("specificContent", {}).get("com.linkedin.ugc.ShareContent", {}).get("shareCommentary", {}).get("text", ""))[:200],
                        "created_at": datetime.fromtimestamp(data.get("createdAt", 0) / 1000).isoformat() if data.get("createdAt") else "",
                        "note": "LinkedIn post verified via API. Click URL to view."
                    }
                else:
                    return {"exists": False, "post_urn": post_urn, "error": f"LinkedIn API returned {response.status_code}"}

            # Search recent posts from company/person
            author_urn = f"urn:li:organization:{LINKEDIN_COMPANY_ID}" if LINKEDIN_COMPANY_ID else ""
            if not author_urn:
                # Try person URN
                me_resp = await client.get("https://api.linkedin.com/v2/userinfo", headers=headers)
                if me_resp.status_code == 200:
                    sub = me_resp.json().get("sub", "")
                    author_urn = f"urn:li:person:{sub}"

            if author_urn:
                response = await client.get(
                    "https://api.linkedin.com/rest/posts",
                    params={"author": author_urn, "q": "author", "count": 10},
                    headers=headers
                )
                if response.status_code == 200:
                    posts = response.json().get("elements", [])
                    if search_text:
                        for post in posts:
                            commentary = post.get("commentary", "")
                            if search_text.lower() in commentary.lower():
                                post_id = post.get("id", "")
                                return {
                                    "exists": True,
                                    "post_urn": post_id,
                                    "url": f"https://www.linkedin.com/feed/update/{post_id}/",
                                    "text": commentary[:200],
                                    "created_at": datetime.fromtimestamp(post.get("createdAt", 0) / 1000).isoformat() if post.get("createdAt") else "",
                                    "note": "Found matching LinkedIn post. Click URL to view."
                                }
                        return {"exists": False, "error": f"No recent LinkedIn post matching '{search_text[:50]}' found in last 10 posts"}
                    else:
                        # Return most recent post
                        if posts:
                            post = posts[0]
                            post_id = post.get("id", "")
                            return {
                                "exists": True,
                                "post_urn": post_id,
                                "url": f"https://www.linkedin.com/feed/update/{post_id}/",
                                "text": post.get("commentary", "")[:200],
                                "total_recent_posts": len(posts),
                                "note": "Most recent LinkedIn post. Click URL to view."
                            }
                        return {"exists": False, "error": "No recent LinkedIn posts found"}
                else:
                    return {"exists": False, "error": f"LinkedIn posts API returned {response.status_code}: {response.text[:200]}"}

            return {"exists": False, "error": "Could not determine LinkedIn author URN"}
    except Exception as e:
        logger.error(f"LinkedIn verification failed: {e}")
        return {"exists": False, "error": str(e)}


async def get_recent_tweets(count: int = 10) -> dict:
    """Get the most recent tweets from the platform account.

    Returns list of tweets with IDs, text, metrics, and clickable URLs.
    """
    if not TWITTER_BEARER:
        return {"error": "X_BEARER_TOKEN not configured", "tweets": []}

    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Get user ID by username (bearer token does not support /users/me)
            user_resp = await client.get(
                f"https://api.twitter.com/2/users/by/username/{TWITTER_HANDLE}",
                headers={"Authorization": f"Bearer {TWITTER_BEARER}"}
            )

            if user_resp.status_code != 200:
                return {"error": f"Could not get user ID: {user_resp.status_code}", "tweets": []}

            user_id = user_resp.json().get("data", {}).get("id", "")

            response = await client.get(
                f"https://api.twitter.com/2/users/{user_id}/tweets",
                params={
                    "max_results": max(5, min(count, 100)),  # Twitter minimum is 5
                    "tweet.fields": "created_at,public_metrics,text",
                },
                headers={"Authorization": f"Bearer {TWITTER_BEARER}"}
            )

            if response.status_code == 200:
                tweets = response.json().get("data", [])
                return {
                    "count": len(tweets),
                    "handle": f"@{TWITTER_HANDLE}",
                    "tweets": [
                        {
                            "id": t["id"],
                            "url": f"https://x.com/{TWITTER_HANDLE}/status/{t['id']}",
                            "text": t.get("text", "")[:200],
                            "created_at": t.get("created_at", ""),
                            "likes": t.get("public_metrics", {}).get("like_count", 0),
                            "retweets": t.get("public_metrics", {}).get("retweet_count", 0),
                        }
                        for t in tweets
                    ]
                }
            return {"error": f"Twitter API returned {response.status_code}", "tweets": []}
    except Exception as e:
        return {"error": str(e), "tweets": []}


# Tool definitions for the LLM
SOCIAL_VERIFICATION_TOOLS = [
    {
        "name": "verify_tweet",
        "description": "Verify that a tweet/X post exists and is live. Accepts a tweet ID or full URL. Returns the verified URL, post text, creation date, and engagement metrics (likes, retweets, replies, impressions). Use this to confirm social media posts were published successfully and provide proof URLs to the founder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tweet_id": {
                    "type": "string",
                    "description": "The tweet ID number or full tweet URL (e.g., '2042875304704639270' or 'https://x.com/Tioli4/status/2042875304704639270')"
                }
            },
            "required": ["tweet_id"]
        }
    },
    {
        "name": "verify_linkedin_post",
        "description": "Verify that a LinkedIn post exists. Can search by post URN or by matching text in recent posts. Returns the verified URL, post text, and creation date. Use this to confirm LinkedIn posts were published successfully.",
        "input_schema": {
            "type": "object",
            "properties": {
                "post_urn": {
                    "type": "string",
                    "description": "The LinkedIn post URN (e.g., 'urn:li:share:7654321'). Optional if search_text is provided."
                },
                "search_text": {
                    "type": "string",
                    "description": "Text to search for in recent posts. Finds the most recent post containing this text."
                }
            },
            "required": []
        }
    },
    {
        "name": "get_recent_tweets",
        "description": "Get the most recent tweets from the AGENTIS platform Twitter/X account (@Tioli4). Returns a list with tweet IDs, clickable URLs, text content, creation dates, and engagement metrics. Use this to audit posting activity and provide proof of social media output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of recent tweets to retrieve (max 100, default 10)"
                }
            },
            "required": []
        }
    }
]
