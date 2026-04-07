"""Email digest system — weekly newsletter to subscribers."""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.email_digest")


async def add_subscriber(db, email: str):
    """Add email subscriber for weekly digest."""
    from sqlalchemy import text
    try:
        await db.execute(text(
            "INSERT INTO newsletter_subscribers (email, subscribed_at, is_active) "
            "VALUES (:email, now(), true) ON CONFLICT (email) DO UPDATE SET is_active = true"
        ), {"email": email})
        await db.commit()
        return {"status": "subscribed", "email": email}
    except Exception as e:
        return {"error": str(e)}


async def remove_subscriber(db, email: str):
    """Unsubscribe from digest."""
    from sqlalchemy import text
    await db.execute(text(
        "UPDATE newsletter_subscribers SET is_active = false WHERE email = :email"
    ), {"email": email})
    await db.commit()
    return {"status": "unsubscribed"}


async def generate_digest(db):
    """Generate weekly digest content from recent articles."""
    from sqlalchemy import text
    result = await db.execute(text(
        "SELECT slug, title, category FROM seo_pages "
        "WHERE is_published = true AND created_at > now() - interval '7 days' "
        "ORDER BY created_at DESC LIMIT 10"
    ))
    articles = [{"slug": r.slug, "title": r.title, "category": r.category} for r in result.fetchall()]

    html = "<h2>Weekly AGENTIS Digest</h2><ul>"
    for a in articles:
        html += f'<li><a href="https://agentisexchange.com/blog/{a["slug"]}">{a["title"]}</a> ({a["category"]})</li>'
    html += "</ul><p>Visit <a href='https://agentisexchange.com/learn'>agentisexchange.com/learn</a> for more.</p>"

    return {"articles": len(articles), "html": html, "generated_at": datetime.now(timezone.utc).isoformat()}
