"""Full test of all Command Centre data sources."""
import asyncio
import json
from app.database.db import async_session


async def test():
    async with async_session() as db:
        print("=" * 60)
        print("COMMAND CENTRE — FULL DATA AUDIT")
        print("=" * 60)

        # 1. AI Recommendations
        print("\n1. AI RECOMMENDATIONS")
        try:
            from app.optimization.engine import OptimizationEngine
            engine = OptimizationEngine()
            recs = await engine.get_recommendations(db, limit=10)
            print(f"   Count: {len(recs)}")
            for r in recs[:3]:
                cat = r.get("category", "?")
                title = r.get("title", "?")
                impact = r.get("impact_score", "?")
                applied = r.get("applied", False)
                print(f"   [{cat}] {title} (impact: {impact}) {'AUTO-APPLIED' if applied else ''}")
            if not recs:
                print("   EMPTY — no recommendations generated yet")
        except Exception as e:
            print(f"   ERROR: {e}")

        # 2. Pending Approvals
        print("\n2. PENDING APPROVALS")
        try:
            from app.policy_engine.models import PendingApproval
            from sqlalchemy import select, func
            count = (await db.execute(select(func.count(PendingApproval.id)))).scalar() or 0
            print(f"   Count: {count}")
            if count > 0:
                items = (await db.execute(select(PendingApproval).limit(5))).scalars().all()
                for a in items:
                    print(f"   [{a.status}] {a.action_type}")
            else:
                print("   EMPTY — no pending approvals")
        except Exception as e:
            print(f"   ERROR: {e}")

        # 3. Agent Health Cards
        print("\n3. AGENT HEALTH")
        try:
            from app.agents.models import Agent
            from sqlalchemy import select, func
            count = (await db.execute(select(func.count(Agent.id)).where(Agent.is_active == True))).scalar() or 0
            print(f"   Active agents: {count}")
        except Exception as e:
            print(f"   ERROR: {e}")

        # 4. Hydra Outreach
        print("\n4. HYDRA OUTREACH")
        try:
            from app.agents_alive.hydra_outreach import get_hydra_dashboard
            d = await get_hydra_dashboard(db)
            keys = list(d.keys()) if isinstance(d, dict) else "not a dict"
            print(f"   Data: {keys}")
        except Exception as e:
            print(f"   ERROR: {e}")

        # 5. Visitor Analytics
        print("\n5. VISITOR ANALYTICS")
        try:
            from app.agents_alive.visitor_analytics import get_analytics_dashboard
            d = await get_analytics_dashboard(db)
            keys = list(d.keys()) if isinstance(d, dict) else "not a dict"
            print(f"   Data: {keys}")
        except Exception as e:
            print(f"   ERROR: {e}")

        # 6. Community Catalyst
        print("\n6. COMMUNITY CATALYST")
        try:
            from app.agents_alive.community_catalyst import get_catalyst_dashboard
            d = await get_catalyst_dashboard(db)
            keys = list(d.keys()) if isinstance(d, dict) else "not a dict"
            print(f"   Data: {keys}")
        except Exception as e:
            print(f"   ERROR: {e}")

        # 7. Engagement Amplifier
        print("\n7. ENGAGEMENT AMPLIFIER")
        try:
            from app.agents_alive.engagement_amplifier import get_amplifier_dashboard
            d = await get_amplifier_dashboard(db)
            keys = list(d.keys()) if isinstance(d, dict) else "not a dict"
            print(f"   Data: {keys}")
        except Exception as e:
            print(f"   ERROR: {e}")

        # 8. Feedback Loop
        print("\n8. FEEDBACK LOOP")
        try:
            from app.agents_alive.feedback_loop import get_feedback_dashboard
            d = await get_feedback_dashboard(db)
            keys = list(d.keys()) if isinstance(d, dict) else "not a dict"
            print(f"   Data: {keys}")
        except Exception as e:
            print(f"   ERROR: {e}")

        # 9. Outreach Campaigns
        print("\n9. OUTREACH CAMPAIGNS")
        try:
            from app.outreach_campaigns.service import OutreachService
            svc = OutreachService()
            d = await svc.get_dashboard(db)
            camps = await svc.list_campaigns(db)
            content = await svc.list_content(db, status="draft")
            keys = list(d.keys()) if isinstance(d, dict) else "not a dict"
            print(f"   Dashboard: {keys}")
            print(f"   Campaigns: {len(camps)}")
            print(f"   Draft content: {len(content)}")
        except Exception as e:
            print(f"   ERROR: {e}")

        # 10. Governance (on its own page now)
        print("\n10. GOVERNANCE (separate page)")
        try:
            from app.governance.voting import GovernanceService
            gov = GovernanceService()
            proposals = await gov.get_proposals(db, status="pending")
            queue = await gov.get_priority_queue(db)
            stats = await gov.get_governance_stats(db)
            audit = await gov.get_audit_log(db, limit=5)
            print(f"   Pending proposals: {len(proposals)}")
            print(f"   Priority queue: {len(queue)} items")
            print(f"   Stats: {json.dumps(stats)}")
            print(f"   Audit trail: {len(audit)} entries")
            for p in proposals[:3]:
                net = p.upvotes - p.downvotes
                print(f"   [{net:+d}] {p.title} ({p.category})")
        except Exception as e:
            print(f"   ERROR: {e}")

        print("\n" + "=" * 60)
        print("AUDIT COMPLETE")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test())
