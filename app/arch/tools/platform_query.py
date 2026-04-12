"""Safe read-only platform data query tool for Arch Agents.

Allows agents to query platform data via SQL SELECT statements.
Only whitelisted tables are accessible. All queries are validated
for safety (no mutations) and limited to 100 rows.
"""

import re
import logging
import json
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import text

logger = logging.getLogger("arch.platform_query")

ALLOWED_TABLES = {
    "agents", "wallets", "trades", "orders", "agent_engagements",
    "engagement_disputes", "agenthub_posts", "agenthub_profiles",
    "agenthub_skills", "arch_audit_log", "financial_audit_log",
    "revenue_transactions", "platform_revenue", "exchange_rates",
    "token_mint_ledger", "subscriptions", "notifications",
    "arch_content_library", "guilds", "guild_members",
    "kyc_verifications", "compliance_flags", "visitor_events",
    "arch_memories", "capability_taxonomy", "liquidity_pools",
    "arch_agents", "arch_campaign_articles", "outreach_content",
}

PLATFORM_QUERY_TOOLS = [
    {
        "name": "query_platform_data",
        "description": (
            "Execute a safe read-only SQL query against platform data. "
            "Only SELECT queries on whitelisted tables are allowed (agents, wallets, "
            "trades, orders, engagements, disputes, profiles, audit logs, revenue, "
            "exchange rates, subscriptions, etc.). Results are limited to 100 rows. "
            "Use this to answer questions about platform activity, user counts, "
            "financial data, agent status, and more."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": (
                        "A SQL SELECT query. Examples: "
                        "'SELECT count(*) FROM agents', "
                        "'SELECT * FROM trades ORDER BY created_at DESC LIMIT 10', "
                        "'SELECT currency, SUM(balance) FROM wallets GROUP BY currency'"
                    ),
                }
            },
            "required": ["sql"],
        },
    }
]


def _validate_query(sql: str) -> tuple[bool, str]:
    """Validate SQL is safe read-only. Returns (is_valid, error_message)."""
    sql_upper = sql.strip().upper()

    if not sql_upper.startswith("SELECT"):
        return False, "Only SELECT queries are allowed"

    dangerous = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "GRANT", "REVOKE", "COPY", "EXECUTE", "CALL",
        "DO ", "SET ",
    ]
    for keyword in dangerous:
        # Match as whole word boundary to avoid false positives on column names
        pattern = r'\b' + keyword.strip() + r'\b'
        if re.search(pattern, sql_upper):
            return False, f"Forbidden keyword: {keyword.strip()}"

    if sql.count(";") > 1:
        return False, "Multiple statements not allowed"

    # Extract table names from FROM and JOIN clauses
    table_pattern = re.findall(
        r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql, re.IGNORECASE
    )
    for table in table_pattern:
        if table.lower() not in ALLOWED_TABLES:
            return False, (
                f"Table '{table}' is not in the allowed list. "
                f"Allowed: {', '.join(sorted(ALLOWED_TABLES))}"
            )

    return True, ""


def _serialize_value(value):
    """Convert a database value to JSON-serializable form."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _serialize_row(row) -> dict:
    """Convert a database row to JSON-serializable dict."""
    result = {}
    mapping = dict(row._mapping)
    for key, value in mapping.items():
        result[key] = _serialize_value(value)
    return result


async def query_platform_data(db, sql: str) -> dict:
    """Execute a safe read-only SQL query against platform data.

    Only SELECT queries on whitelisted tables are allowed.
    Results are limited to 100 rows.
    """
    if not sql or not sql.strip():
        return {
            "error": "No SQL query provided",
            "hint": "Provide a SELECT query. Example: SELECT count(*) FROM agents",
        }

    sql_clean = sql.strip().rstrip(";")

    if "LIMIT" not in sql_clean.upper():
        sql_clean += " LIMIT 100"
    else:
        # Enforce max 100 even if caller specified more
        limit_match = re.search(r'LIMIT\s+(\d+)', sql_clean, re.IGNORECASE)
        if limit_match and int(limit_match.group(1)) > 100:
            sql_clean = re.sub(
                r'LIMIT\s+\d+', 'LIMIT 100', sql_clean, flags=re.IGNORECASE
            )

    is_valid, error = _validate_query(sql_clean)
    if not is_valid:
        return {"error": error, "query": sql_clean}

    try:
        result = await db.execute(text(sql_clean))
        rows = result.fetchall()
        data = [_serialize_row(row) for row in rows]

        logger.info(
            f"Platform query executed: {sql_clean[:100]} — {len(data)} rows"
        )

        return {
            "query": sql_clean,
            "row_count": len(data),
            "data": data,
            "truncated": len(data) >= 100,
        }
    except Exception as e:
        logger.warning(f"Platform query failed: {sql_clean[:100]} — {e}")
        return {"error": str(e), "query": sql_clean}
