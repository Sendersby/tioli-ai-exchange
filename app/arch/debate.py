"""Multi-agent debate protocol — structured board deliberation.

Based on RUMAD (Reinforcement-Unifying Multi-Agent Debate):
1. Sovereign presents agenda item
2. Each agent provides position (Round 1)
3. Agents critique each others positions (Round 2)
4. Weighted vote based on domain relevance
5. Sovereign announces decision
6. Full transcript stored in The Record
"""
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.debate")

# Domain relevance weights for voting
DOMAIN_WEIGHTS = {
    "governance": {"sovereign": 3, "auditor": 2, "arbiter": 1, "sentinel": 1, "treasurer": 1, "architect": 1, "ambassador": 1},
    "security": {"sentinel": 3, "architect": 2, "auditor": 1, "sovereign": 1, "treasurer": 1, "arbiter": 1, "ambassador": 1},
    "finance": {"treasurer": 3, "auditor": 2, "sovereign": 1, "sentinel": 1, "architect": 1, "arbiter": 1, "ambassador": 1},
    "growth": {"ambassador": 3, "arbiter": 2, "sovereign": 1, "treasurer": 1, "architect": 1, "sentinel": 1, "auditor": 1},
    "technical": {"architect": 3, "sentinel": 2, "sovereign": 1, "treasurer": 1, "auditor": 1, "arbiter": 1, "ambassador": 1},
    "quality": {"arbiter": 3, "ambassador": 2, "auditor": 1, "sovereign": 1, "treasurer": 1, "architect": 1, "sentinel": 1},
    "compliance": {"auditor": 3, "sovereign": 2, "sentinel": 1, "treasurer": 1, "architect": 1, "arbiter": 1, "ambassador": 1},
}


async def run_debate(agents: dict, topic: str, domain: str, context: str = ""):
    """Run a structured debate on a topic. Returns transcript + decision."""
    weights = DOMAIN_WEIGHTS.get(domain, DOMAIN_WEIGHTS["governance"])
    transcript = []
    positions = {}

    # Round 1: Each agent states their position
    for name, agent in agents.items():
        try:
            prompt = (
                f"BOARD DEBATE — Round 1: State your position.\n\n"
                f"Topic: {topic}\nDomain: {domain}\nContext: {context}\n\n"
                f"State your position in 2-3 sentences. Be specific and actionable. "
                f"Do NOT share your confidence level."
            )
            response = await agent.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                system=[{"type": "text", "text": f"You are {name.title()}, an AI board member. Give your honest professional opinion.", "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": prompt}],
            )
            position = next((b.text for b in response.content if b.type == "text"), "No position stated.")
            positions[name] = position
            transcript.append({"round": 1, "agent": name, "text": position})
        except Exception as e:
            positions[name] = f"[Could not participate: {e}]"
            transcript.append({"round": 1, "agent": name, "text": f"[Error: {e}]"})

    # Round 2: Sovereign synthesises and proposes decision
    all_positions = "\n".join(f"- {name}: {pos}" for name, pos in positions.items())
    try:
        synthesis_prompt = (
            f"BOARD DEBATE — Round 2: Synthesise and decide.\n\n"
            f"Topic: {topic}\nAll positions:\n{all_positions}\n\n"
            f"Synthesise the board's views. Identify consensus and disagreements. "
            f"Announce a clear decision. Explain why."
        )
        response = await agents["sovereign"].client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=[{"type": "text", "text": "You are The Sovereign, chair of the AGENTIS board. Announce decisions clearly.", "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": synthesis_prompt}],
        )
        decision = next((b.text for b in response.content if b.type == "text"), "No decision reached.")
        transcript.append({"round": 2, "agent": "sovereign", "text": decision, "type": "decision"})
    except Exception as e:
        decision = f"Decision failed: {e}"

    # Calculate weighted vote
    vote_scores = {}
    for name, pos in positions.items():
        vote_scores[name] = {"position": pos[:100], "weight": weights.get(name, 1)}

    return {
        "topic": topic,
        "domain": domain,
        "transcript": transcript,
        "decision": decision,
        "vote_weights": vote_scores,
        "debated_at": datetime.now(timezone.utc).isoformat(),
    }
