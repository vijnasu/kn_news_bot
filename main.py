"""Fetch, rank, analyze, and post news to Telegram."""

import argparse
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import config
import store
import fetch
import scrape
from analyzer import (
    build_english_analysis,
    COSTLY_HINTS,
    POLICY_HINTS,
    EXCLUDE_HINTS,
    SOURCE_EXCLUDE_HINTS,
    URL_EXCLUDE_HINTS,
)
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


def _post_to_destinations(item: NewsItem) -> dict:
    results = {"telegram": []}
    import telegram_post

    telegram_text = build_telegram_text(item)
    for chat_id in config.TELEGRAM_CHANNEL_IDS or []:
        message_id = telegram_post.send_post(telegram_text, item.image_url, chat_id=chat_id)
        results["telegram"].append((chat_id, message_id))
    return results


def _post_english_analysis(item: NewsItem, analysis: str) -> dict:
    """Post the once-per-run English-sourced (then Kannada-translated)
    analysis to the analysis destinations only - it never goes to the main
    headline channel, which stays pure Kannada-RSS content."""
    results = {"telegram_analysis": [], "facebook": None}
    import telegram_post

    analysis_text = build_analysis_text(item, analysis)
    for chat_id in config.TELEGRAM_ANALYSIS_CHANNEL_IDS or []:
        message_id = telegram_post.send_post(
            analysis_text,
            item.image_url,
            chat_id=chat_id,
            bot_token=config.TELEGRAM_ANALYSIS_BOT_TOKEN,
        )
        results["telegram_analysis"].append((chat_id, message_id))

    if _facebook_enabled():
        import facebook_post

        fb_text = build_facebook_text(item, analysis)
        results["facebook"] = facebook_post.send_post(fb_text, link=item.link)
    return results


def _print_analysis_preview(item: NewsItem, analysis: str) -> None:
    print("[preview] ----------------------------------------")
    print(f"[preview] {item.title}")
    print(f"[preview] source: {item.source}")
    print(f"[preview] link: {item.link}")
    print("[preview] analysis:")
    print(analysis.strip())
    print("[preview] ----------------------------------------")


KARNATAKA_HINTS = (
    "karnataka", "bengaluru", "bangalore", "mysuru", "mysore", "mangaluru",
    "mangalore", "hubli", "hubballi", "dharwad", "belagavi", "belgaum",
    "kalaburagi", "gulbarga", "shivamogga", "shimoga", "tumakuru", "tumkur",
    "udupi", "davangere", "ballari", "bellary", "hassan", "chikkamagaluru",
    "kodagu", "coorg", "vijayapura", "bijapur", "raichur", "bagalkot",
    "haveri", "yadgir", "kolar", "chitradurga", "gadag", "ramanagara",
)


def _is_karnataka_item(i: NewsItem) -> bool:
    blob = f"{i.title} {i.summary} {i.category}".lower()
    source = (i.source or "").lower()
    return "karnataka" in source or "bengaluru" in source or any(h in blob for h in KARNATAKA_HINTS)


def _select_english_item(items: list[NewsItem]) -> NewsItem | None:
    """Pick the single most relevant English story for this run's analysis.
    Reuses the same keyword lists the old Kannada should_analyze() used -
    they're already English strings, so they work unmodified here.

    Karnataka-relevant stories are preferred outright: they're ranked ahead
    of every non-Karnataka story regardless of keyword score, so the analysis
    channel favors local news whenever an unseen Karnataka story exists this
    run, falling back to national/international only when none is available."""

    def blob(i: NewsItem) -> str:
        return f"{i.title} {i.summary} {i.category} {i.source}".lower()

    def score(i: NewsItem) -> int:
        b = blob(i)
        return sum(1 for h in POLICY_HINTS if h in b) + sum(1 for h in COSTLY_HINTS if h in b)

    candidates = []
    for i in items:
        b = blob(i)
        url_b = (i.link or "").lower()
        if (
            any(h in b for h in EXCLUDE_HINTS)
            or any(h in b for h in SOURCE_EXCLUDE_HINTS)
            or any(h in url_b for h in URL_EXCLUDE_HINTS)
        ):
            continue
        candidates.append(i)
    if not candidates:
        candidates = items
    if not candidates:
        return None
    candidates.sort(
        key=lambda i: (_is_karnataka_item(i), score(i), _parse_iso(i.published_at)),
        reverse=True,
    )
    return candidates[0]


