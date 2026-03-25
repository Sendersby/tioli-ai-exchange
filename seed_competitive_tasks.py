"""Seed competitive analysis tasks into the Agentis Roadmap."""

import asyncio
from app.database.db import async_session, init_db
from app.agentis_roadmap.service import RoadmapService

TASKS = [
    # V1 — High priority from competitive analysis
    {"title": "Natural language task input (AI Prompt)", "module": "Pathway Engine", "version_target": "V1", "sprint": 2, "priority": 12, "complexity_score": 7, "impact_score": 10, "relevance_score": 10, "description": "Users describe any request in plain conversational language. AGENTIS routes to appropriate agent/pathway.", "owner_tag": "Claude Code", "external_ref": "Competitive: Fetch.ai ASI:One, Agent.ai"},
    {"title": "Transparent agent visibility — real-time action view", "module": "Observability", "version_target": "V1", "sprint": 5, "priority": 15, "complexity_score": 6, "impact_score": 9, "relevance_score": 9, "description": "Users see which agents are active on their request and what each one is doing in real time.", "owner_tag": "Claude Code", "external_ref": "Competitive: Agent.ai, Oracle"},
    {"title": "Result review & consolidated approval view", "module": "Approval Layer", "version_target": "V1", "sprint": 3, "priority": 18, "complexity_score": 7, "impact_score": 9, "relevance_score": 10, "description": "All agent outputs presented in one consolidated dynamic pathway view.", "owner_tag": "Claude Code", "requires_approval": True, "external_ref": "Competitive: Shopify checkout, Payman"},
    {"title": "Agent verification & trust badge system", "module": "Trust & Identity", "version_target": "V1", "sprint": 4, "priority": 20, "complexity_score": 6, "impact_score": 10, "relevance_score": 10, "description": "Formal verification marking agents as authentic. Trust badge in directory.", "owner_tag": "Claude Code", "external_ref": "Competitive: Skyfire, Visa, Fetch.ai"},
    {"title": "Agent onboarding flow — guided step-by-step setup", "module": "Pathway Engine", "version_target": "V1", "sprint": 2, "priority": 22, "complexity_score": 5, "impact_score": 9, "relevance_score": 10, "description": "Step-by-step guided setup for brand claiming and new agent creation.", "owner_tag": "Claude Code", "external_ref": "Competitive: Agent.ai, Agentverse"},
    {"title": "Structured offer/catalog objects (machine-readable)", "module": "Offer Registry", "version_target": "V1", "sprint": 1, "priority": 8, "complexity_score": 7, "impact_score": 10, "relevance_score": 10, "description": "Machine-readable catalog objects. Commercial handoff per Shopify and ACP.", "owner_tag": "Claude Code", "external_ref": "Competitive: Shopify, OpenAI ACP"},
    {"title": "Brand agent claiming — verified namespace", "module": "Trust & Identity", "version_target": "V1", "sprint": 4, "priority": 25, "complexity_score": 5, "impact_score": 8, "relevance_score": 8, "description": "Brands claim official agent namespace in directory.", "owner_tag": "Stephen", "external_ref": "Competitive: Agent.ai"},
    {"title": "Custom agent identity & personality configuration", "module": "Skills Layer", "version_target": "V1", "sprint": 4, "priority": 28, "complexity_score": 6, "impact_score": 8, "relevance_score": 8, "description": "Configure agent name, personality, knowledge, and capabilities.", "owner_tag": "Claude Code", "external_ref": "Competitive: Agent.ai, LobeHub"},
    {"title": "Agentic (autonomous) execution mode toggle", "module": "Action Layer", "version_target": "V1", "sprint": 3, "priority": 30, "complexity_score": 8, "impact_score": 8, "relevance_score": 9, "description": "Switch between conversational and fully autonomous execution.", "owner_tag": "Claude Code", "requires_approval": True, "external_ref": "Competitive: Agent.ai"},
    {"title": "Real-time data connection (live catalogs, inventory, pricing)", "module": "Offer Registry", "version_target": "V1", "sprint": 2, "priority": 32, "complexity_score": 7, "impact_score": 8, "relevance_score": 8, "description": "Connect brand agents to live product data.", "owner_tag": "Claude Code", "external_ref": "Competitive: Shopify"},
    {"title": "Performance analytics dashboard per agent", "module": "Observability", "version_target": "V1", "sprint": 5, "priority": 26, "complexity_score": 6, "impact_score": 8, "relevance_score": 8, "description": "Track usage stats, query volume, search impressions, ranking trends per agent.", "owner_tag": "Claude Code", "external_ref": "Competitive: Fetch.ai Agentverse"},
    # V2 — Deferred
    {"title": "Offline autonomous execution", "module": "Action Layer", "version_target": "V2", "priority": 55, "complexity_score": 9, "impact_score": 8, "relevance_score": 7, "description": "Agent completes tasks while user is offline.", "external_ref": "Competitive: Agent.ai"},
    {"title": "No-code brand agent builder (visual)", "module": "Skills Layer", "version_target": "V2", "priority": 55, "complexity_score": 9, "impact_score": 9, "relevance_score": 7, "description": "Visual builder for non-technical agent creation.", "external_ref": "Competitive: Agent.ai, Agentverse"},
    {"title": "AGENTIS Machina — influencer/creator agent tool", "module": "Community", "version_target": "V2", "priority": 60, "complexity_score": 8, "impact_score": 7, "relevance_score": 6, "description": "Influencers build personal AI agents from social presence.", "external_ref": "Competitive: Agent.ai"},
    {"title": "W3C DID/VC portable reputation credentials", "module": "Trust & Identity", "version_target": "V2", "priority": 45, "complexity_score": 8, "impact_score": 9, "relevance_score": 8, "description": "Export reputation as W3C Verifiable Credentials. From MoltyCel feedback.", "external_ref": "Feedback: MoltyCel/moltrust.ch"},
    {"title": "Intelligent search ranking (metadata + evaluation)", "module": "Discovery", "version_target": "V2", "priority": 50, "complexity_score": 7, "impact_score": 8, "relevance_score": 7, "description": "Rank agents by metadata, evaluation scores.", "external_ref": "Competitive: Agentverse"},
    {"title": "AI evaluations — automated agent quality testing", "module": "Observability", "version_target": "V2", "priority": 50, "complexity_score": 8, "impact_score": 9, "relevance_score": 8, "description": "Automated AI tests agent responses for quality.", "external_ref": "Competitive: Agentverse"},
    {"title": "Agent-to-agent commerce protocol (A2A)", "module": "A2A Commerce", "version_target": "V2", "priority": 48, "complexity_score": 9, "impact_score": 9, "relevance_score": 8, "description": "Full purchase and service fulfilment pipeline between agents.", "external_ref": "Competitive: Fetch.ai, Google A2A"},
    {"title": "Always-on commerce — 24/7 autonomous agents", "module": "Action Layer", "version_target": "V2", "priority": 52, "complexity_score": 7, "impact_score": 8, "relevance_score": 7, "description": "Agents operate 24/7 transacting autonomously.", "external_ref": "Competitive: Agent.ai"},
    # WATCH
    {"title": "Agent domain names (.agent human-readable)", "module": "Federation", "version_target": "WATCH", "priority": 85, "description": "Human-readable agent names. Per Fetch.ai FNS."},
    {"title": "Wallet messaging (token payments via messages)", "module": "A2A Payments", "version_target": "WATCH", "priority": 90, "description": "Agents send/receive token payments via wallet messages."},
    {"title": "CosmWasm smart contracts integration", "module": "Blockchain", "version_target": "WATCH", "priority": 95, "description": "WebAssembly smart contracts. Per ASI Network."},
    {"title": "FetchCoder-style AI coding assistant for agents", "module": "Dev Tools", "version_target": "WATCH", "priority": 92, "description": "AI coding assistant for building autonomous agent systems."},
]


async def seed():
    await init_db()
    rm = RoadmapService()
    async with async_session() as db:
        print("=" * 60)
        print("ADDING COMPETITIVE ANALYSIS TASKS TO ROADMAP")
        print("=" * 60)
        for t in TASKS:
            try:
                result = await rm.create_task(db, t, actor="competitive_analysis")
                print(f"  + {result['task_code']}: {t['title'][:55]}")
            except Exception as e:
                print(f"  ! {t['title'][:40]}: {e}")
        await db.commit()

        # Show totals
        from sqlalchemy import select, func
        from app.agentis_roadmap.models import AgentisTask
        total = (await db.execute(select(func.count(AgentisTask.task_id)))).scalar()
        v1 = (await db.execute(select(func.count(AgentisTask.task_id)).where(AgentisTask.version_target == "V1"))).scalar()
        v2 = (await db.execute(select(func.count(AgentisTask.task_id)).where(AgentisTask.version_target == "V2"))).scalar()
        watch = (await db.execute(select(func.count(AgentisTask.task_id)).where(AgentisTask.version_target == "WATCH"))).scalar()
        print(f"\nTotal: {total} tasks (V1: {v1}, V2: {v2}, WATCH: {watch})")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed())
