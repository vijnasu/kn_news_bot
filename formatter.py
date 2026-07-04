"""Render a NewsItem into channel-specific post text."""

import config
from classical_content import CLASSICAL_HASHTAGS, CLASSICAL_SYSTEM_EMOJI
from models import NewsItem

FACEBOOK_TAGS = ["Vedavidhya", "Kannada", "SanatanaDharma", "CurrentAffairs"]

# Fixed ad line appended to every classical-content post (never LLM-generated,
# so it can never be dropped, mistranslated, or paraphrased away).
CLASSICAL_CTA_LINE = (
    "🔮 ಜ್ಯೋತಿಷ್ಯ, ಆಯುರ್ವೇದ, ತಂತ್ರ ಮತ್ತು ವೈದಿಕ ಸಮಾಲೋಚನೆ ಹಾಗೂ ನಿಗೂಢ ವಿದ್ಯೆಗಳ ಕೋರ್ಸ್‌ಗಳಿಗಾಗಿ ಭೇಟಿ ನೀಡಿ: www.vedavidhya.com"
)


def _esc(text: str) -> str:
    """Escape the 3 characters Telegram's HTML parse_mode treats as markup
    (&, <, >) in dynamic content. Must be applied to every piece of RSS/LLM
    text before it goes into an HTML-mode message, or Telegram's API will
    either mis-render it or reject the whole message with a 400 'can't
    parse entities' error. Never apply this to the literal <b>/</b> tags we
    add ourselves - only to the dynamic strings interpolated around them."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_telegram_text(item: NewsItem) -> str:
    emoji = config.CATEGORY_EMOJI.get(item.category, config.CATEGORY_EMOJI["default"])
    lines = [f"{emoji} {_esc(item.title)}", ""]
    if item.summary:
        lines.append(_esc(item.summary))
        lines.append("")
    lines.append(f"ಮೂಲ: {_esc(item.source)} | {_esc(item.link)}")
    return "\n".join(lines)


def build_analysis_text(item: NewsItem, analysis: str) -> str:
    emoji = config.CATEGORY_EMOJI.get(item.category, config.CATEGORY_EMOJI["default"])
    # Real Telegram bold (HTML parse_mode <b>...</b>), not literal ** markdown
    # characters, which Telegram's default plain-text mode just prints as-is.
    # Blank-line separators between title / body / source link are kept as
    # real empty list entries and joined unconditionally below - the previous
    # version filtered with `if line`, which silently drops "" entries and
    # was why title/body/link ran together with no line break.
    title_line = f"{emoji} <b>{_esc(item.title)}</b>"
    ref_line = f"ಮೂಲ: {_esc(item.source)} | {_esc(item.link)}"
    lines = [title_line, "", _esc(analysis.strip()), "", ref_line]
    return "\n".join(lines)


def build_facebook_text(item: NewsItem, analysis: str) -> str:
    # Blank-line separators are real "" list entries and joined
    # unconditionally - filtering with `if line` (the previous version)
    # silently drops those "" entries and runs every section together.
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
    return "\n".join(lines)


# --- Classical-content rendering -------------------------------------------
#
# The classical-content pipeline (classical_content.py) doesn't have a news
# "source" to cite, so these render a system tag + genre label instead of
# the ಮೂಲ/link footer used above, and pull hashtags from the per-system map
# instead of the fixed news-analysis FACEBOOK_TAGS list.


def build_classical_analysis_text(item: NewsItem, body: str, genre_label: str) -> str:
    emoji = CLASSICAL_SYSTEM_EMOJI.get(item.category, "🕉️")
    title_line = f"{emoji} <b>{_esc(item.title)}</b>"
    tag_line = f"{genre_label} | {_esc(item.category)}"
    lines = [title_line, "", _esc(body.strip()), "", tag_line, "", _esc(CLASSICAL_CTA_LINE)]
    return "\n".join(lines)


def build_classical_facebook_text(item: NewsItem, body: str, genre_label: str) -> str:
    hashtags = ["Vedavidhya", "SanatanaDharma"] + CLASSICAL_HASHTAGS.get(item.category, [])
    tags_line = " ".join(f"#{tag}" for tag in hashtags)
    lines = [item.title.strip(), "", body.strip(), "", CLASSICAL_CTA_LINE, "", tags_line]
    return "\n".join(lines)
