"""Configuration for the Kannada Fast News bot."""

import os


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_csv(name: str) -> list[str]:
    return [x.strip() for x in _env(name).split(",") if x.strip()]


TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
TELEGRAM_ANALYSIS_BOT_TOKEN = _env("TELEGRAM_ANALYSIS_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
TELEGRAM_CHANNEL_IDS = list(
    dict.fromkeys(_env_csv("TELEGRAM_CHANNEL_IDS") + _env_csv("TELEGRAM_CHANNEL_ID"))
)
TELEGRAM_ANALYSIS_CHANNEL_IDS = list(
    dict.fromkeys(_env_csv("TELEGRAM_ANALYSIS_CHANNEL_IDS") + _env_csv("TELEGRAM_LLM_CHANNEL_IDS"))
)

FACEBOOK_GRAPH_VERSION = _env("FACEBOOK_GRAPH_VERSION", "v20.0")
FACEBOOK_TARGET = _env("FACEBOOK_TARGET", "disabled").lower()
FACEBOOK_PAGE_ID = _env("FACEBOOK_PAGE_ID", "vedavidhya.astrology.tantra")
FACEBOOK_PAGE_ACCESS_TOKEN = _env(
    "FACEBOOK_PAGE_ACCESS_TOKEN",
    _env("FACEBOOK_ACCESS_TOKEN"),
)
FACEBOOK_ACCESS_TOKEN = _env("FACEBOOK_ACCESS_TOKEN")
FACEBOOK_GROUP_ID = _env("FACEBOOK_GROUP_ID")

DB_PATH = _env("KN_NEWS_DB", "news.db")
JSONL_EXPORT_PATH = _env("KN_NEWS_JSONL", "news_export.jsonl")

MAX_ITEMS_PER_RUN = 15
POST_DELAY_SECONDS = 4
SUMMARY_MAX_CHARS = 320
TOP_POSTS_PER_RUN = _env_int("KN_NEWS_TOP_POSTS", 4)
MAX_POSTS_PER_SOURCE_PER_RUN = _env_int("KN_NEWS_TOP_PER_SOURCE", 1)
MAX_AI_ANALYSES_PER_RUN = _env_int("KN_NEWS_MAX_ANALYSES", TOP_POSTS_PER_RUN)
MAX_ANALYSIS_TOKENS = _env_int("KN_NEWS_MAX_ANALYSIS_TOKENS", 140)

ENABLE_LLM_ANALYSIS = _env("KN_NEWS_ENABLE_LLM", "0") == "1"
OPENAI_API_KEY = _env("OPENAI_API_KEY")
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o-mini")
STYLE_BRAND_NAME = _env("KN_NEWS_STYLE_BRAND", "Vedavidhya Consultants")
STYLE_SOURCE_URL = _env("KN_NEWS_STYLE_SOURCE_URL", "https://www.vedavidhya.com/")
STYLE_BLOG_URL = _env("KN_NEWS_STYLE_BLOG_URL", "https://www.vedavidhya.com/blog")
STYLE_FACEBOOK_URL = _env("KN_NEWS_STYLE_FACEBOOK_URL", "https://www.facebook.com/vedavidhya.astrology.tantra")
STYLE_CORPUS_PATH = _env("KN_NEWS_STYLE_CORPUS", "style_corpus.json")
STYLE_CORPUS_URLS = [
    x.strip()
    for x in _env(
        "KN_NEWS_STYLE_CORPUS_URLS",
        f"{STYLE_SOURCE_URL},{STYLE_BLOG_URL}",
    ).split(",")
    if x.strip()
]
STYLE_TONE = _env(
    "KN_NEWS_STYLE_TONE",
    "disciplined, rooted, analytical, calm, authoritative, Kannada-first, Sanatana/Hindu framework",
)
STYLE_TOPICS = [
    "Jyotisha",
    "Prashna",
    "Tantra",
    "Vastu",
    "Ayurveda",
    "Artha Shastra",
    "Nyaya Shastra",
    "Ganita",
]

SOURCES = [
    {"name": "Prajavani", "url": "https://www.prajavani.net/feed", "category": "ಸಾಮಾನ್ಯ"},
    {"name": "TV9 Kannada", "url": "https://tv9kannada.com/feed", "category": "ಸಾಮಾನ್ಯ"},
    {"name": "Kannada Oneindia - ಕರ್ನಾಟಕ", "url": "https://kannada.oneindia.com/rss/feeds/kannada-news-fb.xml", "category": "ರಾಜ್ಯ"},
    {"name": "Kannada Oneindia - ಬೆಂಗಳೂರು", "url": "https://kannada.oneindia.com/rss/feeds/kannada-bengaluru-fb.xml", "category": "ಬೆಂಗಳೂರು"},
    {"name": "Kannada Oneindia - ಮನರಂಜನೆ", "url": "https://kannada.oneindia.com/rss/feeds/kannada-entertainment-fb.xml", "category": "ಮನರಂಜನೆ"},
    {"name": "Public TV", "url": "https://publictv.in/feed", "category": "ಸಾಮಾನ್ಯ"},
    {"name": "Asianet Suvarna News", "url": "https://kannada.asianetnews.com/rss", "category": "ಸಾಮಾನ್ಯ"},
]

SCRAPE_SOURCES = [
    {"name": "Daijiworld - ಕರಾವಳಿ", "url": "https://daijiworld.com/kannada/newsCategory?newsCategory=karvalli", "category": "ಕರಾವಳಿ"},
    {"name": "Daijiworld - ರಾಜ್ಯ/ರಾಷ್ಟ್ರ", "url": "https://daijiworld.com/kannada/newsCategory?newsCategory=national", "category": "ರಾಜ್ಯ"},
    {"name": "Daijiworld - ಅಂತಾರಾಷ್ಟ್ರೀಯ", "url": "https://daijiworld.com/kannada/newsCategory?newsCategory=international", "category": "ಅಂತಾರಾಷ್ಟ್ರೀಯ"},
    {"name": "Daijiworld - ಕ್ರೀಡೆ", "url": "https://daijiworld.com/kannada/newsCategory?newsCategory=sports", "category": "ಕ್ರೀಡೆ"},
    {"name": "Daijiworld - ಮನರಂಜನೆ", "url": "https://daijiworld.com/kannada/newsCategory?newsCategory=entertainment", "category": "ಮನರಂಜನೆ"},
]

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
