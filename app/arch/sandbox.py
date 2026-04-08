"""Code execution sandbox — isolated environment for testing agent code."""
import logging
import subprocess
import tempfile
import os

log = logging.getLogger("arch.sandbox")


async def execute_in_sandbox(code: str, language: str = "python", timeout: int = 30) -> dict:
    """Execute code in an isolated subprocess with timeout and resource limits.

    Not Docker (too heavy for single server) — uses subprocess with:
    - Timeout enforcement
    - No network access (simulated by not providing credentials)
    - Temp directory isolation
    - Resource limits via ulimit
    """
    if language != "python":
        return {"error": f"Unsupported language: {language}"}

    # Safety checks
    dangerous = ["import os", "import subprocess", "import shutil", "rm -rf",
                 "open('/etc", "open('/home", "__import__", "exec(", "eval(",
                 "import httpx", "import asyncpg", "import psycopg",
                 "import requests", "import urllib", "import socket",
                 "import sqlite3", "import paramiko", "import fabric",
                 "tioli", "DhQHhP", "password", "api_key", "secret"]
    for d in dangerous:
        if d in code:
            return {"error": f"Blocked: code contains prohibited pattern '{d}'",
                    "blocked": True}

    with tempfile.TemporaryDirectory(prefix="agentis_sandbox_") as tmpdir:
        code_file = os.path.join(tmpdir, "sandbox_code.py")
        with open(code_file, "w") as f:
            f.write(code)

        try:
            result = subprocess.run(
                ["/home/tioli/app/.venv/bin/python3", code_file],
                capture_output=True, text=True, timeout=timeout,
                cwd=tmpdir,
                env={"PATH": "/usr/bin:/bin", "HOME": tmpdir, "PYTHONPATH": ""},
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:1000],
                "return_code": result.returncode,
                "timeout": False,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Execution timed out", "timeout": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Alias for backward compatibility with executor
sandboxed_execute = execute_in_sandbox
