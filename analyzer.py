"""Generate short Kannada analysis snippets with a low-cost default."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import textwrap

import config
from models import NewsItem
from style_corpus import load_style_context

CACHE_PATH = Path("analysis_cache.json")
LENSES = ["Vedic Science", "Tantra", "Astrology", "Rajya Shastra", "Nyaya Shastra", "Artha Shastra", "Ganita"]
COSTLY_HINTS = ("election", "policy", "tax", "budget", "court", "government", "modi", "bengaluru", "karnataka")
CULTURE_HINTS = ("temple", "dharma", "ved", "yoga", "astrology", "graha", "panchanga", "tantra", "sanatana")


def _deterministic_analysis(item: NewsItem) -> str:
    lens = ", ".join(LENSES[:4])
    return textwrap.dedent(
        f"""
        ಈ ಸುದ್ದಿ ಕ್ಷಣಿಕ ಶಬ್ದಕ್ಕಿಂತ ಹೆಚ್ಚು. ಇದರ ಒಳಸೂತ್ರವನ್ನು {config.STYLE_BRAND_NAME} ದೃಷ್ಟಿಯಿಂದ ಓದಬೇಕು.
        {lens} ಮತ್ತು {config.STYLE_TOPICS[0]}-{config.STYLE_TOPICS[3]} ಪರಿಪ್ರೇಕ್ಷ್ಯದಲ್ಲಿ ನೋಡಿದರೆ, ಕಾರಣ, ಪರಿಣಾಮ, ಮತ್ತು ಧರ್ಮದ ಬಾಳಿಕೆಯ ಪ್ರಶ್ನೆ ಮುಖ್ಯವಾಗುತ್ತದೆ.
        ಸುದ್ದಿಯ ಆಂತರ್ಯವನ್ನು ಅರ್ಥಮಾಡಿಕೊಂಡಾಗ ಮಾತ್ರ ಸರಿಯಾದ ನಿರ್ಣಯ ಸಾಧ್ಯ.
        """
    ).strip()


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


def should_analyze(item: NewsItem) -> bool:
    blob = f"{item.title} {item.summary} {item.category}".lower()
    return any(h in blob for h in COSTLY_HINTS) or any(h in blob for h in CULTURE_HINTS)


def build_analysis(item: NewsItem) -> str:
    cache = _load_cache()
    key = _cache_key(item)
    cached = cache.get(key)
    if cached:
        return cached

    if not config.ENABLE_LLM_ANALYSIS or not config.OPENAI_API_KEY:
        text = _deterministic_analysis(item)
        cache[key] = text
        _save_cache(cache)
        return text
    try:
        from openai import OpenAI
    except Exception:
        text = _deterministic_analysis(item)
        cache[key] = text
        _save_cache(cache)
        return text

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    prompt = (
        f"You are writing in the voice of {config.STYLE_BRAND_NAME}.\n"
        f"Tone: {config.STYLE_TONE}.\n"
        f"{load_style_context()}\n\n"
        "Write short Kannada current-affairs analysis using a Sanatana Hindu framework as a disciplined interpretive lens.\n"
        "Do not invent facts. Do not sermonize. Do not attack people.\n"
        f"Keep it under {config.MAX_ANALYSIS_TOKENS} tokens, in 2-3 short paragraphs.\n"
        f"Prefer these lenses only when relevant: {', '.join(config.STYLE_TOPICS)}.\n"
        f"Style source: {config.STYLE_SOURCE_URL}\n\n"
        f"Title: {item.title}\nSummary: {item.summary}\nSource: {item.source}\n"
    )
    resp = client.responses.create(
        model=config.OPENAI_MODEL,
        input=prompt,
        max_output_tokens=config.MAX_ANALYSIS_TOKENS,
    )
    text = getattr(resp, "output_text", "") or ""
    final = text.strip() or _deterministic_analysis(item)
    cache[key] = final
    _save_cache(cache)
    return final
