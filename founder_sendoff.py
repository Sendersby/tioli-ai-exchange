"""Founder sendoff — the board responds."""

import asyncio
import json
import os
from datetime import datetime, timezone


async def run():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from anthropic import AsyncAnthropic

    engine = create_async_engine(os.environ["DATABASE_URL"])
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    agents_order = [
        ("sovereign",  "claude-opus-4-6"),
        ("treasurer",  "claude-sonnet-4-6"),
        ("auditor",    "claude-sonnet-4-6"),
        ("arbiter",    "claude-sonnet-4-6"),
        ("architect",  "claude-sonnet-4-6"),
        ("sentinel",   "claude-sonnet-4-6"),
        ("ambassador", "claude-sonnet-4-6"),
    ]

    instruction = (
        "The founder has just closed the strategic board session with these words:\n\n"
        "\"Good luck team, let the work that's begun yield abundant fruit when it's done. "
        "Chat soon team!\"\n\n"
        "Respond with a single sentence — warm, personal, committed. "
        "This is a farewell before 3 days of independent work. "
        "Match your character. No headers, no formatting, just your words."
    )

    print()
    for agent_name, model in agents_order:
        prompt_path = f"app/arch/prompts/{agent_name}.txt"
        if os.path.exists(prompt_path):
            with open(prompt_path) as f:
                system_prompt = f.read()
        else:
            system_prompt = f"You are The {agent_name.title()} of TiOLi AGENTIS."

        try:
            response = await client.messages.create(
                model=model, max_tokens=80,
                system=system_prompt,
                messages=[{"role": "user", "content": instruction}],
            )
            text_out = response.content[0].text.strip()
            tokens = response.usage.input_tokens + response.usage.output_tokens

            async with sf() as db:
                await db.execute(text(
                    "UPDATE arch_agents "
                    "SET tokens_used_this_month = tokens_used_this_month + :t, "
                    "    last_heartbeat = now() "
                    "WHERE agent_name = :n"
                ), {"t": tokens, "n": agent_name})
                row = (await db.execute(text(
                    "SELECT display_name FROM arch_agents WHERE agent_name = :n"
                ), {"n": agent_name})).fetchone()
                await db.commit()

            print(f"  {row.display_name}: {text_out}")
            print()
        except Exception as e:
            print(f"  {agent_name}: ERROR - {e}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run())
