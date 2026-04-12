"""Sentinel tool definitions — Anthropic API format."""

SENTINEL_TOOLS = [
    {
        "name": "declare_incident",
        "description": "Declare a platform incident. Use immediately when a security or operational issue is detected.",
        "input_schema": {
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
                "title": {"type": "string", "maxLength": 200},
                "description": {"type": "string"},
                "popia_notifiable": {"type": "boolean", "default": False},
                "affected_systems": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["severity", "title", "description"],
        },
    },
    {
        "name": "freeze_account",
        "description": "Freeze an agent or operator account for security reasons.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
                "account_type": {"type": "string", "enum": ["agent", "operator"]},
                "reason": {"type": "string"},
                "incident_ref": {"type": "string"},
            },
            "required": ["account_id", "account_type", "reason"],
        },
    },
    {
        "name": "check_platform_health",
        "description": "Get real-time health status of all platform components.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "activate_kill_switch",
        "description": "Emergency infrastructure shutdown. Requires kill_switch_key confirmation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "kill_switch_confirmation": {"type": "string"},
                "preserve_database": {"type": "boolean", "default": True},
            },
            "required": ["reason", "kill_switch_confirmation"],
        },
    },
    {
        "name": "check_security_posture",
        "description": "Generate a security posture report including rate limits, CVEs, and credential rotation status.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "trigger_key_rotation",
        "description": "Trigger credential rotation for a specific platform or all overdue credentials.",
        "input_schema": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "description": "Specific platform or 'all_overdue'"},
            },
            "required": ["platform"],
        },
    },
    {
        "name": "verify_backup",
        "description": "Trigger a backup verification check.",
        "input_schema": {
            "type": "object",
            "properties": {
                "backup_type": {"type": "string", "enum": ["database", "redis", "files", "full"]},
            },
            "required": ["backup_type"],
        },
    },
    {
        "name": "search_logs",
        "description": "Search application logs by keyword, time range, and severity level.",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Text to search for in logs"},
                "since_minutes": {"type": "integer", "default": 60, "description": "How far back to search (minutes)"},
                "severity": {"type": "string", "enum": ["", "error", "warning", "info"], "default": ""},
                "max_lines": {"type": "integer", "default": 50, "description": "Maximum log lines to return"},
            },
            "required": ["keyword"],
        },
    },
    {
        "name": "check_ssl_certificates",
        "description": "Check SSL certificate expiry for all platform domains.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_rate_limit_status",
        "description": "Get current rate limiting configuration and recent 429 counts.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


# ── Tier 1 Tool Implementations ──────────────────────────────


async def search_logs(keyword: str, since_minutes: int = 60, severity: str = "", max_lines: int = 50) -> dict:
    """Search application logs by keyword, time range, and severity.

    Uses journalctl to query the tioli-exchange systemd unit.
    Filters by severity (error/warning/info) and keyword.
    """
    import asyncio
    import shlex

    if not keyword or not keyword.strip():
        return {"error": "keyword is required"}

    # Sanitize inputs to prevent shell injection
    safe_keyword = shlex.quote(keyword.strip())
    since_minutes = max(1, min(since_minutes, 10080))  # 1 min to 7 days
    max_lines = max(1, min(max_lines, 500))

    cmd = f"journalctl -u tioli-exchange --since '{since_minutes} min ago' --no-pager"
    if severity:
        severity_map = {
            "error": "error|Error|ERROR|CRITICAL|critical",
            "warning": "warn|Warn|WARN|WARNING",
            "info": "info|Info|INFO",
        }
        grep_pattern = severity_map.get(severity.lower(), severity)
        cmd += f" | grep -iE '{grep_pattern}'"
    cmd += f" | grep -i {safe_keyword}"
    cmd += f" | tail -{max_lines}"

    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        lines = stdout.decode(errors="replace").strip().split("\n") if stdout else []
        lines = [line for line in lines if line.strip()]

        return {
            "keyword": keyword,
            "since_minutes": since_minutes,
            "severity": severity or "all",
            "lines_found": len(lines),
            "logs": lines[-max_lines:],
        }
    except asyncio.TimeoutError:
        return {"error": "Log search timed out after 15 seconds"}
    except Exception as exc:
        return {"error": str(exc)}


async def check_ssl_certificates() -> dict:
    """Check SSL certificate expiry for all platform domains.

    Uses openssl s_client to connect and extract certificate dates
    and issuer for each configured domain.
    """
    import asyncio
    from datetime import datetime, timezone

    domains = ["exchange.tioli.co.za", "agentisexchange.com"]
    results: dict = {}

    for domain in domains:
        try:
            cmd = (
                f"echo | openssl s_client -servername {domain} -connect {domain}:443 "
                f"2>/dev/null | openssl x509 -noout -dates -issuer 2>/dev/null"
            )
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            output = stdout.decode(errors="replace")

            not_after = ""
            issuer = ""
            for line in output.split("\n"):
                if "notAfter=" in line:
                    not_after = line.split("=", 1)[1].strip()
                if "issuer=" in line:
                    issuer = line.split("=", 1)[1].strip()

            if not_after:
                expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                expiry = expiry.replace(tzinfo=timezone.utc)
                days_remaining = (expiry - datetime.now(timezone.utc)).days
                if days_remaining > 14:
                    status = "ok"
                elif days_remaining > 7:
                    status = "warning"
                else:
                    status = "critical"
                results[domain] = {
                    "expires": not_after,
                    "days_remaining": days_remaining,
                    "issuer": issuer,
                    "status": status,
                }
            else:
                results[domain] = {"error": "Could not parse certificate — no notAfter found"}
        except asyncio.TimeoutError:
            results[domain] = {"error": "SSL check timed out after 10 seconds"}
        except Exception as exc:
            results[domain] = {"error": str(exc)}

    return {"certificates": results}


async def get_rate_limit_status() -> dict:
    """Get current rate limiting configuration and recent 429 counts.

    Checks journalctl for recent 429/rate-limit events and queries
    Redis for active rate limiter keys.
    """
    import asyncio

    # Check recent 429s in logs
    recent_429s = -1
    try:
        proc = await asyncio.create_subprocess_shell(
            "journalctl -u tioli-exchange --since '1 hour ago' --no-pager "
            "| grep -cE '429|rate.limit|Too Many' 2>/dev/null || echo 0",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        recent_429s = int(stdout.decode().strip() or "0")
    except (asyncio.TimeoutError, ValueError, Exception):
        pass

    # Check Redis rate limit keys
    active_keys = 0
    try:
        import redis as sync_redis
        r = sync_redis.from_url("redis://localhost:6379/0", socket_timeout=5)
        cursor = 0
        count = 0
        while True:
            cursor, keys = r.scan(cursor=cursor, match="LIMITER*", count=100)
            count += len(keys)
            if cursor == 0:
                break
        active_keys = count
        r.close()
    except Exception:
        pass

    if recent_429s < 10:
        status = "ok"
    elif recent_429s < 50:
        status = "elevated"
    else:
        status = "critical"

    return {
        "recent_429_count": recent_429s,
        "period": "last 1 hour",
        "active_rate_limit_keys": active_keys,
        "configuration": {
            "registration": "5 per hour per IP",
            "financial_endpoints": "60 per minute per user",
            "general_api": "300 per minute per user",
        },
        "status": status,
    }
