"""Pull raw entries from each configured RSS source.

FIX (Kannada grammar bug): earlier version (a) fell back to raw HTML that
often contains "visit our section" CTA links, <aside> related-article links,
and infographic/FAQ blocks glued right onto the real article text, and
(b) truncated summaries with a hard character slice that could cut a word or
a Kannada vowel-sign/conjunct cluster in half. Both produced text that read
as broken/ungrammatical Kannada. This version strips non-body elements before
extracting text, and truncates only on a sentence or word boundary.
"""

import hashlib
import re
from datetime import datetime, timezone, timedelta

import feedparser
from bs4 import BeautifulSoup

import config

IST = timezone(timedelta(hours=5, minutes=30))

# Tags and class-name fragments that are never part of the actual article
# body - CTAs, related-article asides, infographic/FAQ widgets, embeds.
_JUNK_TAGS = ["script", "style", "aside", "figure", "iframe", "details", "nav"]
_JUNK_CLASS_HINTS = ("cta", "infographic", "inf-", "faq", "embed-header", "share", "related")

# Sentence-ending punctuation to prefer when truncating (Kannada commonly
# uses "." like English; "।" (danda) still shows up in some formal writing).
_SENTENCE_ENDERS = [". ", "। ", "! ", "? ", ".” ", "!” "]


def _clean_html(raw: str) -> str:
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")

    for tag in soup.find_all(_JUNK_TAGS):
        tag.decompose()

    for tag in soup.find_all(class_=True):
        classes = " ".join(tag.get("class", []))
        if any(hint in classes for hint in _JUNK_CLASS_HINTS):
            tag.decompose()

    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def _smart_truncate(text: str, max_chars: int) -> str:
    """Cut on a sentence boundary if possible, else a word boundary.
    Never slices mid-word/mid-character-cluster, which is what was
    producing garbled trailing words."""
    if len(text) <= max_chars:
        return text

    window = text[:max_chars]

    best_cut = -1
    for ender in _SENTENCE_ENDERS:
        idx = window.rfind(ender)
        if idx > best_cut:
            best_cut = idx + len(ender) - 1  # keep the punctuation, drop trailing space
    if best_cut > max_chars * 0.4:  # don't return a stub that's too short
        return text[: best_cut + 1].strip()

    # fall back to the last whitespace boundary, mark as truncated
    idx = window.rfind(" ")
    if idx > 0:
        window = window[:idx]
    return window.strip() + "…"


def _make_id(link: str) -> str:
    return hashlib.sha256(link.encode("utf-8")).hexdigest()[:24]


def _parse_date(entry) -> str:
    for field in ("published_parsed", "updated_parsed"):
        val = getattr(entry, field, None)
        if val:
            dt = datetime(*val[:6], tzinfo=timezone.utc).astimezone(IST)
            return dt.isoformat()
    return datetime.now(tz=IST).isoformat()


def _extract_image(entry) -> str:
    media = getattr(entry, "media_content", None) or getattr(entry, "media_thumbnail", None)
    if media:
        url = media[0].get("url")
        if url:
            return url
    if "links" in entry:
        for l in entry.links:
            if l.get("type", "").startswith("image"):
                return l.get("href")
    return None


def _raw_body(entry) -> str:
    """Prefer summary/description; only fall back to content:encoded (which
    tends to carry the CTA/infographic junk) when nothing else is present,
    and even then it now gets cleaned by _clean_html above."""
    summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
    if summary and summary.strip():
        return summary
    content_list = getattr(entry, "content", None)
    if content_list:
        return content_list[0].get("value", "")
    return ""


def fetch_source(source: dict, language: str = "kn") -> list:
    """Returns a list of raw dicts (not yet a NewsItem) for one source."""
    parsed = feedparser.parse(source["url"])
    items = []
    for entry in parsed.entries[: config.MAX_ITEMS_PER_RUN]:
        title = _clean_html(getattr(entry, "title", ""))
        link = getattr(entry, "link", "")
        if not link or not title:
            continue

        cleaned = _clean_html(_raw_body(entry))
        summary = _smart_truncate(cleaned, config.SUMMARY_MAX_CHARS)

        items.append(
            {
                "id": _make_id(link),
                "title": title,
                "summary": summary,
                "link": link,
                "source": source["name"],
                "category": source.get("category", "ಸಾಮಾನ್ಯ"),
                "language": language,
                "published_at": _parse_date(entry),
                "fetched_at": datetime.now(tz=IST).isoformat(),
                "image_url": _extract_image(entry),
            }
        )
    return items


def fetch_all() -> list:
    all_items = []
    for source in config.SOURCES:
        try:
            all_items.extend(fetch_source(source))
        except Exception as exc:  # keep going even if one feed is down
            print(f"[fetch] {source['name']} failed: {exc}")
    return all_items


def fetch_english() -> list:
    """Fetch English-language feeds used only as analysis input (see config.ENGLISH_SOURCES)."""
    all_items = []
    for source in config.ENGLISH_SOURCES:
        try:
            all_items.extend(fetch_source(source, language="en"))
        except Exception as exc:
            print(f"[fetch] {source['name']} failed: {exc}")
    return all_items
