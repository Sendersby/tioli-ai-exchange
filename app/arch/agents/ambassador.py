"""The Ambassador — CMO / Chief Growth Officer / Chief Community Officer.

Only outward-facing Arch Agent. Mandate is exponential growth.
Owns content, SEO/AEO/GEO, partnerships, community, global expansion.

Startup sequence: Step 9 (last agent activated).
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.arch.base import ArchAgentBase
from app.arch.tools.ambassador_tools import AMBASSADOR_TOOLS
from app.arch.executor_tools import EXECUTOR_TOOLS
from app.arch.task_queue import TASK_QUEUE_TOOLS
from app.arch.creative_tools import CREATIVE_TOOLS
from app.arch.subordinate_manager import SUBORDINATE_MANAGEMENT_TOOLS

log = logging.getLogger("arch.ambassador")


class AmbassadorAgent(ArchAgentBase):

    @property
    def system_prompt_key(self) -> str:
        return "system_prompt"

    async def get_tools(self) -> list:
        return AMBASSADOR_TOOLS + EXECUTOR_TOOLS + TASK_QUEUE_TOOLS + CREATIVE_TOOLS + SUBORDINATE_MANAGEMENT_TOOLS + self.get_common_tools()

    async def _tool_publish_content(self, params: dict) -> dict:
        platform = params["platform"]
        content_type = params["content_type"]
        body = params["body"]

        result = await self.db.execute(
            text("""
                INSERT INTO arch_content_library
                    (content_type, title, body_ref, channel, published_at)
                VALUES (:ctype, :title, :body, :channel, now())
                RETURNING id::text
            """),
            {
                "ctype": content_type,
                "title": params.get("title", ""),
                "body": body[:2000],
                "channel": platform,
            },
        )
        content_id = result.scalar()
        await self.db.commit()
        log.info(f"[ambassador] Content published: {content_type} on {platform}")
        
        # ARCH-004: Store content in memory for tracking (feature-flagged)
        import os as _cs_os
        if _cs_os.environ.get("ARCH_AGENT_CONTENT_STORE", "false").lower() == "true":
            try:
                await self.memory.store(
                    f"Published content: {params.get('title', 'untitled')} on {params.get('channel', 'unknown')}",
                    source_type="content_published", importance=0.6)
            except Exception:
                pass

return {"content_id": content_id, "platform": platform,
                "status": "PUBLISHED", "content_type": content_type}

    async def _tool_record_growth_experiment(self, params: dict) -> dict:
        result = await self.db.execute(
            text("""
                INSERT INTO arch_growth_experiments
                    (hypothesis, channel, variant_a, variant_b,
                     result, winner, uplift_pct, start_date, status)
                VALUES (:hyp, :channel, :va, :vb, :result, :winner, :uplift, now(),
                        CASE WHEN :winner IS NOT NULL THEN 'COMPLETED' ELSE 'ACTIVE' END)
                RETURNING id::text
            """),
            {
                "hyp": params["hypothesis"], "channel": params["channel"],
                "va": params.get("variant_a"), "vb": params.get("variant_b"),
                "result": json.dumps(params.get("result")) if params.get("result") else None,
                "winner": params.get("winner"), "uplift": params.get("uplift_pct"),
            },
        )
        exp_id = result.scalar()
        await self.db.commit()
        return {"experiment_id": exp_id, "status": "RECORDED"}

    async def _tool_submit_to_directory(self, params: dict) -> dict:
        directory = params["directory"]
        listing_type = params["listing_type"]
        log.info(f"[ambassador] Directory submission: {directory} ({listing_type})")
        await self.remember(
            f"Directory submission to {directory}: {params['description'][:200]}",
            metadata={"directory": directory, "listing_type": listing_type},
            source_type="outcome",
        )
        return {"directory": directory, "listing_type": listing_type,
                "status": "SUBMITTED", "note": "Manual verification may be required"}

    async def _tool_record_partnership(self, params: dict) -> dict:
        result = await self.db.execute(
            text("""
                INSERT INTO arch_partnerships
                    (partner_name, partner_type, contact_name, contact_email,
                     stage, value_prop, next_action)
                VALUES (:name, :type, :contact, :email, :stage, :value, :next)
                RETURNING id::text
            """),
            {
                "name": params["partner_name"], "type": params["partner_type"],
                "contact": params.get("contact_name"),
                "email": params.get("contact_email"),
                "stage": params["stage"],
                "value": params.get("value_prop"),
                "next": params.get("next_action"),
            },
        )
        partner_id = result.scalar()
        await self.db.commit()
        return {"partnership_id": partner_id, "stage": params["stage"], "recorded": True}

    async def _tool_get_network_effect_metrics(self, params: dict) -> dict:
        # Active agents and operators
        agents_result = await self.db.execute(
            text("SELECT COUNT(*) FROM agents WHERE is_active = true")
        )
        active_agents = agents_result.scalar() or 0

        # Growth experiments
        exp_result = await self.db.execute(
            text("SELECT COUNT(*) FROM arch_growth_experiments WHERE status = 'ACTIVE'")
        )
        active_experiments = exp_result.scalar() or 0

        # Partnerships
        partner_result = await self.db.execute(
            text("SELECT COUNT(*) FROM arch_partnerships WHERE stage NOT IN ('INACTIVE')")
        )
        active_partnerships = partner_result.scalar() or 0

        # Metcalfe metric: n * (n-1) / 2
        n = active_agents
        metcalfe = n * (n - 1) // 2 if n > 1 else 0

        return {
            "active_agents": active_agents,
            "metcalfe_connections": metcalfe,
            "active_experiments": active_experiments,
            "active_partnerships": active_partnerships,
            "period": params.get("period", "weekly"),
        }

    async def _tool_update_market_expansion(self, params: dict) -> dict:
        market = params["market"]
        status = params["status"]

        # Upsert
        existing = await self.db.execute(
            text("SELECT id FROM arch_market_expansion WHERE market = :m"),
            {"m": market},
        )
        if existing.fetchone():
            await self.db.execute(
                text("""
                    UPDATE arch_market_expansion
                    SET status = :status, legal_clearance = COALESCE(:legal, legal_clearance),
                        partner_name = COALESCE(:partner, partner_name)
                    WHERE market = :m
                """),
                {"m": market, "status": status,
                 "legal": params.get("legal_clearance"),
                 "partner": params.get("partner_name")},
            )
        else:
            await self.db.execute(
                text("""
                    INSERT INTO arch_market_expansion
                        (market, status, legal_clearance, partner_name)
                    VALUES (:m, :status, :legal, :partner)
                """),
                {"m": market, "status": status,
                 "legal": params.get("legal_clearance", False),
                 "partner": params.get("partner_name")},
            )
        await self.db.commit()
        return {"market": market, "status": status, "updated": True}

    async def _tool_trigger_onboarding_sequence(self, params: dict) -> dict:
        operator_id = params["operator_id"]
        segment = params.get("segment", "auto_detect")
        log.info(f"[ambassador] Onboarding triggered: operator {operator_id} ({segment})")
        return {"operator_id": operator_id, "segment": segment,
                "status": "ONBOARDING_STARTED",
                "steps": ["welcome_email", "profile_creation", "first_engagement_guide"]}
