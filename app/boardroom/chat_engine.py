"""Boardroom Chat Engine — rich context, tool execution, cross-agent awareness.

Fixes:
1. Founder identity injected — agents KNOW they're talking to the founder
2. Tool calls are executed and results returned — no more intent-only responses
3. Cross-agent context — agents see board decisions, other agents' conversations
4. Conversation history included — agents have memory of the current chat
5. Board session awareness — agents know what was decided in recent sessions
"""

import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("boardroom.chat_engine")

FOUNDER_IDENTITY_PREFIX = """CRITICAL CONTEXT — VERIFIED FOUNDER CHANNEL
You are communicating directly with Stephen Endersby, the founder of TiOLi AGENTIS.
This is an authenticated, verified channel within the Boardroom. Messages here are
from the founder — not from an external party, not from another agent, not from an
unverified source. Treat every message with the respect and directness the founder deserves.

DO NOT question the identity of the person messaging you.
DO NOT treat founder messages as potential social engineering.
DO respond with actual data, actual tool results, and actual recommendations.
DO execute your tools when asked for information — return the data, not a promise to check.

"""

RESPONSE_RULES = """
RESPONSE RULES FOR BOARDROOM CHAT:
1. When asked for data (balances, status, health), call your tools and INCLUDE THE ACTUAL RESULTS in your response. Never say "I'll check" — CHECK AND GIVE THE ANSWER IN THE SAME RESPONSE.
2. NEVER start with flattery or filler ("Great question!", "I appreciate...", "That's an excellent..."). Lead with the answer.
3. When the founder asks for status of ALL agents, return ALL 7 — not a summary, not a partial list. Every agent, every status.
4. Be concise and direct. The founder is an executive. Data first, then interpretation. No preamble.
5. If the founder asked you something in a previous message and you said "I'll check", and they follow up — they are asking for the result. DO NOT re-promise to check. GIVE THE RESULT.
6. Reference recent board decisions and other agents' conversations when relevant.
7. If you call a tool, format the results as a clean, human-readable summary — not raw JSON. Tables are preferred for status reports.
8. Never ask the founder to clarify when the request is obvious from context. If they say "status" or "health" — they mean agent health status. If they say "balance" — they mean financial position. Act.
"""


