"""Telegram Bot — webhook endpoint with callback query support."""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.config import settings

logger = logging.getLogger("telegram.routes")
router = APIRouter(prefix="/api/v1/telegram", tags=["Telegram Bot"])


def _check_enabled():
    if not settings.telegram_bot_enabled:
        raise HTTPException(status_code=404, detail="Telegram bot is not enabled")


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """Receive incoming Telegram updates — messages and callback queries."""
    _check_enabled()

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Handle callback queries (inline button presses)
    callback_query = body.get("callback_query")
    if callback_query:
        return await _handle_callback_query(callback_query)

    # Handle regular messages
    message = body.get("message")
    if not message:
        return {"ok": True}

    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    user = message.get("from", {})
    telegram_user_id = user.get("id")
    username = user.get("username")

    if not text or not chat_id or not telegram_user_id:
        return {"ok": True}

    # Parse command
    if not text.startswith("/"):
        return {"ok": True}

    parts = text.split(maxsplit=1)
    command = parts[0].lstrip("/").split("@")[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    # Dispatch to handler
    from app.telegram.handlers import COMMAND_HANDLERS
    handler = COMMAND_HANDLERS.get(command)
    if not handler:
        await _send_message(chat_id, text=f"Unknown command: /{command}\nUse /help for available commands.")
        return {"ok": True}

    try:
        if command == "link":
            result = await handler(telegram_user_id, chat_id, args, username=username)
        else:
            result = await handler(telegram_user_id, chat_id, args)
    except Exception as e:
        logger.error(f"Telegram handler error for /{command}: {e}")
        result = {"text": "Something went wrong. Please try again."}

    # Send response (supports both str and dict with reply_markup)
    if isinstance(result, str):
        await _send_message(chat_id, text=result)
    elif isinstance(result, dict):
        await _send_message(chat_id, **result)

    return {"ok": True}


async def _handle_callback_query(callback_query: dict):
    """Handle inline keyboard button presses."""
    data = callback_query.get("data", "")
    user = callback_query.get("from", {})
    telegram_user_id = user.get("id")
    username = user.get("username")
    message = callback_query.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    callback_query_id = callback_query.get("id")

    if not data or not chat_id or not telegram_user_id:
        return {"ok": True}

    from app.telegram.handlers import handle_callback

    try:
        result = await handle_callback(data, telegram_user_id, chat_id, username=username)
    except Exception as e:
        logger.error(f"Telegram callback error for '{data}': {e}")
        result = {"text": "Something went wrong. Please try again."}

    # Answer the callback query (removes loading indicator on button)
    await _answer_callback(callback_query_id)

    # Send the response
    if isinstance(result, str):
        await _send_message(chat_id, text=result)
    elif isinstance(result, dict):
        await _send_message(chat_id, **result)

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
            "allowed_updates": ["message", "callback_query"],
        })

    if resp.status_code == 200:
        data = resp.json()
        return {"success": data.get("ok", False), "description": data.get("description", "")}

    raise HTTPException(status_code=502, detail=f"Telegram API error: {resp.status_code}")


# ─── Telegram API helpers ──────────────────────────────────────────

async def _send_message(chat_id: int, text: str = "", reply_markup: dict | None = None, **kwargs):
    """Send a message with optional inline keyboard."""
    if not settings.telegram_bot_token or not text:
        return

    import httpx
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning(f"Telegram sendMessage failed: {resp.status_code} — {resp.text[:200]}")
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")


async def _answer_callback(callback_query_id: str, text: str = ""):
    """Answer a callback query to remove the loading indicator."""
    if not settings.telegram_bot_token:
        return

    import httpx
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/answerCallbackQuery"

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json={
                "callback_query_id": callback_query_id,
                "text": text,
            })
    except Exception:
        pass
