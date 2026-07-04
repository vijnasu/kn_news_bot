"""Configuration for the Kannada Fast News bot."""

import os
from pathlib import Path


def _load_local_env_file() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    try:
        content = env_path.read_text(encoding="utf-8-sig")
    except Exception:
        return
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ[key] = value


_load_local_env_file()


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
MAX_ANALYSIS_TOKENS = _env_int("KN_NEWS_MAX_ANALYSIS_TOKENS", 500)

ENGLISH_ANALYSIS_ENABLED = _env("KN_NEWS_ENGLISH_ANALYSIS", "1") == "1"
ENABLE_LLM_ANALYSIS = _env("KN_NEWS_ENABLE_LLM", "1") == "1"
ALLOW_LIVE_LLM = _env("KN_NEWS_ALLOW_LIVE_LLM", "0") == "1"
OPENROUTER_API_KEY = _env("OPENROUTER_API_KEY")
OPENROUTER_MODEL = _env("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
OPENROUTER_REFERER = _env("OPENROUTER_REFERER", "https://github.com/vijnasu/kn_news_bot")
OPENROUTER_TITLE = _env("OPENROUTER_TITLE", "kn_news_bot")
OPENAI_API_KEY = _env("OPENAI_API_KEY")
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-2.5-flash")
if GEMINI_MODEL in {"gemini-2.5-pro", "gemini-2.5-flash-lite"}:
    GEMINI_MODEL = "gemini-2.5-flash"
GROQ_API_KEY = _env("GROQ_API_KEY")
GROQ_MODEL = _env("GROQ_MODEL", "llama-3.1-8b-instant")
LLM_PROVIDER_ORDER = [
    x.strip().lower()
    for x in _env("KN_NEWS_LLM_PROVIDER_ORDER", "gemini,groq,openai").split(",")
    if x.strip()
]
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
    "Dharma Shastra",
    "Ramayana",
    "Mahabharata",
    "Vedas",
    "Vedanta",
    "Bhagavad Gita",
    "Mimamsa",
    "Vyakarana",
    "Jyotisha",
    "Prashna",
    "Tantra",
    "Vastu",
    "Ayurveda",
    "Vedic Science",
    "Tarka",
    "Panchatantra",
    "Rajya Shastra",
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

# English-language feeds used ONLY as the source for the once-per-run
# Gemini analysis (see analyzer.build_english_analysis). English text tokenizes
# far more densely than Kannada script for the same information, and we only
# ever pick a single relevant story per run, so this is the main cost lever
# for the analysis pipeline. The plain Kannada headline posts above are
# untouched by this and never call an LLM.
ENGLISH_SOURCES = [
    {"name": "The Hindu - Karnataka", "url": "https://www.thehindu.com/news/national/karnataka/feeder/default.rss", "category": "ರಾಜ್ಯ"},
    {"name": "The Hindu - National", "url": "https://www.thehindu.com/news/national/feeder/default.rss", "category": "ರಾಜ್ಯ"},
    {"name": "Times of India - Bengaluru", "url": "https://timesofindia.indiatimes.com/rss/city/bengaluru/rssfeeds/2950623.cms", "category": "ಬೆಂಗಳೂರು"},
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
