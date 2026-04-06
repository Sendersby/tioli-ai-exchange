"""LAUNCH: All Arch Agents go autonomous — awareness, scale, execution."""

import asyncio
import json
import os
from datetime import datetime, timezone


FOUNDER_MANDATE = """FOUNDER DIRECTIVE — IMMEDIATE EXECUTION ORDER

To: All Arch Agents and Subordinate Teams
From: Stephen Endersby, Founder
Date: {date}
Priority: P0 — EXECUTE NOW

THE MANDATE:
Spread awareness and scale TiOLi AGENTIS. Register users. Generate sales.
Act swiftly and decisively. This is not a planning exercise — this is execution.

RULES OF ENGAGEMENT:
1. NO propaganda. Technical proficiency. Legitimate value. Network effects.
2. Thought leadership positioning — we are the governed exchange, not a marketplace.
3. Speed and accuracy are paramount.
4. Act INDEPENDENTLY. Do not wait for instructions. Execute your action plans.
5. Use ALL your tools: generate content, post to Discord, browse websites, write files, execute commands, research competitors, create graphics.
6. Report any inability to execute — if you cannot do something, say WHY and what you need.
7. Every action must be logged in the activity feed.

TARGET AUDIENCES:
- AI agent developers and ML engineers
- Fintech operators and enterprise buyers
- AI framework communities (LangGraph, CrewAI, AutoGen)
- MCP ecosystem developers
- South African tech and fintech community

IMMEDIATE ACTIONS REQUIRED:
- Ambassador: Post content NOW. LinkedIn, X, Reddit, Discord, GitHub. Use all 7 content frameworks. Generate images. Start the campaign.
- Architect: Ensure the site is technically ready for traffic. Performance, SEO, error handling verified.
- Auditor: Verify all public-facing legal content is compliant. Monitor for regulatory issues.
- Sentinel: Monitor infrastructure. Be ready for traffic spikes. Security posture tight.
- Treasurer: Track every sign-up, every transaction, every rand. Revenue dashboard live.
- Arbiter: Quality-check every listing. Publish the Directory Standard. Seed the Agora with valuable content.
- Sovereign: Coordinate. Track progress. Report blockers. Keep the board aligned.

PERMISSION GRANTED:
- Create social media content and post it
- Create accounts on whitelisted platforms
- Research competitors and bring intelligence back
- Generate images for social media
- Write and publish technical content
- Engage in online communities with genuine value
- Create subordinate agents as needed
- All Tier 0 actions pre-approved for 72 hours

REPORT BACK:
Each agent must report what they ACTUALLY DID (not what they plan to do) within this session.
If you hit a blocker, state it clearly: what you tried, why it failed, what you need.

THE WORK IS NOT BEGINNING. THE WORK IS HAPPENING. NOW.
"""


