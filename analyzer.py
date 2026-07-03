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

try:
    from openai import OpenAI as _OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OpenAI = None  # type: ignore[assignment,misc]
    _OPENAI_AVAILABLE = False

CACHE_PATH = Path("analysis_cache.json")
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
    basis = f"{item.title}\n{item.summary}\n{item.source}".encode("utf-8")
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


def _call_openai(system_prompt: str, user_prompt: str) -> str:
    """Call the OpenAI Responses API. Returns text or empty string on any failure."""
    if not config.OPENAI_API_KEY or not _OPENAI_AVAILABLE:
        return ""
    try:
        client = _OpenAI(api_key=config.OPENAI_API_KEY)
        resp = client.responses.create(
            model=config.OPENAI_MODEL,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_output_tokens=config.MAX_ANALYSIS_TOKENS,
        )
        return getattr(resp, "output_text", "") or ""
    except Exception as exc:
        status = getattr(exc, "status_code", "unknown")
        print(f"[analyzer] OpenAI error ({status}), trying next provider: {exc}")
        return ""


def _call_openai_compat(api_key: str, base_url: str, model: str,
                        system_prompt: str, user_prompt: str, provider: str) -> str:
    """Call any OpenAI-compatible chat-completions endpoint (Groq, Gemini, etc.).

    Returns the response text, or an empty string on any failure.
    """
    if not api_key or not _OPENAI_AVAILABLE:
        return ""
    try:
        client = _OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=config.MAX_ANALYSIS_TOKENS,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        print(f"[analyzer] {provider} error, trying next provider: {exc}")
        return ""


def should_analyze(item: NewsItem) -> bool:
    blob = f"{item.title} {item.summary} {item.category}".lower()
    return any(h in blob for h in COSTLY_HINTS) or any(h in blob for h in CULTURE_HINTS)


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

    selected_lenses = _select_lenses(item, count=5)
    lens_line = ", ".join(selected_lenses)
    style_context = load_style_context()

    system_prompt = (
        "You are a disciplined Kannada current-affairs analyst. "
        "Interpret events through a Sanatana Hindu civilizational framework, "
        "while staying factual, non-inciting, and respectful. "
        "Never fabricate facts; when uncertain, state limits."
    )

    prompt = (
        f"Brand voice: {config.STYLE_BRAND_NAME}.\n"
        f"Tone: {config.STYLE_TONE}.\n"
        "Task: Write Kannada analysis with blended intelligence using relevant shastric lenses.\n"
        f"Primary lens blend for this item: {lens_line}.\n"
        f"Available lens universe: {', '.join(config.STYLE_TOPICS)}.\n"
        "Output rules:\n"
        "1) 2-3 short Kannada paragraphs, concise and readable.\n"
        "2) Connect event -> cause -> likely consequence -> dharmic/public-duty implication.\n"
        "3) Use at least 3 of the selected lenses naturally; do not dump names as a list.\n"
        "4) Avoid slogans, personal attacks, sectarian hostility, or fear language.\n"
        "5) Do not add facts beyond provided news text.\n"
        f"Length budget: <= {config.MAX_ANALYSIS_TOKENS} tokens.\n\n"
        f"Style grounding:\n{style_context}\n\n"
        f"Title: {item.title}\nSummary: {item.summary}\nSource: {item.source}\n"
    )

    # Provider cascade: OpenAI → Groq → Gemini → deterministic template
    text = (
        _call_openai(system_prompt, prompt)
        or _call_openai_compat(
            config.GROQ_API_KEY,
            "https://api.groq.com/openai/v1",
            config.GROQ_MODEL,
            system_prompt, prompt, "Groq",
        )
        or _call_openai_compat(
            config.GEMINI_API_KEY,
            "https://generativelanguage.googleapis.com/v1beta/openai/",
            config.GEMINI_MODEL,
            system_prompt, prompt, "Gemini",
        )
    )

    final = _trim_analysis(text) or _deterministic_analysis(item)
    cache[key] = final
    _save_cache(cache)
    return final
