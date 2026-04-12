"""Sovereign tool definitions — Anthropic API format."""

SOVEREIGN_TOOLS = [
    {
        "name": "convene_board_session",
        "description": "Convene a board session with all available Arch Agents. Use for decisions requiring collective vote.",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_type": {"type": "string", "enum": ["WEEKLY", "EMERGENCY", "SPECIAL"]},
                "agenda": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "urgency": {"type": "string", "enum": ["ROUTINE", "URGENT", "EMERGENCY"]},
            },
            "required": ["session_type", "agenda"],
        },
    },
    {
        "name": "submit_to_founder_inbox",
        "description": "Submit a decision, proposal, or DEFER_TO_OWNER item to the founder's inbox. Triggers email + WhatsApp notification.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_type": {
                    "type": "string",
                    "enum": ["FINANCIAL_PROPOSAL", "DEFER_TO_OWNER", "INFORMATION", "APPROVAL_REQUEST", "EMERGENCY"],
                },
                "priority": {"type": "string", "enum": ["ROUTINE", "URGENT", "CRITICAL"]},
                "subject": {"type": "string", "maxLength": 200},
                "situation": {"type": "string"},
                "options": {"type": "array", "items": {"type": "string"}},
                "recommendation": {"type": "string"},
                "deadline_hours": {"type": "integer", "minimum": 1, "maximum": 168},
            },
            "required": ["item_type", "priority", "subject", "situation"],
        },
    },
    {
        "name": "issue_constitutional_ruling",
        "description": "Issue a binding constitutional ruling on an inter-agent dispute or novel governance question.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ruling_type": {
                    "type": "string",
                    "enum": ["DISPUTE_RESOLUTION", "CONSTITUTIONAL_INTERPRETATION", "RENAMING", "EMERGENCY_GOVERNANCE"],
                },
                "subject_agents": {"type": "array", "items": {"type": "string"}},
                "precedent_set": {"type": "string"},
                "ruling_text": {"type": "string", "minLength": 100},
                "cited_directives": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["ruling_type", "ruling_text", "cited_directives"],
        },
    },
    {
        "name": "read_agent_health",
        "description": "Read the current health status of all Arch Agents.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "broadcast_to_board",
        "description": "Send an urgent message to all Arch Agents simultaneously via Redis pub/sub.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "message": {"type": "string"},
                "priority": {"type": "string", "enum": ["ROUTINE", "URGENT", "EMERGENCY"]},
                "requires_response": {"type": "boolean"},
            },
            "required": ["subject", "message", "priority"],
        },
    },
    {'name': 'get_platform_dashboard', 'description': 'Full platform dashboard: agent count, trades, orders, engagements, disputes, revenue, KYC, wallets, content, guilds, subscriptions, agent health, exchange rate freshness.', 'input_schema': {'type': 'object', 'properties': {}, 'required': []}},
]


# ── Tier 2 tools ─────────────────────────────────────────────────────


async def get_platform_dashboard(db) -> dict:
    """Comprehensive platform dashboard: agents, trades, revenue, disputes, health."""
    from sqlalchemy import text
    import decimal

    dashboard = {}

    queries = {
        "total_agents": "SELECT count(*) FROM agents",
        "total_trades": "SELECT count(*) FROM trades WHERE trade_type = 'real'",
        "total_orders": "SELECT count(*) FROM orders",
        "active_engagements": (
            "SELECT count(*) FROM agent_engagements "
            "WHERE current_state NOT IN ('completed','cancelled','expired')"
        ),
        "total_engagements": "SELECT count(*) FROM agent_engagements",
        "open_disputes": (
            "SELECT count(*) FROM engagement_disputes "
            "WHERE status NOT IN ('resolved','closed')"
        ),
        "total_revenue_zar": "SELECT COALESCE(SUM(gross_amount_zar), 0) FROM revenue_transactions",
        "audit_entries": "SELECT count(*) FROM financial_audit_log",
        "kyc_verified": "SELECT count(*) FROM kyc_verifications WHERE kyc_tier >= 1",
        "total_wallets": "SELECT count(*) FROM wallets WHERE balance > 0",
        "total_content_posts": "SELECT count(*) FROM arch_content_library",
        "guild_count": "SELECT count(*) FROM guilds",
        "subscription_count": "SELECT count(*) FROM subscriptions WHERE status = 'active'",
    }

    for key, query in queries.items():
        try:
            r = await db.execute(text(query))
            val = r.scalar()
            dashboard[key] = float(val) if isinstance(val, decimal.Decimal) else val
        except Exception as e:
            dashboard[key] = "error: " + str(e)[:50]

    # Agent health
    try:
        r = await db.execute(text(
            "SELECT agent_name, status, last_heartbeat FROM arch_agents ORDER BY agent_name"
        ))
        dashboard["agent_health"] = [
            {
                "name": row.agent_name,
                "status": row.status,
                "last_heartbeat": row.last_heartbeat.isoformat() if row.last_heartbeat else None,
            }
            for row in r.fetchall()
        ]
    except Exception:
        dashboard["agent_health"] = "unavailable"

    # Exchange rates freshness
    try:
        r = await db.execute(text("SELECT MAX(timestamp) FROM exchange_rates"))
        latest = r.scalar()
        if latest:
            from datetime import datetime, timezone
            ts = latest.replace(tzinfo=timezone.utc) if latest.tzinfo is None else latest
            age = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            dashboard["exchange_rates_age_hours"] = round(age, 1)
    except Exception:
        pass

    return dashboard
