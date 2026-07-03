"""Render a NewsItem into the 'fast news' Telegram post text.
This is presentation only - the analytics record (models.NewsItem) never
depends on how the text is formatted here."""

import re
import unicodedata

import config
from models import NewsItem

DEFAULT_TAGS = ["KannadaNews", "ಕರ್ನಾಟಕ"]


def _hashtag_token(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").strip()
    if not text:
        return ""

    # Source names sometimes include separator text like " - ಕರ್ನಾಟಕ".
    # Keep the stable source name part, then strip punctuation so Telegram
    # sees a single valid hashtag token.
    text = re.split(r"\s[-–—]\s", text, maxsplit=1)[0]
    text = re.sub(r"[^\w]+", "", text, flags=re.UNICODE)
    return text


def _hashtags(item: NewsItem) -> str:
    tags = [item.category, item.source] + DEFAULT_TAGS
    seen, ordered = set(), []
    for t in tags:
        token = _hashtag_token(t)
        if token and token not in seen:
            seen.add(token)
            ordered.append(token)
    return " ".join(f"#{t}" for t in ordered)


def build_telegram_text(item: NewsItem) -> str:
    emoji = config.CATEGORY_EMOJI.get(item.category, config.CATEGORY_EMOJI["default"])
    lines = [
        f"{emoji} {item.title}",
        "",
    ]
    if item.summary:
        lines.append(item.summary)
        lines.append("")
    lines.append(f"📰 {item.source}  |  🔗 {item.link}")
    lines.append(_hashtags(item))
    return "\n".join(lines)
