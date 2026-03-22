"""Cost alert notifications — Email and WhatsApp.

Sends budget warnings to the platform owner via:
1. Email (Microsoft Graph API, SMTP fallback)
2. WhatsApp (via Twilio WhatsApp API)

Triggered automatically at warning (70%), critical (90%), and
auto-shutdown (100%) thresholds.
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Owner contact details
OWNER_EMAIL = settings.owner_email
OWNER_PHONE = settings.owner_phone


class AlertService:
    """Sends cost alerts via email and WhatsApp."""

    async def send_budget_alert(
        self, alert_level: str, spend: float, limit: float,
        pct_used: float, message: str = ""
    ) -> dict:
        """Send a budget alert to the owner via all configured channels."""
        subject = f"TiOLi Exchange — {alert_level} Budget Alert"

        if alert_level == "WARNING":
            emoji = "⚠️"
            urgency = "Your infrastructure spend has reached the warning threshold."
        elif alert_level == "CRITICAL":
            emoji = "🚨"
            urgency = "URGENT: Your infrastructure spend is approaching the limit."
        elif alert_level == "AUTO_SHUTDOWN":
            emoji = "🛑"
            urgency = "PLATFORM AUTO-SHUTDOWN: Budget limit exceeded. Platform is now OFF."
        else:
            emoji = "ℹ️"
            urgency = "Budget notification."

        body = (
            f"{emoji} {subject}\n\n"
            f"{urgency}\n\n"
            f"Current spend: ${spend:.2f}\n"
            f"Monthly limit: ${limit:.2f}\n"
            f"Usage: {pct_used:.1f}%\n"
            f"Remaining: ${max(0, limit - spend):.2f}\n\n"
        )

        if alert_level == "AUTO_SHUTDOWN":
            body += (
                "ACTION REQUIRED:\n"
                "The platform has been automatically shut down to prevent overspend.\n"
                "To reactivate: POST /api/infra/activate (requires owner auth)\n"
                "Or login to the dashboard and click Activate.\n\n"
            )
        elif alert_level == "CRITICAL":
            body += (
                "ACTION RECOMMENDED:\n"
                "Consider shutting down non-essential services.\n"
                "Auto-shutdown will trigger at 100% of budget.\n\n"
            )

        body += (
            f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Platform: TiOLi AI Transact Exchange\n"
            f"Dashboard: https://exchange.tioli.co.za/dashboard\n"
        )

        results = {"email": None, "whatsapp": None}

        # Send email
        results["email"] = await self._send_email(subject, body)

        # Send WhatsApp
        results["whatsapp"] = await self._send_whatsapp(body)

        return results

    async def _send_email(self, subject: str, body: str) -> dict:
        """Send email via Microsoft Graph API (primary) with SMTP fallback.

        Graph API works over HTTPS (port 443) — not affected by SMTP port blocks.
        """
        # Try Graph API first
        result = await self._send_via_graph(subject, body)
        if result.get("sent"):
            return result

        # Fallback to SMTP
        return await self._send_via_smtp(subject, body)

    async def _send_via_graph(self, subject: str, body: str) -> dict:
        """Send email via Microsoft Graph API."""
        tenant_id = os.environ.get("AZURE_TENANT_ID", "")
        client_id = os.environ.get("AZURE_CLIENT_ID", "")
        client_secret = os.environ.get("AZURE_CLIENT_SECRET", "")

        if not all([tenant_id, client_id, client_secret]):
            logger.warning("Graph API alert skipped — Azure credentials not configured")
            return {"sent": False, "reason": "Azure credentials not configured"}

        try:
            async with httpx.AsyncClient() as client:
                # Get access token
                token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
                token_resp = await client.post(token_url, data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials",
                }, timeout=15)

                if token_resp.status_code != 200:
                    logger.error(f"Graph API token failed: {token_resp.status_code}")
                    return {"sent": False, "reason": f"Token request failed: {token_resp.status_code}"}

                access_token = token_resp.json().get("access_token")

                # Send email
                sender = OWNER_EMAIL
                mail_url = f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail"
                mail_resp = await client.post(mail_url, headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                }, json={
                    "message": {
                        "subject": subject,
                        "body": {"contentType": "Text", "content": body},
                        "toRecipients": [{"emailAddress": {"address": OWNER_EMAIL}}],
                    },
                    "saveToSentItems": False,
                }, timeout=15)

                if mail_resp.status_code in (200, 202):
                    logger.info(f"Graph API alert sent to {OWNER_EMAIL}: {subject}")
                    return {"sent": True, "to": OWNER_EMAIL, "method": "graph_api"}
                else:
                    logger.error(f"Graph API send failed: {mail_resp.status_code} {mail_resp.text}")
                    return {"sent": False, "reason": f"Graph send failed: {mail_resp.status_code}"}

        except Exception as e:
            logger.error(f"Graph API alert failed: {e}")
            return {"sent": False, "error": str(e)}

    async def _send_via_smtp(self, subject: str, body: str) -> dict:
        """Send email via SMTP (fallback)."""
        smtp_host = os.environ.get("SMTP_HOST", "smtp.office365.com")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_password = os.environ.get("SMTP_PASSWORD", "")

        if not smtp_user or not smtp_password:
            logger.warning("SMTP alert skipped — credentials not configured")
            return {"sent": False, "reason": "SMTP credentials not configured"}

        try:
            msg = MIMEMultipart()
            msg["From"] = smtp_user
            msg["To"] = OWNER_EMAIL
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)

            logger.info(f"SMTP alert sent to {OWNER_EMAIL}: {subject}")
            return {"sent": True, "to": OWNER_EMAIL, "method": "smtp"}
        except Exception as e:
            logger.error(f"SMTP alert failed: {e}")
            return {"sent": False, "error": str(e)}

    async def _send_whatsapp(self, message: str) -> dict:
        """Send WhatsApp message via Twilio WhatsApp API.

        Set these environment variables:
          TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM
        """
        account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        from_number = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # Twilio sandbox default

        if not account_sid or not auth_token:
            logger.warning("WhatsApp alert skipped — Twilio credentials not configured")
            return {"sent": False, "reason": "Twilio credentials not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN env vars."}

        to_number = f"whatsapp:{OWNER_PHONE}"
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    auth=(account_sid, auth_token),
                    data={
                        "From": from_number,
                        "To": to_number,
                        "Body": message[:1600],  # WhatsApp message limit
                    },
                    timeout=15,
                )
                if resp.status_code in (200, 201):
                    logger.info(f"WhatsApp alert sent to {OWNER_PHONE}")
                    return {"sent": True, "to": OWNER_PHONE}
                else:
                    logger.error(f"WhatsApp alert failed: {resp.status_code} {resp.text}")
                    return {"sent": False, "error": f"Twilio returned {resp.status_code}"}
        except Exception as e:
            logger.error(f"WhatsApp alert failed: {e}")
            return {"sent": False, "error": str(e)}

    async def test_alerts(self) -> dict:
        """Send a test alert to verify email and WhatsApp are working."""
        return await self.send_budget_alert(
            alert_level="TEST",
            spend=0, limit=20, pct_used=0,
            message="This is a test alert from TiOLi AI Transact Exchange."
        )
