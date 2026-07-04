"""Generate short Kannada analysis snippets with a low-cost default."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import textwrap
import re

import config
from models import NewsItem
from style_corpus import load_style_context

CACHE_PATH = Path("analysis_cache.json")
ANALYSIS_PROMPT_VERSION = "2026-07-04-v3"
_DISABLED_PROVIDERS: set[str] = set()
LENSES = [
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
    "Vedic Science",
    "Tarka",
    "Panchatantra",
    "Rajya Shastra",
    "Artha Shastra",
    "Nyaya Shastra",
    "Ganita",
]
COSTLY_HINTS = ("election", "policy", "tax", "budget", "court", "government", "modi", "bengaluru", "karnataka")
CULTURE_HINTS = ("temple", "dharma", "ved", "yoga", "astrology", "graha", "panchanga", "tantra", "sanatana")


def _select_lenses(item: NewsItem, count: int = 5) -> list[str]:
    all_lenses = config.STYLE_TOPICS or LENSES
    if not all_lenses:
        return LENSES[:count]

    blob = f"{item.title} {item.summary} {item.category}".lower()
    keyword_map = {
        "Rajya Shastra": ("election", "government", "policy", "minister", "party"),
        "Artha Shastra": ("economy", "tax", "budget", "market", "inflation", "rupee"),
        "Nyaya Shastra": ("court", "judge", "law", "legal", "verdict"),
        "Dharma Shastra": ("temple", "ritual", "dharma", "tradition"),
        "Jyotisha": ("graha", "nakshatra", "panchanga", "auspicious"),
        "Ganita": ("data", "ratio", "trend", "statistics", "numbers"),
    }

    selected = []
    for lens, hints in keyword_map.items():
        if lens in all_lenses and any(h in blob for h in hints):
            selected.append(lens)

    stable_seed = int(hashlib.sha256(blob.encode("utf-8")).hexdigest()[:8], 16)
    remaining = [lens for lens in all_lenses if lens not in selected]
    if remaining:
        offset = stable_seed % len(remaining)
        remaining = remaining[offset:] + remaining[:offset]
    selected.extend(remaining)
    return selected[: max(3, count)]


def _deterministic_analysis(item: NewsItem) -> str:
    lens = ", ".join(_select_lenses(item, count=4))
    return textwrap.dedent(
        f"""
        ಈ ಸುದ್ದಿಯನ್ನು ಕೇವಲ ಘಟನೆ ಎಂದು ನೋಡದೇ, ಕಾರಣ-ಪರಿಣಾಮ-ಕರ್ತವ್ಯ ಎಂಬ ತ್ರಿಮಟ್ಟದಲ್ಲಿ ಓದಬೇಕು.
        {config.STYLE_BRAND_NAME} ದೃಷ್ಟಿಯಲ್ಲಿ {lens} ಪರಿಪ್ರೇಕ್ಷ್ಯವನ್ನು ಒಟ್ಟಿಗೆ ಬಳಸಿದಾಗ, ನೀತಿ, ಧರ್ಮ, ಮತ್ತು ಸಾರ್ವಜನಿಕ ಹಿತದ ಸಮತೋಲನ ಸ್ಪಷ್ಟವಾಗುತ್ತದೆ.
        ದೃಢವಾದ ನಿರ್ಣಯಕ್ಕೆ ತರ್ಕ (ಪ್ರಮಾಣ), ಸಂದರ್ಭ, ಮತ್ತು ಧಾರ್ಮಿಕ-ನೈತಿಕ ಹೊಣೆಗಾರಿಕೆಯನ್ನು ಜೊತೆಯಲ್ಲಿ ಪರಿಗಣಿಸಬೇಕು.
        """
    ).strip()


def _trim_analysis(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return cleaned
    max_chars = max(280, config.MAX_ANALYSIS_TOKENS * 5)
    if len(cleaned) <= max_chars:
        return cleaned
    cut = cleaned[:max_chars]
    space_idx = cut.rfind(" ")
    if space_idx > int(max_chars * 0.7):
        cut = cut[:space_idx]
    return cut.rstrip(" ,;:-") + "…"


def _cache_key(item: NewsItem) -> str:
    basis = (
        f"{ANALYSIS_PROMPT_VERSION}\n"
        f"{config.OPENAI_MODEL}|{config.GEMINI_MODEL}|{config.GROQ_MODEL}\n"
        f"{','.join(config.STYLE_TOPICS)}\n"
        f"{item.title}\n{item.summary}\n{item.source}"
    ).encode("utf-8")
    return hashlib.sha256(basis).hexdigest()[:24]


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "429" in msg
        or "insufficient_quota" in msg
        or "quota exceeded" in msg
        or "resource_exhausted" in msg
    )


def should_analyze(item: NewsItem) -> bool:
    blob = f"{item.title} {item.summary} {item.category}".lower()
    return any(h in blob for h in COSTLY_HINTS) or any(h in blob for h in CULTURE_HINTS)


def _normalized_words(text: str) -> set[str]:
    cleaned = re.sub(r"[^\w\s]", " ", (text or "").lower(), flags=re.UNICODE)
    return {w for w in cleaned.split() if len(w) > 2}


def _too_close_to_source(item: NewsItem, analysis_text: str) -> bool:
    src = f"{item.title} {item.summary}".strip()
    if not src or not analysis_text:
        return False
    src_words = _normalized_words(src)
    out_words = _normalized_words(analysis_text)
    if not src_words or not out_words:
        return False
    overlap = len(src_words & out_words) / max(1, len(src_words))
    return overlap >= 0.72


def _build_prompt(item: NewsItem, style_context: str) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for LLM analysis."""
    selected_lenses = _select_lenses(item, count=5)
    lens_line = ", ".join(selected_lenses)
    system_prompt = (
        "You are a disciplined Kannada current-affairs analyst. "
        "Interpret events through a Sanatana Hindu civilizational framework, "
        "while staying factual, non-inciting, and respectful. "
        "Never fabricate facts; when uncertain, state limits."
    )
    user_prompt = (
        f"Brand voice: {config.STYLE_BRAND_NAME}.\n"
        f"Tone: {config.STYLE_TONE}.\n"
        "Task: Write Kannada analysis with blended intelligence using relevant shastric lenses.\n"
        f"Primary lens blend for this item: {lens_line}.\n"
        f"Available lens universe: {', '.join(config.STYLE_TOPICS)}.\n"
        "Output rules:\n"
        "1) 2-3 short Kannada paragraphs, concise and readable.\n"
        "2) Start with a fresh thesis that interprets the event, not a summary.\n"
        "3) Connect event -> cause -> likely consequence -> dharmic/public-duty implication.\n"
        "4) Use at least 3 of the selected lenses naturally; do not dump names as a list.\n"
        "5) Avoid slogans, personal attacks, sectarian hostility, or fear language.\n"
        "6) Do not add facts beyond provided news text.\n"
        "7) Do NOT paraphrase/copy the summary line-by-line; provide interpretation and implication.\n"
        f"Length budget: <= {config.MAX_ANALYSIS_TOKENS} tokens.\n\n"
        f"Style grounding:\n{style_context}\n\n"
        f"Title: {item.title}\nSummary: {item.summary}\nSource: {item.source}\n"
    )
    return system_prompt, user_prompt