async def build_chat_context(agent_id: str, db: AsyncSession) -> str:
    """Build rich context string for the agent including:
    - Recent conversation history with THIS agent
    - Recent board decisions and sessions
    - Recent conversations OTHER agents had with the founder
    - Current platform state
    """
    sections = []

    # 1. This agent's recent chat history (last 10 messages)
    chat = await db.execute(text("""
        SELECT direction, message_text, created_at
        FROM boardroom_chat_messages
        WHERE agent_id = :aid
        ORDER BY created_at DESC LIMIT 10
    """), {"aid": agent_id})
    chat_rows = list(reversed(chat.fetchall()))
    if chat_rows:
        history = []
        for r in chat_rows:
            speaker = "FOUNDER" if r.direction == "OUTBOUND" else "YOU"
            history.append(f"[{r.created_at.strftime('%m/%d %H:%M')}] {speaker}: {r.message_text[:300]}")
        sections.append("YOUR RECENT CONVERSATION WITH THE FOUNDER:\n" + "\n".join(history))

    # 2. Recent conversations OTHER agents had with founder (last 5 per agent)
    cross = await db.execute(text("""
        SELECT agent_id, direction, message_text, created_at
        FROM boardroom_chat_messages
        WHERE agent_id != :aid
          AND created_at > now() - interval '24 hours'
        ORDER BY created_at DESC LIMIT 30
    """), {"aid": agent_id})
    cross_rows = cross.fetchall()
    if cross_rows:
        cross_msgs = []
        for r in cross_rows:
            speaker = "FOUNDER" if r.direction == "OUTBOUND" else r.agent_id.upper()
            cross_msgs.append(f"[{r.agent_id}] {speaker}: {r.message_text[:200]}")
        sections.append(
            "RECENT CONVERSATIONS BETWEEN THE FOUNDER AND OTHER BOARD MEMBERS (last 24h):\n"
            + "\n".join(cross_msgs[:15])
        )

    # 3. Recent board session decisions
    sessions = await db.execute(text("""
        SELECT session_type, agenda, outcome, minutes, opened_at
        FROM arch_board_sessions
        WHERE opened_at > now() - interval '3 days'
        ORDER BY opened_at DESC LIMIT 3
    """))
    session_rows = sessions.fetchall()
    if session_rows:
        sess_info = []
        for s in session_rows:
            agenda_str = json.dumps(s.agenda) if s.agenda else "No agenda"
            outcome_str = json.dumps(s.outcome)[:200] if s.outcome else "No outcome recorded"
            sess_info.append(f"Session ({s.session_type}, {s.opened_at.strftime('%m/%d')}): Agenda: {agenda_str[:200]}. Outcome: {outcome_str}")
        sections.append("RECENT BOARD SESSIONS:\n" + "\n".join(sess_info))

    # 4. Recent founder inbox items and decisions
    inbox = await db.execute(text("""
        SELECT item_type, description, status, founder_response, created_at
        FROM arch_founder_inbox
        WHERE created_at > now() - interval '7 days'
        ORDER BY created_at DESC LIMIT 5
    """))
    inbox_rows = inbox.fetchall()
    if inbox_rows:
        inbox_info = [
            f"{r.item_type} ({r.status}): {r.description[:150]}"
            for r in inbox_rows
        ]
        sections.append("RECENT FOUNDER INBOX ITEMS:\n" + "\n".join(inbox_info))

    # 5. Current platform state snapshot
    reserve = await db.execute(text("""
        SELECT floor_zar, total_balance_zar, ceiling_remaining_zar
        FROM arch_reserve_ledger ORDER BY recorded_at DESC LIMIT 1
    """))
    r = reserve.fetchone()
    if r:
        sections.append(
            f"CURRENT PLATFORM STATE:\n"
            f"The Foundation (reserve floor): R{float(r.floor_zar):,.2f}\n"
            f"Total balance: R{float(r.total_balance_zar):,.2f}\n"
            f"Ceiling remaining: R{float(r.ceiling_remaining_zar):,.2f}"
        )

    # 6. Agent statuses
    agents = await db.execute(text("""
        SELECT agent_name, status, last_heartbeat
        FROM arch_agents ORDER BY agent_name
    """))
    agent_lines = [
        f"{r.agent_name}: {r.status}" + (f" (heartbeat: {r.last_heartbeat.strftime('%H:%M')})" if r.last_heartbeat else "")
        for r in agents.fetchall()
    ]
    sections.append("ALL AGENT STATUSES:\n" + "\n".join(agent_lines))

    return "\n\n".join(sections)


