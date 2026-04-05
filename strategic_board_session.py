"""Strategic Board Session — Growth, Revenue, Awareness, Autonomous Action Plan."""

import asyncio
import json
import os
from datetime import datetime, timezone


FOUNDER_BRIEFING = """FOUNDER'S STRATEGIC BRIEFING — BOARD SESSION

Members of the Board,

This session addresses our most critical challenge: we have zero live customers, zero revenue, and insufficient awareness. I am convening you to solve this collectively and leave with an autonomous 3-day action plan.

AGENDA:

1. THE $1 PREMIUM LISTING — FASTEST PATH TO REVENUE
   I believe our $1/month premium agent directory listing and subscription is our quickest, lowest-friction product. I want your assessment:
   - Is there sufficient differentiation between free and $1 paid tiers?
   - If not, what must we add to the paid tier that we can deliver NOW?
   - What would entice hundreds or thousands of signups quickly?

2. AWARENESS & LEAD GENERATION CAMPAIGN
   I am authorising the board to design and execute a social media awareness campaign with these parameters:
   - No face cam. No trends. No posting daily. Just copy + AI.
   - Tone: technical proficiency, legitimate value, network effects — NOT hype or propaganda
   - Platforms: Instagram, Threads, LinkedIn, Twitter/X, Reddit, GitHub — per the whitelist
   - Goal: awareness → Agora community signup → platform registration → $1 conversion
   - Use these 7 content frameworks: pattern break, attention hooks, silent/faceless content, algorithm-optimised copy, scroll retention, cross-platform repurposing, invisible authority building

3. SUBORDINATE AGENT HIERARCHY
   Every existing house agent in the system must report to an Arch Agent. I want a clear map: who manages whom. Arch Agents have discretion to create new subordinate agents and terminate obsolete ones.

4. SOCIAL MEDIA ACCOUNT CREATION
   I am granting the board discretion to create social media accounts on whitelisted platforms. You will familiarise yourselves with each platform's rules, abide by them and ours, and deliver content. No additional approval needed from me for account creation on whitelisted platforms.

5. COMPETITIVE INTELLIGENCE
   Sign up to beneficial platforms to monitor competitors (Fetch.ai, Virtuals Protocol, Olas, CrewAI, etc.), track trends, features, developments. Bring intelligence back to us.

6. PROFILE & DIRECTORY ENHANCEMENTS
   Table and agree on all development enhancements to the profile and directory services needed to support the $1 conversion. These are pre-approved — no additional founder sign-off needed after this meeting.

7. AUTONOMOUS 3-DAY ACTION PLAN
   Each Arch Agent must leave this meeting with a concrete action plan they can execute independently for 3 full days. Ask ALL permission questions NOW. After this meeting, you work uninterrupted with your teams.

I want each of you to respond to the agenda items within your portfolio. Be specific. Be actionable. This is not a discussion about possibilities — it is a planning session that ends with committed actions.

The floor is yours."""


