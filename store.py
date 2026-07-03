"""SQLite storage (source of truth for analytics) + a JSONL export helper
so the data can be dropped straight into pandas / any other tool."""

import json
import sqlite3
from contextlib import contextmanager

import config
from models import NewsItem

SCHEMA = """
CREATE TABLE IF NOT EXISTS news_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    link TEXT NOT NULL,
    source TEXT NOT NULL,
    category TEXT,
    language TEXT,
    published_at TEXT,
    fetched_at TEXT,
    image_url TEXT,
    posted_at TEXT,
    telegram_message_id INTEGER,
    tags TEXT,
    analysis_text TEXT
);
CREATE INDEX IF NOT EXISTS idx_news_source ON news_items(source);
CREATE INDEX IF NOT EXISTS idx_news_category ON news_items(category);
CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_at);
"""


@contextmanager
def _conn():
    conn = sqlite3.connect(config.DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _conn() as conn:
        conn.executescript(SCHEMA)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(news_items)").fetchall()}
        if "analysis_text" not in columns:
            conn.execute("ALTER TABLE news_items ADD COLUMN analysis_text TEXT")


def exists(item_id: str) -> bool:
    with _conn() as conn:
        row = conn.execute("SELECT 1 FROM news_items WHERE id = ?", (item_id,)).fetchone()
        return row is not None


def insert(item: NewsItem):
    d = item.to_dict()
    with _conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO news_items
               (id, title, summary, link, source, category, language,
                published_at, fetched_at, image_url, posted_at,
               telegram_message_id, tags, analysis_text)
               VALUES (:id, :title, :summary, :link, :source, :category, :language,
                       :published_at, :fetched_at, :image_url, :posted_at,
                       :telegram_message_id, :tags, :analysis_text)""",
            d,
        )


def mark_posted(item_id: str, message_id: int, posted_at: str):
    with _conn() as conn:
        conn.execute(
            "UPDATE news_items SET posted_at = ?, telegram_message_id = ? WHERE id = ?",
            (posted_at, message_id, item_id),
        )


def save_analysis(item_id: str, analysis_text: str):
    with _conn() as conn:
        conn.execute(
            "UPDATE news_items SET analysis_text = ? WHERE id = ?",
            (analysis_text, item_id),
        )


def export_jsonl(path: str = None):
    """Dump the full table to JSON Lines for analytics tools (pandas.read_json(path, lines=True))."""
    path = path or config.JSONL_EXPORT_PATH
    with _conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM news_items ORDER BY published_at DESC").fetchall()
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(dict(row), ensure_ascii=False) + "\n")
    return len(rows)
