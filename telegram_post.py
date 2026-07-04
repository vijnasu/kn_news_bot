"""Minimal Telegram Bot API wrapper."""

import requests

import config

API_BASE = "https://api.telegram.org/bot{token}/{method}"


def _url(method: str, token: str = None) -> str:
    token = token or config.TELEGRAM_BOT_TOKEN
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    return API_BASE.format(token=token, method=method)


def send_post(
    text: str,
    image_url: str = None,
    chat_id: str = None,
    bot_token: str = None,
    parse_mode: str = "HTML",
) -> int:
    if not config.TELEGRAM_CHANNEL_IDS and not chat_id:
        raise RuntimeError("TELEGRAM_CHANNEL_IDS is not set")
    target = chat_id or config.TELEGRAM_CHANNEL_IDS[0]
    if image_url:
        payload = {"chat_id": target, "caption": text[:1024], "photo": image_url}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        resp = requests.post(_url("sendPhoto", bot_token), data=payload, timeout=20)
    else:
        payload = {"chat_id": target, "text": text[:4096], "disable_web_page_preview": False}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        resp = requests.post(_url("sendMessage", bot_token), data=payload, timeout=20)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    return data["result"]["message_id"]
