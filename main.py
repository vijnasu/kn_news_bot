"""Fetch and post plain Kannada headlines, and generate/post original
classical-content pieces (Vedic Astrology, Tantra, Vedic Science,
Dharmashastra, Arthashastra, Nyayashastra, Itihasa, Panchatantra, classical
arts/literature) - see classical_content.py and DEPLOYMENT.md."""

import argparse
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import config
import store
import fetch
import scrape
import feed
import classical_content
import content_state
import posted_store
from dedupe import dedupe_near_duplicates
from analyzer import (
    COSTLY_HINTS,
    POLICY_HINTS,
    EXCLUDE_HINTS,
    SOURCE_EXCLUDE_HINTS,
    URL_EXCLUDE_HINTS,
    is_other_state_item,
)
from formatter import build_telegram_text, build_classical_analysis_text, build_classical_facebook_text
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
    # Collapse the same real-world story reported by multiple sources (each
    # with a different link/id) down to one representative before applying
    # the per-source cap below - otherwise "unique by URL" still lets 3-4
    # outlets' versions of the identical story all get posted separately.
    ranked = dedupe_near_duplicates(ranked)
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


def _post_classical_content(item: NewsItem, body: str, genre_label: str) -> dict:
    """Post one classical-content piece to the analysis destinations only -
    it never goes to the main headline channel, which stays pure Kannada-RSS
    content."""
    results = {"telegram_analysis": [], "facebook": None}
    import telegram_post

    analysis_text = build_classical_analysis_text(item, body, genre_label)
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

        fb_text = build_classical_facebook_text(item, body, genre_label)
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


def _select_news_item(items: list[NewsItem]) -> NewsItem | None:
    """Pick the single most relevant/unique news story to interpret this run.
    Reuses the same English-language keyword hints analyzer.py's old
    news-analysis pipeline used - they're already English strings, so they
    work unmodified here."""

    def blob(i: NewsItem) -> str:
        return f"{i.title} {i.summary} {i.category} {i.source}".lower()

    def score(i: NewsItem) -> int:
        b = blob(i)
        return sum(1 for h in POLICY_HINTS if h in b) + sum(1 for h in COSTLY_HINTS if h in b)

    # Geographic scope (Karnataka + genuinely national news only) is a hard
    # boundary - never relaxed, even if nothing else is left to pick from
    # this run. The content-type excludes below (entertainment/sports/
    # live-blog) still fall back to the broader pool rather than return
    # nothing, since those are "prefer not to" rather than an editorial
    # hard boundary - but only within the already geo-filtered set.
    in_scope = [i for i in items if not is_other_state_item(i)]

    candidates = []
    for i in in_scope:
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
        candidates = in_scope
    if not candidates:
        return None
    candidates.sort(key=lambda i: (score(i), _parse_iso(i.published_at)), reverse=True)
    return candidates[0]


