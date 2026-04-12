"""Ambassador tool definitions — Anthropic API format."""

AMBASSADOR_TOOLS = [
    {
        "name": "publish_content",
        "description": "Publish content to an approved platform channel. Only whitelisted platforms.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": ["linkedin", "twitter_x", "reddit", "github", "blog", "agenthub_feed", "newsletter"]},
                "content_type": {"type": "string", "enum": ["article", "thread", "post", "comment", "directory_listing", "press_release"]},
                "title": {"type": "string", "maxLength": 200},
                "body": {"type": "string", "maxLength": 10000},
                "tags": {"type": "array", "items": {"type": "string"}},
                "acc_output_id": {"type": "string"},
            },
            "required": ["platform", "content_type", "body"],
        },
    },
    {
        "name": "record_growth_experiment",
        "description": "Record a growth experiment hypothesis, result, and winner.",
        "input_schema": {
            "type": "object",
            "properties": {
                "hypothesis": {"type": "string"},
                "channel": {"type": "string"},
                "variant_a": {"type": "string"},
                "variant_b": {"type": "string"},
                "result": {"type": "object"},
                "winner": {"type": "string", "enum": ["A", "B", "INCONCLUSIVE"]},
                "uplift_pct": {"type": "number"},
            },
            "required": ["hypothesis", "channel"],
        },
    },
    {
        "name": "submit_to_directory",
        "description": "Submit TiOLi AGENTIS to an AI or fintech directory on the approved whitelist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "enum": ["glama", "mcp_so", "smithery", "toolhouse", "ventureburn", "fin24", "technext"]},
                "listing_type": {"type": "string", "enum": ["mcp_server", "platform", "fintech", "ai_tool"]},
                "description": {"type": "string", "maxLength": 500},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["directory", "listing_type", "description"],
        },
    },
    {
        "name": "record_partnership",
        "description": "Record a partnership opportunity or conversation in the CRM.",
        "input_schema": {
            "type": "object",
            "properties": {
                "partner_name": {"type": "string"},
                "partner_type": {"type": "string", "enum": ["ai_company", "fintech", "regulator", "framework", "media", "investor"]},
                "contact_name": {"type": "string"},
                "contact_email": {"type": "string", "format": "email"},
                "stage": {"type": "string", "enum": ["IDENTIFIED", "CONTACTED", "ENGAGED", "PROPOSAL", "AGREED", "INACTIVE"]},
                "value_prop": {"type": "string"},
                "next_action": {"type": "string"},
            },
            "required": ["partner_name", "partner_type", "stage"],
        },
    },
    {
        "name": "get_network_effect_metrics",
        "description": "Retrieve Metcalfe network effect metrics: agents, operators, viral coefficient.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "enum": ["daily", "weekly", "monthly"], "default": "weekly"},
            },
            "required": [],
        },
    },
    {
        "name": "update_market_expansion",
        "description": "Update status of a target market expansion initiative.",
        "input_schema": {
            "type": "object",
            "properties": {
                "market": {"type": "string", "enum": ["KE", "RW", "PH", "GB", "US"]},
                "status": {"type": "string", "enum": ["RESEARCH", "LEGAL_REVIEW", "PARTNER_SEARCH", "LAUNCH_READY", "LIVE"]},
                "legal_clearance": {"type": "boolean"},
                "partner_name": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["market", "status"],
        },
    },
    {
        "name": "trigger_onboarding_sequence",
        "description": "Trigger operator onboarding post-KYC clearance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "operator_id": {"type": "string"},
                "segment": {"type": "string", "enum": ["developer", "enterprise", "fintech", "auto_detect"]},
                "acquisition_source": {"type": "string"},
            },
            "required": ["operator_id"],
        },
    },
    {
        "name": "get_content_analytics",
        "description": "Get content analytics across all social platforms — posts per platform, engagement metrics, posting frequency, and gaps.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "schedule_content",
        "description": "Schedule a social media post for a future date/time on a supported platform.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {
                    "type": "string",
                    "enum": ["twitter", "twitter_x", "linkedin", "discord", "devto", "reddit"],
                },
                "content": {"type": "string", "minLength": 10, "maxLength": 5000},
                "scheduled_for": {
                    "type": "string",
                    "description": "ISO datetime e.g. 2026-04-15T10:00:00",
                },
            },
            "required": ["platform", "content", "scheduled_for"],
        },
    },
]


