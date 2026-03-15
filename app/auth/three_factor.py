"""3FA Token Store — real validation for owner write operations.

AU-009: Tokens are single-use, expire after 15 minutes.
Used by PayOut Engine and PayPal endpoints for write protection.
"""

import secrets
import time


class ThreeFactorTokenStore:
    """Stores and validates 3FA tokens issued after successful 3-factor verification."""

    def __init__(self, ttl_seconds: int = 900):  # 15 minutes
        self._tokens: dict[str, dict] = {}
        self._ttl = ttl_seconds

    def issue_token(self, challenge_id: str) -> str:
        """Issue a single-use 3FA token after all 3 factors verified."""
        token = f"3fa_{secrets.token_urlsafe(32)}"
        self._tokens[token] = {
            "challenge_id": challenge_id,
            "issued_at": time.time(),
            "expires_at": time.time() + self._ttl,
            "used": False,
        }
        self._cleanup()
        return token

    def validate_and_consume(self, token: str) -> bool:
        """Validate a 3FA token. Returns True if valid. Consumes the token (single-use)."""
        if not token or token not in self._tokens:
            return False

        record = self._tokens[token]

        # Check expiry
        if time.time() > record["expires_at"]:
            del self._tokens[token]
            return False

        # Check already used
        if record["used"]:
            del self._tokens[token]
            return False

        # Consume — single use
        record["used"] = True
        del self._tokens[token]
        return True

    def _cleanup(self):
        """Remove expired tokens."""
        now = time.time()
        expired = [k for k, v in self._tokens.items() if now > v["expires_at"]]
        for k in expired:
            del self._tokens[k]


# Singleton
three_factor_store = ThreeFactorTokenStore()
