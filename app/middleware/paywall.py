"""Paywall middleware — enforces tier-level access on protected endpoints."""
import logging
log = logging.getLogger("tioli.paywall")

PROTECTED_ENDPOINTS = {
    "/api/v1/intelligence": 2,      # Professional tier
    "/api/v1/analytics/premium": 2,
    "/api/v1/training-data": 2,
    "/api/v1/benchmarking": 2,
    "/api/v1/futures": 3,           # Enterprise tier
}

async def check_paywall(path: str, user_tier: int = 0) -> bool:
    """Check if user has access to the requested endpoint."""
    for protected_path, required_tier in PROTECTED_ENDPOINTS.items():
        if path.startswith(protected_path) and user_tier < required_tier:
            log.warning(f"Paywall blocked: {path} requires tier {required_tier}, user has tier {user_tier}")
            return False
    return True
