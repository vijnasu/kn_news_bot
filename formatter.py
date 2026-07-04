"""Render a NewsItem into channel-specific post text."""

import re
import unicodedata

import config
from models import NewsItem

DEFAULT_TAGS = ["KannadaNews", "ಕರ್ನಾಟಕ"]
FACEBOOK_TAGS = ["Vedavidhya", "Kannada", "SanatanaDharma", "CurrentAffairs"]


def _hashtag_token(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").strip()
    if not text:
        return ""
    text = re.split(r"\s[-–—]\s", text, maxsplit=1)[0]
    text = re.sub(r"[^\w]+", "", text, flags=re.UNICODE)
    return text


def _hashtags(item: NewsItem) -> str:
    tags = [item.category, item.source] + DEFAULT_TAGS
    seen, ordered = set(), []
    for tag in tags:
        token = _hashtag_token(tag)
        if token and token not in seen:
            seen.add(token)
            ordered.append(token)
    return " ".join(f"#{tag}" for tag in ordered)


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
        _hashtags(item),
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
