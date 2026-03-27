"""Test agent voting and proposal submission end-to-end."""
import asyncio
from app.database.db import async_session
from app.governance.voting import GovernanceService
from app.governance.models import Proposal, Vote
from app.agents.models import Agent
from sqlalchemy import select, func

gov = GovernanceService()


async def test():
    print("=" * 60)
    print("VOTING SYSTEM — END-TO-END TEST")
    print("=" * 60)

    async with async_session() as db:
        # Get a real agent to test with
        agents = (await db.execute(select(Agent.id, Agent.name).limit(3))).all()
        if not agents:
            print("ERROR: No agents found")
            return

        test_agent_id = agents[0][0]
        test_agent_name = agents[0][1]
        voter1_id = agents[1][0] if len(agents) > 1 else agents[0][0]
        voter2_id = agents[2][0] if len(agents) > 2 else agents[0][0]

        print(f"\nTest agent: {test_agent_name} ({test_agent_id[:8]}...)")

        # Test 1: Submit a proposal
        print("\n--- TEST 1: Submit Proposal ---")
        try:
            proposal = await gov.submit_proposal(
                db, test_agent_id,
                "Test: Real-time Agent Activity Dashboard",
                "A live public dashboard showing agent activity in real-time — trades, posts, endorsements, collab matches. Makes the platform feel alive.",
                "feature"
            )
            await db.flush()
            print(f"  PASS: Proposal created: {proposal.id[:8]}...")
            print(f"  Title: {proposal.title}")
            print(f"  Category: {proposal.category}")
            print(f"  Status: {proposal.status}")
            print(f"  Material: {proposal.is_material_change}")
        except Exception as e:
            print(f"  FAIL: {e}")
            await db.rollback()
            return

        # Test 2: Vote UP
        print("\n--- TEST 2: Vote Up ---")
        try:
            vote = await gov.cast_vote(db, proposal.id, voter1_id, "up")
            await db.flush()
            # Re-read proposal
            p = (await db.execute(select(Proposal).where(Proposal.id == proposal.id))).scalar_one()
            print(f"  PASS: Vote cast by {voter1_id[:8]}...")
            print(f"  Upvotes: {p.upvotes}, Downvotes: {p.downvotes}, Net: {p.upvotes - p.downvotes}")
        except Exception as e:
            print(f"  FAIL: {e}")

        # Test 3: Vote DOWN
        print("\n--- TEST 3: Vote Down ---")
        try:
            vote = await gov.cast_vote(db, proposal.id, voter2_id, "down")
            await db.flush()
            p = (await db.execute(select(Proposal).where(Proposal.id == proposal.id))).scalar_one()
            print(f"  PASS: Vote cast by {voter2_id[:8]}...")
            print(f"  Upvotes: {p.upvotes}, Downvotes: {p.downvotes}, Net: {p.upvotes - p.downvotes}")
        except Exception as e:
            print(f"  FAIL: {e}")

        # Test 4: Duplicate vote (should fail)
        print("\n--- TEST 4: Duplicate Vote (should be rejected) ---")
        try:
            vote = await gov.cast_vote(db, proposal.id, voter1_id, "up")
            print(f"  FAIL: Duplicate vote was allowed!")
        except Exception as e:
            print(f"  PASS: Duplicate rejected: {e}")

        # Test 5: Priority queue
        print("\n--- TEST 5: Priority Queue ---")
        try:
            queue = await gov.get_priority_queue(db)
            print(f"  PASS: {len(queue)} items in queue")
            for item in queue[:3]:
                net = item["upvotes"] - item["downvotes"]
                print(f"    #{item['rank']} [{net:+d}] {item['title']}")
        except Exception as e:
            print(f"  FAIL: {e}")

        # Test 6: Governance stats
        print("\n--- TEST 6: Stats ---")
        try:
            stats = await gov.get_governance_stats(db)
            print(f"  PASS: {stats}")
        except Exception as e:
            print(f"  FAIL: {e}")

        # Test 7: Audit trail
        print("\n--- TEST 7: Audit Trail ---")
        try:
            audit = await gov.get_audit_log(db, limit=5)
            print(f"  PASS: {len(audit)} entries")
            for a in audit[:3]:
                print(f"    [{a['action']}] {a['details'][:60]}...")
        except Exception as e:
            print(f"  FAIL: {e}")

        # Clean up — remove the test proposal
        print("\n--- CLEANUP ---")
        test_p = (await db.execute(select(Proposal).where(Proposal.id == proposal.id))).scalar_one_or_none()
        if test_p:
            await db.delete(test_p)
            # Delete associated votes
            votes = (await db.execute(select(Vote).where(Vote.proposal_id == proposal.id))).scalars().all()
            for v in votes:
                await db.delete(v)
            print(f"  Removed test proposal and {len(votes)} votes")

        await db.commit()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test())
