"""B-7: Benchmarking report generator — automated agent comparison report."""
import os, json, logging, uuid
from datetime import datetime, timezone

log = logging.getLogger("arch.benchmark_report")


async def generate_report(db, agent_id=None, agent_client=None):
    """Generate benchmarking report comparing agent against platform averages."""
    if os.environ.get("SANDBOX_MODE", "false").lower() != "true":
        return {"error": "Requires SANDBOX_MODE=true"}

    from sqlalchemy import text
    try:
        await db.rollback()
    except Exception:
        pass

    # Get platform averages
    avg_score = await db.execute(text("SELECT avg(aggregate_score) FROM agent_evaluation_scores"))
    avg = float(avg_score.scalar() or 50)

    avg_trades = await db.execute(text("SELECT count(*) FROM trades"))
    total_trades = avg_trades.scalar() or 0

    avg_rep = 5.0  # Default platform average reputation

    # Get agent-specific data if provided
    agent_data = {}
    if agent_id:
        eval_r = await db.execute(text(
            "SELECT m1_production, m4_cost, m5_governance, m7_proactivity, aggregate_score "
            "FROM agent_evaluation_scores WHERE agent_id = :aid ORDER BY evaluated_at DESC LIMIT 1"
        ), {"aid": agent_id})
        row = eval_r.fetchone()
        if row:
            agent_data = {
                "production": float(row.m1_production),
                "cost_efficiency": float(row.m4_cost),
                "governance": float(row.m5_governance),
                "proactivity": float(row.m7_proactivity) if row.m7_proactivity else 0,
                "aggregate": float(row.aggregate_score),
            }

    report = {
        "agent_id": agent_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform_averages": {"aggregate_score": round(avg, 1), "total_trades": total_trades,
                               "avg_reputation": avg_rep},
        "agent_scores": agent_data,
        "comparison": {
            "vs_platform_avg": round(agent_data.get("aggregate", 0) - avg, 1) if agent_data else 0,
            "percentile": "top 50%" if agent_data.get("aggregate", 0) > avg else "below average",
        },
        "recommendations": [],
        "sandbox": True,
    }

    if agent_data:
        if agent_data.get("proactivity", 0) < 30:
            report["recommendations"].append("Increase proactive actions — current score below platform average")
        if agent_data.get("cost_efficiency", 0) < 50:
            report["recommendations"].append("Improve cost efficiency — consider model tiering for routine tasks")

    # Store report
    report_id = str(uuid.uuid4())
    await db.execute(text(
        "INSERT INTO sandbox_benchmark_reports (id, agent_id, report_data, report_type, created_at) "
        "VALUES (:id, :aid, cast(:data as jsonb), 'comprehensive', now())"
    ), {"id": report_id, "aid": agent_id or "platform", "data": json.dumps(report)})
    await db.commit()

    report["report_id"] = report_id
    return report