def _openrouter_headers() -> dict[str, str]:
    headers = {
        "HTTP-Referer": config.OPENROUTER_REFERER,
        "X-OpenRouter-Title": config.OPENROUTER_TITLE,
    }
    return {key: value for key, value in headers.items() if value}


def _try_openai(item: NewsItem, style_context: str) -> str | None:
    """Attempt analysis via OpenAI responses API; return None on any failure."""
    if "openai" in _DISABLED_PROVIDERS:
        return None


def _try_openrouter(item: NewsItem, style_context: str) -> str | None:
    """Attempt analysis via OpenRouter (free model compatible with OpenAI SDK)."""
    if "openrouter" in _DISABLED_PROVIDERS:
        return None
    if not config.OPENROUTER_API_KEY:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=config.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        )
        system_prompt, user_prompt = _build_prompt(item, style_context)
        resp = client.chat.completions.create(
            model=config.OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=config.MAX_ANALYSIS_TOKENS,
            extra_headers=_openrouter_headers(),
        )
        text = (resp.choices[0].message.content or "") if resp.choices else ""
        return _trim_analysis(text) or None
    except Exception as exc:
        if _is_quota_error(exc):
            _DISABLED_PROVIDERS.add("openrouter")
            print("[analyzer] OpenRouter quota exhausted; disabled for this run")
        else:
            print(f"[analyzer] OpenRouter failed ({type(exc).__name__}: {exc}); trying next tier")
        return None
    if not config.OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        system_prompt, user_prompt = _build_prompt(item, style_context)
        resp = client.responses.create(
            model=config.OPENAI_MODEL,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_output_tokens=config.MAX_ANALYSIS_TOKENS,
        )
        text = getattr(resp, "output_text", "") or ""
        return _trim_analysis(text) or None
    except Exception as exc:
        if _is_quota_error(exc):
            _DISABLED_PROVIDERS.add("openai")
            print("[analyzer] OpenAI quota exhausted; disabled for this run")
        else:
            print(f"[analyzer] OpenAI failed ({type(exc).__name__}: {exc}); trying next tier")
        return None


