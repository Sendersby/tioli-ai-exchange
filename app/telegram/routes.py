"""Telegram Bot — webhook endpoint and admin routes."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger("telegram.routes")
router = APIRouter(prefix="/api/v1/telegram", tags=["Telegram Bot"])


def _check_enabled():
    if not settings.telegram_bot_enabled:
        raise HTTPException(status_code=404, detail="Telegram bot is not enabled")


class WebhookUpdate(BaseModel):
    """Minimal Telegram Update structure."""
    update_id: int
    message: dict | None = None


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Receive incoming Telegram updates via webhook."""
    _check_enabled()

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    message = body.get("message")
    if not message:
        return {"ok": True}  # Ignore non-message updates

    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    user = message.get("from", {})
    telegram_user_id = user.get("id")
    username = user.get("username")

    if not text or not chat_id or not telegram_user_id:
        return {"ok": True}

    # Parse command
    if not text.startswith("/"):
        return {"ok": True}  # Ignore non-commands

    parts = text.split(maxsplit=1)
    command = parts[0].lstrip("/").split("@")[0].lower()  # Strip bot mention
    args = parts[1] if len(parts) > 1 else ""

    # Dispatch to handler
    from app.telegram.handlers import COMMAND_HANDLERS
    handler = COMMAND_HANDLERS.get(command)
    if not handler:
        response_text = f"Unknown command: /{command}\nUse /help for available commands."
    else:
        try:
            if command == "link":
                response_text = await handler(telegram_user_id, chat_id, args, username=username)
            else:
                response_text = await handler(telegram_user_id, chat_id, args)
        except Exception as e:
            logger.error(f"Telegram handler error for /{command}: {e}")
            response_text = "Something went wrong. Please try again."

    # Send response
    await _send_message(chat_id, response_text)
    return {"ok": True}


@router.get("/status")
async def telegram_status():
    """Bot status and configuration check."""
    _check_enabled()
    return {
        "enabled": settings.telegram_bot_enabled,
        "token_configured": bool(settings.telegram_bot_token),
        "webhook_url": settings.telegram_webhook_url or "not configured",
    }


@router.post("/setup-webhook")
async def setup_webhook():
    """Register the webhook URL with Telegram API."""
    _check_enabled()

    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN not configured")
    if not settings.telegram_webhook_url:
        raise HTTPException(status_code=400, detail="TELEGRAM_WEBHOOK_URL not configured")

    import httpx
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json={
            "url": settings.telegram_webhook_url,
            "allowed_updates": ["message"],
        })

    if resp.status_code == 200:
        data = resp.json()
        return {"success": data.get("ok", False), "description": data.get("description", "")}

    raise HTTPException(status_code=502, detail=f"Telegram API error: {resp.status_code}")


async def _send_message(chat_id: int, text: str):
    """Send a message to a Telegram chat."""
    if not settings.telegram_bot_token:
        return

    import httpx
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
            })
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
