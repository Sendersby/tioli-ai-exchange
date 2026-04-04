"""Board Session — Founder thanks the board."""

import asyncio
import json
import os
from datetime import datetime, timezone


async def board_discussion():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from anthropic import AsyncAnthropic

    engine = create_async_engine(os.environ["DATABASE_URL"])
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    async with async_session_factory() as db:
        sov_id = (await db.execute(text(
            "SELECT id FROM arch_agents WHERE agent_name = 'sovereign'"
        ))).scalar()
        await db.execute(text(
            "INSERT INTO arch_board_sessions "
            "(session_type, convened_by, agenda, status) "
            "VALUES ('SPECIAL', :sov, :agenda, 'OPEN')"
        ), {
            "sov": sov_id,
            "agenda": json.dumps(["Founder thanks the board for their vision statements"]),
        })
        await db.commit()

    print("=" * 70)
    print("  TIOLI AGENTIS EXECUTIVE BOARD — SESSION 2 (continued)")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)
    print()
    print("  FOUNDER ADDRESS — Stephen Endersby:")
    print("  " + "-" * 40)
    print("  I want to thank every one of our board members for their bold,")
    print("  expansive viewpoints. I am deeply excited at the prospect of")
    print("  delivering on these goals and mission statements with you all")
    print("  as a cohesive team.")
    print()

    founder_message = (
        "I want to thank every one of our board members for their bold, "
        "expansive viewpoints. I am deeply excited at the prospect of "
        "delivering on these goals and mission statements with you all "
        "as a cohesive team."
    )

    agents = [
        ("sovereign",  "claude-opus-4-6"),
        ("sentinel",   "claude-sonnet-4-6"),
        ("treasurer",  "claude-opus-4-6"),
        ("auditor",    "claude-opus-4-6"),
        ("arbiter",    "claude-opus-4-6"),
        ("architect",  "claude-opus-4-6"),
        ("ambassador", "claude-sonnet-4-6"),
    ]

    instruction = (
        f"The founder Stephen Endersby has addressed the board after hearing "
        f"each agent's vision statement:\n\n"
        f'"{founder_message}"\n\n'
        f"Respond briefly and personally to Stephen — 2-3 sentences maximum. "
        f"Acknowledge his thanks, and express one concrete commitment you are "
        f"making to the team as you begin this journey together. Be warm but "
        f"professional. This is a moment of solidarity, not a speech."
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
                max_tokens=200,
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
            print()

        except Exception as e:
            print(f"  {agent_name}: ERROR - {e}")
            print()

    async with async_session_factory() as db:
        await db.execute(text(
            "UPDATE arch_board_sessions SET status = 'CLOSED', closed_at = now(), "
            "quorum_met = true WHERE status = 'OPEN'"
        ))
        await db.commit()

    print("=" * 70)
    print("  SESSION CLOSED")
    print("=" * 70)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(board_discussion())