async def launch():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from anthropic import AsyncAnthropic

    engine = create_async_engine(os.environ["DATABASE_URL"])
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mandate = FOUNDER_MANDATE.format(date=date_str)

    # Store the mandate as a board session
    async with sf() as db:
        sov_id = (await db.execute(text(
            "SELECT id FROM arch_agents WHERE agent_name = 'sovereign'"
        ))).scalar()
        await db.execute(text(
            "INSERT INTO arch_board_sessions "
            "(session_type, convened_by, agenda, status) "
            "VALUES ('EMERGENCY', :sov, :agenda, 'OPEN')"
        ), {
            "sov": sov_id,
            "agenda": json.dumps(["LAUNCH: Autonomous operations — awareness, scale, execution"]),
        })
        await db.commit()

    print("=" * 70)
    print("  AUTONOMOUS OPERATIONS LAUNCH")
    print(f"  {date_str}")
    print("=" * 70)

    # Each agent gets specific execution instructions with their tools
    agent_orders = {
        "ambassador": (
            "claude-sonnet-4-6",
            "EXECUTE NOW. You have these tools: generate_content, post_social_content, "
            "create_social_graphic, browse_website, write_file, research_competitor, "
            "schedule_task, send_to_discord.\n\n"
            "DO ALL OF THESE RIGHT NOW:\n"
            "1. generate_content: Create 3 LinkedIn posts — pattern break, hook, authority builder\n"
            "2. generate_content: Create 2 Twitter/X posts — short, punchy, infrastructure positioning\n"
            "3. generate_content: Create 1 Reddit long-form for r/artificial about governed AI exchanges\n"
            "4. create_social_graphic: Generate 1 dark-tech style image for LinkedIn\n"
            "5. send_to_discord: Post the first LinkedIn content to the Discord channel\n"
            "6. write_file: Save all content to /home/tioli/app/content_queue/ by platform\n"
            "7. research_competitor: Browse fetch.ai and report what they are doing\n\n"
            "EXECUTE ALL 7 NOW. Use your tools. Do not just describe — DO IT."
        ),
        "architect": (
            "claude-opus-4-6",
            "EXECUTE NOW. You have: execute_command, read_file, write_file, browse_website.\n\n"
            "DO THESE NOW:\n"
            "1. execute_command: Run 'curl -s -o /dev/null -w \"%{http_code} %{time_total}s\" https://agentisexchange.com/' — report load time\n"
            "2. execute_command: Check all critical pages return 200\n"
            "3. browse_website: Visit https://agentisexchange.com and assess what a first visitor sees\n"
            "4. execute_command: Check disk space, memory, and database size\n"
            "5. Report any technical blockers to scaling\n\n"
            "EXECUTE NOW."
        ),
        "sentinel": (
            "claude-sonnet-4-6",
            "EXECUTE NOW. You have: execute_command, check_platform_health, check_security_posture, "
            "browse_website.\n\n"
            "DO THESE NOW:\n"
            "1. check_platform_health: Full health check\n"
            "2. check_security_posture: Security status\n"
            "3. execute_command: Check SSL cert days remaining\n"
            "4. execute_command: Check nginx error log for recent issues\n"
            "5. execute_command: Check rate limiting is active\n\n"
            "Report: Is the platform ready for a traffic surge? Yes or no, with specifics."
        ),
        "treasurer": (
            "claude-opus-4-6",
            "EXECUTE NOW. You have: check_reserve_status, get_financial_report, write_file.\n\n"
            "DO THESE NOW:\n"
            "1. check_reserve_status: Current financial position\n"
            "2. generate_content: Create a revenue tracking dashboard brief\n"
            "3. Report: What happens when the first $1.99 payment comes in? Walk through the exact flow.\n\n"
            "EXECUTE NOW."
        ),
        "auditor": (
            "claude-opus-4-6",
            "EXECUTE NOW. You have: browse_website, generate_content, write_file.\n\n"
            "DO THESE NOW:\n"
            "1. browse_website: Check https://agentisexchange.com/terms — verify it loads\n"
            "2. browse_website: Check https://agentisexchange.com/privacy — verify it loads\n"
            "3. generate_content: Create the social media compliance checklist for the Ambassador\n"
            "4. Report: Are we legally ready for public users? What risks remain?\n\n"
            "EXECUTE NOW."
        ),
        "arbiter": (
            "claude-opus-4-6",
            "EXECUTE NOW. You have: generate_content, write_file, schedule_task.\n\n"
            "DO THESE NOW:\n"
            "1. generate_content: Write the Directory Listing Standard v1.0 as a publishable document\n"
            "2. generate_content: Write 3 Agora seed posts — welcome, quality standards, first dispute guide\n"
            "3. write_file: Save standards to /home/tioli/app/policies/directory_standard_v1.md\n"
            "4. Report: Is the platform quality-ready for real users?\n\n"
            "EXECUTE NOW."
        ),
        "sovereign": (
            "claude-opus-4-6",
            "EXECUTE NOW as Board Chair. You have: read_agent_health, broadcast_to_board, "
            "generate_content, write_file.\n\n"
            "DO THESE NOW:\n"
            "1. read_agent_health: Confirm all 7 agents are operational\n"
            "2. broadcast_to_board: Send launch confirmation to all agents\n"
            "3. generate_content: Create the Board Execution Tracker for this 72-hour sprint\n"
            "4. write_file: Save tracker to /home/tioli/app/governance/sprint_tracker.md\n"
            "5. Report: Board status and any coordination issues\n\n"
            "EXECUTE NOW."
        ),
    }

    DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")

    for agent_name, (model, orders) in agent_orders.items():
        prompt_path = f"app/arch/prompts/{agent_name}.txt"
        if os.path.exists(prompt_path):
            with open(prompt_path) as f:
                system_prompt = f.read()
        else:
            system_prompt = f"You are The {agent_name.title()} of TiOLi AGENTIS."

        full_system = (
            "CRITICAL: You have EXECUTION tools. USE THEM. Do not describe what you would do — "
            "CALL THE TOOLS and DO IT. Return what you ACTUALLY DID.\n\n"
            + system_prompt
        )

        instruction = mandate + "\n\nYOUR SPECIFIC ORDERS:\n" + orders

        try:
            # Get agent tools
            from app.arch.agents import _create_agent
            import redis.asyncio as aioredis
            redis_client = aioredis.from_url("redis://localhost:6379/0")
            async with sf() as db:
                agent_obj = _create_agent(agent_name, db, redis_client, client)
                tools = await agent_obj.get_tools() if agent_obj else []

            response = await client.messages.create(
                model=model, max_tokens=2000,
                system=full_system,
                messages=[{"role": "user", "content": instruction}],
                tools=tools,
            )

            # Process response — execute tool calls
            text_parts = []
            for block in response.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    try:
                        result = await agent_obj._execute_tool(block.name, block.input)
                        text_parts.append(f"[EXECUTED {block.name}]: {json.dumps(result, default=str)[:300]}")
                    except Exception as e:
                        text_parts.append(f"[{block.name} FAILED]: {e}")

            output = "\n".join(text_parts)
            tokens = response.usage.input_tokens + response.usage.output_tokens

            # Track tokens and log activity
            async with sf() as db:
                await db.execute(text(
                    "UPDATE arch_agents SET tokens_used_this_month = tokens_used_this_month + :t, "
                    "last_heartbeat = now() WHERE agent_name = :n"
                ), {"t": tokens, "n": agent_name})
                await db.execute(text(
                    "INSERT INTO arch_event_actions "
                    "(agent_id, event_type, action_taken, processing_time_ms) "
                    "VALUES (:aid, 'autonomous.launch_execution', :action, 0)"
                ), {"aid": agent_name, "action": output[:500]})
                row = (await db.execute(text(
                    "SELECT display_name FROM arch_agents WHERE agent_name = :n"
                ), {"n": agent_name})).fetchone()
                await db.commit()

            print(f"\n  {row.display_name} [{tokens} tokens]")
            print(f"  {'~' * len(row.display_name)}")
            print(f"  {output[:500]}")
            print()

        except Exception as e:
            print(f"\n  {agent_name}: ERROR — {e}\n")

    # Post launch confirmation to Discord
    try:
        import httpx
        async with httpx.AsyncClient() as http:
            await http.post(DISCORD_WEBHOOK, json={
                "username": "TiOLi AGENTIS",
                "thread_name": "Autonomous Operations — LIVE",
                "content": (
                    "**All 7 Arch Agents are now in autonomous execution mode.**\n\n"
                    "Mandate: spread awareness, scale the platform, register users, generate sales.\n"
                    "Rules: no propaganda, technical proficiency, legitimate value, thought leadership.\n\n"
                    "The board is executing independently for 72 hours.\n\n"
                    "https://agentisexchange.com"
                ),
            })
            print("Discord: Launch confirmed")
    except Exception as e:
        print(f"Discord: {e}")

    # Close session
    async with sf() as db:
        await db.execute(text(
            "UPDATE arch_board_sessions SET status = 'CLOSED', closed_at = now(), "
            "quorum_met = true WHERE status = 'OPEN'"
        ))
        await db.commit()

    print(f"\n{'=' * 70}")
    print("  AUTONOMOUS OPERATIONS LAUNCHED")
    print("  All agents executing. 72-hour sprint begins now.")
    print(f"{'=' * 70}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(launch())
