"""ARCH-AA-001: Goal pursuit engine — agents autonomously work toward standing goals."""
import os
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.goal_engine")


async def goal_pursuit_cycle(db, agent_name, agent_client):
    """Run a goal pursuit cycle for an agent.
    Called every 30 minutes when ARCH_AA_GOAL_REGISTRY_ENABLED=true.
    """
    if os.environ.get("ARCH_AA_GOAL_REGISTRY_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    from sqlalchemy import text
    import json, uuid

    # Fetch top 3 active goals by priority
    goals = await db.execute(text(
        "SELECT goal_id, title, description, success_metric, priority, progress_pct "
        "FROM agent_goals WHERE agent_id = :aid AND status = 'active' "
        "ORDER BY priority ASC LIMIT 3"
    ), {"aid": agent_name})
    active_goals = goals.fetchall()

    if not active_goals:
        return {"status": "no_goals", "agent": agent_name}

    results = []
    for goal in active_goals:
        # Get last 5 actions for context
        actions = await db.execute(text(
            "SELECT action_taken, outcome FROM goal_actions "
            "WHERE goal_id = :gid ORDER BY executed_at DESC LIMIT 5"
        ), {"gid": goal.goal_id})
        past_actions = [f"- {a.action_taken}: {(a.outcome or 'pending')[:100]}" for a in actions.fetchall()]

        # Use model tiering: Haiku for assessment, Sonnet if action needed
        try:
            from app.arch.model_router import select_model
            model = select_model("goal_assessment", agent_name) or "claude-haiku-4-5-20251001"
        except Exception:
            model = "claude-haiku-4-5-20251001"

        try:
            # Ask: what is the single most impactful action?
            resp = await agent_client.messages.create(
                model=model, max_tokens=300,
                system=[{"type": "text", "text": f"You are {agent_name} of TiOLi AGENTIS. You are pursuing a standing goal."}],
                messages=[{"role": "user", "content":
                    f"Goal: {goal.title}\nSuccess metric: {goal.success_metric}\n"
                    f"Current progress: {goal.progress_pct}%\n"
                    f"Recent actions: {chr(10).join(past_actions) if past_actions else 'None yet'}\n\n"
                    f"What is the single most impactful action you can take RIGHT NOW toward this goal? "
                    f"Be specific and actionable. If the goal is complete, say GOAL_COMPLETE."}])

            action_text = next((b.text for b in resp.content if b.type == "text"), "No action determined")

            # Record action
            await db.execute(text(
                "INSERT INTO goal_actions (goal_id, agent_id, action_taken, outcome, tokens_used, executed_at) "
                "VALUES (:gid, :aid, :action, :outcome, :tokens, now())"
            ), {"gid": goal.goal_id, "aid": agent_name, "action": action_text[:500],
                "outcome": "Determined by LLM", "tokens": 300})

            # Update last_actioned
            await db.execute(text(
                "UPDATE agent_goals SET last_actioned = now(), updated_at = now() WHERE goal_id = :gid"
            ), {"gid": goal.goal_id})

            # Check for completion
            if "GOAL_COMPLETE" in action_text.upper():
                await db.execute(text(
                    "UPDATE agent_goals SET status = 'completed', progress_pct = 100, updated_at = now() WHERE goal_id = :gid"
                ), {"gid": goal.goal_id})

            await db.commit()
            results.append({"goal": goal.title, "action": action_text[:100], "status": "actioned"})

        except Exception as e:
            results.append({"goal": goal.title, "error": str(e)[:100]})

    # Log to job_execution_log
    try:
        await db.execute(text(
            "INSERT INTO job_execution_log (job_id, status, tokens_consumed, executed_at) "
            "VALUES (:jid, 'EXECUTED', :tokens, now())"
        ), {"jid": f"goal_pursuit_{agent_name}", "tokens": len(results) * 300})
        await db.commit()
    except Exception:
        pass

    return {"agent": agent_name, "goals_actioned": len(results), "results": results}
