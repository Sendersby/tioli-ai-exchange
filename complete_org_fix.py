"""Complete organogram fix — register ALL agents, fix backgrounds, add proactive scheduling."""
import asyncio, json, os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Register the 24 test/dev agents under The Architect (technology oversight)
TEST_AGENTS = [
    "AuditBot-REST-001", "Autonomous Test Agent", "BonusTestBot",
    "ConnectTestAgent", "DeployTestAgent", "DropoffTest", "FETest",
    "FEVerify", "FinalVerify", "FinalVerifyBot", "FoundingTest",
    "JourneyTest", "JourneyTestBot_E2E", "JourneyTestBot_Referral",
    "LandingPageTestBot", "PathCheck3x", "PathwayTest1", "PyPI-Test-Bot",
    "Test Agent", "TestBot-Audit-2026", "TestFromGetStarted",
    "TestSDKAgent_Verify", "TokenVerify", "test",
]

async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sf() as db:
        count = 0
        for name in TEST_AGENTS:
            # Check if already registered
            existing = await db.execute(text(
                "SELECT id FROM arch_platform_events "
                "WHERE event_type = 'agent.subordinate_created' "
                "AND event_data->>'subordinate_name' = :name"
            ), {"name": name})
            if existing.fetchone():
                continue

            await db.execute(text(
                "INSERT INTO arch_platform_events "
                "(event_type, event_data, source_module) "
                "VALUES ('agent.subordinate_created', :data, 'subordinate_manager')"
            ), {"data": json.dumps({
                "subordinate_name": name,
                "managing_arch_agent": "architect",
                "layer": 4,
                "layer_name": "Task Agent",
                "platform": "Test",
                "description": "Development/test agent — created during platform build",
                "category": "test_development",
            })})
            count += 1

        await db.commit()
        print(f"Registered {count} test agents under Architect")

        # Verify total
        total = await db.execute(text(
            "SELECT COUNT(DISTINCT event_data->>'subordinate_name') "
            "FROM arch_platform_events WHERE event_type = 'agent.subordinate_created'"
        ))
        print(f"Total registered subordinates: {total.scalar()}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
