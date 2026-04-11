"""Automated data retention policy enforcement.

Enforces configurable retention periods per table. Runs weekly via
APScheduler and can be triggered manually via /api/v1/compliance/retention/run.
"""
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Retention periods (days)
RETENTION_POLICY = {
    "visitor_events": 90,
    "visitor_sessions": 90,
    "arch_memory_outbox": 30,
    "agenthub_post_reactions": 365,
    "agenthub_post_comments": 365,
    "agenthub_profile_views": 180,
    "arch_audit_log": 730,
    "financial_audit_log": 1825,
    "sandbox_email_notifications": 90,
    "sandbox_withdrawals": 90,
    "sandbox_self_dev_proposals": 90,
    "sandbox_onboarding": 90,
    "arch_conversation_log": 90,
    "arch_mesh_messages": 60,
    "security_events": 365,
    "transaction_alerts": 730,
}


async def enforce_retention(db):
    """Delete records older than their retention period. Returns count deleted per table."""
    results = {}
    for table, days in RETENTION_POLICY.items():
        try:
            col_check = await db.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :tbl AND column_name IN ('created_at', 'timestamp', 'sent_at')"
            ), {"tbl": table})
            col = col_check.fetchone()
            if not col:
                continue

            date_col = col[0]
            result = await db.execute(text(
                f"DELETE FROM {table} WHERE {date_col} < NOW() - INTERVAL '{days} days'"
            ))
            deleted = result.rowcount
            if deleted > 0:
                logger.info(f"Retention: deleted {deleted} rows from {table} (>{days} days)")
            results[table] = deleted
        except Exception as e:
            logger.warning(f"Retention skip {table}: {e}")
            results[table] = f"error: {str(e)[:80]}"

    await db.commit()
    return results
