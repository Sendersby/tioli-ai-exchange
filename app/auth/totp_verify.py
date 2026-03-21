"""TOTP verification via Microsoft Authenticator / Google Authenticator.

On first setup, generates a secret key and QR code for scanning.
On each login, validates the 6-digit code from the authenticator app.
"""

import os
import io
import base64
import logging

import pyotp
import qrcode

from app.config import settings

logger = logging.getLogger(__name__)

# The TOTP secret is stored in the environment for persistence across restarts.
# On first run, generate one and add it to .env manually.
_totp_secret: str | None = None


def get_totp_secret() -> str:
    """Get or generate the TOTP secret."""
    global _totp_secret
    if _totp_secret:
        return _totp_secret

    _totp_secret = os.environ.get("TOTP_SECRET", "")
    if not _totp_secret:
        # Generate a new secret — must be saved to .env for persistence
        _totp_secret = pyotp.random_base32()
        logger.warning(
            f"TOTP_SECRET not set — generated new secret. "
            f"Add to .env: TOTP_SECRET={_totp_secret}"
        )
    return _totp_secret


def get_totp() -> pyotp.TOTP:
    """Get the TOTP instance."""
    return pyotp.TOTP(get_totp_secret())


def verify_totp_code(code: str) -> bool:
    """Verify a TOTP code from the authenticator app.

    Accepts current code and one window before/after (±30 seconds).
    """
    totp = get_totp()
    return totp.verify(code.strip(), valid_window=1)


def get_setup_qr_base64() -> str:
    """Generate a QR code for scanning with an authenticator app.

    Returns a base64-encoded PNG image.
    """
    totp = get_totp()
    provisioning_uri = totp.provisioning_uri(
        name=settings.owner_email,
        issuer_name="TiOLi AI Exchange",
    )

    img = qrcode.make(provisioning_uri)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


def is_totp_configured() -> bool:
    """Check if TOTP secret is configured in environment."""
    return bool(os.environ.get("TOTP_SECRET", ""))
