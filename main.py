"""Orchestrates one run: fetch -> dedupe -> store -> post -> export.

Run manually:
    python main.py

Run without posting (dry run, just fetch+store+export - useful for testing
the analytics pipeline without touching Telegram):
    python main.py --dry-run

Schedule it (e.g. cron) to run every 10-15 minutes for a "fast news" feel:
    */10 * * * * cd /path/to/kn_news_bot && /usr/bin/python3 main.py >> run.log 2>&1
"""

import argparse
import time
from datetime import datetime, timezone, timedelta

import config
import store
import fetch
import scrape
from models import NewsItem
from formatter import build_telegram_text

IST = timezone(timedelta(hours=5, minutes=30))


def run(dry_run: bool = False):
    store.init_db()
    raw_items = fetch.fetch_all() + scrape.fetch_all_scraped()
    total_sources = len(config.SOURCES) + len(config.SCRAPE_SOURCES)
    print(f"[main] fetched {len(raw_items)} raw entries across {total_sources} sources")

    new_count, posted_count = 0, 0
    for raw in raw_items:
        if store.exists(raw["id"]):
            continue  # already seen, skip (this is how we stay "fast" without duplicates)

        item = NewsItem(**raw)
        store.insert(item)
        new_count += 1

        if not dry_run:
            try:
                text = build_telegram_text(item)
                message_id = __import__("telegram_post").send_post(text, item.image_url)
                store.mark_posted(item.id, message_id, datetime.now(tz=IST).isoformat())
                posted_count += 1
                time.sleep(config.POST_DELAY_SECONDS)
            except Exception as exc:
                print(f"[main] failed to post '{item.title[:40]}...': {exc}")

    rows = store.export_jsonl()
    print(f"[main] {new_count} new items stored, {posted_count} posted, "
          f"{rows} total rows exported to {config.JSONL_EXPORT_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                         help="fetch/store/export only, do not post to Telegram")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
