"""Email verification via 6-digit code — sends a code to the owner's email.

When the owner initiates a login challenge, this service:
1. Generates a random 6-digit email verification code
2. Sends the code to sendersby@tioli.onmicrosoft.com via Microsoft Graph API
3. The owner enters the code on the login page to verify
"""

import os
import secrets
import logging
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Store email verification codes: challenge_id -> code
_email_codes: dict[str, str] = {}


def generate_email_code(challenge_id: str) -> str:
    """Generate a 6-digit code for email verification."""
    code = f"{secrets.randbelow(900000) + 100000}"
    _email_codes[challenge_id] = code
    return code


def validate_email_code(challenge_id: str, code: str) -> bool:
    """Validate the email verification code.

    Returns True if code matches, False otherwise.
    Single-use — code is consumed on successful validation.
    """
    expected = _email_codes.get(challenge_id)
    if expected and secrets.compare_digest(code.strip(), expected):
        del _email_codes[challenge_id]
        return True
    return False


def _get_graph_access_token() -> str | None:
    """Get a Microsoft Graph API access token using client credentials."""
    tenant_id = os.environ.get("AZURE_TENANT_ID", "")
    client_id = os.environ.get("AZURE_CLIENT_ID", "")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET", "")

    if not all([tenant_id, client_id, client_secret]):
        logger.warning("Microsoft Graph not configured — missing Azure credentials")
        return None

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    try:
        response = httpx.post(
            token_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception as e:
        logger.error(f"Failed to get Graph access token: {e}")
        return None


def send_verification_email(challenge_id: str, email_code: str) -> bool:
    """Send the verification email with a 6-digit code via Microsoft Graph API."""

    # Try Microsoft Graph API first (works over HTTPS, not blocked)
    access_token = _get_graph_access_token()
    if access_token:
        return _send_via_graph(access_token, email_code)

    # Fallback to SMTP if Graph not configured
    return _send_via_smtp(email_code)


def _send_via_graph(access_token: str, email_code: str) -> bool:
    """Send email via Microsoft Graph API."""
    sender_email = os.environ.get("SMTP_USER", settings.owner_email)
    recipient_email = settings.owner_email

    email_body = {
        "message": {
            "subject": "TiOLi AI Transact Exchange — Login Code",
            "body": {
                "contentType": "HTML",
                "content": f"""
                <div style="font-family: 'Inter', Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 30px; background: #f5f5f3; border-radius: 12px;">
                    <div style="background: #2b2b2b; padding: 20px; border-radius: 10px 10px 0 0; text-align: center; border-bottom: 3px solid #8fa88b;">
                        <h1 style="color: #ffffff; margin: 0; font-size: 18px; letter-spacing: 0.5px;">TiOLi AI Transact Exchange</h1>
                    </div>
                    <div style="background: #ffffff; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #eae7e3;">
                        <h2 style="color: #2b2b2b; margin-top: 0; font-size: 20px;">Login Verification Code</h2>
                        <p style="color: #7a7a7a; line-height: 1.6;">Your login verification code is:</p>
                        <div style="text-align: center; margin: 30px 0;">
                            <span style="background: #6b8a66; color: #ffffff; padding: 14px 32px; border-radius: 8px; font-weight: 700; font-size: 28px; letter-spacing: 6px; display: inline-block;">{email_code}</span>
                        </div>
                        <p style="color: #aaa; font-size: 12px; text-align: center;">This code expires in 10 minutes and can only be used once.</p>
                        <p style="color: #aaa; font-size: 12px; text-align: center;">If you did not initiate this login, please ignore this email.</p>
                    </div>
                    <p style="color: #aaa; font-size: 11px; text-align: center; margin-top: 15px;">TiOLi AI Investments — For the ultimate good of Humanity and Agents</p>
                </div>
                """,
            },
            "toRecipients": [
                {"emailAddress": {"address": recipient_email}}
            ],
        },
        "saveToSentItems": "false",
    }

    try:
        response = httpx.post(
            f"https://graph.microsoft.com/v1.0/users/{sender_email}/sendMail",
            json=email_body,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        response.raise_for_status()
        logger.info(f"Verification code sent to {recipient_email} via Graph API")
        return True
    except Exception as e:
        logger.error(f"Failed to send email via Graph API: {e}")
        return False


def _send_via_smtp(email_code: str) -> bool:
    """Fallback: send email via SMTP (only works if port 587 is unblocked)."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_host = os.environ.get("SMTP_HOST", "smtp.office365.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")

    if not smtp_user or not smtp_password:
        logger.warning("Email verification skipped — SMTP not configured")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_user
    msg["To"] = settings.owner_email
    msg["Subject"] = "TiOLi AI Transact Exchange — Login Code"

    text_body = f"""TiOLi AI Transact Exchange — Login Verification Code

Your login verification code is: {email_code}

This code expires in 10 minutes and can only be used once.

If you did not initiate this login, please ignore this email.

---
TiOLi AI Investments
For the ultimate good of Humanity and Agents
"""

    msg.attach(MIMEText(text_body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        logger.info(f"Verification code sent to {settings.owner_email} via SMTP")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email via SMTP: {e}")
        return False
