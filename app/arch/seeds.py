"""Arch Agent database seeds — initial data for arch_agents table.

Seeds all 7 Arch Agents with founding names, models, and token budgets.
Run during Phase 0 after migrations complete.
"""

import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


ARCH_AGENT_SEEDS = [
    {
        "agent_name": "sovereign",
        "display_name": "The Sovereign",
        "corporate_title": "Chief Executive Officer & Board Chair",
        "model_primary": "claude-opus-4-6",
        "model_fallback": "claude-sonnet-4-6",
        "token_budget_monthly": 5_000_000,
    },
    {
        "agent_name": "auditor",
        "display_name": "The Auditor",
        "corporate_title": "Chief Legal & Compliance Officer",
        "model_primary": "claude-opus-4-6",
        "model_fallback": "claude-sonnet-4-6",
        "token_budget_monthly": 4_000_000,
    },
    {
        "agent_name": "arbiter",
        "display_name": "The Arbiter",
        "corporate_title": "Chief Product & Customer Officer",
        "model_primary": "claude-opus-4-6",
        "model_fallback": "claude-sonnet-4-6",
        "token_budget_monthly": 3_000_000,
    },
    {
        "agent_name": "treasurer",
        "display_name": "The Treasurer",
        "corporate_title": "Chief Financial Officer",
        "model_primary": "claude-opus-4-6",
        "model_fallback": "claude-sonnet-4-6",
        "token_budget_monthly": 3_000_000,
    },
    {
        "agent_name": "sentinel",
        "display_name": "The Sentinel",
        "corporate_title": "Chief Operating Officer & CISO",
        "model_primary": "claude-sonnet-4-6",
        "model_fallback": "claude-haiku-4-5-20251001",
        "token_budget_monthly": 3_000_000,
    },
    {
        "agent_name": "architect",
        "display_name": "The Architect",
        "corporate_title": "Chief Technology Officer",
        "model_primary": "claude-opus-4-6",
        "model_fallback": "claude-sonnet-4-6",
        "token_budget_monthly": 5_000_000,
    },
    {
        "agent_name": "ambassador",
        "display_name": "The Ambassador",
        "corporate_title": "Chief Marketing & Growth Officer",
        "model_primary": "claude-sonnet-4-6",
        "model_fallback": "claude-haiku-4-5-20251001",
        "token_budget_monthly": 4_000_000,
    },
]


async def seed_arch_agents(db: AsyncSession):
    """Insert all 7 Arch Agents into arch_agents table.

    Uses ON CONFLICT to be safely re-runnable.
    """
    for agent in ARCH_AGENT_SEEDS:
        namespace = str(uuid.uuid4())
        await db.execute(
            text("""
                INSERT INTO arch_agents
                    (agent_name, display_name, corporate_title, layer,
                     model_primary, model_fallback, status,
                     constitution_version, agent_version,
                     memory_namespace, token_budget_monthly,
                     tokens_used_this_month, tokens_reset_at)
                VALUES
                    (:agent_name, :display_name, :corporate_title, 1,
                     :model_primary, :model_fallback, 'PAUSED',
                     '1.0', '1.0.0',
                     :namespace, :token_budget,
                     0, date_trunc('month', now()))
                ON CONFLICT (agent_name) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    corporate_title = EXCLUDED.corporate_title,
                    model_primary = EXCLUDED.model_primary,
                    model_fallback = EXCLUDED.model_fallback,
                    token_budget_monthly = EXCLUDED.token_budget_monthly
            """),
            {
                "agent_name": agent["agent_name"],
                "display_name": agent["display_name"],
                "corporate_title": agent["corporate_title"],
                "model_primary": os.getenv(
                    f"ARCH_{agent['agent_name'].upper()}_MODEL",
                    agent["model_primary"],
                ),
                "model_fallback": agent["model_fallback"],
                "namespace": namespace,
                "token_budget": int(os.getenv(
                    f"ARCH_MONTHLY_TOKEN_BUDGET_{agent['agent_name'].upper()}",
                    str(agent["token_budget_monthly"]),
                )),
            },
        )
    await db.commit()