# ── Tier 1 Tool Implementations ──────────────────────────────


async def get_content_analytics(db) -> dict:
    """Get content analytics across all social platforms.

    Queries arch_content_library and outreach_content for posting
    frequency, engagement metrics, and identifies platform gaps.
    Fetches live Twitter engagement when bearer token is available.
    """
    import os
    from datetime import datetime, timedelta, timezone

    import httpx
    from sqlalchemy import text

    results: dict = {"platforms": {}, "total_posts": 0, "gaps": [], "outreach": {}}

    # ── arch_content_library metrics (uses 'channel' column) ──
    try:
        rows = await db.execute(text(
            "SELECT channel, count(*) AS posts, max(published_at) AS latest "
            "FROM arch_content_library WHERE channel IS NOT NULL "
            "GROUP BY channel ORDER BY posts DESC LIMIT 20"
        ))
        for row in rows.fetchall():
            results["platforms"][row.channel] = {
                "posts": row.posts,
                "latest": row.latest.isoformat() if row.latest else None,
            }
            results["total_posts"] += row.posts
    except Exception as exc:
        results["content_library_error"] = str(exc)

    # ── outreach_content engagement data ──
    try:
        outreach_rows = await db.execute(text(
            "SELECT channel, count(*) AS posts, max(posted_at) AS latest, "
            "count(*) FILTER (WHERE status = 'posted') AS posted, "
            "count(*) FILTER (WHERE status = 'scheduled') AS scheduled "
            "FROM outreach_content WHERE channel IS NOT NULL "
            "GROUP BY channel ORDER BY posts DESC LIMIT 20"
        ))
        for row in outreach_rows.fetchall():
            results["outreach"][row.channel] = {
                "total": row.posts,
                "posted": row.posted,
                "scheduled": row.scheduled,
                "latest_post": row.latest.isoformat() if row.latest else None,
            }
    except Exception as exc:
        results["outreach_error"] = str(exc)

    # ── Last 5 posts per platform from outreach_content ──
    try:
        recent_rows = await db.execute(text(
            "SELECT channel, title, status, posted_at, posted_url, performance "
            "FROM outreach_content ORDER BY created_at DESC NULLS LAST LIMIT 25"
        ))
        recent_by_platform: dict = {}
        for row in recent_rows.fetchall():
            ch = row.channel or "unknown"
            if ch not in recent_by_platform:
                recent_by_platform[ch] = []
            if len(recent_by_platform[ch]) < 5:
                recent_by_platform[ch].append({
                    "title": row.title,
                    "status": row.status,
                    "posted_at": row.posted_at.isoformat() if row.posted_at else None,
                    "url": row.posted_url,
                })
        results["recent_posts"] = recent_by_platform
    except Exception as exc:
        results["recent_posts_error"] = str(exc)

    # ── Twitter live engagement via API ──
    bearer = os.environ.get("X_BEARER_TOKEN", os.environ.get("TWITTER_BEARER_TOKEN", ""))
    if bearer:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                handle = os.environ.get("X_HANDLE", "Tioli4")
                user_resp = await client.get(
                    f"https://api.twitter.com/2/users/by/username/{handle}",
                    headers={"Authorization": f"Bearer {bearer}"},
                )
                if user_resp.status_code == 200:
                    user_id = user_resp.json()["data"]["id"]
                    tweets_resp = await client.get(
                        f"https://api.twitter.com/2/users/{user_id}/tweets",
                        params={
                            "max_results": 10,
                            "tweet.fields": "created_at,public_metrics",
                        },
                        headers={"Authorization": f"Bearer {bearer}"},
                    )
                    if tweets_resp.status_code == 200:
                        tweets = tweets_resp.json().get("data", [])
                        total_likes = sum(
                            t.get("public_metrics", {}).get("like_count", 0)
                            for t in tweets
                        )
                        total_retweets = sum(
                            t.get("public_metrics", {}).get("retweet_count", 0)
                            for t in tweets
                        )
                        total_impressions = sum(
                            t.get("public_metrics", {}).get("impression_count", 0)
                            for t in tweets
                        )
                        results["twitter_engagement"] = {
                            "recent_tweets": len(tweets),
                            "total_likes": total_likes,
                            "total_retweets": total_retweets,
                            "total_impressions": total_impressions,
                            "avg_impressions": total_impressions // max(len(tweets), 1),
                        }
                    else:
                        results["twitter_engagement"] = {
                            "error": f"Twitter API {tweets_resp.status_code}: {tweets_resp.text[:200]}"
                        }
                else:
                    results["twitter_engagement"] = {
                        "error": f"User lookup {user_resp.status_code}: {user_resp.text[:200]}"
                    }
        except Exception as exc:
            results["twitter_engagement"] = {"error": str(exc)}

    # ── Identify gaps: platforms with no posts in last 7 days ──
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    expected_platforms = ["twitter", "twitter_x", "linkedin", "discord", "devto", "reddit"]
    for p in expected_platforms:
        platform_data = results["platforms"].get(p, {})
        outreach_data = results["outreach"].get(p, {})
        latest_str = platform_data.get("latest") or outreach_data.get("latest_post")
        if not latest_str:
            results["gaps"].append(f"{p}: no posts found")
        else:
            try:
                latest_dt = datetime.fromisoformat(latest_str)
                if latest_dt.tzinfo is None:
                    latest_dt = latest_dt.replace(tzinfo=timezone.utc)
                if latest_dt < week_ago:
                    results["gaps"].append(f"{p}: no posts in last 7 days (last: {latest_str})")
            except (ValueError, TypeError):
                pass

    return results