def _try_gemini(item: NewsItem, style_context: str) -> str | None:
    """Attempt analysis via Gemini (OpenAI-compat v1beta); return None on any failure."""
    if "gemini" in _DISABLED_PROVIDERS:
        return None
    if not config.GEMINI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=config.GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        system_prompt, user_prompt = _build_prompt(item, style_context)
        resp = client.chat.completions.create(
            model=config.GEMINI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=config.MAX_ANALYSIS_TOKENS,
        )
        text = (resp.choices[0].message.content or "") if resp.choices else ""
        return _trim_analysis(text) or None
    except Exception as exc:
        if _is_quota_error(exc):
            _DISABLED_PROVIDERS.add("gemini")
            print("[analyzer] Gemini quota exhausted; disabled for this run")
        else:
            print(f"[analyzer] Gemini failed ({type(exc).__name__}: {exc}); trying next tier")
        return None


def _try_groq(item: NewsItem, style_context: str) -> str | None:
    """Attempt analysis via Groq (OpenAI-compat); return None on any failure."""
    if "groq" in _DISABLED_PROVIDERS:
        return None
    if not config.GROQ_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=config.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
        )
        system_prompt, user_prompt = _build_prompt(item, style_context)
        resp = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=config.MAX_ANALYSIS_TOKENS,
        )
        text = (resp.choices[0].message.content or "") if resp.choices else ""
        return _trim_analysis(text) or None
    except Exception as exc:
        if _is_quota_error(exc):
            _DISABLED_PROVIDERS.add("groq")
            print("[analyzer] Groq quota exhausted; disabled for this run")
        else:
            print(f"[analyzer] Groq failed ({type(exc).__name__}: {exc}); trying next tier")
        return None


def _try_provider(name: str, item: NewsItem, style_context: str) -> str | None:
    if name == "openrouter":
        return _try_openrouter(item, style_context)
    if name == "openai":
        return _try_openai(item, style_context)
    if name == "gemini":
        return _try_gemini(item, style_context)
    if name == "groq":
        return _try_groq(item, style_context)
    return None


def build_analysis(item: NewsItem) -> str:
    cache = _load_cache()
    key = _cache_key(item)
    cached = cache.get(key)
    if cached:
        return cached

    if not config.ENABLE_LLM_ANALYSIS:
        text = _deterministic_analysis(item)
        cache[key] = text
        _save_cache(cache)
        return text

    style_context = load_style_context()
    provider_order = config.LLM_PROVIDER_ORDER or ["groq", "openai", "gemini"]
    if "openrouter" not in provider_order:
        provider_order = ["openrouter", *provider_order]
    text = None
    for provider in provider_order:
        text = _try_provider(provider, item, style_context)
        if text:
            print(f"[analyzer] analysis generated by {provider}")
            break
    if not text:
        text = _deterministic_analysis(item)
        print("[analyzer] all LLM providers unavailable; used deterministic fallback")
    elif _too_close_to_source(item, text):
        print("[analyzer] LLM output too close to source text; using interpretive fallback")
        text = _deterministic_analysis(item)

    cache[key] = text
    _save_cache(cache)
    return text
