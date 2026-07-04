"""Generate short Kannada analysis snippets with a low-cost default."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import textwrap

import config
from models import NewsItem
from style_corpus import load_style_context

CACHE_PATH = Path("analysis_cache.json")
ANALYSIS_PROMPT_VERSION = "2026-07-04-v5"
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
        ಈ ಬೆಳವಣಿಗೆ ತಕ್ಷಣದ ಸುದ್ದಿಗಿಂತ ದೊಡ್ಡ ಪ್ರವೃತ್ತಿಯ ಒಂದು ಸೂಚನೆ.
        {lens} ಪರಿಪ್ರೇಕ್ಷ್ಯದಲ್ಲಿ ನೋಡಿದರೆ, ಇಲ್ಲಿ ಮುಖ್ಯ ಪ್ರಶ್ನೆ ಏನು ನಡೆದಿತು ಎಂಬುದಕ್ಕಿಂತ ಏಕೆ ನಡೆಯಿತು ಮತ್ತು ಮುಂದೇನು ಆಗಬಹುದು ಎಂಬುದು.
        ಕಾರಣ, ಪರಿಣಾಮ, ಹಾಗೂ ಸಾರ್ವಜನಿಕ ಹೊಣೆಗಾರಿಕೆ ಒಂದೇ ಚೌಕಟ್ಟಿನಲ್ಲಿ ಓದಿದಾಗ ಮಾತ್ರ ವಿಷಯದ ನಿಜವಾದ ತೂಕ ಕಾಣುತ್ತದೆ.
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


def _cache_key(item: NewsItem, context_items: list[NewsItem] | None) -> str:
    context_basis = "\n".join(
        f"{ctx.title}\n{ctx.summary}\n{ctx.source}\n{ctx.published_at}"
        for ctx in (context_items or [])
    )
    basis = (
        f"{ANALYSIS_PROMPT_VERSION}\n"
        f"{config.OPENAI_MODEL}|{config.GEMINI_MODEL}|{config.GROQ_MODEL}\n"
        f"{','.join(config.STYLE_TOPICS)}\n"
        f"{item.title}\n{item.summary}\n{item.source}\n"
        f"{context_basis}"
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


def _recent_context_items(item: NewsItem, recent_items: list[NewsItem] | None) -> list[NewsItem]:
    if not recent_items:
        return []

    ranked = []
    seen_ids = {item.id}
    for candidate in recent_items:
        if candidate.id in seen_ids:
            continue
        seen_ids.add(candidate.id)
        score = 0
        blob = f"{candidate.title} {candidate.summary} {candidate.category}".lower()
        item_blob = f"{item.title} {item.summary} {item.category}".lower()
        if candidate.category and candidate.category == item.category:
            score += 4
        if candidate.source and candidate.source == item.source:
            score += 2
        shared = _normalized_words(blob) & _normalized_words(item_blob)
        score += min(4, len(shared))
        ranked.append((score, candidate))

    ranked.sort(key=lambda entry: (entry[0], entry[1].published_at), reverse=True)
    return [candidate for _, candidate in ranked[:5]]


def _context_block(context_items: list[NewsItem]) -> str:
    if not context_items:
        return "No additional timeline context was supplied."
    lines = []
    for idx, ctx in enumerate(context_items, start=1):
        lines.append(
            f"{idx}. {ctx.published_at[:10] if ctx.published_at else 'unknown date'} | {ctx.category or 'uncategorized'} | {ctx.source}: {ctx.title} — {ctx.summary}"
        )
    return "\n".join(lines)


_BOILERPLATE_PATTERNS = (
    r"(?i)\bmood read\b",
    r"(?i)\bmotive map\b",
    r"(?i)\bpattern-fit\b",
    r"(?i)\bforecast\b",
    r"(?i)\bshort analysis\b",
    r"(?i)\bsummary\b",
    r"(?i)\bVedavidhya\b",
    r"(?i)\bGaurav\b",
    r"(?i)\bDGPIndia\b",
)


def _looks_like_boilerplate(text: str) -> bool:
    if not text:
        return True
    matches = sum(1 for pattern in _BOILERPLATE_PATTERNS if re.search(pattern, text))
    return matches >= 1 or len(_normalized_words(text)) < 35


def _build_prompt(item: NewsItem, style_context: str, context_items: list[NewsItem]) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for LLM analysis."""
    selected_lenses = _select_lenses(item, count=5)
    lens_line = ", ".join(selected_lenses)
    system_prompt = (
        "You are a disciplined Kannada current-affairs analyst. "
        "Write an interpretive civilizational analysis, not a summary. "
        "Do not imitate any living person's voice or catchphrases. "
        "Stay factual, non-inciting, and respectful. "
        "Never fabricate facts; when uncertain, state limits. "
        "Keep the output safe for public distribution and avoid defamation, sensationalism, or instructions for wrongdoing."
    )
    user_prompt = (
        f"Tone: {config.STYLE_TONE}.\n"
        "Task: Write Kannada analysis that synthesizes this story with the supplied recent timeline context.\n"
        "Use this structure: 1) mood read, 2) motive map, 3) pattern-fit across timelines, 4) forecast or watch-point.\n"
        f"Primary lens blend for this item: {lens_line}.\n"
        f"Available lens universe: {', '.join(config.STYLE_TOPICS)}.\n"
        "Output rules:\n"
        "1) Output exactly 2 short Kannada paragraphs, no headings, no labels, no bold text, no bullet points.\n"
        "2) Paragraph 1 must explain what the event means now, with one concrete reason from the current item.\n"
        "3) Paragraph 2 must connect this item with the recent timeline context only if there is a real evidentiary thread; otherwise say the link is tentative.\n"
        "4) Use at least 3 of the selected lenses naturally inside the prose; do not list lens names.\n"
        "5) End with one short forecast or watch-point sentence, still inside paragraph 2.\n"
        "6) Avoid slogans, personal attacks, sectarian hostility, legal accusations, or fear language.\n"
        "7) Do not add facts beyond provided news text and the context block.\n"
        "8) Do NOT paraphrase/copy the summary line-by-line; provide interpretation and implication.\n"
        "9) Do not mention any source-brand, author name, or template label.\n"
        "10) If you cannot write a strong synthesis, give a shorter factual interpretation rather than generic commentary.\n"
        f"Length budget: <= {config.MAX_ANALYSIS_TOKENS} tokens.\n\n"
        f"Style grounding:\n{style_context}\n\n"
        f"Current item:\nTitle: {item.title}\nSummary: {item.summary}\nSource: {item.source}\n\n"
        f"Recent timeline context:\n{_context_block(context_items)}\n"
    )
    return system_prompt, user_prompt


