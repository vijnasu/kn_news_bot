"""Render a NewsItem into the 'fast news' Telegram post text.
This is presentation only - the analytics record (models.NewsItem) never
depends on how the text is formatted here."""

import config
from models import NewsItem

DEFAULT_TAGS = ["KannadaNews", "ಕರ್ನಾಟಕ"]


def _hashtags(item: NewsItem) -> str:
    tags = [item.category.replace(" ", ""), item.source.replace(" ", "")] + DEFAULT_TAGS
    seen, ordered = set(), []
    for t in tags:
        if t and t not in seen:
            seen.add(t)
            ordered.append(t)
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