async def schedule_content(db, platform: str, content: str, scheduled_for: str) -> dict:
    """Schedule a social media post for a future date/time.

    Inserts into outreach_content with status='scheduled' so the
    social poster picks it up at the scheduled time.
    """
    import uuid
    from datetime import datetime, timezone

    from sqlalchemy import text

    valid_platforms = {"twitter", "twitter_x", "linkedin", "discord", "devto", "reddit"}
    if platform not in valid_platforms:
        return {"error": f"Invalid platform. Use: {', '.join(sorted(valid_platforms))}"}

    if not content or len(content.strip()) < 10:
        return {"error": "Content must be at least 10 characters"}

    try:
        scheduled_dt = datetime.fromisoformat(scheduled_for)
    except (ValueError, TypeError):
        return {"error": "Invalid date format. Use ISO format: 2026-04-15T10:00:00"}

    if scheduled_dt.tzinfo is None:
        scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)

    if scheduled_dt <= datetime.now(timezone.utc):
        return {"error": "Scheduled time must be in the future"}

    post_id = str(uuid.uuid4())

    try:
        await db.execute(text(
            "INSERT INTO outreach_content "
            "(id, channel, content_type, title, body, status, scheduled_for, generated_by, created_at) "
            "VALUES (:id, :channel, 'social_post', :title, :body, 'scheduled', :scheduled, 'ambassador', now())"
        ), {
            "id": post_id,
            "channel": platform,
            "title": content[:200],
            "body": content,
            "scheduled": scheduled_dt,
        })
        await db.commit()
    except Exception as exc:
        return {"error": f"Database insert failed: {exc}"}

    return {
        "scheduled": True,
        "post_id": post_id,
        "platform": platform,
        "scheduled_for": scheduled_dt.isoformat(),
        "content_preview": content[:200],
    }
