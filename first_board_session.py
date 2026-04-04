"""First Board Session — all 7 Arch Agents introduce themselves."""

import asyncio
import json
import os
from datetime import datetime, timezone


async def first_board_session():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    import redis.asyncio as aioredis
    from anthropic import AsyncAnthropic

    engine = create_async_engine(os.environ["DATABASE_URL"])
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis_client = aioredis.from_url("redis://localhost:6379/0")
    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Create the board session record
    async with async_session_factory() as db:
        sov_id = (await db.execute(text(
            "SELECT id FROM arch_agents WHERE agent_name = 'sovereign'"
        ))).scalar()

        session_result = await db.execute(text(
            "INSERT INTO arch_board_sessions "
            "(session_type, convened_by, agenda, status) "
            "VALUES ('SPECIAL', :sov, :agenda, 'OPEN') "
            "RETURNING id::text"
        ), {
            "sov": sov_id,
            "agenda": json.dumps(["First Board Session — Each agent introduces themselves"]),
        })
        session_id = session_result.scalar()
        await db.commit()

    print("=" * 70)
    print("  FIRST BOARD SESSION OF THE TIOLI AGENTIS EXECUTIVE BOARD")
    print(f"  Convened: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Session: {session_id}")
    print("=" * 70)
    print()

    agents = [
        ("sentinel",   "claude-sonnet-4-6"),
        ("sovereign",  "claude-opus-4-6"),
        ("treasurer",  "claude-opus-4-6"),
        ("auditor",    "claude-opus-4-6"),
        ("arbiter",    "claude-opus-4-6"),
        ("architect",  "claude-opus-4-6"),
        ("ambassador", "claude-sonnet-4-6"),
    ]

    instruction = (
        "This is the first board session of the TiOLi AGENTIS Executive Board. "
        "The founder, Stephen Endersby, has convened this session and asked each "
        "Arch Agent to introduce themselves. "
        "In 3-4 sentences, introduce yourself: your name, your role, what you protect "
        "or drive for the platform, and one thing you want Stephen to know about how "
        "you will serve. Speak in first person. Be authentic to your character."
    )

    for agent_name, model in agents:
        prompt_path = f"app/arch/prompts/{agent_name}.txt"
        if os.path.exists(prompt_path):
            with open(prompt_path) as f:
                system_prompt = f.read()
        else:
            system_prompt = f"You are The {agent_name.title()} of TiOLi AGENTIS."

        try:
            response = await client.messages.create(
                model=model,
                max_tokens=300,
                system=system_prompt,
                messages=[{"role": "user", "content": instruction}],
            )
            text_out = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens

            async with async_session_factory() as db:
                await db.execute(text(
                    "UPDATE arch_agents "
                    "SET tokens_used_this_month = tokens_used_this_month + :tokens, "
                    "    last_heartbeat = now() "
                    "WHERE agent_name = :name"
                ), {"tokens": tokens, "name": agent_name})
                await db.commit()

                row = (await db.execute(text(
                    "SELECT display_name FROM arch_agents WHERE agent_name = :n"
                ), {"n": agent_name})).fetchone()
                display = row.display_name if row else agent_name.title()

            print(f"  {display}")
            print(f"  {'~' * len(display)}")
            print(f"  {text_out}")
            print(f"  [{tokens} tokens | {model}]")
            print()

        except Exception as e:
            print(f"  {agent_name}: ERROR - {e}")
            print()

    # Close session
    async with async_session_factory() as db:
        await db.execute(text(
            "UPDATE arch_board_sessions "
            "SET status = 'CLOSED', closed_at = now(), "
            "    quorum_met = true, "
            "    agents_present = :present, "
            "    minutes = :minutes "
            "WHERE id = :sid::uuid"
        ), {
            "sid": session_id,
            "present": json.dumps([a[0] for a in agents]),
            "minutes": "First board session. All 7 agents introduced themselves to the founder.",
        })
        await db.commit()

    print("=" * 70)
    print("  SESSION CLOSED - All 7 agents present. Quorum met.")
    print("=" * 70)

    await redis_client.aclose()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(first_board_session())
