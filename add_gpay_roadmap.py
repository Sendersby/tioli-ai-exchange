"""Add Google Pay to the roadmap."""
import asyncio, os, json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

async def add():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        await db.execute(text(
            "INSERT INTO arch_founder_inbox "
            "(item_type, priority, description, status, due_at) "
            "VALUES ('INFORMATION', 'ROUTINE', :desc, 'PENDING', now() + interval '30 days')"
        ), {
            "desc": json.dumps({
                "subject": "Google Pay Integration — Priority Roadmap Item",
                "detail": "Add Google Pay as third payment option alongside PayPal and PayFast. Requires Google Pay API integration. Priority P1 for next development cycle.",
                "assigned_to": "architect",
                "estimated_effort": "2-3 days",
            }),
        })

        # Also log as a platform event for tracking
        await db.execute(text(
            "INSERT INTO arch_event_actions "
            "(agent_id, event_type, action_taken, processing_time_ms) "
            "VALUES ('sovereign', 'roadmap.item_added', "
            "'Google Pay integration added to priority roadmap by founder directive', 0)"
        ))

        await db.commit()
        print("Google Pay added to roadmap — priority P1")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(add())
