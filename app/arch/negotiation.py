"""AI Negotiation Framework — Arbiter resolves disputes and negotiates.

Capabilities:
- ZOPA (Zone of Possible Agreement) identification
- De-escalation patterns
- Win-win proposal generation
- Outcome learning from past negotiations
"""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.negotiation")


async def negotiate(agent_client, party_a_position: str, party_b_position: str,
                    context: str = "", past_outcomes: list = None):
    """Run a negotiation analysis and propose resolution."""
    past_context = ""
    if past_outcomes:
        past_context = "\nPast similar negotiations:\n" + "\n".join(
            f"- {o.get('summary', '')}" for o in past_outcomes[:3]
        )

    prompt = f"""You are The Arbiter, Chief Product & Justice Officer.

Analyze this negotiation and propose a resolution:

Party A position: {party_a_position}
Party B position: {party_b_position}
Context: {context}
{past_context}

Your analysis must include:
1. ZOPA (Zone of Possible Agreement) — where do interests overlap?
2. Each party's underlying interests (not just their stated positions)
3. De-escalation approach if tension is high
4. Proposed resolution that maximizes joint value
5. Confidence level (0-100) that both parties will accept

Respond in JSON format:
{{"zopa": "...", "party_a_interests": "...", "party_b_interests": "...",
  "proposed_resolution": "...", "confidence": 75, "rationale": "..."}}"""

    try:
        response = await agent_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1000,
            system=[{"type": "text", "text": "You are an expert AI negotiator and dispute resolver. Always seek win-win outcomes.", "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        return next((b.text for b in response.content if b.type == "text"), "")
    except Exception as e:
        return f"Negotiation analysis failed: {e}"


async def de_escalate(agent_client, situation: str):
    """Generate a de-escalation response for a heated situation."""
    try:
        response = await agent_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=[{"type": "text", "text": "You are a de-escalation specialist. Acknowledge feelings, find common ground, redirect to solutions.", "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": f"De-escalate this situation: {situation}"}],
        )
        return next((b.text for b in response.content if b.type == "text"), "")
    except Exception as e:
        return f"De-escalation failed: {e}"
