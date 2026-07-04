"""Persistent cadence + rotation state for the classical-content pipeline.

Why this exists: like feed.py, news.db does NOT persist across scheduled
GitHub Actions runs (fresh checkout every run — see DEPLOYMENT.md), so any
cross-run memory has to live in a file that gets committed back to the repo.
This tracks:

1. When the last classical-content post went out, so a cron that fires every
   15 minutes still only actually posts roughly every N hours (see
   config.CLASSICAL_CONTENT_MIN_GAP_HOURS).
2. Which (system, subtopic, genre) combinations were used recently, so
   classical_content.py's rotation doesn't repeat the same angle back-to-back.

The workflow commits docs/content_state.json alongside docs/analysis_feed.xml
in the same step (see .github/workflows/post_news.yml).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

STATE_PATH = Path("docs/content_state.json")
DEFAULT_STATE = {"last_posted_at": None, "recent": []}


def read_state(path: Path | None = None) -> dict:
    target = path or STATE_PATH
    if not target.exists():
        return dict(DEFAULT_STATE)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return dict(DEFAULT_STATE)
    return {**DEFAULT_STATE, **data}


def write_state(state: dict, path: Path | None = None) -> Path:
    target = path or STATE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def should_post_now(
    min_gap_hours: float,
    state: dict | None = None,
    path: Path | None = None,
    now: datetime | None = None,
) -> bool:
    """True if enough time has passed since the last classical-content post
    (or none has ever been posted) to allow another one this run."""
    state = state if state is not None else read_state(path)
    last = state.get("last_posted_at")
    if not last:
        return True
    now = now or datetime.now(timezone.utc)
    try:
        last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
    except ValueError:
        return True
    gap_hours = (now - last_dt).total_seconds() / 3600
    return gap_hours >= max(0.0, min_gap_hours)


def record_post(
    system: str,
    subtopic: str,
    genre: str,
    posted_at_iso: str,
    state: dict | None = None,
    path: Path | None = None,
    keep: int = 20,
    style: str | None = None,
) -> dict:
    state = state if state is not None else read_state(path)
    state["last_posted_at"] = posted_at_iso
    recent = list(state.get("recent", []))
    recent.append({"system": system, "subtopic": subtopic, "genre": genre, "style": style, "posted_at": posted_at_iso})
    state["recent"] = recent[-keep:]
    write_state(state, path)
    return state
