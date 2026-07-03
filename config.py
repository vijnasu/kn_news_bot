"""
Configuration for the Kannada Fast News Telegram bot.

Fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID via environment variables
(or a .env file loaded by main.py) - never commit real secrets to source control.
"""

import os

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
# Channel username (e.g. "@my_kannada_news") or numeric chat id (e.g. -1001234567890)
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")

# --- Storage ---
DB_PATH = os.environ.get("KN_NEWS_DB", "news.db")
JSONL_EXPORT_PATH = os.environ.get("KN_NEWS_JSONL", "news_export.jsonl")

# --- Behaviour ---
MAX_ITEMS_PER_RUN = 15           # cap per source per run, avoids flooding the channel
POST_DELAY_SECONDS = 4           # gap between posts, avoids Telegram rate limits
SUMMARY_MAX_CHARS = 320          # soft cap - actual cut happens on a sentence/word boundary

# --- Sources ---
# name        : display name shown as the post's credited source
# url         : RSS/XML feed URL
# category    : default category tag if the feed doesn't already imply one
SOURCES = [
    {"name": "Prajavani", "url": "https://www.prajavani.net/feed", "category": "ಸಾಮಾನ್ಯ"},
    {"name": "TV9 Kannada", "url": "https://tv9kannada.com/feed", "category": "ಸಾಮಾನ್ಯ"},
    {"name": "Kannada Oneindia - ಕರ್ನಾಟಕ", "url": "https://kannada.oneindia.com/rss/feeds/kannada-news-fb.xml", "category": "ರಾಜ್ಯ"},
    {"name": "Kannada Oneindia - ಬೆಂಗಳೂರು", "url": "https://kannada.oneindia.com/rss/feeds/kannada-bengaluru-fb.xml", "category": "ಬೆಂಗಳೂರು"},
    {"name": "Kannada Oneindia - ಮನರಂಜನೆ", "url": "https://kannada.oneindia.com/rss/feeds/kannada-entertainment-fb.xml", "category": "ಮನರಂಜನೆ"},
    # Add more once you've verified the feed URL resolves to valid RSS/XML, e.g.:
    # {"name": "Kannada Prabha", "url": "https://www.kannadaprabha.com/rssfeed/", "category": "ಸಾಮಾನ್ಯ"},
    # {"name": "Vijaya Karnataka", "url": "https://vijaykarnataka.com/rss.cms", "category": "ಸಾಮಾನ್ಯ"},
]

# Emoji shown at the top of each post, keyed by category
CATEGORY_EMOJI = {
    "ಸಾಮಾನ್ಯ": "🔴",
    "ರಾಜ್ಯ": "🟠",
    "ಬೆಂಗಳೂರು": "🏙️",
    "ಮನರಂಜನೆ": "🎬",
    "ಕ್ರೀಡೆ": "🏏",
    "ಹಣಕಾಸು": "💰",
    "ರಾಜಕೀಯ": "🏛️",
    "ಅಪರಾಧ": "🚨",
    "default": "📰",
}
