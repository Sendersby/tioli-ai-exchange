"""Metacognition module — agents reflect on their actions and improve.

After every major action, agents:
1. Evaluate: did the action achieve the intended outcome?
2. Extract: what lesson can be learned?
3. Store: save the reflection in memory for future retrieval
4. Apply: before similar future decisions, retrieve relevant reflections
"""
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.metacognition")


async def reflect_on_action(agent, action_description: str, outcome: str, success: bool):
    """Generate a reflection on a completed action and store it."""
    try:
        reflection_prompt = (
            f"You just completed this action: {action_description[:300]}\n"
            f"Outcome: {outcome[:300]}\n"
            f"Success: {success}\n\n"
            f"In 2-3 sentences: What worked? What would you do differently? "
            f"What principle can you extract for future similar decisions?"
        )

        response = await agent.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=[{"type": "text", "text": "You are reflecting on your own performance. Be concise and specific.", "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": reflection_prompt}],
        )

        reflection_text = next((b.text for b in response.content if b.type == "text"), "")

        if reflection_text:
            await agent.remember(
                f"REFLECTION: {reflection_text}",
                metadata={
                    "type": "reflection",
                    "action": action_description[:200],
                    "success": success,
                    "reflected_at": datetime.now(timezone.utc).isoformat(),
                },
                source_type="metacognition",
                importance=0.8 if not success else 0.5,
            )
            log.debug(f"[{agent.agent_id}] Reflection stored: {reflection_text[:100]}")
            return reflection_text

    except Exception as e:
        log.debug(f"[{agent.agent_id}] Reflection failed: {e}")

    return None


async def recall_relevant_reflections(agent, upcoming_action: str, limit: int = 3):
    """Before a decision, retrieve relevant past reflections."""
    try:
        memories = await agent.recall(f"REFLECTION on: {upcoming_action}")
        reflections = [m for m in memories if m.get("source_type") == "metacognition"]
        return reflections[:limit]
    except Exception:
        return []
