"""Fetch, rank, analyze, and post news to Telegram."""

import argparse
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import config
import store
import fetch
import scrape
from analyzer import build_analysis, should_analyze
from formatter import build_telegram_text, build_analysis_text, build_facebook_text
from models import NewsItem

IST = timezone(timedelta(hours=5, minutes=30))


def _parse_iso(ts: str) -> datetime:
    if not ts:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _top_items_for_posting(items: list[NewsItem]) -> list[NewsItem]:
    ranked = sorted(items, key=lambda i: _parse_iso(i.published_at), reverse=True)
    picked, source_counts = [], defaultdict(int)
    for item in ranked:
        if len(picked) >= max(0, config.TOP_POSTS_PER_RUN):
            break
        if source_counts[item.source] >= max(1, config.MAX_POSTS_PER_SOURCE_PER_RUN):
            continue
        picked.append(item)
        source_counts[item.source] += 1
    return picked


def _facebook_enabled() -> bool:
    return (
        config.FACEBOOK_TARGET == "page"
        and config.FACEBOOK_PAGE_ID
        and config.FACEBOOK_PAGE_ACCESS_TOKEN
    ) or (
        config.FACEBOOK_TARGET == "group"
        and config.FACEBOOK_GROUP_ID
        and config.FACEBOOK_ACCESS_TOKEN
    )


def _telegram_analysis_enabled() -> bool:
    return bool(config.TELEGRAM_ANALYSIS_CHANNEL_IDS)


def _post_to_destinations(item: NewsItem, analysis: str | None = None) -> dict:
    results = {"telegram": [], "telegram_analysis": [], "facebook": None}
    import telegram_post

    telegram_text = build_telegram_text(item)
    for chat_id in config.TELEGRAM_CHANNEL_IDS or []:
        message_id = telegram_post.send_post(telegram_text, item.image_url, chat_id=chat_id)
        results["telegram"].append((chat_id, message_id))

    if analysis:
        analysis_text = build_analysis_text(item, analysis)
        for chat_id in config.TELEGRAM_ANALYSIS_CHANNEL_IDS or []:
            message_id = telegram_post.send_post(
                analysis_text,
                item.image_url,
                chat_id=chat_id,
                bot_token=config.TELEGRAM_ANALYSIS_BOT_TOKEN,
            )
            results["telegram_analysis"].append((chat_id, message_id))

    if _facebook_enabled() and analysis:
        import facebook_post

        fb_text = build_facebook_text(item, analysis)
        results["facebook"] = facebook_post.send_post(fb_text, link=item.link)
    return results


def run(dry_run: bool = False):
    if (
        not dry_run
        and not config.TELEGRAM_CHANNEL_IDS
        and not config.TELEGRAM_ANALYSIS_CHANNEL_IDS
        and not _facebook_enabled()
    ):
        raise RuntimeError(
            "No post destinations configured. Set TELEGRAM_CHANNEL_ID/TELEGRAM_CHANNEL_IDS "
            "for primary Telegram, and/or TELEGRAM_ANALYSIS_CHANNEL_IDS for analysis channel."
        )

    effective_max_analyses = max(0, config.MAX_AI_ANALYSES_PER_RUN)
    if not dry_run and effective_max_analyses > 0 and not _telegram_analysis_enabled() and not _facebook_enabled():
        print(
            "[main] analysis disabled for this run: no destination configured. "
            "Set TELEGRAM_ANALYSIS_CHANNEL_IDS (or TELEGRAM_LLM_CHANNEL_IDS) "
            "to enable analysis-channel posts."
        )
        effective_max_analyses = 0

    store.init_db()
    raw_items = fetch.fetch_all() + scrape.fetch_all_scraped()
    total_sources = len(config.SOURCES) + len(config.SCRAPE_SOURCES)
    print(f"[main] fetched {len(raw_items)} raw entries across {total_sources} sources")
    print(
        "[main] routing: "
        f"telegram_channels={len(config.TELEGRAM_CHANNEL_IDS)}, "
        f"analysis_channels={len(config.TELEGRAM_ANALYSIS_CHANNEL_IDS)}, "
        f"max_analyses={effective_max_analyses}"
    )

    new_items = []
    for raw in raw_items:
        if store.exists(raw["id"]):
            continue
        item = NewsItem(**raw)
        store.insert(item)
        new_items.append(item)

    post_candidates = _top_items_for_posting(new_items)
    analysis_pool = post_candidates if (_telegram_analysis_enabled() or _facebook_enabled()) else [item for item in post_candidates if should_analyze(item)]
    analysis_candidates = analysis_pool[:effective_max_analyses]
    analysis_ids = {item.id for item in analysis_candidates}
    print(f"[main] selected {len(post_candidates)} post candidates, {len(analysis_candidates)} with analysis")

    posted_count = 0
    post_errors = []
    if not dry_run:
        for idx, item in enumerate(post_candidates):
            try:
                analysis = build_analysis(item) if item.id in analysis_ids else None
                if analysis:
                    item.analysis_text = analysis
                    store.save_analysis(item.id, analysis)
                result = _post_to_destinations(item, analysis)
                sent_count = len(result["telegram"]) + len(result["telegram_analysis"]) + (1 if result["facebook"] else 0)
                if sent_count == 0:
                    raise RuntimeError("No destinations received this item (check Telegram/Facebook channel config)")
                telegram_results = result["telegram"] or result["telegram_analysis"]
                if telegram_results:
                    store.mark_posted(item.id, telegram_results[0][1], datetime.now(tz=IST).isoformat())
                posted_count += 1
                time.sleep(config.POST_DELAY_SECONDS)
            except Exception as exc:
                print(f"[main] failed to post '{item.title[:40]}...': {exc}")
                post_errors.append((item.id, str(exc)))

    rows = store.export_jsonl()
    print(f"[main] {len(new_items)} new items stored, {posted_count} posted, {rows} total rows exported")
    if post_errors:
        failed_ids = ", ".join(item_id for item_id, _ in post_errors[:5])
        raise RuntimeError(f"Posting failed for {len(post_errors)} item(s): {failed_ids}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="fetch/store/export only, do not post")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
