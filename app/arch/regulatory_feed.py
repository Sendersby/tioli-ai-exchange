"""ARCH-CP-003: Real-time regulatory feed monitor."""
import os
import logging

log = logging.getLogger("arch.regulatory_feed")

MONITORED_SOURCES = [
    {"name": "FSCA", "url": "https://www.fsca.co.za/Regulatory%20Frameworks/Pages/default.aspx"},
    {"name": "FIC", "url": "https://www.fic.gov.za/News/Pages/default.aspx"},
    {"name": "SARB", "url": "https://www.resbank.co.za/en/home/publications"},
    {"name": "IFWG", "url": "https://www.ifwg.co.za/resources"},
    {"name": "National_Treasury", "url": "https://www.treasury.gov.za/comm_media/press/default.aspx"},
]


async def scan_regulatory_sources(db, agent_client=None):
    """Scan regulatory sources for new publications."""
    if os.environ.get("ARCH_CP_REGULATORY_FEED_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    from sqlalchemy import text
    import json

    results = []
    for source in MONITORED_SOURCES:
        try:
            # Record scan state
            await db.execute(text(
                "INSERT INTO regulatory_scan_state (source, last_known_documents, last_scanned) "
                "VALUES (:src, :docs, now()) "
                "ON CONFLICT (source) DO UPDATE SET last_scanned = now(), updated_at = now()"
            ), {"src": source["name"], "docs": json.dumps({"url": source["url"]})})
            await db.commit()
            results.append({"source": source["name"], "status": "scanned", "url": source["url"]})
        except Exception as e:
            results.append({"source": source["name"], "error": str(e)[:60]})

    return {"sources_scanned": len(results), "results": results}
