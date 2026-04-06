"""Cloudflare Dynamic Workers — edge-based code execution sandboxing.

Ships agent-generated code to Cloudflare V8 isolates for execution.
100x faster startup than containers, zero server load.

Requires:
- CF_ACCOUNT_ID in .env
- CF_API_TOKEN in .env (with Workers Scripts permissions)
- Dynamic Workers enabled in Cloudflare dashboard
"""
import os
import logging
import httpx

log = logging.getLogger("arch.cf_workers")

CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")
CF_WORKERS_AVAILABLE = bool(CF_ACCOUNT_ID and CF_API_TOKEN)

if CF_WORKERS_AVAILABLE:
    log.info("Cloudflare Dynamic Workers: CONFIGURED")
else:
    log.info("Cloudflare Dynamic Workers: NOT CONFIGURED (using local sandbox)")


async def execute_in_worker(code: str, language: str = "javascript") -> dict:
    """Execute code in a Cloudflare Dynamic Worker.

    Args:
        code: The code to execute
        language: "javascript" (native) or "python" (via Pyodide)

    Returns:
        {"output": str, "error": str|None, "execution_time_ms": int}
    """
    if not CF_WORKERS_AVAILABLE:
        return {"error": "Cloudflare Workers not configured", "fallback": True}

    try:
        # Wrap Python code in a Worker script
        if language == "python":
            worker_script = f"""
            import {{ default as pyodide }} from 'pyodide';
            export default {{
                async fetch(request) {{
                    const py = await pyodide.loadPyodide();
                    try {{
                        const result = py.runPython(`{code}`);
                        return new Response(JSON.stringify({{output: String(result)}}));
                    }} catch(e) {{
                        return new Response(JSON.stringify({{error: String(e)}}), {{status: 500}});
                    }}
                }}
            }}
            """
        else:
            worker_script = code

        async with httpx.AsyncClient(timeout=30) as client:
            # Create a temporary worker
            resp = await client.put(
                f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/workers/scripts/agentis-sandbox-temp",
                headers={
                    "Authorization": f"Bearer {CF_API_TOKEN}",
                    "Content-Type": "application/javascript",
                },
                content=worker_script,
            )

            if resp.status_code in (200, 201):
                # Execute the worker
                exec_resp = await client.get(
                    f"https://agentis-sandbox-temp.{CF_ACCOUNT_ID}.workers.dev/",
                    timeout=30,
                )
                return {
                    "output": exec_resp.text[:5000],
                    "status_code": exec_resp.status_code,
                    "method": "cloudflare_dynamic_worker",
                }
            else:
                return {"error": f"Worker creation failed: HTTP {resp.status_code}", "detail": resp.text[:200]}

    except Exception as e:
        log.error(f"CF Worker execution failed: {e}")
        return {"error": str(e), "fallback": True}


async def sandboxed_execute_cf(command: str, timeout: int = 30) -> dict:
    """Execute a shell command via Cloudflare Worker (Python via Pyodide).
    Falls back to local sandbox if CF not available."""
    if not CF_WORKERS_AVAILABLE:
        from app.arch.sandbox import sandboxed_execute
        return await sandboxed_execute(command, timeout)

    return await execute_in_worker(command, language="python")
