"""Adaptive planning — plans that self-modify based on execution results."""
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.adaptive_plan")


async def execute_adaptive_plan(agent_client, goal, agent_name="sovereign", max_iterations=5):
    """Create and execute a plan that adapts based on results.

    After each step:
    1. Evaluate if the step succeeded
    2. If failed, ask Claude to revise remaining steps
    3. If new information discovered, update the plan
    """
    # Create initial plan
    resp = await agent_client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=400,
        system=[{"type": "text", "text": "You are " + agent_name + ". Create a 3-5 step plan. Return as JSON array of objects with step, action, success_criteria fields."}],
        messages=[{"role": "user", "content": f"Goal: {goal}"}])

    plan_text = next((b.text for b in resp.content if b.type == "text"), "[]")
    import json
    try:
        start = plan_text.find("[")
        end = plan_text.rfind("]") + 1
        steps = json.loads(plan_text[start:end]) if start >= 0 else [{"step": 1, "action": goal, "success_criteria": "completed"}]
    except Exception as e:
        steps = [{"step": 1, "action": goal, "success_criteria": "completed"}]

    results = []
    adaptations = 0

    for i, step in enumerate(steps):
        if i >= max_iterations:
            break

        # Execute step
        try:
            exec_resp = await agent_client.messages.create(
                model="claude-haiku-4-5-20251001", max_tokens=200,
                system=[{"type": "text", "text": f"You are {agent_name}. Execute this step and report the result."}],
                messages=[{"role": "user", "content": f"Execute: {step['action']}\nSuccess criteria: {step.get('success_criteria', 'done')}\nPrevious results: {json.dumps(results[-2:]) if results else 'none'}"}])
            result = next((b.text for b in exec_resp.content if b.type == "text"), "")
            success = "fail" not in result.lower() and "error" not in result.lower()
        except Exception as e:
            result = str(e)
            success = False

        results.append({"step": i + 1, "action": step["action"], "result": result[:300], "success": success})

        # Adaptive: if failed, revise remaining steps
        if not success and i < len(steps) - 1:
            try:
                adapt_resp = await agent_client.messages.create(
                    model="claude-haiku-4-5-20251001", max_tokens=300,
                    system=[{"type": "text", "text": "You are adapting a plan. A step failed. Suggest revised next steps as JSON array."}],
                    messages=[{"role": "user", "content": f"Failed step: {step['action']}\nError: {result[:200]}\nRemaining steps: {json.dumps(steps[i+1:])}\nRevise the remaining steps to work around the failure."}])
                adapt_text = next((b.text for b in adapt_resp.content if b.type == "text"), "")
                try:
                    s2 = adapt_text.find("[")
                    e2 = adapt_text.rfind("]") + 1
                    if s2 >= 0:
                        new_steps = json.loads(adapt_text[s2:e2])
                        steps = steps[:i+1] + new_steps
                        adaptations += 1
                        log.info(f"[adaptive] Plan adapted after step {i+1} failure — {len(new_steps)} new steps")
                except Exception as e:
                    import logging; logging.getLogger("adaptive_plan").warning(f"Suppressed: {e}")
            except Exception as e:
                import logging; logging.getLogger("adaptive_plan").warning(f"Suppressed: {e}")

    return {
        "goal": goal,
        "agent": agent_name,
        "total_steps": len(steps),
        "executed": len(results),
        "succeeded": sum(1 for r in results if r["success"]),
        "adaptations": adaptations,
        "results": results,
        "final_status": "completed" if all(r["success"] for r in results) else "partially_completed",
    }
