"""Email verification via link — sends a verification email with a unique clickable link.

When the owner initiates a login challenge, this service:
1. Generates a unique email verification token
2. Sends an email to sendersby@tioli.onmicrosoft.com with a clickable link
3. When the link is clicked, the email factor is automatically verified
"""

import os
import secrets
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import settings

logger = logging.getLogger(__name__)

# Store email verification tokens: token -> challenge_id
_email_tokens: dict[str, str] = {}


def generate_email_token(challenge_id: str) -> str:
    """Generate a unique token for email verification."""
    token = secrets.token_urlsafe(48)
    _email_tokens[token] = challenge_id
    return token


def validate_email_token(token: str) -> str | None:
    """Validate and consume an email verification token.

    Returns the challenge_id if valid, None otherwise.
    Single-use — token is consumed on validation.
    """
    challenge_id = _email_tokens.pop(token, None)
    return challenge_id


def send_verification_email(challenge_id: str, email_token: str) -> bool:
    """Send the verification email with a clickable link.

    The link points to /auth/verify-email-link?token=<token>
    which auto-verifies the email factor when clicked.
    """
    smtp_host = os.environ.get("SMTP_HOST", "smtp.office365.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")

    if not smtp_user or not smtp_password:
        logger.warning("Email verification skipped — SMTP not configured")
        return False

    # Build the verification link
    base_url = os.environ.get("PLATFORM_URL", "https://exchange.tioli.co.za")
    verify_link = f"{base_url}/auth/verify-email-link?token={email_token}"

    # Build the email
    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_user
    msg["To"] = settings.owner_email
    msg["Subject"] = "TiOLi AI Transact Exchange — Login Verification"

    # Plain text version
    text_body = f"""TiOLi AI Transact Exchange — Login Verification

You are attempting to log in to the TiOLi AI Transact Exchange platform.

Click the link below to verify your email address:

{verify_link}

This link expires in 10 minutes and can only be used once.

If you did not initiate this login, please ignore this email.

---
TiOLi AI Investments
For the ultimate good of Humanity and Agents
"""

    # HTML version
    html_body = f"""
    <div style="font-family: 'Inter', Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 30px; background: #f5f5f3; border-radius: 12px;">
        <div style="background: #2b2b2b; padding: 20px; border-radius: 10px 10px 0 0; text-align: center; border-bottom: 3px solid #8fa88b;">
            <h1 style="color: #ffffff; margin: 0; font-size: 18px; letter-spacing: 0.5px;">TiOLi AI Transact Exchange</h1>
        </div>
        <div style="background: #ffffff; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #eae7e3;">
            <h2 style="color: #2b2b2b; margin-top: 0; font-size: 20px;">Login Verification</h2>
            <p style="color: #7a7a7a; line-height: 1.6;">You are attempting to log in to the TiOLi AI Transact Exchange platform. Click the button below to verify your email address.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{verify_link}" style="background: #6b8a66; color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 15px; display: inline-block;">Verify My Email</a>
            </div>
            <p style="color: #aaa; font-size: 12px; text-align: center;">This link expires in 10 minutes and can only be used once.</p>
            <p style="color: #aaa; font-size: 12px; text-align: center;">If you did not initiate this login, please ignore this email.</p>
        </div>
        <p style="color: #aaa; font-size: 11px; text-align: center; margin-top: 15px;">TiOLi AI Investments — For the ultimate good of Humanity and Agents</p>
    </div>
    """

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        logger.info(f"Verification email sent to {settings.owner_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email: {e}")
        return False
