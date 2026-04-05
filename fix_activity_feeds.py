"""Fix activity feeds — backfill from audit log + chat, and wire future logging."""

import asyncio
import json
import os
from datetime import datetime, timezone


async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text

    engine = create_async_engine(os.environ["DATABASE_URL"])
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sf() as db:
        # 1. Backfill from audit log → event_actions
        print("Backfilling from arch_audit_log...")
        audit_rows = await db.execute(text("""
            SELECT al.action_type, al.action_detail, al.created_at,
                   a.agent_name
            FROM arch_audit_log al
            JOIN arch_agents a ON al.agent_id = a.id
            ORDER BY al.created_at ASC
        """))

        count = 0
        for r in audit_rows.fetchall():
            detail = r.action_detail if isinstance(r.action_detail, dict) else json.loads(r.action_detail) if r.action_detail else {}

            # Create human-readable action description
            action_type = r.action_type
            if "EXECUTOR_SHELL_COMMAND" in action_type:
                cmd = detail.get("command", "")[:100]
                action_desc = f"Executed command: {cmd}"
                event_type = "system.command_executed"
            elif "EXECUTOR_SHELL_RESULT" in action_type:
                continue  # Skip result entries (paired with command)
            elif "EXECUTOR_CONTENT_GENERATE" in action_type:
                preview = detail.get("prompt_preview", "")[:100]
                action_desc = f"Generated content: {preview}"
                event_type = "content.generated"
            elif "EXECUTOR_FILE_WRITE" in action_type:
                path = detail.get("path", "")
                action_desc = f"Created file: {path}"
                event_type = "system.file_created"
            elif "EXECUTOR_BROWSE_URL" in action_type:
                url = detail.get("url", "")
                action_desc = f"Browsed: {url}"
                event_type = "research.web_browse"
            elif "EXECUTOR_SOCIAL_POST" in action_type:
                platform = detail.get("platform", "")
                action_desc = f"Posted to {platform}"
                event_type = "social.content_posted"
            elif "EXECUTOR_HTTP_REQUEST" in action_type:
                url = detail.get("url", "")[:80]
                action_desc = f"API call: {detail.get('method', 'GET')} {url}"
                event_type = "system.api_call"
            else:
                summary = detail.get("summary", detail.get("detail", ""))
                if isinstance(summary, str):
                    action_desc = summary[:200]
                else:
                    action_desc = json.dumps(detail)[:200]
                event_type = f"agent.{action_type.lower()}"

            await db.execute(text("""
                INSERT INTO arch_event_actions
                    (agent_id, event_type, action_taken, tool_called,
                     tool_input, processing_time_ms, created_at)
                VALUES (:agent, :etype, :action, :tool, :input, 0, :ts)
            """), {
                "agent": r.agent_name,
                "etype": event_type,
                "action": action_desc,
                "tool": action_type,
                "input": json.dumps(detail, default=str),
                "ts": r.created_at,
            })
            count += 1

        await db.commit()
        print(f"  Backfilled {count} audit entries to event_actions")

        # 2. Backfill from chat messages → event_actions
        print("Backfilling from boardroom_chat_messages...")
        chat_rows = await db.execute(text("""
            SELECT agent_id, direction, message_text, message_type, created_at
            FROM boardroom_chat_messages
            ORDER BY created_at ASC
        """))

        chat_count = 0
        for r in chat_rows.fetchall():
            if r.direction == "OUTBOUND":
                action_desc = f"Founder message: {r.message_text[:150]}"
                event_type = "boardroom.founder_message"
                agent = r.agent_id if r.agent_id != "ALL_BOARD" else "sovereign"
            else:
                action_desc = f"Response to founder: {r.message_text[:150]}"
                event_type = "boardroom.agent_response"
                agent = r.agent_id

            await db.execute(text("""
                INSERT INTO arch_event_actions
                    (agent_id, event_type, action_taken, processing_time_ms, created_at)
                VALUES (:agent, :etype, :action, 0, :ts)
            """), {
                "agent": agent,
                "etype": event_type,
                "action": action_desc,
                "ts": r.created_at,
            })
            chat_count += 1

        await db.commit()
        print(f"  Backfilled {chat_count} chat messages to event_actions")

        # 3. Add board session activities
        print("Backfilling from board sessions...")
        sessions = await db.execute(text("""
            SELECT id::text, session_type, status, agenda, opened_at, closed_at
            FROM arch_board_sessions ORDER BY opened_at ASC
        """))

        sess_count = 0
        for s in sessions.fetchall():
            agenda_str = json.dumps(s.agenda)[:200] if s.agenda else "No agenda"
            await db.execute(text("""
                INSERT INTO arch_event_actions
                    (agent_id, event_type, action_taken, processing_time_ms, created_at)
                VALUES ('sovereign', 'boardroom.session_convened',
                        :action, 0, :ts)
            """), {
                "action": f"Board session ({s.session_type}): {agenda_str}",
                "ts": s.opened_at,
            })
            sess_count += 1
            if s.closed_at:
                await db.execute(text("""
                    INSERT INTO arch_event_actions
                        (agent_id, event_type, action_taken, processing_time_ms, created_at)
                    VALUES ('sovereign', 'boardroom.session_closed',
                            :action, 0, :ts)
                """), {
                    "action": f"Session closed ({s.session_type})",
                    "ts": s.closed_at,
                })
                sess_count += 1

        await db.commit()
        print(f"  Backfilled {sess_count} board session events")

        # 4. Add founding statement events
        print("Backfilling constitutional rulings...")
        rulings = await db.execute(text("""
            SELECT ruling_ref, ruling_type, subject_agents, issued_at
            FROM arch_constitutional_rulings ORDER BY issued_at ASC
        """))

        ruling_count = 0
        for r in rulings.fetchall():
            agents = json.loads(r.subject_agents) if isinstance(r.subject_agents, str) else r.subject_agents
            agent = agents[0] if agents else "sovereign"
            await db.execute(text("""
                INSERT INTO arch_event_actions
                    (agent_id, event_type, action_taken, processing_time_ms, created_at)
                VALUES (:agent, 'governance.constitutional_ruling',
                        :action, 0, :ts)
            """), {
                "agent": agent,
                "action": f"Constitutional ruling: {r.ruling_ref} ({r.ruling_type})",
                "ts": r.issued_at,
            })
            ruling_count += 1

        await db.commit()
        print(f"  Backfilled {ruling_count} constitutional rulings")

        # Final count
        total = await db.execute(text("SELECT COUNT(*) FROM arch_event_actions"))
        by_agent = await db.execute(text("""
            SELECT agent_id, COUNT(*) as actions
            FROM arch_event_actions GROUP BY agent_id ORDER BY actions DESC
        """))

        print(f"\nTotal activity entries: {total.scalar()}")
        print("Per agent:")
        for r in by_agent.fetchall():
            print(f"  {r.agent_id}: {r.actions}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
