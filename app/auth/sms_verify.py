"""SMS verification via Twilio — sends a 6-digit code to the owner's phone."""

import os
import logging
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def send_sms_code(phone_code: str) -> bool:
    """Send the 6-digit verification code via Twilio SMS."""
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_number = os.environ.get("TWILIO_FROM_NUMBER", "")

    if not all([account_sid, auth_token, from_number]):
        logger.warning("SMS verification skipped — Twilio not configured")
        return False

    to_number = settings.owner_phone

    try:
        response = httpx.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
            auth=(account_sid, auth_token),
            data={
                "From": from_number,
                "To": to_number,
                "Body": f"TiOLi Exchange login code: {phone_code}\n\nThis code expires in 10 minutes. Do not share it.",
            },
            timeout=10,
        )
        response.raise_for_status()
        logger.info(f"SMS code sent to {to_number}")
        return True
    except Exception as e:
        logger.error(f"Failed to send SMS: {e}")
        return False
