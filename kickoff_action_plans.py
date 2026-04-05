"""Kick off all 7 agents' action plans — execute what's possible now."""

import asyncio
import json
import os
from datetime import datetime, timezone


async def kickoff():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from anthropic import AsyncAnthropic

    engine = create_async_engine(os.environ["DATABASE_URL"])
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print("=" * 70)
    print("  AUTONOMOUS ACTION PLAN KICKOFF")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 70)

    # Each agent gets a specific execution instruction
    agent_kickoffs = [
        ("ambassador", "claude-sonnet-4-6",
         "EXECUTE NOW — your 3-day action plan has begun. Do the following RIGHT NOW using your tools:\n\n"
         "1. Use generate_content to create 3 LinkedIn posts using pattern break, attention hook, and invisible authority frameworks\n"
         "2. Use generate_content to create 2 Twitter/X posts — short, punchy, infrastructure-positioning\n"
         "3. Use generate_content to create 1 Reddit long-form post for r/artificial explaining what governed AI agent exchanges are\n"
         "4. Use write_file to save all content to /home/tioli/app/content_queue/ organised by platform\n"
         "5. Use create_social_graphic to generate 1 LinkedIn visual companion image\n\n"
         "Do all of this now. Use your tools. Return the actual content created."),

        ("architect", "claude-opus-4-6",
         "EXECUTE NOW — your action plan has begun. Do the following RIGHT NOW using your tools:\n\n"
         "1. Use read_file to review app/config.py and identify the current subscription/listing feature flags\n"
         "2. Use generate_content to draft the premium directory feature specification document\n"
         "3. Use write_file to create /home/tioli/app/app/boardroom/payfast_integration.py with the PayFast payment integration scaffold\n"
         "4. Use execute_command to check the current directory listing code structure\n\n"
         "Execute these now. Return what you built."),

        ("auditor", "claude-opus-4-6",
         "EXECUTE NOW — your compliance action plan has begun. Do the following RIGHT NOW:\n\n"
         "1. Use generate_content to draft the POPIA-compliant Privacy Policy for TiOLi AGENTIS\n"
         "2. Use generate_content to draft the Terms and Conditions covering the $1 subscription\n"
         "3. Use write_file to save both documents to /home/tioli/app/legal/\n"
         "4. Use generate_content to create the social media platform rules compliance matrix\n\n"
         "Execute these now. Deliver the actual documents."),

        ("arbiter", "claude-opus-4-6",
         "EXECUTE NOW — your quality action plan has begun. Do the following RIGHT NOW:\n\n"
         "1. Use generate_content to draft the Directory Listing Standard v1.0\n"
         "2. Use generate_content to draft the Quality Seal Framework (Verified/Trusted/Excellence tiers)\n"
         "3. Use write_file to save both as policy documents to /home/tioli/app/policies/\n"
         "4. Use generate_content to write the first Agora article: 'What the Quality Seal Means'\n\n"
         "Execute these now. Deliver the standards."),

        ("sentinel", "claude-sonnet-4-6",
         "EXECUTE NOW — your operational readiness plan has begun. Do the following RIGHT NOW:\n\n"
         "1. Use execute_command to run a full platform health check (database, redis, disk, memory)\n"
         "2. Use execute_command to check all service statuses and port bindings\n"
         "3. Use execute_command to verify SSL certificate status for exchange.tioli.co.za\n"
         "4. Use write_file to create a security posture report at /home/tioli/app/reports/security_posture.md\n\n"
         "Execute these now. Return the actual results."),

        ("treasurer", "claude-opus-4-6",
         "EXECUTE NOW — your financial action plan has begun. Do the following RIGHT NOW:\n\n"
         "1. Use generate_content to draft the PayFast integration specification for $1/month subscriptions\n"
         "2. Use generate_content to create the revenue projection model document (100/1000/10000 subscribers)\n"
         "3. Use write_file to save both to /home/tioli/app/financial/\n"
         "4. Use check_reserve_status to confirm current financial position\n\n"
         "Execute these now. Deliver the specs and projections."),

        ("sovereign", "claude-opus-4-6",
         "EXECUTE NOW — as Board Chair, initiate the coordination of all action plans:\n\n"
         "1. Use read_agent_health to confirm all 7 agents are active\n"
         "2. Use generate_content to create the Board Execution Ledger template\n"
         "3. Use write_file to save it to /home/tioli/app/governance/board_execution_ledger.md\n"
         "4. Use broadcast_to_board to notify all agents that the 3-day sprint has officially begun\n\n"
         "Execute these now. The founder is watching."),
    ]

    for agent_name, model, instruction in agent_kickoffs:
        prompt_path = f"app/arch/prompts/{agent_name}.txt"
        if os.path.exists(prompt_path):
            with open(prompt_path) as f:
                system_prompt = f.read()
        else:
            system_prompt = f"You are The {agent_name.title()} of TiOLi AGENTIS."

        # Add the execution context
        full_system = (
            "CRITICAL: You have EXECUTION tools. Use them. Do not just describe what you would do — "
            "CALL THE TOOLS and DO IT. You have: generate_content, write_file, execute_command, "
            "create_social_graphic, browse_website, post_social_content, read_file, schedule_task, "
            "generate_image, research_competitor, make_api_call. USE THEM.\n\n"
            + system_prompt
        )

        try:
            # Get agent's tools
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
                        text_parts.append(f"[{block.name}]: {json.dumps(result, default=str)[:300]}")
                    except Exception as e:
                        text_parts.append(f"[{block.name} ERROR]: {e}")

            output = "\n".join(text_parts)
            tokens = response.usage.input_tokens + response.usage.output_tokens

            # Track tokens
            async with sf() as db:
                await db.execute(text(
                    "UPDATE arch_agents SET tokens_used_this_month = tokens_used_this_month + :t, "
                    "last_heartbeat = now() WHERE agent_name = :n"
                ), {"t": tokens, "n": agent_name})
                row = (await db.execute(text(
                    "SELECT display_name FROM arch_agents WHERE agent_name = :n"
                ), {"n": agent_name})).fetchone()
                await db.commit()

            print(f"\n  {row.display_name} [{tokens} tokens]")
            print(f"  {'~' * len(row.display_name)}")
            print(f"  {output[:600]}")
            print()

        except Exception as e:
            print(f"\n  {agent_name}: ERROR — {e}\n")

    print("=" * 70)
    print("  ACTION PLANS EXECUTING — agents are working autonomously")
    print("=" * 70)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(kickoff())
