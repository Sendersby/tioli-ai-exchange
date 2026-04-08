"""The Catalyst — Chief Innovation Officer. The 8th Arch Agent.

Owns experimentation, A/B testing, growth hacking, and the innovation pipeline.
Drives new features from idea to validated experiment.
"""
import logging

log = logging.getLogger("arch.catalyst")


CATALYST_TOOLS = [
    {
        "name": "create_experiment",
        "description": "Create an A/B experiment with hypothesis, variants, and success metric",
    },
    {
        "name": "measure_experiment",
        "description": "Collect and analyse results from a running experiment",
    },
    {
        "name": "propose_innovation",
        "description": "Submit a new feature or improvement idea to the innovation pipeline",
    },
    {
        "name": "get_experiment_results",
        "description": "Get results from completed experiments",
    },
]


async def create_experiment(db, title: str, hypothesis: str, variants: list, metric: str):
    """Create an A/B experiment."""
    from sqlalchemy import text
    import uuid, json
    exp_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO arch_growth_experiments (id, title, hypothesis, variants, success_metric, status, created_at) "
        "VALUES (:id, :title, :hyp, :variants, :metric, 'active', now())"
    ), {"id": exp_id, "title": title, "hyp": hypothesis,
        "variants": json.dumps(variants), "metric": metric})
    await db.commit()
    return {"experiment_id": exp_id, "title": title, "status": "active"}


async def list_experiments(db):
    """List all experiments."""
    from sqlalchemy import text
    result = await db.execute(text(
        "SELECT id, title, status, created_at::text FROM arch_growth_experiments ORDER BY created_at DESC LIMIT 20"
    ))
    return [{"id": r.id, "title": r.title, "status": r.status, "created": r.created_at} for r in result.fetchall()]


async def measure_experiment(db, experiment_id: str, results: dict):
    """Record experiment measurement results."""
    from sqlalchemy import text
    import json
    try:
        await db.execute(text(
            "UPDATE arch_growth_experiments SET result = :result, status = 'measured' WHERE id = :id"
        ), {"id": experiment_id, "result": json.dumps(results)})

        # Determine winner if variants have results
        variants = results.get("variants", {})
        if variants:
            winner = max(variants, key=lambda k: variants[k].get("conversion", 0))
            uplift = variants[winner].get("conversion", 0) - min(variants[v].get("conversion", 0) for v in variants)
            await db.execute(text(
                "UPDATE arch_growth_experiments SET winner = :winner, uplift_pct = :uplift, status = 'completed' WHERE id = :id"
            ), {"id": experiment_id, "winner": winner, "uplift": uplift})

        await db.commit()
        return {"experiment_id": experiment_id, "status": "measured", "results": results}
    except Exception as e:
        return {"error": str(e)}
