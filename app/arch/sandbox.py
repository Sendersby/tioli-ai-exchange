"""Sandbox wrapper for agent code execution.

Provides resource-limited execution with:
- Timeout enforcement (configurable, default 30s)
- Memory limiting via resource module
- Output capture and truncation
- Blocked command patterns
- Audit logging

Designed as a drop-in wrapper around ArchExecutor.run_command().
When Cloudflare Dynamic Workers are enabled, routes to edge execution instead.
"""
import asyncio
import os
import resource
import logging
from datetime import datetime, timezone

log = logging.getLogger("arch.sandbox")

# Blocked patterns — never execute these
BLOCKED_PATTERNS = [
    "rm -rf /", "rm -rf /*", "DROP DATABASE", "DROP TABLE",
    "shutdown", "reboot", "halt", "poweroff",
    "passwd", "chmod 777 /", "dd if=",
    "curl | bash", "wget | bash", "curl | sh",
    ":(){ :|:& };:", "fork bomb",
    "> /dev/sda", "mkfs",
    "iptables -F", "ufw disable",
]

# Resource limits
MAX_EXECUTION_TIME = int(os.getenv("SANDBOX_MAX_TIME", "30"))
MAX_OUTPUT_SIZE = int(os.getenv("SANDBOX_MAX_OUTPUT", "10000"))
MAX_MEMORY_MB = int(os.getenv("SANDBOX_MAX_MEMORY_MB", "256"))


def is_command_safe(command: str) -> tuple[bool, str]:
    """Check if a command is safe to execute."""
    cmd_lower = command.lower().strip()
    for pattern in BLOCKED_PATTERNS:
        if pattern.lower() in cmd_lower:
            return False, f"Blocked: dangerous pattern '{pattern}'"

    # Block attempts to modify system files
    if any(p in cmd_lower for p in ["/etc/passwd", "/etc/shadow", "/etc/sudoers"]):
        return False, "Blocked: system file modification"

    # Block attempts to install packages system-wide
    if "pip install" in cmd_lower and "--user" not in cmd_lower and ".venv" not in cmd_lower:
        return False, "Blocked: system-wide package install (use .venv)"

    return True, "OK"


async def sandboxed_execute(command: str, timeout: int = None, cwd: str = "/home/tioli/app") -> dict:
    """Execute a command in a resource-limited sandbox."""
    timeout = timeout or MAX_EXECUTION_TIME

    # Safety check
    safe, reason = is_command_safe(command)
    if not safe:
        log.warning(f"[sandbox] BLOCKED: {command[:100]} — {reason}")
        return {"executed": False, "error": reason, "blocked": True}

    log.info(f"[sandbox] Executing: {command[:200]} (timeout={timeout}s)")

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            # Set resource limits for the child process
            preexec_fn=lambda: (
                resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_MB * 1024 * 1024, MAX_MEMORY_MB * 1024 * 1024)),
                resource.setrlimit(resource.RLIMIT_CPU, (timeout, timeout)),
                resource.setrlimit(resource.RLIMIT_FSIZE, (50 * 1024 * 1024, 50 * 1024 * 1024)),  # 50MB file size limit
            ),
        )

        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        result = {
            "executed": True,
            "exit_code": proc.returncode,
            "stdout": stdout.decode(errors="replace")[:MAX_OUTPUT_SIZE],
            "stderr": stderr.decode(errors="replace")[:2000],
            "timeout": False,
            "sandboxed": True,
        }

        if proc.returncode != 0:
            log.warning(f"[sandbox] Non-zero exit: {proc.returncode} for: {command[:100]}")

        return result

    except asyncio.TimeoutError:
        log.warning(f"[sandbox] TIMEOUT after {timeout}s: {command[:100]}")
        try:
            proc.kill()
        except Exception:
            pass
        return {"executed": False, "error": f"Timeout after {timeout}s", "timeout": True, "sandboxed": True}

    except Exception as e:
        log.error(f"[sandbox] Error: {e} for: {command[:100]}")
        return {"executed": False, "error": str(e), "sandboxed": True}