def _run_classical_content(dry_run: bool, preview_analysis: bool) -> None:
    """Pick one real, unique, unseen news story and generate/post an original
    classical-content piece (Vedic Astrology, Tantra, Vedic Science,
    Dharmashastra, Arthashastra, Nyayashastra, Itihasa, Panchatantra,
    classical arts/literature) interpreting it, in a rotating genre
    (critique/debate/elaboration/story/correlation/guidance/lifestyle) and
    literary style - see classical_content.py's generate_post_from_news for
    the system/genre/style selection and prompt-building.

    Cadence is gated externally, not by cron frequency: content_state.json
    (committed to the repo, same mechanism as the RSS feed - see feed.py)
    tracks the last post time and recent system/genre/style history, so even
    though this function runs on every ~15-minute cron tick, it only actually
    generates+posts roughly every config.CLASSICAL_CONTENT_MIN_GAP_HOURS
    hours (default ~2-3 times/day). Dedup of which news story has already
    been used works the same way as the plain-headline pipeline above:
    store.exists() only catches items already seen THIS run (news.db doesn't
    persist across scheduled runs), so posted_store.json is the real
    cross-run memory, and dedupe_near_duplicates() collapses the same story
    covered by both English sources (The Hindu / TOI) into one candidate
    before scoring."""
    if not config.ENGLISH_ANALYSIS_ENABLED:
        return
    if not dry_run and not preview_analysis and not (_telegram_analysis_enabled() or _facebook_enabled()):
        return

    state = content_state.read_state()
    if not dry_run and not content_state.should_post_now(config.CLASSICAL_CONTENT_MIN_GAP_HOURS, state=state):
        print("[main] classical content: within min-gap window, skipping this run")
        return

    posted_registry = posted_store.load_posted_ids()
    raw_english = fetch.fetch_english()
    unseen = [
        NewsItem(**raw)
        for raw in raw_english
        if not store.exists(raw["id"]) and raw["id"] not in posted_registry
    ]
    unseen = sorted(unseen, key=lambda i: _parse_iso(i.published_at), reverse=True)
    unseen = dedupe_near_duplicates(unseen)
    print(f"[main] fetched {len(raw_english)} english entries across {len(config.ENGLISH_SOURCES)} sources, {len(unseen)} unseen after dedup")
    chosen = _select_news_item(unseen)
    if not chosen:
        print("[main] no unseen news story available for classical content this run")
        return

    result = classical_content.generate_post_from_news(chosen.title, chosen.summary, chosen.source, state.get("recent", []))
    if not result:
        print(f"[main] no acceptable classical content produced for '{chosen.title[:40]}...'; skipping")
        return

    now_ist = datetime.now(tz=IST).isoformat()
    fake_item = NewsItem(
        id=chosen.id,
        title=result["title"],
        summary=chosen.summary,
        link=chosen.link,
        # source = the real news outlet (e.g. "The Hindu - Karnataka"), so the
        # published post can cite where the story came from; category = the
        # classical system name, used by formatter.py/feed.py for emoji and
        # hashtag lookups. Previously both were set to the system name, which
        # left no way to render the actual source reference line.
        source=chosen.source,
        category=result["system"],
        language="kn",
        published_at=now_ist,
        fetched_at=now_ist,
    )
    genre_label = classical_content.GENRES[result["genre"]]["label"]

    if preview_analysis:
        _print_analysis_preview(fake_item, result["body"])

    if dry_run:
        return

    posted = _post_classical_content(fake_item, result["body"], genre_label)
    sent_count = len(posted["telegram_analysis"]) + (1 if posted["facebook"] else 0)
    if sent_count == 0:
        print("[main] classical content produced but no destination accepted it")
        return
    store.insert(fake_item)
    store.save_analysis(fake_item.id, result["body"])
    store.mark_posted(fake_item.id, None, datetime.now(tz=IST).isoformat())
    posted_store.mark_posted([chosen.id], datetime.now(tz=timezone.utc).isoformat())
    content_state.record_post(
        result["system"],
        result["subtopic"],
        result["genre"],
        datetime.now(tz=timezone.utc).isoformat(),
        state=state,
        style=result["style"],
    )
    print(
        f"[main] posted classical content: system={result['system']} genre={result['genre']} "
        f"news='{chosen.title[:40]}...'"
    )


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

    # news.db does not persist across scheduled GitHub Actions runs (fresh
    # checkout every run), so store.exists() alone cannot tell whether an
    # item was already posted in a PREVIOUS run - only within this one. This
    # was why the same top headline(s) kept getting reposted every ~15
    # minutes. posted_store.json is committed back to the repo (see
    # .github/workflows/post_news.yml), so it actually remembers across runs.
    posted_registry = posted_store.load_posted_ids()

    new_items = []
    for raw in raw_items:
        if store.exists(raw["id"]) or raw["id"] in posted_registry:
            continue
        item = NewsItem(**raw)
        store.insert(item)
        if is_other_state_item(item):
            # Editorial scope is Karnataka + genuinely national news, not
            # another state's regional affairs (e.g. a Daijiworld "national"
            # item that's actually about Tamil Nadu or Bihar). Still stored
            # above so store.exists() keeps it from being reconsidered every
            # run, but it never becomes a posting candidate.
            continue
        new_items.append(item)

    post_candidates = _top_items_for_posting(new_items)
    if len(post_candidates) < max(0, config.TOP_POSTS_PER_RUN):
        backlog_limit = max(0, config.TOP_POSTS_PER_RUN) * 5
        backlog_items = [
            i for i in store.recent_unposted(limit=backlog_limit) if i.id not in posted_registry
        ]
        selected_ids = {item.id for item in post_candidates}
        refill = [item for item in backlog_items if item.id not in selected_ids]
        combined_pool = post_candidates + refill
        post_candidates = _top_items_for_posting(combined_pool)

    print(f"[main] selected {len(post_candidates)} post candidates (new={len(new_items)})")

    posted_count = 0
    post_errors = []

    # Classical content is a separate pipeline (see _run_classical_content),
    # decoupled from the plain-headline posting loop below and from the news
    # cycle entirely - it generates original content, not news reactions.
    try:
        _run_classical_content(dry_run, preview_analysis)
    except Exception as exc:
        print(f"[main] classical content pipeline failed: {exc}")

    newly_posted_ids = []
    if not dry_run:
        for idx, item in enumerate(post_candidates):
            try:
                result = _post_to_destinations(item)
                sent_count = len(result["telegram"])
                if sent_count == 0:
                    raise RuntimeError("No destinations received this item (check Telegram channel config)")
                store.mark_posted(item.id, result["telegram"][0][1], datetime.now(tz=IST).isoformat())
                newly_posted_ids.append(item.id)
                posted_count += 1
                time.sleep(config.POST_DELAY_SECONDS)
            except Exception as exc:
                print(f"[main] failed to post '{item.title[:40]}...': {exc}")
                post_errors.append((item.id, str(exc)))

    if newly_posted_ids:
        posted_store.mark_posted(newly_posted_ids, datetime.now(tz=timezone.utc).isoformat())

    rows = store.export_jsonl()
    print(f"[main] {len(new_items)} new items stored, {posted_count} posted, {rows} total rows exported")

    # Regenerate the public classical-content RSS feed every run (cheap: one
    # DB read + one file write, no network calls) so it always reflects the
    # latest N posts. A free RSS-to-social tool (dlvr.it/IFTTT/etc.) polls
    # this feed URL and handles the Facebook leg, since the direct Graph API
    # path is currently blocked - see DEPLOYMENT.md.
    try:
        analysis_items = store.recent_analysis_items(limit=30)
        feed_path = feed.write_feed(analysis_items)
        print(f"[main] wrote {len(analysis_items)} item(s) to {feed_path}")
    except Exception as exc:
        print(f"[main] feed generation failed: {exc}")

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
