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
TOP_POSTS_PER_RUN = int(os.environ.get("KN_NEWS_TOP_POSTS", "4"))
MAX_POSTS_PER_SOURCE_PER_RUN = int(os.environ.get("KN_NEWS_TOP_PER_SOURCE", "1"))

# --- RSS sources ---
# name        : display name shown as the post's credited source
# url         : RSS/XML feed URL
# category    : default category tag if the feed doesn't already imply one
SOURCES = [
    {"name": "Prajavani", "url": "https://www.prajavani.net/feed", "category": "ಸಾಮಾನ್ಯ"},
    {"name": "TV9 Kannada", "url": "https://tv9kannada.com/feed", "category": "ಸಾಮಾನ್ಯ"},
    {"name": "Kannada Oneindia - ಕರ್ನಾಟಕ", "url": "https://kannada.oneindia.com/rss/feeds/kannada-news-fb.xml", "category": "ರಾಜ್ಯ"},
    {"name": "Kannada Oneindia - ಬೆಂಗಳೂರು", "url": "https://kannada.oneindia.com/rss/feeds/kannada-bengaluru-fb.xml", "category": "ಬೆಂಗಳೂರು"},
    {"name": "Kannada Oneindia - ಮನರಂಜನೆ", "url": "https://kannada.oneindia.com/rss/feeds/kannada-entertainment-fb.xml", "category": "ಮನರಂಜನೆ"},
    {"name": "Public TV", "url": "https://publictv.in/feed", "category": "ಸಾಮಾನ್ಯ"},
    {"name": "Asianet Suvarna News", "url": "https://kannada.asianetnews.com/rss", "category": "ಸಾಮಾನ್ಯ"},
    # Add more once you've verified the feed URL resolves to valid RSS/XML, e.g.:
    # {"name": "Kannada Prabha", "url": "https://www.kannadaprabha.com/rssfeed/", "category": "ಸಾಮಾನ್ಯ"},
    # {"name": "Vijaya Karnataka", "url": "https://vijaykarnataka.com/rss.cms", "category": "ಸಾಮಾನ್ಯ"},
]

# --- Scraped (non-RSS) sources ---
# Daijiworld's Kannada section (daijiworld.com/kannada/...) does not expose an
# RSS feed - only the main English site does (daijiworld.com/rssfeed.xml).
# These category pages are scraped directly instead; see scrape.py.
SCRAPE_SOURCES = [
    {"name": "Daijiworld - ಕರಾವಳಿ", "url": "https://daijiworld.com/kannada/newsCategory?newsCategory=karvalli", "category": "ಕರಾವಳಿ"},
    {"name": "Daijiworld - ರಾಜ್ಯ/ರಾಷ್ಟ್ರ", "url": "https://daijiworld.com/kannada/newsCategory?newsCategory=national", "category": "ರಾಜ್ಯ"},
    {"name": "Daijiworld - ಅಂತಾರಾಷ್ಟ್ರೀಯ", "url": "https://daijiworld.com/kannada/newsCategory?newsCategory=international", "category": "ಅಂತಾರಾಷ್ಟ್ರೀಯ"},
    {"name": "Daijiworld - ಕ್ರೀಡೆ", "url": "https://daijiworld.com/kannada/newsCategory?newsCategory=sports", "category": "ಕ್ರೀಡೆ"},
    {"name": "Daijiworld - ಮನರಂಜನೆ", "url": "https://daijiworld.com/kannada/newsCategory?newsCategory=entertainment", "category": "ಮನರಂಜನೆ"},
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
    "ಕರಾವಳಿ": "🌊",
    "ಅಂತಾರಾಷ್ಟ್ರೀಯ": "🌍",
    "default": "📰",
}
