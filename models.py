"""Shared data schema for a news item. This is the single source of truth
for what gets stored for downstream analytics - the Telegram post text is
just one *rendering* of this record, never the record itself."""

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class NewsItem:
    id: str                 # sha256(link) - stable dedup key
    title: str               # Kannada headline
    summary: str             # short cleaned summary (HTML stripped, truncated)
    link: str                # canonical article URL
    source: str               # display name, e.g. "Prajavani"
    category: str             # e.g. "ರಾಜ್ಯ", "ಕ್ರೀಡೆ", "ಮನರಂಜನೆ"
    language: str             # "kn"
    published_at: str         # ISO 8601, from the feed (IST)
    fetched_at: str           # ISO 8601, when our bot pulled it
    image_url: Optional[str] = None
    posted_at: Optional[str] = None       # ISO 8601, when sent to Telegram
    telegram_message_id: Optional[int] = None
    tags: Optional[str] = None            # comma-separated hashtags actually used
    analysis_text: Optional[str] = None   # cached short analysis, if generated

    def to_dict(self) -> dict:
        return asdict(self)
