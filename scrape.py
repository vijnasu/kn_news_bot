"""Lightweight HTML scraper for Kannada sources that don't expose RSS.

Daijiworld's Kannada section (daijiworld.com/kannada/...) has no feed - only
the main English site does. Its category listing pages consistently link to
articles via an href containing "newsDisplay?newsID=", regardless of CSS
classes/markup changes, so we key off that instead of fragile selectors.

Note: list pages only show a relative/absolute date string next to each
headline, not a machine-readable timestamp, so published_at here is set to
the scrape time (fetched_at) rather than the true publish time - close
enough for a "fast news" feed, but worth knowing for time-series analytics.
"""

import hashlib
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import config
from fetch import _clean_html  # reuse the same junk-stripping HTML cleaner

IST = timezone(timedelta(hours=5, minutes=30))
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; KannadaFastNewsBot/1.0)"}

# Substring that identifies an article link on Daijiworld's Kannada pages.
ARTICLE_HREF_HINT = "newsDisplay?newsID="
MIN_TITLE_CHARS = 8  # filters out empty/near-empty anchors (e.g. image wrappers)


def _make_id(link: str) -> str:
    return hashlib.sha256(link.encode("utf-8")).hexdigest()[:24]


def fetch_scrape_source(source: dict) -> list:
    resp = requests.get(source["url"], headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    items, seen_links = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ARTICLE_HREF_HINT not in href:
            continue

        title = _clean_html(str(a))
        if len(title) < MIN_TITLE_CHARS:
            continue  # usually the image-wrapper anchor around the same article

        link = href if href.startswith("http") else urljoin(source["url"], href)
        if link in seen_links:
            continue
        seen_links.add(link)

        now = datetime.now(tz=IST).isoformat()
        items.append(
            {
                "id": _make_id(link),
                "title": title,
                "summary": "",  # list pages don't expose body text; see module docstring
                "link": link,
                "source": source["name"],
                "category": source.get("category", "ಸಾಮಾನ್ಯ"),
                "language": "kn",
                "published_at": now,
                "fetched_at": now,
                "image_url": None,
            }
        )
        if len(items) >= config.MAX_ITEMS_PER_RUN:
            break

    return items


def fetch_all_scraped() -> list:
    all_items = []
    for source in config.SCRAPE_SOURCES:
        try:
            all_items.extend(fetch_scrape_source(source))
        except Exception as exc:
            print(f"[scrape] {source['name']} failed: {exc}")
    return all_items
