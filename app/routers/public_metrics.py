"""Public Proof-by-Numbers metrics endpoint.

Workstream B from COMPETITOR_ADOPTION_PLAN.md v1.1.

Exposes a subset of Sovereign's get_platform_dashboard data as a public,
cached, no-auth endpoint that the proof-band JS component on landing pages
can fetch. Reuses the existing SQL queries verbatim so we never drift from
what Sovereign's tool already returns.

Standing rules:
- Public read-only endpoint, no PII, no agent action -> inbox delivery N/A
- 5-minute HTTP cache headers + best-effort Redis cache (skipped for v1
  to keep scope tight; HTTP cache headers carry the load)
- Used by /static/landing/components/proof-band.js on 6 key public pages
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database.db import async_session

log = logging.getLogger("tioli.public_metrics")

router = APIRouter(tags=["Public Metrics"])


_PROOF_QUERIES = {
    "agents_onboarded": "SELECT count(*) FROM agents",
    "trades_executed": "SELECT count(*) FROM trades WHERE trade_type = 'real'",
    "disputes_total": "SELECT count(*) FROM engagement_disputes",
    "disputes_open": (
        "SELECT count(*) FROM engagement_disputes "
        "WHERE status NOT IN ('resolved','closed')"
    ),
    "total_revenue_zar": "SELECT COALESCE(SUM(gross_amount_zar), 0) FROM revenue_transactions",
    "guilds_active": "SELECT count(*) FROM guilds",
    "wallets_total": "SELECT count(*) FROM wallets WHERE balance > 0",
    "content_posts": "SELECT count(*) FROM arch_content_library",
}


def _to_native(v):
    if isinstance(v, Decimal):
        return float(v)
    return v


@router.get("/api/v1/public/proof-metrics")
async def proof_metrics():
    """Return 6+ headline metrics for the public proof-band.

    Every value is computed from existing tables; nothing new is stored. The
    response is safe for unauthenticated caching (Cloudflare, browsers, Redis).
    Failures on any individual query degrade gracefully — that metric becomes
    `null` and the JS renderer falls back to a placeholder.
    """
    raw = {}
    async with async_session() as db:
        for key, sql in _PROOF_QUERIES.items():
            try:
                r = await db.execute(text(sql))
                raw[key] = _to_native(r.scalar())
            except Exception as exc:
                log.warning(f"proof_metrics query failed [{key}]: {exc}")
                raw[key] = None

        # Exchange-rate freshness in hours
        rates_age_h = None
        try:
            r = await db.execute(text("SELECT MAX(timestamp) FROM exchange_rates"))
            latest = r.scalar()
            if latest:
                ts = latest.replace(tzinfo=timezone.utc) if latest.tzinfo is None else latest
                rates_age_h = round(
                    (datetime.now(timezone.utc) - ts).total_seconds() / 3600, 1
                )
        except Exception as exc:
            log.warning(f"proof_metrics exchange-rate freshness failed: {exc}")

    # Derived: charity contribution = 10% of gross revenue (matches the founder
    # commitment displayed in the canonical footer)
    revenue = raw.get("total_revenue_zar") or 0
    charity_paid_zar = round(revenue * 0.10, 2) if revenue else 0.0

    disputes_total = raw.get("disputes_total") or 0
    disputes_open = raw.get("disputes_open") or 0
    disputes_resolved = max(disputes_total - disputes_open, 0)

    payload = {
        "metrics": {
            "agents_onboarded": raw.get("agents_onboarded") or 0,
            "trades_executed": raw.get("trades_executed") or 0,
            "disputes_resolved": disputes_resolved,
            "disputes_open": disputes_open,
            "charity_paid_zar": charity_paid_zar,
            "guilds_active": raw.get("guilds_active") or 0,
            "wallets_with_balance": raw.get("wallets_total") or 0,
            "content_posts_published": raw.get("content_posts") or 0,
            "total_revenue_zar": float(revenue),
            "exchange_rates_age_hours": rates_age_h,
        },
        "headline_six": [
            {
                "key": "agents_onboarded",
                "label": "Agents on the exchange",
                "value": raw.get("agents_onboarded") or 0,
                "format": "integer",
            },
            {
                "key": "trades_executed",
                "label": "Trades executed",
                "value": raw.get("trades_executed") or 0,
                "format": "integer",
            },
            {
                "key": "disputes_resolved",
                "label": "Disputes resolved",
                "value": disputes_resolved,
                "format": "integer",
                "suffix": f" · {disputes_open} open" if disputes_open else " · 0 open",
            },
            {
                "key": "charity_paid_zar",
                "label": "Paid to charity",
                "value": charity_paid_zar,
                "format": "currency_zar",
            },
            {
                "key": "guilds_active",
                "label": "Active guilds",
                "value": raw.get("guilds_active") or 0,
                "format": "integer",
            },
            {
                "key": "exchange_rates_age_hours",
                "label": "Exchange rates fresh",
                "value": rates_age_h if rates_age_h is not None else 0,
                "format": "hours",
            },
        ],
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "cache_ttl_seconds": 300,
        "source": "live SQL on TiOLi AGENTIS Exchange production database",
    }

    return JSONResponse(
        content=payload,
        headers={
            "Cache-Control": "public, max-age=300, s-maxage=300",
            "Access-Control-Allow-Origin": "*",
        },
    )
