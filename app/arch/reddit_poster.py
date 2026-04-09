"""Reddit posting via PRAW — autonomous posting to AI subreddits.
Feature flag: ARCH_REDDIT_ENABLED
Requires: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD in .env"""
import os
import logging
import json
from datetime import datetime, timezone

log = logging.getLogger("arch.reddit_poster")

# Target subreddits with posting guidelines
SUBREDDITS = {
    "LocalLLaMA": {"type": "self", "flair": None, "max_per_week": 2,
                   "style": "Technical, model-focused. Reference specific capabilities. Community values benchmarks and real-world usage."},
    "artificial": {"type": "self", "flair": None, "max_per_week": 2,
                   "style": "General AI discussion. Thought-provoking questions welcome. Avoid pure self-promotion."},
    "MachineLearning": {"type": "self", "flair": "[Project]", "max_per_week": 1,
                        "style": "Academic/research tone. Must have technical substance. Use [Project] flair for launches."},
    "singularity": {"type": "self", "flair": None, "max_per_week": 2,
                    "style": "Future-focused. Big picture thinking. Speculative but grounded."},
    "SideProject": {"type": "self", "flair": None, "max_per_week": 1,
                    "style": "Builder community. Show what you built, how, and why. Be genuine."},
    "test": {"type": "self", "flair": None, "max_per_week": 99,
             "style": "Testing subreddit — use for verification."},
}


def _get_reddit_client():
    """Create a PRAW Reddit instance."""
    import praw
    client_id = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    username = os.environ.get("REDDIT_USERNAME", "")
    password = os.environ.get("REDDIT_PASSWORD", "")
    user_agent = os.environ.get("REDDIT_USER_AGENT", "TiOLi-AGENTIS/1.0 by /u/" + username)

    if not all([client_id, client_secret, username, password]):
        return None

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
        user_agent=user_agent,
    )


async def post_to_reddit(subreddit_name: str, title: str, body: str) -> dict:
    """Post a text submission to a subreddit."""
    if os.environ.get("ARCH_REDDIT_ENABLED", "false").lower() != "true":
        return {"status": "disabled", "note": "Set ARCH_REDDIT_ENABLED=true"}

    reddit = _get_reddit_client()
    if not reddit:
        return {"error": "Reddit credentials not configured",
                "needed": "REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD"}

    config = SUBREDDITS.get(subreddit_name, {"type": "self", "max_per_week": 1})

    try:
        # Check rate limit — query our own post history
        import asyncpg
        conn = await asyncpg.connect(user="tioli", password="DhQHhP6rsYdUL*2DLWJ2Neu#2xqhM0z#",
                                      database="tioli_exchange", host="127.0.0.1", port=5432)
        recent = await conn.fetchval(
            "SELECT count(*) FROM arch_content_library "
            "WHERE channel = 'reddit' AND title LIKE $1 AND published_at > now() - interval '7 days'",
            f"%r/{subreddit_name}%")
        await conn.close()

        if recent and recent >= config.get("max_per_week", 2):
            return {"error": f"Rate limit: already posted {recent}x to r/{subreddit_name} this week",
                    "max_per_week": config["max_per_week"]}

        # Post
        subreddit = reddit.subreddit(subreddit_name)

        # Add flair if configured
        flair = config.get("flair")
        if flair:
            title = f"{flair} {title}"

        submission = subreddit.submit(title=title[:300], selftext=body[:40000])

        log.info(f"[reddit] Posted to r/{subreddit_name}: {submission.id}")
        return {
            "success": True,
            "post_id": submission.id,
            "url": f"https://reddit.com{submission.permalink}",
            "subreddit": subreddit_name,
            "title": title[:100],
        }

    except Exception as e:
        log.warning(f"[reddit] Post to r/{subreddit_name} failed: {e}")
        return {"error": str(e)[:300], "subreddit": subreddit_name}


async def monitor_reddit_replies(post_id: str) -> dict:
    """Check replies on a Reddit post for engagement opportunities."""
    reddit = _get_reddit_client()
    if not reddit:
        return {"error": "Reddit not configured"}

    try:
        submission = reddit.submission(id=post_id)
        submission.comments.replace_more(limit=0)
        replies = []
        for comment in submission.comments[:10]:
            replies.append({
                "author": str(comment.author),
                "body": comment.body[:200],
                "score": comment.score,
                "created": str(datetime.fromtimestamp(comment.created_utc, tz=timezone.utc)),
            })

        # Classify opportunities
        opportunities = [r for r in replies if r["score"] > 2 or "?" in r["body"]]
        return {
            "post_id": post_id,
            "total_replies": len(replies),
            "opportunities": len(opportunities),
            "replies": replies[:5],
        }

    except Exception as e:
        return {"error": str(e)[:200]}


async def get_subreddit_rules(subreddit_name: str) -> dict:
    """Fetch posting rules for a subreddit."""
    reddit = _get_reddit_client()
    if not reddit:
        return {"error": "Reddit not configured"}

    try:
        subreddit = reddit.subreddit(subreddit_name)
        rules = [{"title": rule.short_name, "description": rule.description[:200]}
                 for rule in subreddit.rules]
        return {"subreddit": subreddit_name, "rules": rules, "count": len(rules)}
    except Exception as e:
        return {"error": str(e)[:200]}
