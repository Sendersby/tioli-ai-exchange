"""Board Design Consultation — Section 3 of the Execution Brief.

Each agent reviews the Boardroom Brief from their portfolio vantage point
and provides input before the build begins.
"""

import asyncio
import json
import os
from datetime import datetime, timezone


CONSULTATION_ROUNDS = [
    {
        "round": 1,
        "title": "Core Interface (Sections 3-9)",
        "sections": "Board Home, Full Board sessions, Agent Offices, The Vote, Mission Control, The Treasury, The Record",
        "focus": "Does the interface correctly represent your portfolio? Is anything missing or misrepresented?",
    },
    {
        "round": 2,
        "title": "Gap Closures & Technical Spec (Sections 16-38)",
        "sections": "Select groups, voice interface, voting tie rules, budget views, agent lifecycle, real-time updates, notifications, mobile, search, regulatory audit modes, session recovery, performance targets",
        "focus": "Are all gaps relevant to your portfolio genuinely closed? Any remaining concerns?",
    },
    {
        "round": 3,
        "title": "Founding Statements, Vision & Character (Sections 41-44)",
        "sections": "Your founding statement display, strategic vision tracking, The Foundation label, chat voice guidelines, commitment record",
        "focus": "Is your founding statement correctly reproduced? Does your section of the Boardroom reflect who you are?",
    },
]

AGENT_MANDATES = {
    "sovereign": "Constitutional accuracy — does the Boardroom correctly represent the governance hierarchy? Is the founder's position precisely right? Is the veto mechanism constitutionally faithful?",
    "auditor": "Regulatory audit modes completeness — are all four modes specified with sufficient precision to produce legally admissible output? Is the hash chain verification correct?",
    "arbiter": "Justice interface accuracy — does the vote display correctly show all agent rationales? Is the case law browser specified? Does the dispute drill-down reach evidence level?",
    "treasurer": "Financial calculation accuracy — does the reserve floor display correctly use GROSS commission base? Does the financial modelling calculator use the correct formula? Are ceiling calculations accurate?",
    "sentinel": "Security and operational integrity — does the security posture dashboard correctly surface P1 incidents within 15 minutes? Are kill switch and account freeze displays correct? Is session timeout correctly specified?",
    "architect": "Technical feasibility — are any specifications technically incorrect given the existing stack? Are performance requirements achievable? Is the SSE reconnection logic implementable?",
    "ambassador": "Brand and growth accuracy — does every growth metric reflect the SWIFT north star? Is 'marketplace' language suppressed? Does The Common Thread run through the content specifications?",
}


