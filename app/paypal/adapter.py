"""PayPal Adapter — OAuth, Payouts, Orders, Billing Agreements, Webhooks.

Implements the PayPalAdapterInterface per Section 5 of the brief.
Uses sandbox by default (PAYPAL_SANDBOX=true).
"""

import os
import base64
import logging
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

SANDBOX_URL = "https://api-m.sandbox.paypal.com"
LIVE_URL = "https://api-m.paypal.com"


class PayPalAdapter:
    """PayPal API adapter — all PayPal interactions go through here."""

    def __init__(self):
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    @property
    def base_url(self) -> str:
        return SANDBOX_URL if os.environ.get("PAYPAL_SANDBOX", "true").lower() == "true" else LIVE_URL

    @property
    def is_sandbox(self) -> bool:
        return os.environ.get("PAYPAL_SANDBOX", "true").lower() == "true"

    async def get_access_token(self) -> str:
        """OAuth 2.0 client credentials — cached until near expiry."""
        if self._token and self._token_expires_at and \
           self._token_expires_at > datetime.now(timezone.utc) + timedelta(seconds=60):
            return self._token

        client_id = os.environ.get("PAYPAL_CLIENT_ID", "")
        client_secret = os.environ.get("PAYPAL_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            raise ValueError("PayPal credentials not configured. Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET.")

        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v1/oauth2/token",
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
                timeout=15,
            )
            if resp.status_code != 200:
                raise ValueError(f"PayPal OAuth failed: {resp.status_code} {resp.text}")
            data = resp.json()
            self._token = data["access_token"]
            self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
            return self._token

    async def send_payout(
        self, recipient_email: str, usd_amount: float,
        note: str, idempotency_key: str
    ) -> dict:
        """Send a single payout via PayPal Payouts API v1."""
        token = await self.get_access_token()
        payload = {
            "sender_batch_header": {
                "sender_batch_id": idempotency_key,
                "email_subject": "TiOLi AI Investments — Commission Disbursement",
                "email_message": note,
            },
            "items": [{
                "recipient_type": "EMAIL",
                "amount": {"value": f"{usd_amount:.2f}", "currency": "USD"},
                "receiver": recipient_email,
                "note": note,
                "sender_item_id": f"{idempotency_key}_item",
            }],
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v1/payments/payouts",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            if resp.status_code not in (200, 201):
                raise ValueError(f"PayPal Payout failed: {resp.status_code} {resp.text}")

            data = resp.json()
            batch_header = data.get("batch_header", {})
            items = data.get("items", [{}])
            return {
                "batch_id": batch_header.get("payout_batch_id"),
                "item_id": items[0].get("payout_item_id") if items else None,
                "status": batch_header.get("batch_status"),
                "paypal_fee_usd": 0.0,  # Updated via webhook
            }

    async def check_payout_status(self, batch_id: str) -> dict:
        """Check payout batch status."""
        token = await self.get_access_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/v1/payments/payouts/{batch_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            if resp.status_code != 200:
                return {"error": f"Status check failed: {resp.status_code}"}
            data = resp.json()
            return {
                "batch_id": batch_id,
                "batch_status": data.get("batch_header", {}).get("batch_status"),
                "items": [
                    {
                        "item_id": item.get("payout_item_id"),
                        "status": item.get("transaction_status"),
                        "tx_id": item.get("transaction_id"),
                    }
                    for item in data.get("items", [])
                ],
            }

    async def create_billing_agreement_token(
        self, description: str, max_monthly_charge_usd: float
    ) -> dict:
        """Create billing agreement token for owner approval."""
        token = await self.get_access_token()
        payload = {
            "description": description,
            "payer": {"payment_method": "PAYPAL"},
            "plan": {
                "type": "MERCHANT_INITIATED_BILLING",
                "merchant_preferences": {
                    "return_url": "https://exchange.tioli.co.za/api/v1/owner/paypal/billing-agreement/complete",
                    "cancel_url": "https://exchange.tioli.co.za/dashboard",
                    "max_fail_attempts": "3",
                },
            },
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v1/payments/billing-agreements/",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            if resp.status_code not in (200, 201):
                raise ValueError(f"Billing agreement creation failed: {resp.status_code}")
            data = resp.json()
            approval_url = next(
                (link["href"] for link in data.get("links", []) if link["rel"] == "approval_url"),
                None
            )
            return {"token": data.get("token_id"), "approval_url": approval_url}

    async def execute_billing_agreement(self, ba_token: str) -> dict:
        """Execute billing agreement after owner approval."""
        token = await self.get_access_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v1/payments/billing-agreements/{ba_token}/agreement-execute",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=15,
            )
            if resp.status_code not in (200, 201):
                raise ValueError(f"Billing agreement execution failed: {resp.status_code}")
            data = resp.json()
            return {
                "agreement_id": data.get("id"),
                "status": data.get("state"),
                "payer_email": data.get("payer", {}).get("payer_info", {}).get("email"),
            }

    async def cancel_billing_agreement(self, agreement_id: str) -> bool:
        """Cancel an active billing agreement."""
        token = await self.get_access_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v1/payments/billing-agreements/{agreement_id}/cancel",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"note": "Cancelled by platform owner"},
                timeout=15,
            )
            return resp.status_code in (200, 204)

    async def create_order(
        self, usd_amount: float, description: str, idempotency_key: str
    ) -> dict:
        """Create a PayPal Order for one-time payment."""
        token = await self.get_access_token()
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {"currency_code": "USD", "value": f"{usd_amount:.2f}"},
                "description": description,
                "reference_id": idempotency_key,
            }],
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v2/checkout/orders",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            if resp.status_code not in (200, 201):
                raise ValueError(f"Order creation failed: {resp.status_code}")
            data = resp.json()
            approval_url = next(
                (link["href"] for link in data.get("links", []) if link["rel"] == "approve"),
                None
            )
            return {"order_id": data.get("id"), "approval_url": approval_url, "status": data.get("status")}

    async def capture_order(self, order_id: str) -> dict:
        """Capture an approved PayPal Order."""
        token = await self.get_access_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v2/checkout/orders/{order_id}/capture",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=15,
            )
            if resp.status_code not in (200, 201):
                raise ValueError(f"Order capture failed: {resp.status_code}")
            data = resp.json()
            captures = data.get("purchase_units", [{}])[0].get("payments", {}).get("captures", [{}])
            capture = captures[0] if captures else {}
            return {
                "capture_id": capture.get("id"),
                "status": data.get("status"),
                "amount_usd": float(capture.get("amount", {}).get("value", 0)),
                "paypal_fee_usd": float(
                    capture.get("seller_receivable_breakdown", {}).get("paypal_fee", {}).get("value", 0)
                ),
            }

    async def verify_webhook_signature(
        self, headers: dict, raw_body: bytes, webhook_id: str
    ) -> bool:
        """Verify PayPal webhook signature."""
        token = await self.get_access_token()
        payload = {
            "auth_algo": headers.get("paypal-auth-algo", ""),
            "cert_url": headers.get("paypal-cert-url", ""),
            "transmission_id": headers.get("paypal-transmission-id", ""),
            "transmission_sig": headers.get("paypal-transmission-sig", ""),
            "transmission_time": headers.get("paypal-transmission-time", ""),
            "webhook_id": webhook_id,
            "webhook_event": raw_body.decode() if isinstance(raw_body, bytes) else raw_body,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v1/notifications/verify-webhook-signature",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("verification_status") == "SUCCESS"
            return False

    async def health_check(self) -> dict:
        """Check PayPal API availability."""
        try:
            token = await self.get_access_token()
            return {"status": "UP", "sandbox": self.is_sandbox}
        except Exception as e:
            return {"status": "DOWN", "error": str(e), "sandbox": self.is_sandbox}
