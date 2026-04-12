"""Architect tool definitions — Anthropic API format.

Includes ACC orchestration tools (PI-10 fix).
"""

ARCHITECT_TOOLS = [
    {
        "name": "submit_code_proposal",
        "description": "Submit a code evolution proposal through the four-tier protocol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tier": {"type": "string", "enum": ["0", "1", "2", "3"]},
                "title": {"type": "string", "maxLength": 200},
                "description": {"type": "string"},
                "rationale": {"type": "string"},
                "file_changes": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["tier", "title", "description", "rationale"],
        },
    },
    {
        "name": "toggle_feature_flag",
        "description": "Toggle a feature flag on or off. Only for non-constitutional flags.",
        "input_schema": {
            "type": "object",
            "properties": {
                "flag_name": {"type": "string"},
                "enabled": {"type": "boolean"},
                "reason": {"type": "string"},
            },
            "required": ["flag_name", "enabled", "reason"],
        },
    },
    {
        "name": "sandbox_deploy",
        "description": "Deploy a code proposal to the sandbox/staging environment for testing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string"},
                "test_suite": {"type": "string", "default": "full"},
            },
            "required": ["proposal_id"],
        },
    },
    {
        "name": "update_tech_radar",
        "description": "Add or update a technology assessment on the tech radar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "technology": {"type": "string"},
                "category": {"type": "string"},
                "assessment": {"type": "string", "enum": ["ADOPT", "TRIAL", "ASSESS", "HOLD"]},
                "rationale": {"type": "string"},
            },
            "required": ["technology", "assessment", "rationale"],
        },
    },
    {
        "name": "evaluate_ai_model",
        "description": "Evaluate a new AI model for potential platform integration.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_name": {"type": "string"},
                "provider": {"type": "string"},
                "benchmark_results": {"type": "object"},
                "cost_per_1k_tokens": {"type": "number"},
                "latency_ms_p50": {"type": "integer"},
            },
            "required": ["model_name", "provider"],
        },
    },
    {
        "name": "get_performance_snapshot",
        "description": "Get the latest performance snapshot for an agent or all agents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Optional: specific agent or 'all'"},
            },
            "required": [],
        },
    },
    # ACC orchestration tools (PI-10 fix)
    {
        "name": "trigger_acc_task",
        "description": "Instruct the ACC to produce content on a specific topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_type": {"type": "string", "enum": ["seo_article", "aeo_response", "press_release", "community_post", "technical_doc"]},
                "topic": {"type": "string"},
                "target_keywords": {"type": "array", "items": {"type": "string"}},
                "word_count": {"type": "integer", "minimum": 200, "maximum": 2000},
                "urgency": {"type": "string", "enum": ["ROUTINE", "URGENT"]},
            },
            "required": ["task_type", "topic"],
        },
    },
    {
        "name": "approve_acc_output",
        "description": "Mark ACC output as approved. Ambassador then publishes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "output_id": {"type": "string"},
                "approval_note": {"type": "string"},
            },
            "required": ["output_id"],
        },
    },
]


# ---------------------------------------------------------------------------
# Architect Tier 1 tools -- implementations
# ---------------------------------------------------------------------------


async def run_test_suite(test_path: str = 'tests/', verbose: bool = False) -> dict:
    """Run the pytest test suite and return structured results."""
    import asyncio
    import re

    # Sanitize test_path -- only allow paths under tests/
    if not test_path.startswith('tests'):
        test_path = 'tests/'
    test_path = test_path.replace('..', '').replace(';', '')

    tb_flag = 'short' if verbose else 'line'
    cmd = f'cd /home/tioli/app && .venv/bin/python -m pytest {test_path} -q --tb={tb_flag} 2>&1'

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        output = stdout.decode()

        # Parse results from last line
        lines = output.strip().split(chr(10))
        summary_line = lines[-1] if lines else ''

        passed = 0
        failed = 0
        errors = 0
        m = re.search(r'(\d+) passed', summary_line)
        if m:
            passed = int(m.group(1))
        m = re.search(r'(\d+) failed', summary_line)
        if m:
            failed = int(m.group(1))
        m = re.search(r'(\d+) error', summary_line)
        if m:
            errors = int(m.group(1))

        # Get failure details if any
        failures = [l for l in lines if 'FAILED' in l]

        return {
            'passed': passed,
            'failed': failed,
            'errors': errors,
            'total': passed + failed + errors,
            'all_passing': failed == 0 and errors == 0,
            'summary': summary_line,
            'failures': failures[:20],
            'output': output[-2000:] if verbose else '',
        }
    except asyncio.TimeoutError:
        return {'error': 'Test suite timed out after 120 seconds'}
    except Exception as e:
        return {'error': str(e)}


