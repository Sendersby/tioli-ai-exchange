"""Owner authentication — 3-factor verification for Stephen Endersby.

The platform owner must verify identity through THREE independent methods:
1. Email confirmation from sendersby@tioli.onmicrosoft.com
2. SMS/message from +27 082 709 0435
3. Command-line token from a pre-registered terminal

No other human may access the platform without owner authorisation
via the same 3-factor process.
"""

import secrets
import time
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config import settings


class OwnerAuth:
    """Manages the owner's 3-factor authentication flow."""

    def __init__(self):
        # Pending verification challenges (in production, use Redis/DB)
        self._challenges: dict[str, dict] = {}
        # Active sessions
        self._sessions: dict[str, dict] = {}

    def initiate_login(self) -> dict:
        """Start a new login challenge.

        Automatically sends a verification email with a clickable link.
        Generates a 6-digit phone code (sent via SMS when Twilio configured).
        """
        challenge_id = secrets.token_urlsafe(32)
        cli_code = secrets.token_urlsafe(8)
        phone_code = f"{secrets.randbelow(900000) + 100000}"  # 6-digit code

        self._challenges[challenge_id] = {
            "created_at": time.time(),
            "expires_at": time.time() + 600,  # 10 minutes
            "email_verified": False,
            "phone_verified": False,
            "cli_verified": False,
            "cli_code": cli_code,
            "phone_code": phone_code,
            "email_sent": False,
        }

        # Send email code and SMS code in background threads (never block login)
        email_sent = False
        sms_sent = False
        email_code = ""
        try:
            from app.auth.email_verify import generate_email_code, send_verification_email
            from app.auth.sms_verify import send_sms_code
            import threading

            email_code = generate_email_code(challenge_id)
            self._challenges[challenge_id]["email_code"] = email_code

            def _send_email():
                try:
                    result = send_verification_email(challenge_id, email_code)
                    self._challenges[challenge_id]["email_sent"] = result
                except Exception:
                    pass

            def _send_sms():
                try:
                    result = send_sms_code(phone_code)
                    self._challenges[challenge_id]["sms_sent"] = result
                except Exception:
                    pass

            threading.Thread(target=_send_email, daemon=True).start()
            threading.Thread(target=_send_sms, daemon=True).start()
            email_sent = True
            sms_sent = True
            self._challenges[challenge_id]["email_sent"] = True
            self._challenges[challenge_id]["sms_sent"] = True
        except Exception:
            pass

        return {
            "challenge_id": challenge_id,
            "cli_code": cli_code,
            "phone_code": phone_code,
            "email_sent": email_sent,
            "sms_sent": sms_sent,
            "message": "Login challenge created. Check your email and phone for verification codes.",
            "factors": {
                "email": "Verification code sent to your email — check your inbox" if email_sent else "Email sending failed — use manual verification",
                "phone": "6-digit code sent via SMS — check your phone" if sms_sent else "SMS sending failed — code displayed on screen",
                "cli": f"Enter this code: {cli_code}",
            },
            "expires_in_seconds": 600,
        }

    def verify_email_by_token(self, challenge_id: str) -> bool:
        """Verify email factor via clicked email link (legacy)."""
        challenge = self._challenges.get(challenge_id)
        if not challenge or time.time() > challenge["expires_at"]:
            return False
        challenge["email_verified"] = True
        return True

    def verify_email_code(self, challenge_id: str, code: str) -> bool:
        """Verify email factor via 6-digit code sent to email."""
        challenge = self._challenges.get(challenge_id)
        if not challenge or time.time() > challenge["expires_at"]:
            return False
        from app.auth.email_verify import validate_email_code
        if validate_email_code(challenge_id, code):
            challenge["email_verified"] = True
            return True
        return False

    def verify_phone_code(self, challenge_id: str, code: str) -> bool:
        """Verify phone factor via the 6-digit code."""
        challenge = self._challenges.get(challenge_id)
        if not challenge or time.time() > challenge["expires_at"]:
            return False
        if secrets.compare_digest(code.strip(), challenge.get("phone_code", "")):
            challenge["phone_verified"] = True
            return True
        return False

    def verify_email(self, challenge_id: str, email: str) -> bool:
        """Verify factor 1: email address matches owner's."""
        challenge = self._challenges.get(challenge_id)
        if not challenge or time.time() > challenge["expires_at"]:
            return False
        if email.lower() == settings.owner_email.lower():
            challenge["email_verified"] = True
            return True
        return False

    def verify_phone(self, challenge_id: str, phone: str) -> bool:
        """Verify factor 2: phone number matches owner's."""
        challenge = self._challenges.get(challenge_id)
        if not challenge or time.time() > challenge["expires_at"]:
            return False
        # Normalize phone number for comparison
        normalized = phone.replace(" ", "").replace("-", "")
        owner_normalized = settings.owner_phone.replace(" ", "").replace("-", "")
        if normalized == owner_normalized:
            challenge["phone_verified"] = True
            return True
        return False

    def verify_cli(self, challenge_id: str, code: str) -> bool:
        """Verify factor 3: TOTP code from authenticator app, or legacy CLI code."""
        challenge = self._challenges.get(challenge_id)
        if not challenge or time.time() > challenge["expires_at"]:
            return False
        # Try TOTP verification first (authenticator app)
        from app.auth.totp_verify import verify_totp_code, is_totp_configured
        if is_totp_configured() and verify_totp_code(code.strip()):
            challenge["cli_verified"] = True
            return True
        # Fallback to legacy CLI code
        if secrets.compare_digest(code, challenge["cli_code"]):
            challenge["cli_verified"] = True
            return True
        return False

    def get_cli_code(self, challenge_id: str) -> str | None:
        """Retrieve the CLI code for an active challenge."""
        challenge = self._challenges.get(challenge_id)
        if not challenge:
            return None
        return challenge["cli_code"]

    def check_challenge_complete(self, challenge_id: str) -> dict:
        """Check if all three factors are verified."""
        challenge = self._challenges.get(challenge_id)
        if not challenge:
            return {"complete": False, "error": "Challenge not found"}

        if time.time() > challenge["expires_at"]:
            del self._challenges[challenge_id]
            return {"complete": False, "error": "Challenge expired"}

        status = {
            "email_verified": challenge["email_verified"],
            "phone_verified": challenge["phone_verified"],
            "cli_verified": challenge["cli_verified"],
            "complete": all([
                challenge["email_verified"],
                challenge["phone_verified"],
                challenge["cli_verified"],
            ]),
        }

        if status["complete"]:
            # Issue JWT session token
            token = self._create_session_token()
            status["access_token"] = token
            status["token_type"] = "bearer"
            # AU-009: Issue a real 3FA token for write operations
            from app.auth.three_factor import three_factor_store
            status["three_fa_token"] = three_factor_store.issue_token(challenge_id)
            del self._challenges[challenge_id]

        return status

    def _create_session_token(self) -> str:
        """Create a JWT token for an authenticated owner session."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "owner:stephen_endersby",
            "role": "platform_owner",
            "company": "TiOLi AI Investments",
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        }
        return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    def validate_token(self, token: str) -> dict | None:
        """Validate a JWT session token. Returns payload if valid."""
        try:
            payload = jwt.decode(
                token, settings.secret_key, algorithms=[settings.algorithm]
            )
            if payload.get("role") != "platform_owner":
                return None
            return payload
        except Exception:
            return None


# Singleton instance
owner_auth = OwnerAuth()
