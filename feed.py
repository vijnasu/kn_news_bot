"""Build a public RSS feed of analysis posts.

Why this exists: the bot can post straight to Telegram (works fine) but the
direct Facebook Graph API path (facebook_post.py) is blocked by a Meta-side
issue (token/permission/app-review - not something fixable from this code).
ViralDashboard already has the Facebook Page connected on its own, reviewed
integration, and can auto-publish from any RSS feed URL. So instead of
posting to Facebook directly, this module renders analysis items as an RSS
2.0 feed; a GitHub Actions step publishes it to GitHub Pages, and
ViralDashboard's "RSS Feeds Connect" + Automation polls that URL and posts to
the Page on our behalf.

Telegram keeps using the direct path (main.py / telegram_post.py) - this feed
is purely the Facebook leg.

Important: news.db does NOT persist across scheduled GitHub Actions runs
(each run is a fresh checkout - see DEPLOYMENT.md), so store.recent_analysis_
items() only ever reflects the current run's own DB. The committed feed XML
file, on the other hand, DOES persist (it's checked into git). So this
module reads back whatever is already in the committed feed, merges in
whatever new analysis item(s) this run produced, dedupes by guid, and keeps
a rolling window - otherwise every run would blow away the feed history with
just the 0-1 items its own ephemeral DB happened to contain.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as _xml_escape

import config
from models import NewsItem

FEED_PATH = Path("docs/analysis_feed.xml")
MAX_ITEMS = 30
FEED_TITLE = "Vedavidhya Consultants - Current Affairs Analysis"
FEED_LINK = config.STYLE_FACEBOOK_URL or "https://www.vedavidhya.com/"
FEED_DESCRIPTION = "Kannada current-affairs analysis, Sanatana-rooted, from Vedavidhya Consultants."
FACEBOOK_TAGS = ["Vedavidhya", "Kannada", "SanatanaDharma", "CurrentAffairs"]


@dataclass
class FeedEntry:
    guid: str
    title: str
    link: str
    pub_date: str  # already-formatted RFC 822 string
    description: str


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(tz=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(tz=timezone.utc)


def _sort_key(entry: FeedEntry) -> datetime:
    try:
        return parsedate_to_datetime(entry.pub_date)
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)


def _cdata(text: str) -> str:
    # CDATA sidesteps entity-escaping for Kannada punctuation/em-dashes/quotes;
    # only the literal sequence "]]>" would break it, which real prose never
    # contains, but we still guard for it defensively.
    safe = (text or "").replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[{safe}]]>"


def _entry_from_item(item: NewsItem) -> FeedEntry:
    pub_dt = _parse_dt(item.posted_at or item.published_at)
    tags_line = " ".join(f"#{t}" for t in FACEBOOK_TAGS)
    description = f"{(item.analysis_text or '').strip()}\n\nಮೂಲ: {item.source}\n\n{tags_line}"
    return FeedEntry(
        guid=item.id,
        title=item.title,
        link=item.link or FEED_LINK,
        pub_date=format_datetime(pub_dt),
        description=description,
    )


def _read_existing_entries(path: Path) -> list[FeedEntry]:
    if not path.exists():
        return []
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return []
    entries = []
    for item_el in tree.getroot().iter("item"):
        guid = (item_el.findtext("guid") or "").strip()
        if not guid:
            continue
        entries.append(
            FeedEntry(
                guid=guid,
                title=(item_el.findtext("title") or "").strip(),
                link=(item_el.findtext("link") or "").strip(),
                pub_date=(item_el.findtext("pubDate") or "").strip(),
                description=(item_el.findtext("description") or "").strip(),
            )
        )
    return entries


def _entry_xml(entry: FeedEntry) -> str:
    link = _xml_escape(entry.link)
    guid = _xml_escape(entry.guid)
    return (
        "    <item>\n"
        f"      <title>{_cdata(entry.title)}</title>\n"
        f"      <link>{link}</link>\n"
        f'      <guid isPermaLink="false">{guid}</guid>\n'
        f"      <pubDate>{entry.pub_date}</pubDate>\n"
        f"      <description>{_cdata(entry.description)}</description>\n"
        "    </item>"
    )


def build_rss_feed(entries: list[FeedEntry]) -> str:
    now = format_datetime(datetime.now(tz=timezone.utc))
    items_xml = "\n".join(_entry_xml(e) for e in entries)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        "  <channel>\n"
        f"    <title>{_xml_escape(FEED_TITLE)}</title>\n"
        f"    <link>{_xml_escape(FEED_LINK)}</link>\n"
        f"    <description>{_xml_escape(FEED_DESCRIPTION)}</description>\n"
        "    <language>kn</language>\n"
        f"    <lastBuildDate>{now}</lastBuildDate>\n"
        f"{items_xml}\n"
        "  </channel>\n"
        "</rss>\n"
    )


def write_feed(new_items: list[NewsItem], path: Path | None = None) -> Path:
    """Merge this run's analysis items into whatever feed is already
    committed, dedupe by guid (newest wins), sort newest-first, cap to
    MAX_ITEMS, and write. Safe to call every run even when new_items is
    empty - it just re-serializes the existing window."""
    target = path or FEED_PATH
    existing = _read_existing_entries(target)
    new_entries = [_entry_from_item(item) for item in new_items]

    merged: dict[str, FeedEntry] = {}
    for entry in existing:
        merged[entry.guid] = entry
    for entry in new_entries:
        merged[entry.guid] = entry  # this run's version wins on conflict

    ordered = sorted(merged.values(), key=_sort_key, reverse=True)[:MAX_ITEMS]

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_rss_feed(ordered), encoding="utf-8")
    return target
