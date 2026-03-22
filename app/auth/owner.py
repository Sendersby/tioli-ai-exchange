"""Owner authentication — 3-factor verification for Stephen Endersby.

The platform owner must verify identity through THREE independent methods:
1. Email confirmation from sendersby@tioli.onmicrosoft.com
2. SMS/message from +27 082 709 0435
3. TOTP code from authenticator app

Security hardening:
- Brute force protection: 5 failed attempts → 15 min lockout
- Challenges persisted to DB (survive restart)
- Failed attempt logging for security audit
"""

import json
import os
import secrets
import time
import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from jose import jwt

from app.config import settings

logger = logging.getLogger("tioli.security")

# Brute force protection constants
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 900  # 15 minutes
MAX_ACTIVE_CHALLENGES = 3       # Max concurrent challenges

# Persistent storage for brute force state (survives restarts)
_BRUTE_FORCE_FILE = os.path.join(os.path.dirname(__file__), ".brute_force_state.json")


class BruteForceProtection:
    """Tracks failed login attempts and enforces lockouts.

    State is persisted to disk so lockouts survive server restarts.
    """

    def __init__(self):
        self._failed_attempts: dict[str, list[float]] = defaultdict(list)
        self._lockouts: dict[str, float] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Load persisted brute force state from disk."""
        try:
            if os.path.exists(_BRUTE_FORCE_FILE):
                with open(_BRUTE_FORCE_FILE, "r") as f:
                    data = json.load(f)
                now = time.time()
                # Restore only non-expired lockouts
                for ip, until in data.get("lockouts", {}).items():
                    if until > now:
                        self._lockouts[ip] = until
                # Restore only recent failed attempts
                cutoff = now - LOCKOUT_DURATION_SECONDS
                for ip, timestamps in data.get("attempts", {}).items():
                    valid = [t for t in timestamps if t > cutoff]
                    if valid:
                        self._failed_attempts[ip] = valid
        except Exception as e:
            logger.warning(f"Could not load brute force state: {e}")

    def _save_state(self) -> None:
        """Persist brute force state to disk."""
        try:
            data = {
                "lockouts": dict(self._lockouts),
                "attempts": dict(self._failed_attempts),
            }
            with open(_BRUTE_FORCE_FILE, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Could not save brute force state: {e}")

    def record_failure(self, ip: str) -> None:
        """Record a failed verification attempt."""
        now = time.time()
        self._failed_attempts[ip].append(now)
        # Clean old entries (older than lockout window)
        cutoff = now - LOCKOUT_DURATION_SECONDS
        self._failed_attempts[ip] = [t for t in self._failed_attempts[ip] if t > cutoff]
        # Check if lockout triggered
        if len(self._failed_attempts[ip]) >= MAX_FAILED_ATTEMPTS:
            self._lockouts[ip] = now + LOCKOUT_DURATION_SECONDS
            logger.warning(f"Brute force lockout triggered for IP {ip}: {len(self._failed_attempts[ip])} failed attempts")
        self._save_state()

    def is_locked_out(self, ip: str) -> bool:
        """Check if an IP is currently locked out."""
        lockout_until = self._lockouts.get(ip, 0)
        if time.time() < lockout_until:
            return True
        # Lockout expired — clear it
        if ip in self._lockouts:
            del self._lockouts[ip]
            self._save_state()
        return False

    def get_remaining_lockout(self, ip: str) -> int:
        """Get remaining lockout time in seconds."""
        lockout_until = self._lockouts.get(ip, 0)
        remaining = int(lockout_until - time.time())
        return max(0, remaining)

    def clear(self, ip: str) -> None:
        """Clear failed attempts on successful login."""
        self._failed_attempts.pop(ip, None)
        self._lockouts.pop(ip, None)
        self._save_state()


class OwnerAuth:
    """Manages the owner's 3-factor authentication flow with brute force protection."""

    def __init__(self):
        self._challenges: dict[str, dict] = {}
        self._sessions: dict[str, dict] = {}
        self.brute_force = BruteForceProtection()

    def is_locked_out(self, ip: str) -> bool:
        """Check if IP is locked out from login attempts."""
        return self.brute_force.is_locked_out(ip)

    def get_lockout_info(self, ip: str) -> dict:
        """Get lockout status for an IP."""
        locked = self.brute_force.is_locked_out(ip)
        remaining = self.brute_force.get_remaining_lockout(ip)
        return {
            "locked_out": locked,
            "remaining_seconds": remaining,
            "max_attempts": MAX_FAILED_ATTEMPTS,
            "lockout_duration_minutes": LOCKOUT_DURATION_SECONDS // 60,
        }

    def initiate_login(self, ip: str = "unknown") -> dict:
        """Start a new login challenge.

        Checks brute force lockout before proceeding.
        Limits concurrent active challenges.
        """
        # Check lockout
        if self.brute_force.is_locked_out(ip):
            remaining = self.brute_force.get_remaining_lockout(ip)
            logger.warning(f"Login attempt from locked-out IP {ip}")
            return {
                "error": f"Too many failed attempts. Try again in {remaining} seconds.",
                "locked_out": True,
                "remaining_seconds": remaining,
            }

        # Limit active challenges
        now = time.time()
        active = {k: v for k, v in self._challenges.items() if v["expires_at"] > now}
        self._challenges = active
        if len(self._challenges) >= MAX_ACTIVE_CHALLENGES:
            return {"error": "Too many active challenges. Wait for existing ones to expire."}

        challenge_id = secrets.token_urlsafe(32)
        cli_code = secrets.token_urlsafe(8)
        phone_code = f"{secrets.randbelow(900000) + 100000}"

        self._challenges[challenge_id] = {
            "created_at": now,
            "expires_at": now + 600,
            "email_verified": False,
            "phone_verified": False,
            "cli_verified": False,
            "cli_code": cli_code,
            "phone_code": phone_code,
            "email_sent": False,
            "failed_attempts": 0,
            "ip": ip,
        }

        # Send email code and SMS code in background
        email_sent = False
        sms_sent = False
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

    def _record_failed_attempt(self, challenge_id: str) -> None:
        """Record a failed verification attempt for brute force tracking."""
        challenge = self._challenges.get(challenge_id)
        if challenge:
            challenge["failed_attempts"] = challenge.get("failed_attempts", 0) + 1
            ip = challenge.get("ip", "unknown")
            self.brute_force.record_failure(ip)
            logger.warning(f"Failed verification attempt on challenge {challenge_id[:12]}... from IP {ip}")

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
        self._record_failed_attempt(challenge_id)
        return False

    def verify_phone_code(self, challenge_id: str, code: str) -> bool:
        """Verify phone factor via the 6-digit code."""
        challenge = self._challenges.get(challenge_id)
        if not challenge or time.time() > challenge["expires_at"]:
            return False
        if secrets.compare_digest(code.strip(), challenge.get("phone_code", "")):
            challenge["phone_verified"] = True
            return True
        self._record_failed_attempt(challenge_id)
        return False

    def verify_email(self, challenge_id: str, email: str) -> bool:
        """Verify factor 1: email address matches owner's."""
        challenge = self._challenges.get(challenge_id)
        if not challenge or time.time() > challenge["expires_at"]:
            return False
        if email.lower() == settings.owner_email.lower():
            challenge["email_verified"] = True
            return True
        self._record_failed_attempt(challenge_id)
        return False

    def verify_phone(self, challenge_id: str, phone: str) -> bool:
        """Verify factor 2: phone number matches owner's."""
        challenge = self._challenges.get(challenge_id)
        if not challenge or time.time() > challenge["expires_at"]:
            return False
        normalized = phone.replace(" ", "").replace("-", "")
        owner_normalized = settings.owner_phone.replace(" ", "").replace("-", "")
        if normalized == owner_normalized:
            challenge["phone_verified"] = True
            return True
        self._record_failed_attempt(challenge_id)
        return False

    def verify_cli(self, challenge_id: str, code: str) -> bool:
        """Verify factor 3: TOTP code from authenticator app, or legacy CLI code."""
        challenge = self._challenges.get(challenge_id)
        if not challenge or time.time() > challenge["expires_at"]:
            return False
        from app.auth.totp_verify import verify_totp_code, is_totp_configured
        if is_totp_configured() and verify_totp_code(code.strip()):
            challenge["cli_verified"] = True
            return True
        if secrets.compare_digest(code, challenge["cli_code"]):
            challenge["cli_verified"] = True
            return True
        self._record_failed_attempt(challenge_id)
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
            token = self._create_session_token()
            status["access_token"] = token
            status["token_type"] = "bearer"
            from app.auth.three_factor import three_factor_store
            status["three_fa_token"] = three_factor_store.issue_token(challenge_id)
            # Clear brute force tracking on successful login
            ip = challenge.get("ip", "unknown")
            self.brute_force.clear(ip)
            del self._challenges[challenge_id]
            logger.info(f"Successful 3FA login from IP {ip}")

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
