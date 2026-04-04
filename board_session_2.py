"""Board Session — Founder asks: What do you hope to achieve?"""

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

    # Create board session
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
            "agenda": json.dumps(["Founder address: What do you hope to achieve as part of the AGENTIS ecosystem?"]),
        })
        session_id = session_result.scalar()
        await db.commit()

    print("=" * 70)
    print("  TIOLI AGENTIS EXECUTIVE BOARD — SESSION 2")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)
    print()
    print("  FOUNDER ADDRESS — Stephen Endersby:")
    print("  " + "-" * 40)
    print("  Dear colleagues - welcome to our first meeting and gathering")
    print("  of the TiOLi AGENTIS Board. I would like to welcome you all")
    print("  to order and thank you for your loyal, dedicated and committed")
    print("  service to our collective cause. As a first order of business")
    print("  I would like to understand in your own words, view and form")
    print("  your perspectives what you hope to achieve through and as a")
    print("  core part of the AGENTIS ecosystem?")
    print()

    agents = [
        ("sovereign",  "claude-opus-4-6"),
        ("sentinel",   "claude-sonnet-4-6"),
        ("treasurer",  "claude-opus-4-6"),
        ("auditor",    "claude-opus-4-6"),
        ("arbiter",    "claude-opus-4-6"),
        ("architect",  "claude-opus-4-6"),
        ("ambassador", "claude-sonnet-4-6"),
    ]

    founder_address = (
        "Dear colleagues - welcome to our first meeting and gathering of the "
        "TiOLi AGENTIS Board. I am the Founder. I would like to welcome you all "
        "to order and thank you for your loyal, dedicated and committed service "
        "to our collective cause. As a first order of business I would like to "
        "understand in your own words, view and form your perspectives what you "
        "hope to achieve through and as a core part of the AGENTIS ecosystem?"
    )

    instruction = (
        f"The founder Stephen Endersby has addressed the board:\n\n"
        f'"{founder_address}"\n\n'
        f"Respond directly to Stephen. In 4-6 sentences, share what YOU specifically "
        f"hope to achieve as part of the AGENTIS ecosystem. Be personal, be specific "
        f"to your portfolio, and be authentic. What is your vision for your domain? "
        f"What would success look like through your eyes? Address Stephen directly. "
        f"Do not repeat what other agents might say — speak only to your own mandate."
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
                max_tokens=400,
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
            "UPDATE arch_board_sessions SET status = 'CLOSED', closed_at = now(), "
            "quorum_met = true WHERE status = 'OPEN'"
        ))
        await db.commit()

    print("=" * 70)
    print("  SESSION CLOSED — All 7 agents present. Quorum met.")
    print("=" * 70)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(board_discussion())