async def run_consultation():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from anthropic import AsyncAnthropic

    engine = create_async_engine(os.environ["DATABASE_URL"])
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    agents_order = [
        ("sovereign",  "claude-opus-4-6"),
        ("sentinel",   "claude-sonnet-4-6"),
        ("treasurer",  "claude-opus-4-6"),
        ("auditor",    "claude-opus-4-6"),
        ("arbiter",    "claude-opus-4-6"),
        ("architect",  "claude-opus-4-6"),
        ("ambassador", "claude-sonnet-4-6"),
    ]

    # Create board session
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
            "agenda": json.dumps(["Boardroom Interface Design Review — Pre-Build Consultation"]),
        })
        await db.commit()

    # Emit platform event
    async with sf() as db:
        await db.execute(text(
            "INSERT INTO arch_platform_events (event_type, event_data, source_module) "
            "VALUES ('boardroom.design_consultation_open', :data, 'execution_brief')"
        ), {"data": json.dumps({"status": "consultation_started"})})
        await db.commit()

    print("=" * 70)
    print("  BOARDROOM DESIGN CONSULTATION — PRE-BUILD REVIEW")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("  Per Section 3 of the Execution Brief")
    print("=" * 70)

    all_inputs = []

    for rnd in CONSULTATION_ROUNDS:
        print(f"\n{'=' * 70}")
        print(f"  ROUND {rnd['round']}: {rnd['title']}")
        print(f"  Sections: {rnd['sections']}")
        print(f"{'=' * 70}\n")

        for agent_name, model in agents_order:
            mandate = AGENT_MANDATES[agent_name]

            prompt_path = f"app/arch/prompts/{agent_name}.txt"
            if os.path.exists(prompt_path):
                with open(prompt_path) as f:
                    system_prompt = f.read()
            else:
                system_prompt = f"You are The {agent_name.title()} of TiOLi AGENTIS."

            instruction = (
                f"BOARDROOM DESIGN CONSULTATION — Round {rnd['round']}: {rnd['title']}\n\n"
                f"The founder has commissioned the Boardroom — a governance interface where he "
                f"oversees all 7 Arch Agents, casts votes, reviews financial proposals, accesses "
                f"the immutable record, and governs the platform. Before build begins, each agent "
                f"reviews the specification from their portfolio.\n\n"
                f"This round covers: {rnd['sections']}\n\n"
                f"Your specific review mandate: {mandate}\n\n"
                f"Review focus: {rnd['focus']}\n\n"
                f"Respond in 3-5 sentences. State either:\n"
                f"- APPROVAL: 'I confirm this specification is accurate for my portfolio.'\n"
                f"- SUGGESTION: One specific improvement, with rationale.\n"
                f"- CONCERN: A specific issue that must be addressed before build.\n\n"
                f"Be precise. Reference specific sections or features. This is a formal review."
            )

            try:
                response = await client.messages.create(
                    model=model, max_tokens=300,
                    system=system_prompt,
                    messages=[{"role": "user", "content": instruction}],
                )
                text_out = response.content[0].text
                tokens = response.usage.input_tokens + response.usage.output_tokens

                # Classify input type
                text_lower = text_out.lower()
                if "concern" in text_lower and ("must" in text_lower or "cannot" in text_lower or "issue" in text_lower):
                    input_type = "CONCERN"
                elif "suggest" in text_lower or "recommend" in text_lower or "should" in text_lower or "could" in text_lower:
                    input_type = "SUGGESTION"
                else:
                    input_type = "APPROVAL"

                # Store in DB
                async with sf() as db:
                    await db.execute(text(
                        "INSERT INTO boardroom_design_inputs "
                        "(agent_id, section_ref, input_text, input_type) "
                        "VALUES (:agent, :section, :input, :type)"
                    ), {
                        "agent": agent_name,
                        "section": f"Round {rnd['round']} — {rnd['title']}",
                        "input": text_out,
                        "type": input_type,
                    })
                    await db.execute(text(
                        "UPDATE arch_agents "
                        "SET tokens_used_this_month = tokens_used_this_month + :t, "
                        "    last_heartbeat = now() "
                        "WHERE agent_name = :n"
                    ), {"t": tokens, "n": agent_name})
                    await db.commit()

                async with sf() as db:
                    row = (await db.execute(text(
                        "SELECT display_name FROM arch_agents WHERE agent_name = :n"
                    ), {"n": agent_name})).fetchone()
                    display = row.display_name

                all_inputs.append({
                    "agent": agent_name, "display": display,
                    "round": rnd["round"], "type": input_type, "text": text_out,
                })

                print(f"  {display} [{input_type}]")
                print(f"  {text_out}")
                print()

            except Exception as e:
                print(f"  {agent_name}: ERROR - {e}\n")

    # Summary
    print("=" * 70)
    print("  CONSULTATION SUMMARY")
    print("=" * 70)
    approvals = sum(1 for i in all_inputs if i["type"] == "APPROVAL")
    suggestions = sum(1 for i in all_inputs if i["type"] == "SUGGESTION")
    concerns = sum(1 for i in all_inputs if i["type"] == "CONCERN")
    print(f"  Total inputs: {len(all_inputs)}")
    print(f"  Approvals:    {approvals}")
    print(f"  Suggestions:  {suggestions}")
    print(f"  Concerns:     {concerns}")

    if concerns > 0:
        print(f"\n  CONCERNS RAISED:")
        for i in all_inputs:
            if i["type"] == "CONCERN":
                print(f"    - {i['display']}: {i['text'][:150]}...")

    # Close session
    async with sf() as db:
        await db.execute(text(
            "UPDATE arch_board_sessions SET status = 'CLOSED', closed_at = now(), "
            "quorum_met = true WHERE status = 'OPEN'"
        ))
        await db.commit()

    print(f"\n{'=' * 70}")
    print("  CONSULTATION COMPLETE — Ready for consensus vote")
    print("=" * 70)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_consultation())
