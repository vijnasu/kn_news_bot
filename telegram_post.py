"""Thin wrapper around the raw Telegram Bot API (no extra SDK dependency).
Docs: https://core.telegram.org/bots/api#sendmessage
"""

import requests

import config

API_BASE = "https://api.telegram.org/bot{token}/{method}"


def _url(method: str) -> str:
    if not config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set (see .env.example)")
    return API_BASE.format(token=config.TELEGRAM_BOT_TOKEN, method=method)


def send_post(text: str, image_url: str = None) -> int:
    """Sends the post to the configured channel and returns the Telegram message_id."""
    if not config.TELEGRAM_CHANNEL_ID:
        raise RuntimeError("TELEGRAM_CHANNEL_ID is not set (see .env.example)")

    if image_url:
        resp = requests.post(
            _url("sendPhoto"),
            data={
                "chat_id": config.TELEGRAM_CHANNEL_ID,
                "caption": text[:1024],  # Telegram caption limit
                "photo": image_url,
            },
            timeout=20,
        )
    else:
        resp = requests.post(
            _url("sendMessage"),
            data={
                "chat_id": config.TELEGRAM_CHANNEL_ID,
                "text": text[:4096],  # Telegram message limit
                "disable_web_page_preview": False,
            },
            timeout=20,
        )

    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    return data["result"]["message_id"]
