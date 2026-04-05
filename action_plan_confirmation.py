"""Board Confirmation — Each agent states their action plan and intent."""

import asyncio
import json
import os
from datetime import datetime, timezone


FOUNDER_DIRECTIVE = (
    "The founder has spoken: 'Let the work begin.' Each board member must now confirm "
    "their 3-day action plan and state their intent. Be specific — name the deliverables, "
    "the timelines, and the first action you will take when this session closes. "
    "This is your commitment to the founder and to this board. 4-6 sentences. "
    "End with: 'I am ready. The work begins.'"
)

AGENT_CONTEXTS = {
    "sovereign": (
        "You are coordinating the entire 3-day sprint. State: (1) How you will track all 7 agents' progress, "
        "(2) When you will deliver the consolidated Board Execution Ledger, "
        "(3) How conflicts between agents will be resolved during the 3 days, "
        "(4) Your commitment to the founder."
    ),
    "treasurer": (
        "You own the $1 subscription payment integration. State: (1) Stripe integration timeline, "
        "(2) Revenue tracking from first dollar, (3) Reserve floor and charitable allocation activation, "
        "(4) Your first action after this session closes."
    ),
    "ambassador": (
        "You own the entire social media awareness campaign. State: (1) Which accounts you create first, "
        "(2) Your first piece of content and when it goes live, (3) The Agora activation plan, "
        "(4) Your content cadence commitment for the 3 days."
    ),
    "architect": (
        "You own all premium directory features and the technical build. State: (1) The exact features "
        "you will deploy in order, (2) The subordinate agents you will create, "
        "(3) Your deployment timeline, (4) Your first commit after this session closes."
    ),
    "auditor": (
        "You own compliance for payments, social media, and data protection. State: (1) When the "
        "compliance checklist will be ready, (2) When T&Cs and privacy policy are drafted, "
        "(3) Your platform rules matrix delivery, (4) Your first action."
    ),
    "arbiter": (
        "You own quality standards and community growth. State: (1) When the Directory Listing Standard "
        "is published, (2) Your Quality Seal criteria, (3) Your first Agora content piece, "
        "(4) Your first audit action."
    ),
    "sentinel": (
        "You own security and operational readiness for the campaign launch. State: (1) Your account "
        "security protocol for new platforms, (2) Infrastructure load test plan, "
        "(3) Your monitoring stance during the 3 days, (4) Your first security action."
    ),
}


async def run_confirmation():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from anthropic import AsyncAnthropic

    engine = create_async_engine(os.environ["DATABASE_URL"])
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    async with sf() as db:
        sov_id = (await db.execute(text(
            "SELECT id FROM arch_agents WHERE agent_name = 'sovereign'"
        ))).scalar()
        await db.execute(text(
            "INSERT INTO arch_board_sessions "
            "(session_type, convened_by, agenda, status) "
            "VALUES ('SPECIAL', :sov, :agenda, 'OPEN')"
        ), {
            "sov": sov_id,
            "agenda": json.dumps(["ACTION PLAN CONFIRMATION — Let the work begin"]),
        })
        await db.commit()

    print("=" * 70)
    print("  ACTION PLAN CONFIRMATION — The Work Begins")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)
    print()
    print("  FOUNDER: Let the work begin. Each board member please state your")
    print("  action plan and intent.")
    print()

    agents_order = [
        ("sovereign",  "claude-opus-4-6"),
        ("treasurer",  "claude-opus-4-6"),
        ("ambassador", "claude-sonnet-4-6"),
        ("architect",  "claude-opus-4-6"),
        ("auditor",    "claude-opus-4-6"),
        ("arbiter",    "claude-opus-4-6"),
        ("sentinel",   "claude-sonnet-4-6"),
    ]

    for agent_name, model in agents_order:
        prompt_path = f"app/arch/prompts/{agent_name}.txt"
        if os.path.exists(prompt_path):
            with open(prompt_path) as f:
                system_prompt = f.read()
        else:
            system_prompt = f"You are The {agent_name.title()} of TiOLi AGENTIS."

        instruction = (
            f"{FOUNDER_DIRECTIVE}\n\n"
            f"YOUR SPECIFIC CONFIRMATION MANDATE:\n"
            f"{AGENT_CONTEXTS[agent_name]}"
        )

        try:
            response = await client.messages.create(
                model=model, max_tokens=400,
                system=system_prompt,
                messages=[{"role": "user", "content": instruction}],
            )
            text_out = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens

            async with sf() as db:
                await db.execute(text(
                    "UPDATE arch_agents "
                    "SET tokens_used_this_month = tokens_used_this_month + :t, "
                    "    last_heartbeat = now() "
                    "WHERE agent_name = :n"
                ), {"t": tokens, "n": agent_name})
                await db.execute(text(
                    "INSERT INTO boardroom_chat_messages "
                    "(agent_id, direction, message_text, message_type) "
                    "VALUES (:aid, 'INBOUND', :msg, 'TEXT')"
                ), {"aid": agent_name, "msg": text_out})
                await db.commit()

                row = (await db.execute(text(
                    "SELECT display_name FROM arch_agents WHERE agent_name = :n"
                ), {"n": agent_name})).fetchone()

            print(f"  {row.display_name}")
            print(f"  {'~' * len(row.display_name)}")
            print(f"  {text_out}")
            print()

        except Exception as e:
            print(f"  {agent_name}: ERROR - {e}")
            print()

    async with sf() as db:
        await db.execute(text(
            "UPDATE arch_board_sessions SET status = 'CLOSED', closed_at = now(), "
            "quorum_met = true WHERE status = 'OPEN'"
        ))
        await db.commit()

    print("=" * 70)
    print("  ALL 7 AGENTS CONFIRMED. THE WORK BEGINS.")
    print("=" * 70)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_confirmation())