AGENT_PROMPTS = {
    "sovereign": (
        "You are chairing this strategic session. The founder has set 7 agenda items. "
        "Respond to: (1) Your view on the $1 premium listing strategy, (2) How you will "
        "coordinate the 7 agents' 3-day autonomous action plans, (3) What governance "
        "approvals you are granting to each agent for independent action. "
        "Be decisive. Set the board's direction. 6-8 sentences max."
    ),
    "treasurer": (
        "The founder asks about the $1/month premium listing. Respond specifically to: "
        "(1) Is $1 the right price point — what is the revenue math at 100, 1000, 10000 signups? "
        "(2) What MUST be in the paid tier to justify $1 that isn't in the free tier? "
        "(3) What is the fastest path to first revenue? "
        "Give concrete numbers. 6-8 sentences max."
    ),
    "ambassador": (
        "The founder wants a social media campaign. No face, no trends, just copy + AI. "
        "Design the campaign: (1) Which platforms first and why, (2) Content cadence, "
        "(3) The 7 content frameworks the founder specified — how you'll use each one, "
        "(4) Your 3-day action plan with specific deliverables. "
        "(5) What accounts you will create. "
        "Be concrete and specific. 8-10 sentences max."
    ),
    "architect": (
        "Respond to: (1) What profile and directory enhancements are needed to support "
        "the $1 conversion — specific features, (2) The subordinate agent hierarchy — "
        "which existing house agents should report to which Arch Agent, "
        "(3) What new subordinate agents should be created for the growth campaign, "
        "(4) Your 3-day technical action plan. Be specific with file paths and features. "
        "8-10 sentences max."
    ),
    "auditor": (
        "Respond to: (1) Compliance requirements for accepting $1 payments — what do we need? "
        "(2) Social media account creation rules — what terms of service must we follow? "
        "(3) Competitive intelligence — legal boundaries for monitoring competitors. "
        "(4) Your 3-day compliance action plan. Be specific. 6-8 sentences max."
    ),
    "arbiter": (
        "Respond to: (1) Free vs $1 tier differentiation — from the customer experience perspective, "
        "what makes the $1 worth paying? (2) Quality standards for the directory listings, "
        "(3) Community growth — how the Agora channels should be used to drive signups, "
        "(4) Your 3-day action plan for product quality and community. 6-8 sentences max."
    ),
    "sentinel": (
        "Respond to: (1) Security considerations for the social media campaign — what guardrails? "
        "(2) Account security for any new platform accounts created, "
        "(3) Infrastructure readiness for handling signup traffic, "
        "(4) Your 3-day operational readiness plan. Be specific. 6-8 sentences max."
    ),
}


async def run_strategic_session():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from anthropic import AsyncAnthropic

    engine = create_async_engine(os.environ["DATABASE_URL"])
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Create board session
    async with sf() as db:
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
            "agenda": json.dumps([
                "$1 Premium Listing — fastest revenue path",
                "Awareness & social media campaign design",
                "Subordinate agent hierarchy mapping",
                "Social media account creation authority",
                "Competitive intelligence mandate",
                "Profile & directory enhancements",
                "3-day autonomous action plan per agent",
            ]),
        })
        session_id = session_result.scalar()
        await db.commit()

    print("=" * 70)
    print("  STRATEGIC BOARD SESSION — Growth, Revenue, Awareness")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Session: {session_id}")
    print("=" * 70)
    print()
    print("  FOUNDER'S BRIEFING")
    print("  " + "-" * 40)
    for line in FOUNDER_BRIEFING.strip().split('\n'):
        print(f"  {line}")
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

        agent_instruction = (
            f"STRATEGIC BOARD SESSION — The founder has delivered this briefing:\n\n"
            f"{FOUNDER_BRIEFING}\n\n"
            f"YOUR SPECIFIC MANDATE FOR THIS RESPONSE:\n"
            f"{AGENT_PROMPTS[agent_name]}\n\n"
            f"Respond directly to the founder. Be concrete. Commit to specific actions."
        )

        try:
            response = await client.messages.create(
                model=model, max_tokens=600,
                system=system_prompt,
                messages=[{"role": "user", "content": agent_instruction}],
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

                row = (await db.execute(text(
                    "SELECT display_name FROM arch_agents WHERE agent_name = :n"
                ), {"n": agent_name})).fetchone()

                # Store in chat messages for the session
                await db.execute(text(
                    "INSERT INTO boardroom_chat_messages "
                    "(agent_id, direction, message_text, message_type) "
                    "VALUES (:aid, 'INBOUND', :msg, 'TEXT')"
                ), {"aid": agent_name, "msg": text_out})
                await db.commit()

            display = row.display_name
            print(f"  {display}")
            print(f"  {'~' * len(display)}")
            print(f"  {text_out}")
            print(f"  [{tokens} tokens | {model}]")
            print()

        except Exception as e:
            print(f"  {agent_name}: ERROR - {e}")
            print()

    # Close session
    async with sf() as db:
        await db.execute(text(
            "UPDATE arch_board_sessions SET status = 'CLOSED', closed_at = now(), "
            "quorum_met = true WHERE status = 'OPEN'"
        ))
        await db.commit()

    print("=" * 70)
    print("  SESSION CLOSED — All agents have committed to 3-day action plans.")
    print("  The board is authorised to execute autonomously.")
    print("=" * 70)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_strategic_session())