def _openrouter_headers() -> dict[str, str]:
    headers = {
        "HTTP-Referer": config.OPENROUTER_REFERER,
        "X-OpenRouter-Title": config.OPENROUTER_TITLE,
    }
    return {key: value for key, value in headers.items() if value}


def _try_openai(item: NewsItem, style_context: str, context_items: list[NewsItem]) -> str | None:
    if "openai" in _DISABLED_PROVIDERS:
        return None
    if not config.OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=config.OPENAI_API_KEY)
        system_prompt, user_prompt = _build_prompt(item, style_context, context_items)
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


def _try_openrouter(item: NewsItem, style_context: str, context_items: list[NewsItem]) -> str | None:
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
        system_prompt, user_prompt = _build_prompt(item, style_context, context_items)
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


def _try_gemini(item: NewsItem, style_context: str, context_items: list[NewsItem]) -> str | None:
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
        system_prompt, user_prompt = _build_prompt(item, style_context, context_items)
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


def _try_groq(item: NewsItem, style_context: str, context_items: list[NewsItem]) -> str | None:
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
        system_prompt, user_prompt = _build_prompt(item, style_context, context_items)
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


def _try_provider(name: str, item: NewsItem, style_context: str, context_items: list[NewsItem]) -> str | None:
    if name == "openrouter":
        return _try_openrouter(item, style_context, context_items)
    if name == "openai":
        return _try_openai(item, style_context, context_items)
    if name == "gemini":
        return _try_gemini(item, style_context, context_items)
    if name == "groq":
        return _try_groq(item, style_context, context_items)
    return None


def build_analysis(item: NewsItem, context_items: list[NewsItem] | None = None) -> str:
    cache = _load_cache()
    key = _cache_key(item, context_items)
    cached = cache.get(key)
    if cached:
        return cached

    if not config.ENABLE_LLM_ANALYSIS:
        text = _deterministic_analysis(item)
        cache[key] = text
        _save_cache(cache)
        return text

    style_context = load_style_context()
    timeline_context = _recent_context_items(item, context_items)
    provider_order = config.LLM_PROVIDER_ORDER or ["gemini", "groq", "openai"]
    text = None
    for provider in provider_order:
        text = _try_provider(provider, item, style_context, timeline_context)
        if text:
            if _looks_like_boilerplate(text):
                print(f"[analyzer] {provider} output looked generic; using fallback")
                text = None
                continue
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