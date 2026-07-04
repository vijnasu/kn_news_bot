"""Render a NewsItem into channel-specific post text."""

import config
from models import NewsItem

FACEBOOK_TAGS = ["Vedavidhya", "Kannada", "SanatanaDharma", "CurrentAffairs"]


def build_telegram_text(item: NewsItem) -> str:
    emoji = config.CATEGORY_EMOJI.get(item.category, config.CATEGORY_EMOJI["default"])
    lines = [f"{emoji} {item.title}", ""]
    if item.analysis_text:
        lines.append(item.analysis_text.strip())
    elif item.summary:
        lines.append(item.summary)
        lines.append("")
    lines.append(f"ಮೂಲ: {item.source} | {item.link}")
    return "\n".join(lines)


def build_analysis_text(item: NewsItem, analysis: str) -> str:
    emoji = config.CATEGORY_EMOJI.get(item.category, config.CATEGORY_EMOJI["default"])
    lines = [
        f"{emoji} {item.title}",
        "",
        analysis.strip(),
        "",
        f"ಮೂಲ: {item.source} | {item.link}",
    ]
    return "\n".join(line for line in lines if line)


def build_facebook_text(item: NewsItem, analysis: str) -> str:
    tags = " ".join(f"#{tag}" for tag in FACEBOOK_TAGS)
    lines = [
        item.title.strip(),
        "",
        analysis.strip(),
        "",
        f"ಮೂಲ: {item.source}",
        item.link,
        "",
        tags,
    ]
    return "\n".join(line for line in lines if line)
