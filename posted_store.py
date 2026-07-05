"""Persistent cross-run registry of already-posted item ids.

Why this exists: news.db is gitignored and GitHub Actions checks out a fresh
copy of the repo on every scheduled run, so it starts EMPTY every ~15
minutes. store.exists()/store.recent_unposted() only ever reflect the
current run's own ephemeral database - they cannot actually tell whether an
item was posted in a previous run. In practice this meant the same top
headline(s) from each source kept getting re-fetched, found "unseen" (because
the fresh db has never heard of them), and re-posted on every run until the
source's RSS feed happened to rotate past them - the "dumping repeated news"
behavior reported on the plain-headline channel, and the identical bug
existed in the news-analyzer pipeline's "unseen" check (main.py's
_run_classical_content).

The fix follows the same pattern already used for feed.py/content_state.py:
persist the bit of cross-run memory that actually matters (here: which item
ids have already been posted) to a small JSON file that the workflow commits
back to the repo, and read it back at the start of every run.

Entries are pruned by age so the file stays small forever - RSS feeds churn
through new stories continuously, so remembering more than ~10 days of
history has no benefit and would only make the committed file grow
unbounded.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

POSTED_IDS_PATH = Path("state/posted_ids.json")
DEFAULT_MAX_AGE_DAYS = 10


def load_posted_ids(path: Path | None = None) -> dict[str, str]:
    """Return {item_id: iso_timestamp_first_posted}."""
    target = path or POSTED_IDS_PATH
    if not target.exists():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    ids = data.get("ids", data) if isinstance(data, dict) else {}
    return {str(k): str(v) for k, v in ids.items()} if isinstance(ids, dict) else {}


def _prune(ids: dict[str, str], max_age_days: int, now: datetime | None = None) -> dict[str, str]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, max_age_days))
    kept = {}
    for item_id, ts in ids.items():
        try:
            when = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            continue  # drop unparsable entries rather than keep them forever
        if when >= cutoff:
            kept[item_id] = ts
    return kept


def save_posted_ids(ids: dict[str, str], path: Path | None = None, max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> Path:
    target = path or POSTED_IDS_PATH
    pruned = _prune(ids, max_age_days)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"ids": pruned}, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def mark_posted(
    new_ids: list[str],
    when_iso: str,
    path: Path | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> dict[str, str]:
    """Re-read the current persisted registry, add new_ids, prune, and save.

    Deliberately reloads from disk instead of taking the caller's
    previously-loaded dict as a parameter: both the plain-headline pipeline
    and the news-analyzer pipeline call this within the same process run
    (main.py's run() and _run_classical_content()). If this took an
    in-memory snapshot from the caller, whichever of the two writes LAST
    would silently overwrite the other's update, since each loaded its own
    copy before the other had written anything. Always merging against the
    latest on-disk state avoids that lost-update bug."""
    current = load_posted_ids(path)
    for item_id in new_ids:
        if item_id:
            current[item_id] = when_iso
    pruned = _prune(current, max_age_days)
    save_posted_ids(pruned, path=path, max_age_days=max_age_days)
    return pruned