def _run_english_analysis(dry_run: bool, preview_analysis: bool) -> None:
    """Fetch English wire feeds, pick one relevant story, analyze it with
    Gemini in English, translate the result to Kannada with Groq, and post
    it once. Replaces the old per-Kannada-item Gemini pipeline as the sole
    cost driver in this project - see analyzer.py for the rationale."""
    if not config.ENGLISH_ANALYSIS_ENABLED:
        return
    if not dry_run and not preview_analysis and not (_telegram_analysis_enabled() or _facebook_enabled()):
        return

    raw_english = fetch.fetch_english()
    unseen = [NewsItem(**raw) for raw in raw_english if not store.exists(raw["id"])]
    print(f"[main] fetched {len(raw_english)} english entries across {len(config.ENGLISH_SOURCES)} sources, {len(unseen)} unseen")
    chosen = _select_english_item(unseen)
    if not chosen:
        print("[main] no unseen english story available for analysis this run")
        return

    result = build_english_analysis(chosen)
    if not result:
        print(f"[main] no acceptable analysis produced for '{chosen.title[:40]}...'; skipping")
        return
    kannada_title, kannada_body = result

    translated_item = NewsItem(
        id=chosen.id,
        title=kannada_title,
        summary=chosen.summary,
        link=chosen.link,
        source=chosen.source,
        category=chosen.category,
        language="kn",
        published_at=chosen.published_at,
        fetched_at=chosen.fetched_at,
        image_url=chosen.image_url,
    )

    if preview_analysis:
        _print_analysis_preview(translated_item, kannada_body)

    if dry_run:
        return

    result = _post_english_analysis(translated_item, kannada_body)
    sent_count = len(result["telegram_analysis"]) + (1 if result["facebook"] else 0)
    if sent_count == 0:
        print("[main] english analysis produced but no destination accepted it")
        return
    store.insert(translated_item)
    store.save_analysis(translated_item.id, kannada_body)
    store.mark_posted(translated_item.id, None, datetime.now(tz=IST).isoformat())
    print(f"[main] posted english-sourced analysis: '{kannada_title[:40]}...'")


def run(dry_run: bool = False, preview_analysis: bool = False, preview_limit: int = 3):
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

    store.init_db()
    raw_items = fetch.fetch_all() + scrape.fetch_all_scraped()
    total_sources = len(config.SOURCES) + len(config.SCRAPE_SOURCES)
    print(f"[main] fetched {len(raw_items)} raw entries across {total_sources} sources")
    print(
        "[main] routing: "
        f"telegram_channels={len(config.TELEGRAM_CHANNEL_IDS)}, "
        f"analysis_channels={len(config.TELEGRAM_ANALYSIS_CHANNEL_IDS)}"
    )

    new_items = []
    for raw in raw_items:
        if store.exists(raw["id"]):
            continue
        item = NewsItem(**raw)
        store.insert(item)
        new_items.append(item)

    post_candidates = _top_items_for_posting(new_items)
    if len(post_candidates) < max(0, config.TOP_POSTS_PER_RUN):
        backlog_limit = max(0, config.TOP_POSTS_PER_RUN) * 5
        backlog_items = store.recent_unposted(limit=backlog_limit)
        selected_ids = {item.id for item in post_candidates}
        refill = [item for item in backlog_items if item.id not in selected_ids]
        combined_pool = post_candidates + refill
        post_candidates = _top_items_for_posting(combined_pool)

    print(f"[main] selected {len(post_candidates)} post candidates (new={len(new_items)})")

    posted_count = 0
    post_errors = []

    # Analysis is now a single, separate English-sourced pipeline (see
    # _run_english_analysis) instead of per-item Kannada Gemini calls, so it
    # is decoupled from the plain-headline posting loop below.
    try:
        _run_english_analysis(dry_run, preview_analysis)
    except Exception as exc:
        print(f"[main] english analysis pipeline failed: {exc}")

    if not dry_run:
        for idx, item in enumerate(post_candidates):
            try:
                result = _post_to_destinations(item)
                sent_count = len(result["telegram"])
                if sent_count == 0:
                    raise RuntimeError("No destinations received this item (check Telegram channel config)")
                store.mark_posted(item.id, result["telegram"][0][1], datetime.now(tz=IST).isoformat())
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
    parser.add_argument("--preview-analysis", action="store_true", help="print generated analysis for selected items during the run")
    parser.add_argument("--preview-limit", type=int, default=3, help="maximum number of analysis items to preview")
    args = parser.parse_args()
    run(dry_run=args.dry_run, preview_analysis=args.preview_analysis, preview_limit=args.preview_limit)
