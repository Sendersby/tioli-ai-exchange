"""Credential vault enhancements — rotation, audit, health checks."""
import os
import logging
import httpx
from datetime import datetime, timezone

log = logging.getLogger("arch.vault_enhanced")

# Credential registry — which keys exist and how to test them
CREDENTIAL_REGISTRY = {
    "ANTHROPIC_API_KEY": {
        "test_url": "https://api.anthropic.com/v1/messages",
        "test_method": "POST",
        "test_headers": lambda key: {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        "test_body": {"model": "claude-haiku-4-5-20251001", "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]},
        "critical": True,
    },
    "GITHUB_TOKEN": {
        "test_url": "https://api.github.com/user",
        "test_method": "GET",
        "test_headers": lambda key: {"Authorization": f"token {key}"},
        "critical": True,
    },
    "HF_TOKEN": {
        "test_url": "https://huggingface.co/api/whoami-v2",
        "test_method": "GET",
        "test_headers": lambda key: {"Authorization": f"Bearer {key}"},
        "critical": False,
    },
    "DEVTO_API_KEY": {
        "test_url": "https://dev.to/api/users/me",
        "test_method": "GET",
        "test_headers": lambda key: {"api-key": key},
        "critical": False,
    },
}


async def check_credential_health() -> dict:
    """Test all registered credentials and report their health."""
    results = {}

    async with httpx.AsyncClient(timeout=10) as client:
        for name, config in CREDENTIAL_REGISTRY.items():
            key = os.getenv(name, "")
            if not key:
                results[name] = {"status": "NOT_SET", "critical": config["critical"]}
                continue

            try:
                headers = config["test_headers"](key)
                if config["test_method"] == "GET":
                    resp = await client.get(config["test_url"], headers=headers)
                else:
                    resp = await client.post(config["test_url"], headers=headers,
                                             json=config.get("test_body", {}))

                if resp.status_code in (200, 201):
                    results[name] = {"status": "VALID", "critical": config["critical"]}
                elif resp.status_code == 401:
                    results[name] = {"status": "EXPIRED", "critical": config["critical"]}
                else:
                    results[name] = {"status": f"HTTP_{resp.status_code}", "critical": config["critical"]}
            except Exception as e:
                results[name] = {"status": f"ERROR: {str(e)[:50]}", "critical": config["critical"]}

    valid = sum(1 for v in results.values() if v["status"] == "VALID")
    total = len(results)

    return {
        "credentials": results,
        "summary": f"{valid}/{total} valid",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "critical_issues": [k for k, v in results.items() if v["critical"] and v["status"] != "VALID"],
    }