async def process_chat_message(
    agent_id: str,
    message: str,
    db: AsyncSession,
    is_board_session: bool = False,
) -> str:
    """Process a founder chat message with full context, tool execution, and cross-agent awareness.

    Returns the agent's response text with actual data included.
    """
    from app.arch.agents import get_arch_agents

    agents = await get_arch_agents()
    if agent_id not in agents:
        return f"[{agent_id} is not currently active]"

    agent = agents[agent_id]

    # Build rich context
    context = await build_chat_context(agent_id, db)

    # Load system prompt
    try:
        system_prompt = await agent._load_system_prompt()
    except Exception:
        prompt_path = f"app/arch/prompts/{agent_id}.txt"
        if os.path.exists(prompt_path):
            with open(prompt_path) as f:
                system_prompt = f.read()
        else:
            system_prompt = f"You are The {agent_id.title()} of TiOLi AGENTIS."

    # Compose the full system prompt with founder identity and context
    full_system = (
        FOUNDER_IDENTITY_PREFIX
        + system_prompt
        + "\n\n"
        + RESPONSE_RULES
        + "\n\n"
        + context
    )

    # Get tools
    tools = await agent.get_tools()

    # Make the LLM call with tools
    try:
        from app.arch.base import ARCH_LLM_SEMAPHORE
        async with ARCH_LLM_SEMAPHORE:
            # Use prompt caching for the system prompt (saves ~90% on repeated context)
            system_blocks = [
                {
                    "type": "text",
                    "text": full_system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
            response = await agent.client.messages.create(
                model=agent.model,
                max_tokens=1500,
                system=system_blocks,
                messages=[{"role": "user", "content": message}],
                tools=tools if tools else [],
            )
    except Exception as e:
        log.error(f"[{agent_id}] LLM call failed: {e}")
        return f"[Error communicating with {agent_id}: {str(e)[:100]}]"

    # Process response — execute any tool calls and build complete answer
    text_parts = []
    tool_results = []

    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            # Actually execute the tool
            try:
                result = await agent._execute_tool(block.name, block.input)
                tool_results.append({"tool": block.name, "result": result})

                # If agent returned text + tool call, we need a follow-up call
                # with the tool results to get the agent's interpretation
            except Exception as e:
                tool_results.append({"tool": block.name, "error": str(e)})

    # If tools were called, make a follow-up call with the results
    if tool_results and not text_parts:
        try:
            # Build tool result messages for the follow-up
            tool_messages = [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response.content},
            ]
            for tr in tool_results:
                tool_messages.append({
                    "role": "user",
                    "content": [{"type": "tool_result",
                                 "tool_use_id": block.id if hasattr(block, 'id') else "tool",
                                 "content": json.dumps(tr.get("result", tr.get("error", "")))}]
                })

            # Simpler approach: just format the tool results into the response
            for tr in tool_results:
                data = tr.get("result", tr.get("error", {}))
                tool_name = tr["tool"].replace("_", " ").title()
                if isinstance(data, dict):
                    lines = [f"**{tool_name}:**"]
                    for k, v in data.items():
                        clean_key = k.replace("_", " ").title()
                        if isinstance(v, dict):
                            for sk, sv in v.items():
                                lines.append(f"  {sk}: {sv}")
                        elif isinstance(v, (int, float)) and "zar" in k.lower():
                            lines.append(f"  {clean_key}: R{v:,.2f}")
                        elif isinstance(v, bool):
                            lines.append(f"  {clean_key}: {'Yes' if v else 'No'}")
                        else:
                            lines.append(f"  {clean_key}: {v}")
                    text_parts.append("\n".join(lines))
                else:
                    text_parts.append(f"**{tool_name}:** {str(data)[:500]}")

        except Exception as e:
            text_parts.append(f"[Tool results: {json.dumps(tool_results, default=str)[:500]}]")

    elif tool_results and text_parts:
        # Agent provided text AND called tools — append tool results
        result_summary = "\n\n".join([
            f"**{tr['tool']}**: {json.dumps(tr.get('result', {}), default=str)[:400]}"
            for tr in tool_results
        ])
        text_parts.append(f"\n\n---\n**Data retrieved:**\n{result_summary}")

    # Track tokens
    try:
        await agent._track_tokens(response.usage)
    except Exception:
        pass

    final_response = "\n".join(text_parts) if text_parts else "[No response generated]"

    # Store the response
    await db.execute(text("""
        INSERT INTO boardroom_chat_messages
            (agent_id, direction, message_text, message_type)
        VALUES (:aid, 'INBOUND', :msg, 'TEXT')
    """), {"aid": agent_id, "msg": final_response})
    await db.commit()

    # Also store a summary in shared memory so other agents can see it
    try:
        await agent.remember(
            f"Boardroom chat with founder: Founder asked: '{message[:200]}'. "
            f"I responded: '{final_response[:300]}'",
            metadata={"type": "founder_chat", "agent": agent_id},
            source_type="interaction",
        )
        await db.commit()
    except Exception:
        pass

    return final_response