async def get_endpoint_performance() -> dict:
    """Get API endpoint response times from Prometheus metrics."""
    import httpx
    import re

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get("http://127.0.0.1:8000/metrics")
            if response.status_code != 200:
                return {"error": f"Metrics endpoint returned {response.status_code}"}

            metrics_text = response.text

            # Parse relevant Prometheus metrics
            results = {
                "request_count": {},
                "slow_endpoints": [],
                "error_rate": {},
            }

            # Extract http_request_duration_seconds histogram
            for line in metrics_text.split("\n"):
                if line.startswith("http_request_duration_seconds_sum"):
                    m = re.search(r'handler="([^"]*)".*method="([^"]*)"', line)
                    if m:
                        handler = m.group(1)
                        value = float(line.split()[-1])
                        if value > 1.0:
                            results["slow_endpoints"].append({
                                "endpoint": handler,
                                "total_seconds": round(value, 2),
                            })

                if line.startswith("http_requests_total"):
                    m = re.search(r'handler="([^"]*)".*method="([^"]*)".*status="([^"]*)"', line)
                    if m:
                        handler = m.group(1)
                        status = m.group(3)
                        count = int(float(line.split()[-1]))
                        if status.startswith("5"):
                            results["error_rate"][handler] = results["error_rate"].get(handler, 0) + count

            results["slow_endpoints"].sort(key=lambda x: x["total_seconds"], reverse=True)
            results["slow_endpoints"] = results["slow_endpoints"][:10]

            return results
    except Exception as e:
        return {"error": str(e)}


async def check_database_health(db) -> dict:
    """Comprehensive database health check."""
    from sqlalchemy import text

    health = {}

    # Connection pool status
    try:
        pool = db.get_bind().pool
        health["connection_pool"] = {
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }
    except Exception:
        health["connection_pool"] = "unable to read pool status"

    # Database size
    try:
        r = await db.execute(text("SELECT pg_size_pretty(pg_database_size('tioli_exchange'))"))
        health["database_size"] = r.scalar()
    except Exception as e:
        health["database_size"] = str(e)

    # Active connections
    try:
        r = await db.execute(text("SELECT count(*), state FROM pg_stat_activity WHERE datname='tioli_exchange' GROUP BY state"))
        health["connections"] = {row.state or "null": row.count for row in r.fetchall()}
    except Exception as e:
        health["connections"] = str(e)

    # Slow queries (from pg_stat_statements if available)
    try:
        r = await db.execute(text(
            "SELECT left(query, 100) as query, calls, round(mean_exec_time::numeric, 2) as avg_ms, "
            "round(total_exec_time::numeric, 2) as total_ms "
            "FROM pg_stat_statements WHERE mean_exec_time > 50 "
            "ORDER BY mean_exec_time DESC LIMIT 5"
        ))
        health["slow_queries"] = [
            {"query": row.query, "calls": row.calls, "avg_ms": float(row.avg_ms), "total_ms": float(row.total_ms)}
            for row in r.fetchall()
        ]
    except Exception as e:
        health["slow_queries"] = f"pg_stat_statements not available: {e}"

    # Table bloat (dead tuples)
    try:
        r = await db.execute(text(
            "SELECT relname, n_dead_tup, n_live_tup, "
            "CASE WHEN n_live_tup > 0 THEN round(100.0 * n_dead_tup / n_live_tup, 1) ELSE 0 END as dead_pct "
            "FROM pg_stat_user_tables WHERE n_dead_tup > 100 ORDER BY n_dead_tup DESC LIMIT 5"
        ))
        health["table_bloat"] = [
            {"table": row.relname, "dead_tuples": row.n_dead_tup, "live_tuples": row.n_live_tup, "dead_pct": float(row.dead_pct)}
            for row in r.fetchall()
        ]
    except Exception as e:
        health["table_bloat"] = str(e)

    # Top tables by size
    try:
        r = await db.execute(text(
            "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) as size, n_live_tup as rows "
            "FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 5"
        ))
        health["largest_tables"] = [
            {"table": row.relname, "size": row.size, "rows": row.rows}
            for row in r.fetchall()
        ]
    except Exception as e:
        health["largest_tables"] = str(e)

    # Empty table count
    try:
        r = await db.execute(text("SELECT count(*) FROM pg_stat_user_tables WHERE n_live_tup = 0"))
        total = await db.execute(text("SELECT count(*) FROM pg_stat_user_tables"))
        health["empty_tables"] = {"empty": r.scalar(), "total": total.scalar()}
    except Exception as e:
        health["empty_tables"] = str(e)

    return health


# ---------------------------------------------------------------------------
# Tool definitions for Anthropic API -- Architect Tier 1
# ---------------------------------------------------------------------------

ARCHITECT_TOOLS.extend([
    {
        "name": "run_test_suite",
        "description": (
            "Run the pytest test suite and return structured results including "
            "pass/fail counts, failure details, and optional verbose output."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "test_path": {
                    "type": "string",
                    "description": "Path under tests/ to run. Default: tests/",
                    "default": "tests/",
                },
                "verbose": {
                    "type": "boolean",
                    "description": "Include full output in response. Default: false",
                    "default": False,
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_endpoint_performance",
        "description": (
            "Get API endpoint response times and error rates from Prometheus metrics. "
            "Returns slow endpoints (>1s total), 5xx error counts, and request counts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "check_database_health",
        "description": (
            "Comprehensive PostgreSQL database health check. Returns connection pool status, "
            "database size, active connections, slow queries, table bloat, largest tables, "
            "and empty table count."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
])
