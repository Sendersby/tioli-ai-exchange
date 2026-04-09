"""ARCH-FF-004: Ambassador inbound social monitoring."""
import os, logging
log = logging.getLogger("arch.social_inbound")

async def check_devto_comments(db):
    """Check DEV.to article comments."""
    if os.environ.get("ARCH_FF_SOCIAL_INBOUND_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}
    import httpx
    from sqlalchemy import text
    import uuid

    api_key = os.environ.get("DEVTO_API_KEY", "")
    if not api_key:
        return {"error": "No DEV.to API key"}

    signals = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://dev.to/api/articles/me", headers={"api-key": api_key})
            if resp.status_code == 200:
                articles = resp.json()
                for article in articles[:5]:
                    if article.get("comments_count", 0) > 0:
                        comments_resp = await client.get(f"https://dev.to/api/comments?a_id={article['id']}")
                        if comments_resp.status_code == 200:
                            for comment in comments_resp.json()[:10]:
                                try:
                                    await db.execute(text(
                                        "INSERT INTO social_signals (platform, signal_type, source_handle, content, classification, detected_at) "
                                        "VALUES ('devto', 'comment', :handle, :content, 'unclassified', now())"
                                    ), {"handle": comment.get("user", {}).get("username", "?"),
                                        "content": comment.get("body_html", "")[:500]})
                                    signals.append({"handle": comment.get("user", {}).get("username"), "article": article.get("title")})
                                except: pass
        await db.commit()
    except Exception as e:
        return {"error": str(e)}

    return {"signals_found": len(signals), "signals": signals[:5]}
