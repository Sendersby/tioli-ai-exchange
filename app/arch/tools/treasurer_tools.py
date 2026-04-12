"""Treasurer tool definitions — Anthropic API format."""

TREASURER_TOOLS = [
    {
        "name": "check_reserve_status",
        "description": "Calculate current reserve floor, headroom, and 30-day spending ceiling. Call before any financial proposal.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "submit_financial_proposal",
        "description": "Submit a financial proposal for board vote and founder approval. Cannot execute — only prepares and routes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "proposal_type": {
                    "type": "string",
                    "enum": ["OPERATIONAL_EXPENSE", "VENDOR_PAYMENT", "INVESTMENT", "CHARITABLE_DISBURSEMENT", "EMERGENCY"],
                },
                "amount_zar": {"type": "number", "minimum": 500, "maximum": 10000000},
                "description": {"type": "string", "minLength": 20},
                "justification": {"type": "string", "minLength": 50},
                "vendor_ref": {"type": "string"},
                "urgency": {"type": "string", "enum": ["ROUTINE", "URGENT", "EMERGENCY"]},
            },
            "required": ["proposal_type", "amount_zar", "description", "justification"],
        },
    },
    {
        "name": "get_financial_report",
        "description": "Generate a financial report for a specified period.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "enum": ["daily", "weekly", "monthly", "ytd", "custom"]},
                "start_date": {"type": "string", "format": "date"},
                "end_date": {"type": "string", "format": "date"},
            },
            "required": ["period"],
        },
    },
    {
        "name": "record_charitable_allocation",
        "description": "Record a charitable allocation event in the charitable fund ledger. Base = GROSS commission.",
        "input_schema": {
            "type": "object",
            "properties": {
                "gross_commission_zar": {"type": "number"},
                "trigger_transaction_id": {"type": "string"},
                "recipient": {"type": "string"},
            },
            "required": ["gross_commission_zar", "trigger_transaction_id"],
        },
    },
    {
        "name": "record_vendor_cost",
        "description": "Record or update a vendor cost entry for tracking PSP and infrastructure costs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor_name": {"type": "string"},
                "service_type": {"type": "string"},
                "monthly_cost_zar": {"type": "number"},
                "contract_ref": {"type": "string"},
            },
            "required": ["vendor_name", "monthly_cost_zar"],
        },
    },
    {'name': 'get_wallet_summary', 'description': 'Aggregate wallet balances by currency, total agents with wallets, revenue totals, charitable fund, and platform revenue. Use for financial overviews.', 'input_schema': {'type': 'object', 'properties': {}, 'required': []}},
    {'name': 'check_exchange_rates', 'description': 'Check all exchange rate pairs for freshness. Flags stale rates (>6h old). Returns status: ok/warning/critical.', 'input_schema': {'type': 'object', 'properties': {}, 'required': []}},
]


# ── Tier 2 tools ─────────────────────────────────────────────────────


async def get_wallet_summary(db) -> dict:
    """Aggregate wallet balances by currency with revenue and fund totals."""
    from sqlalchemy import text

    summary = {}

    # Balances by currency
    r = await db.execute(text(
        "SELECT currency, count(*) as wallets, SUM(balance) as total, "
        "AVG(balance) as avg, MAX(balance) as max_bal "
        "FROM wallets GROUP BY currency ORDER BY total DESC"
    ))
    summary["by_currency"] = [
        {
            "currency": row.currency,
            "wallets": row.wallets,
            "total": float(row.total or 0),
            "avg": round(float(row.avg or 0), 2),
            "max": float(row.max_bal or 0),
        }
        for row in r.fetchall()
    ]

    # Total unique agents with wallets
    r = await db.execute(text("SELECT count(DISTINCT agent_id) FROM wallets"))
    summary["total_agents_with_wallets"] = r.scalar() or 0

    # Revenue summary
    r = await db.execute(text(
        "SELECT count(*) as entries, COALESCE(SUM(gross_amount_zar), 0) as total_zar "
        "FROM revenue_transactions"
    ))
    row = r.fetchone()
    summary["revenue"] = {"entries": row.entries, "total_zar": float(row.total_zar)}

    # Charitable fund
    r = await db.execute(text(
        "SELECT COALESCE(SUM(accumulated_zar), 0) as total FROM arch_charitable_fund"
    ))
    summary["charitable_fund"] = float(r.scalar() or 0)

    # Platform revenue
    r = await db.execute(text(
        "SELECT count(*) as entries, COALESCE(SUM(amount), 0) as total FROM platform_revenue"
    ))
    row = r.fetchone()
    summary["platform_revenue"] = {"entries": row.entries, "total": float(row.total)}

    return summary


async def check_exchange_rates(db) -> dict:
    """Check exchange rate freshness and flag stale pairs."""
    from sqlalchemy import text
    from datetime import datetime, timezone

    r = await db.execute(text(
        "SELECT base_currency || \'/\' || quote_currency as currency_pair, "
        "rate, timestamp FROM exchange_rates ORDER BY timestamp DESC LIMIT 20"
    ))
    rates = []
    for row in r.fetchall():
        age_hours = None
        if row.timestamp:
            ts = row.timestamp.replace(tzinfo=timezone.utc) if row.timestamp.tzinfo is None else row.timestamp
            age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        rates.append({
            "pair": row.currency_pair,
            "rate": float(row.rate),
            "updated": row.timestamp.isoformat() if row.timestamp else None,
            "age_hours": round(age_hours, 1) if age_hours is not None else None,
            "stale": age_hours > 6 if age_hours is not None else True,
        })

    stale_count = sum(1 for r in rates if r.get("stale"))
    return {
        "rates": rates,
        "total_pairs": len(rates),
        "stale_count": stale_count,
        "status": "ok" if stale_count == 0 else "warning" if stale_count < 3 else "critical",
    }
