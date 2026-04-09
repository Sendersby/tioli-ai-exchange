"""ARCH-AA-006: Rolling entity re-screening programme."""
import os
import logging

log = logging.getLogger("arch.rescreening")


async def run_rescreening_batch(db, batch_size=50):
    """Daily re-screening of agents due for review."""
    if os.environ.get("ARCH_AA_ROLLING_RESCREENING_ENABLED", "false").lower() != "true":
        return {"status": "disabled"}

    from sqlalchemy import text
    import uuid

    # Find agents due for rescreening
    due = await db.execute(text(
        "SELECT id, name FROM agents WHERE is_active = true AND is_house_agent = false "
        "AND (last_rescreened IS NULL OR last_rescreened < now() - interval '30 days') "
        "ORDER BY last_rescreened ASC NULLS FIRST LIMIT :lim"
    ), {"lim": batch_size})
    agents = due.fetchall()

    results = []
    for agent in agents:
        try:
            from app.arch.compliance_real import screen_sanctions
            screening = await screen_sanctions(agent.name)
            hit = screening.get("sanctions_hit", False)
            status = "flagged" if hit else "clear"

            # Log result
            await db.execute(text(
                "INSERT INTO rescreening_log (agent_id, result, match_details, action_taken) "
                "VALUES (:aid, :result, :details, :action)"
            ), {"aid": str(agent.id), "result": status,
                "details": str(screening.get("fuzzy_matches", 0)) + " fuzzy matches",
                "action": "suspended" if hit else "cleared"})

            # Update agent
            await db.execute(text(
                "UPDATE agents SET last_rescreened = now(), rescreening_status = :status WHERE id = :aid"
            ), {"status": status, "aid": agent.id})

            if hit:
                # Suspend and alert
                await db.execute(text("UPDATE agents SET is_active = false WHERE id = :aid"), {"aid": agent.id})
                try:
                    from app.arch.blackboard import post_to_blackboard
                    await post_to_blackboard(db, "auditor", "compliance",
                        f"OFAC_RESCREENING_HIT:{agent.id}", f"Agent {agent.name} flagged on rescreening")
                except Exception:
                    pass

            await db.commit()
            results.append({"agent": agent.name, "result": status})

        except Exception as e:
            results.append({"agent": agent.name, "error": str(e)[:60]})

    return {"screened": len(results), "results": results}
