"""ARCH-CP-004: Monthly cross-agent performance review."""
import os, logging, json
log = logging.getLogger("arch.performance_review")

async def generate_monthly_review(db, agent_client):
    """Sovereign generates monthly performance review of all agents."""
    if os.environ.get("ARCH_CP_PERFORMANCE_REVIEW_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    if agent_client is None:
        import anthropic
        agent_client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    from sqlalchemy import text
    from datetime import date

    metrics = {}
    agents = await db.execute(text("SELECT agent_name, tokens_used_this_month, token_budget_monthly FROM arch_agents"))
    for a in agents.fetchall():
        goals = await db.execute(text("SELECT count(*) FROM agent_goals WHERE agent_id = :aid AND status = 'completed'"), {"aid": a.agent_name})
        total_goals = await db.execute(text("SELECT count(*) FROM agent_goals WHERE agent_id = :aid"), {"aid": a.agent_name})
        actions = await db.execute(text("SELECT count(*) FROM goal_actions WHERE agent_id = :aid"), {"aid": a.agent_name})

        metrics[a.agent_name] = {
            "tokens_used": a.tokens_used_this_month,
            "token_budget": a.token_budget_monthly,
            "token_efficiency": f"{(a.tokens_used_this_month/a.token_budget_monthly*100):.1f}%",
            "goals_completed": goals.scalar() or 0,
            "total_goals": total_goals.scalar() or 0,
            "goal_actions": actions.scalar() or 0,
        }

    try:
        resp = await agent_client.messages.create(
            model="claude-opus-4-6", max_tokens=1500,
            system=[{"type": "text", "text": "You are The Sovereign conducting a monthly performance review of all 7 Arch Agents. Be specific, fair, and constructive."}],
            messages=[{"role": "user", "content": f"Agent metrics:\n{json.dumps(metrics, indent=2)}\n\nGenerate: individual agent assessments, board-level summary, top 3 recommendations."}])
        review = next((b.text for b in resp.content if b.type == "text"), "")

        await db.execute(text(
            "INSERT INTO performance_reviews (review_month, agent_metrics, board_summary, recommendations, generated_at) "
            "VALUES (:d, :metrics, :summary, :recs, now())"
        ), {"d": date.today(), "metrics": json.dumps(metrics), "summary": review, "recs": review[:500]})
        await db.commit()
        return {"month": str(date.today()), "agents_reviewed": len(metrics), "review_length": len(review)}
    except Exception as e:
        return {"error": str(e)}
