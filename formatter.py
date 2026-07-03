"""Render a NewsItem into the 'fast news' Telegram post text.
This is presentation only - the analytics record (models.NewsItem) never
depends on how the text is formatted here."""

import config
from models import NewsItem


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
    return "\n".join(lines)
