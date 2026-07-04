"""Generate short Kannada analysis snippets with a low-cost default."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import textwrap

import config
from models import NewsItem
from style_corpus import load_style_context, load_voice_anchors

CACHE_PATH = Path("analysis_cache.json")
ANALYSIS_PROMPT_VERSION = "2026-07-04-v13"
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
CURRENT_AFFAIRS_CATEGORIES = {"ರಾಜ್ಯ", "ಬೆಂಗಳೂರು", "ಕರಾವಳಿ", "ಅಂತಾರಾಷ್ಟ್ರೀಯ", "ಅಪರಾಧ", "ಹಣಕಾಸು", "ರಾಜಕೀಯ"}
EXCLUDE_HINTS = (
    "ಧಾರಾವಾಹಿ", "ಚಿತ್ರ", "ಸಿನಿಮಾ", "ಮನರಂಜನೆ", "ಕ್ರೀಡೆ", "sports", "serial", "movie", "film",
    # Rolling "live blog" articles: the feed's <description> is whatever
    # snippet was current when the RSS was generated, which routinely has
    # nothing to do with the page's overall headline - analyzing these
    # produces a title/body that talk about two different stories.
    "live:", "live updates", "as it happened",
)
SOURCE_EXCLUDE_HINTS = ("ಮನರಂಜನೆ", "entertainment", "sports", "sport", "cinema", "movie", "film")
URL_EXCLUDE_HINTS = ("/entertainment/", "/sports/", "/sport/", "/movies/", "/movie/", "/film/", "/television/")
POLICY_HINTS = (
    "police",
    "court",
    "government",
    "minister",
    "budget",
    "tax",
    "case",
    "investigation",
    "inquiry",
    "ed ",
    "nhrc",
    "alert",
    "order",
    "scheme",
    "scam",
    "donation",
    "rescue",
    "accident",
    "flood",
    "rain",
    "strike",
    "license",
    "corruption",
)


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
        ಈ ಸುದ್ದಿಯ ಮುಖ್ಯ ಅರ್ಥ: ಇದು {item.category or 'ಸಾರ್ವಜನಿಕ'} ಕ್ಷೇತ್ರದಲ್ಲಿ ತಕ್ಷಣದ ಬೆಳವಣಿಗೆ ಮಾತ್ರವಲ್ಲ, ಮುಂದಿನ ನಿರ್ಧಾರಗಳು ಮತ್ತು ಪ್ರತಿಕ್ರಿಯೆಗಳನ್ನು ರೂಪಿಸುವ ಘಟನೆ.
        {item.source} ವರದಿಯ ಪ್ರಕಾರ ಬಂದಿರುವ ಈ ವಿಷಯವನ್ನು {lens} ಚೌಕಟ್ಟಿನಲ್ಲಿ ನೋಡಿದಾಗ, ಕಾರಣ, ಪರಿಣಾಮ, ಮತ್ತು ಸಾರ್ವಜನಿಕ ಹೊಣೆಗಾರಿಕೆಯ ಸಂಬಂಧ ಸ್ಪಷ್ಟವಾಗುತ್ತದೆ.
        ಮುಂದಿನ ಹಂತದಲ್ಲಿ ಯಾವ ಪಾಲುದಾರರು ಲಾಭಪಡೆಯುತ್ತಾರೆ, ಯಾರ ಮೇಲೆ ಹೊಣೆ ಬರುತ್ತದೆ, ಮತ್ತು ಯಾವ ರೀತಿಯ ಪ್ರತಿಕ್ರಿಯೆ ಸಾಧ್ಯ ಎಂಬುದೇ ಗಮನಿಸಬೇಕಾದ ಪ್ರಶ್ನೆ.
        """
    ).strip()


def _clean_paragraph(text: str) -> str:
    """Collapse only intra-paragraph whitespace (no line breaks left to
    collapse here), tidy spacing around punctuation, and make sure sentence
    enders are followed by exactly one space."""
    text = re.sub(r"[ \t]+", " ", text).strip()
    # No space before punctuation (ASCII or Kannada danda), single space after.
    text = re.sub(r"\s+([,.;:!?।])", r"\1", text)
    text = re.sub(r"([,.;:!?।])(?=\S)", r"\1 ", text)
    return text


def _trim_analysis(text: str) -> str:
    """Normalize an LLM response into clean paragraphs. Paragraph breaks
    (blank lines) are preserved - collapsing ALL whitespace to single spaces
    (the old behaviour) silently merged every paragraph into one unbroken
    wall of text with no visible structure once posted."""
    raw = (text or "").strip()
    if not raw:
        return raw

    paragraphs = [p for p in re.split(r"\n\s*\n", raw) if p.strip()]
    if not paragraphs:
        paragraphs = [raw]
    cleaned = "\n\n".join(_clean_paragraph(p) for p in paragraphs)

    max_chars = max(280, config.MAX_ANALYSIS_TOKENS * 5)
    if len(cleaned) <= max_chars:
        return cleaned

    cut = cleaned[:max_chars]
    # Prefer cutting at a paragraph boundary, then a sentence boundary,
    # then finally just a word boundary - never mid-word.
    para_idx = cut.rfind("\n\n")
    if para_idx > int(max_chars * 0.4):
        return cut[:para_idx].rstrip()
    sentence_idx = max(cut.rfind(ender) for ender in (". ", "। ", "! ", "? "))
    if sentence_idx > int(max_chars * 0.4):
        return cut[: sentence_idx + 1].rstrip()
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
    blob = f"{item.title} {item.summary} {item.category} {item.source}".lower()
    url_blob = (item.link or "").lower()
    if any(h in blob for h in EXCLUDE_HINTS) or any(h in blob for h in SOURCE_EXCLUDE_HINTS) or any(h in url_blob for h in URL_EXCLUDE_HINTS):
        if not any(h in blob for h in POLICY_HINTS):
            return False
        return False
    if item.category in CURRENT_AFFAIRS_CATEGORIES:
        return True
    return any(h in blob for h in POLICY_HINTS) or any(h in blob for h in COSTLY_HINTS) or any(h in blob for h in CULTURE_HINTS)


def _normalized_words(text: str) -> set[str]:
    # \w alone does not include Kannada vowel-sign/virama combining marks
    # (Unicode category Mn), so a plain [^\w\s] strip shreds every
    # conjunct/matra-bearing Kannada word into single-letter fragments and
    # massively undercounts words. Explicitly keep the whole Kannada block.
    cleaned = re.sub(r"[^\w\sಀ-೿]", " ", (text or "").lower(), flags=re.UNICODE)
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
    # Only keep items with real topical overlap (shared category/source plus
    # actual shared words). Feeding in unrelated stories makes the model
    # invent fake connections between them instead of writing about the item.
    relevant = [(score, candidate) for score, candidate in ranked if score >= 4]
    return [candidate for _, candidate in relevant[:3]]


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
    return matches >= 1 or len(_normalized_words(text)) < 20


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
    has_context = bool(context_items)
    user_prompt = (
        f"Tone: {config.STYLE_TONE}.\n"
        "Task: Write a Kannada analysis of ONLY the current item below. It must be entirely about "
        "this one story — not a report, not a digest, not a list of other news.\n"
        f"Internal lens for interpretation: {lens_line}. Do not mention lens/framework names in the final text.\n"
        "Output rules:\n"
        "1) Output exactly 2 short Kannada paragraphs (roughly 40-70 words each), separated by one blank line, no headings, no labels, no bold text, no bullet points, no lists.\n"
        "2) Paragraph 1 must state one concrete fact from the current item and what it changes or reveals now.\n"
        "3) Paragraph 2 must give interpretation/implication of THIS item and end with one short forecast or watch-point sentence.\n"
        + (
            "4) The 'recent timeline context' below is background only, to help you judge whether this item fits a pattern. "
            "Only mention it if it shares the same real people, place, or exact issue as the current item. "
            "Never list, summarize, or describe the context items' own content — that turns the analysis into a digest, which is forbidden. "
            "If nothing in the context is genuinely and specifically connected, ignore the context completely and write only about the current item.\n"
            if has_context
            else "4) No timeline context was supplied; write only about the current item.\n"
        )
        + "5) Avoid slogans, personal attacks, sectarian hostility, legal accusations, or fear language.\n"
        "6) Do not add facts beyond the current item's title and summary.\n"
        "7) Do NOT paraphrase/copy the summary line-by-line; provide interpretation and implication.\n"
        "8) Do not mention any source-brand, author name, or template label.\n"
        "9) Do not use generic filler like 'big trend', 'thesis', 'mood read', or 'motive map'.\n"
        "10) Stop after the forecast sentence. Do not add a third paragraph or trail off.\n"
        f"Length budget: <= {config.MAX_ANALYSIS_TOKENS} tokens.\n\n"
        f"Style grounding:\n{style_context}\n\n"
        f"Current item (the ONLY subject of your analysis):\nTitle: {item.title}\nSummary: {item.summary}\nSource: {item.source}\n\n"
        f"Recent timeline context (background only, see rule 4):\n{_context_block(context_items)}\n"
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
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        system_prompt, user_prompt = _build_prompt(item, style_context, context_items)
        resp = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=config.MAX_ANALYSIS_TOKENS,
                temperature=0.4,
                # Gemini 2.5 models spend max_output_tokens on hidden "thinking"
                # tokens by default, which was starving the actual answer and
                # truncating it mid-sentence. Disable thinking for this task.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        text = getattr(resp, "text", "") or ""
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


def build_analysis(item: NewsItem, context_items: list[NewsItem] | None = None) -> str | None:
    """Return an LLM-quality Kannada analysis, or None if none could be produced.

    We deliberately do not publish the generic templated fallback anymore —
    it reads as obvious boilerplate and is not fit for public posting. When
    live LLM analysis is unavailable or every provider's output is rejected,
    callers should simply skip the analysis post for this item.
    """
    cache = _load_cache()
    key = _cache_key(item, context_items)
    cached = cache.get(key)
    if cached:
        return cached

    if not config.ENABLE_LLM_ANALYSIS or not config.ALLOW_LIVE_LLM:
        # Non-live mode (tests/dry-run/no API keys): keep the cheap
        # deterministic text so local previews still produce something.
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
                print(f"[analyzer] {provider} output looked generic; trying next provider")
                text = None
                continue
            if _too_close_to_source(item, text):
                print(f"[analyzer] {provider} output too close to source text; trying next provider")
                text = None
                continue
            print(f"[analyzer] analysis generated by {provider}")
            break

    if not text:
        print("[analyzer] no acceptable LLM analysis produced; skipping analysis post for this item")
        return None

    cache[key] = text
    _save_cache(cache)
    return text


# --- English-source analysis pipeline -------------------------------------
#
# The Kannada pipeline above sends Kannada-script text to Gemini and gets
# Kannada-script text back. Indic scripts are notably token-inefficient in
# current LLM tokenizers (each akshara commonly costs several tokens), so the
# same idea costs several times more than the English equivalent - on both
# the input and the output side. This pipeline instead: picks a single
# relevant story from English wire feeds, asks Gemini to analyze it in
# English (cheap), then translates the short result to Kannada with Groq's
# free tier (a pure translation task, not worth spending Gemini credits on).
# Net effect: one Gemini call and one Groq call per run, instead of up to
# MAX_AI_ANALYSES_PER_RUN Gemini calls on expensive Kannada text.

ENGLISH_ANALYSIS_PROMPT_VERSION = "2026-07-04-en-v5"

# Phrases that keep showing up as the model's default "safe" filler when it's
# told to sound decisive but isn't given a concrete alternative. These read as
# NGO-report/press-release boilerplate, not analysis, and were the exact
# complaint about the v3 prompt (flat facts + a generic "action is needed"
# closer). Any of these surviving into the English draft means the model
# reverted to the generic register instead of committing to a specific read.
_GENERIC_FILLER_PATTERNS = (
    r"(?i)systemic (weakness|vulnerability|failure)",
    r"(?i)(swift|prompt|urgent),?\s*transparent action",
    r"(?i)restor(e|ing) (public )?trust",
    r"(?i)accountability (is|remains) (needed|essential|crucial)",
    r"(?i)watch (for|out for) (accountability|new (measures|steps))",
    r"(?i)keep an eye on",
    r"(?i)raises questions (about|regarding)",
    r"(?i)cannot be (overlooked|ignored)",
    r"(?i)it is (important|essential|crucial) (to note|that)",
    r"(?i)(needs?|ought) to (be addressed|improve)",
    r"(?i)sends? a (strong )?signal",
    r"(?i)underscores? the (need|importance)",
)


def _has_generic_filler(text: str) -> bool:
    return any(re.search(pattern, text or "") for pattern in _GENERIC_FILLER_PATTERNS)


def _english_cache_key(item: NewsItem) -> str:
    basis = f"{ENGLISH_ANALYSIS_PROMPT_VERSION}\n{config.GEMINI_MODEL}|{config.GROQ_MODEL}\n{item.link}\n{item.title}".encode("utf-8")
    return "en:" + hashlib.sha256(basis).hexdigest()[:24]


_FEWSHOT_EXAMPLE = (
    "EXAMPLE — a flat, REJECTED version and why it fails, then the FIXED version:\n\n"
    "REJECTED (flat, generic — never write like this):\n"
    "\"Temple X now faces allegations of donation theft. After a similar problem in "
    "Location Y, this is a challenge to trust in temple administration. An investigation "
    "has been ordered.\n\nSuch repeated incidents show systemic weakness. Swift, "
    "transparent action is needed to restore trust. Watch for accountability and new "
    "safety measures.\"\n"
    "Why it fails: paragraph 1 is a bare restatement of the headline with no hook; "
    "paragraph 2 closes on a content-free civic-duty slogan ('accountability is needed') "
    "that could be pasted under literally any scandal story and says nothing concrete.\n\n"
    "FIXED (specific hook, committed read, concrete forecast):\n"
    "\"Donation money at Temple X allegedly went missing the same way it did at Location Y "
    "two years ago — same method, same excuse, different shrine. An 'investigation' is "
    "the standard reflex; the Location Y one never named a single person.\n\nRepeat "
    "failures like this are not bad luck, they are a system built to absorb the loss "
    "quietly rather than fix the leak. Expect this one to end the same way: a transfer "
    "order for a junior official within weeks, and the actual money never traced.\"\n"
    "Notice: it commits to a specific, checkable prediction instead of a vague call to "
    "action, and it treats the pattern (cause → repetition → institutional response) as "
    "the real story instead of restating the headline.\n"
)


def _build_english_prompt(item: NewsItem) -> tuple[str, str]:
    selected_lenses = _select_lenses(item, count=3)
    lens_line = ", ".join(selected_lenses)
    style_context = load_style_context()
    system_prompt = (
        "You are a sharp current-affairs analyst writing in English for a Sanatana "
        "Dharma-rooted advisory brand (Jyotisha, Tantra, Dharma Shastra, Vastu, Ayurveda). "
        f"Overall tone: {config.STYLE_TONE}. "
        "Write in a punchy, decisive voice: short sentences, active voice, one idea per "
        "sentence, vivid concrete word choice over abstract nouns. No hedging chains, no "
        "stacked subordinate clauses, no legalistic or bureaucratic phrasing "
        "('which... thereby... underscoring...'). "
        "Above all: NEVER default to generic press-release/NGO-report closers. Banned "
        "phrases (in any wording, English or translated): 'systemic weakness', 'swift/"
        "transparent action needed', 'restore trust', 'accountability is needed', 'watch "
        "for accountability or new measures', 'keep an eye on', 'raises questions', "
        "'sends a signal', 'underscores the need'. If your draft contains any of these, "
        "rewrite it before answering. "
        "Root the interpretation in the given dharmic lens below — read the story through "
        "cause, timing, duty, and consequence — without ever naming the lens or using "
        "jargon labels in the output. "
        f"{style_context}\n"
        "Do not imitate any living person's voice, brand, or catchphrases. "
        "Stay factual, non-inciting, and respectful. "
        "Never fabricate facts; when uncertain, say so plainly instead of hedging with soft language. "
        "Keep the output safe for public distribution and avoid defamation, sensationalism, or instructions for wrongdoing."
    )
    user_prompt = (
        f"{_FEWSHOT_EXAMPLE}\n"
        f"Interpretive lens for this story (apply naturally; never name it in the output): {lens_line}.\n"
        "Task: Write a short, decisive analysis of ONLY the story below, in the FIXED style above, not the REJECTED style.\n"
        "Output rules:\n"
        "1) Output exactly 2 short paragraphs (roughly 40-70 words each), separated by one blank line, no headings, no labels, no bullet points.\n"
        "2) Paragraph 1 MUST open with a sharp, specific hook in its first sentence — a concrete comparison, an ironic detail, or the sharpest fact stated bluntly. Do not open with a neutral 'X happened at Y' restatement of the headline.\n"
        "3) Paragraph 2: give the cause-consequence-duty reading through the lens above, ending with ONE concrete, checkable forecast (name a specific likely next step, outcome, or repeat pattern — not a vague call for 'action', 'vigilance', or 'improvement'). Commit to a read — avoid 'may', 'could potentially', or stacked qualifiers.\n"
        "4) Do not add facts beyond the title and summary given below — the specificity comes from framing and interpretation, not invented details.\n"
        "5) Do NOT paraphrase/copy the summary line-by-line; provide interpretation.\n"
        "6) Avoid slogans, personal attacks, sectarian hostility, legal accusations, or fear language.\n"
        "7) Do not mention any source-brand, author name, template label, or the lens name itself.\n"
        "8) Stop after the forecast sentence; do not add a third paragraph.\n\n"
        f"Title: {item.title}\nSummary: {item.summary}\nSource: {item.source}\n"
    )
    return system_prompt, user_prompt


def _try_gemini_english(item: NewsItem) -> str | None:
    if "gemini" in _DISABLED_PROVIDERS or not config.GEMINI_API_KEY:
        return None
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        system_prompt, user_prompt = _build_english_prompt(item)

        text = ""
        for attempt in range(2):
            prompt = user_prompt
            if attempt == 1:
                # First draft still had banned generic filler - name the exact
                # violation and force a rewrite instead of silently accepting it.
                prompt = (
                    user_prompt
                    + "\n\nYour previous draft used banned generic filler phrasing "
                    "(things like 'systemic weakness', 'transparent action needed', "
                    "'watch for accountability'). Rewrite from scratch: sharper hook "
                    "in paragraph 1, and a specific, concrete, checkable forecast in "
                    "paragraph 2 - no generic civic-duty closers."
                )
            resp = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=300,
                    temperature=0.6,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            text = getattr(resp, "text", "") or ""
            if text and not _has_generic_filler(text):
                break
            if text:
                print(f"[analyzer] gemini english draft (attempt {attempt + 1}) had generic filler; retrying" if attempt == 0 else "[analyzer] gemini english draft still had generic filler after retry")

        return _trim_analysis(text) or None
    except Exception as exc:
        if _is_quota_error(exc):
            _DISABLED_PROVIDERS.add("gemini")
            print("[analyzer] Gemini quota exhausted; disabled for this run")
        else:
            print(f"[analyzer] Gemini (english analysis) failed ({type(exc).__name__}: {exc})")
        return None


def _parse_translation(raw: str) -> tuple[str, str] | None:
    m_title = re.search(r"TITLE:\s*(.+)", raw)
    m_body = re.search(r"BODY:\s*(.+)", raw, re.DOTALL)
    if not m_title or not m_body:
        return None
    title = m_title.group(1).strip()
    body = _trim_analysis(m_body.group(1).strip())
    if not title or not body:
        return None
    return title, body


def _voice_anchor_block() -> str:
    anchors = load_voice_anchors(count=6)
    if not anchors:
        return ""
    numbered = "\n\n".join(f"{i}. {a}" for i, a in enumerate(anchors, start=1))
    return (
        "\n\nVOICE REFERENCE - real excerpts of this brand's own past Kannada writing. "
        "Mirror their RHETORICAL DEVICES ONLY (rhetorical question as a pivot, the "
        "mainstream-assumption-then-'ಆದರೆ'-rebuttal structure, em-dash pauses, a precise "
        "number or detail used as evidence, a confident one-line close). Do NOT copy their "
        "topics, claims, or specific facts - those excerpts are about unrelated subjects; "
        "this translation must stay strictly about the news item given below:\n"
        f"{numbered}\n"
    )


def _translation_prompt(title: str, body: str) -> str:
    return (
        "Translate the following English news title and analysis into natural, fluent "
        "Kannada with a punchy, decisive register: short confident sentences, plain "
        "everyday diction. Do NOT use formal/legalistic/bureaucratic Kannada register — "
        "avoid long chained clauses stacked before a single verb, and avoid overusing "
        "verbs like ಬಹಿರಂಗಪಡಿಸುತ್ತದೆ, ಸೂಚಿಸುತ್ತದೆ, ಒತ್ತಿಹೇಳುತ್ತದೆ/ಒತ್ತಿಹೇಳುತ್ತವೆ, ಪ್ರಶ್ನಿಸುತ್ತದೆ as "
        "sentence-ending hedges. Also do NOT substitute in generic press-release Kannada "
        "idioms even if they feel like a natural translation — avoid ವ್ಯವಸ್ಥಿತ ದೌರ್ಬಲ್ಯ "
        "(systemic weakness), ತ್ವರಿತ/ಪಾರದರ್ಶಕ ಕ್ರಮ ಅಗತ್ಯ (swift/transparent action needed), "
        "ನಂಬಿಕೆ ಮರುಸ್ಥಾಪಿಸಲು (restore trust), ಹೊಣೆಗಾರಿಕೆ ... ಗಮನಿಸಿ (watch for accountability). "
        "If the English source already made a specific, concrete claim, keep it specific and "
        "concrete in Kannada — do not flatten it into one of those generic phrases. "
        "Prefer short, direct sentences that state the claim and stop. "
        "Preserve the meaning and the confident tone exactly; do not add, remove, soften, "
        "or hedge claims that were stated plainly in English, and do not editorialize beyond "
        "the source text."
        f"{_voice_anchor_block()}\n"
        "The body has two paragraphs separated by a blank line - keep that "
        "same two-paragraph structure with a blank line between them in your Kannada "
        "translation; do not merge them into one paragraph. Respond in exactly this format "
        "and nothing else:\n"
        "TITLE: <kannada title>\nBODY: <kannada paragraph 1>\n\n<kannada paragraph 2>\n\n"
        f"TITLE: {title}\nBODY: {body}"
    )


def _translate_to_kannada(title: str, body: str) -> tuple[str, str] | None:
    """Translate an English title+analysis to Kannada. Tries Groq first
    (free tier, pure translation task) and only falls back to Gemini if Groq
    is unavailable, since the whole point of this path is to keep Kannada
    token volume off the paid/quota-limited provider."""
    prompt = _translation_prompt(title, body)

    if config.GROQ_API_KEY and "groq" not in _DISABLED_PROVIDERS:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=config.GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
            resp = client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=700,
                temperature=0.2,
            )
            raw = (resp.choices[0].message.content or "") if resp.choices else ""
            parsed = _parse_translation(raw)
            if parsed:
                return parsed
            print("[analyzer] Groq translation output malformed; trying Gemini fallback")
        except Exception as exc:
            if _is_quota_error(exc):
                _DISABLED_PROVIDERS.add("groq")
            print(f"[analyzer] Groq translation failed ({type(exc).__name__}: {exc}); trying Gemini fallback")

    if config.GEMINI_API_KEY and "gemini" not in _DISABLED_PROVIDERS:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=config.GEMINI_API_KEY)
            resp = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=700,
                    temperature=0.2,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            raw = getattr(resp, "text", "") or ""
            return _parse_translation(raw)
        except Exception as exc:
            print(f"[analyzer] Gemini translation fallback failed ({type(exc).__name__}: {exc})")

    return None


def build_english_analysis(item: NewsItem) -> tuple[str, str] | None:
    """Return (kannada_title, kannada_analysis_body) for a single English
    item, or None if no acceptable result could be produced. Caches by the
    item's link so a re-selected story doesn't re-spend LLM calls."""
    if not config.ENABLE_LLM_ANALYSIS or not config.ALLOW_LIVE_LLM:
        return None

    cache = _load_cache()
    key = _english_cache_key(item)
    cached = cache.get(key)
    if cached and isinstance(cached, dict) and cached.get("title") and cached.get("body"):
        return cached["title"], cached["body"]

    english_text = _try_gemini_english(item)
    if not english_text or len(_normalized_words(english_text)) < 15:
        print("[analyzer] english analysis too short/empty; skipping")
        return None
    if _too_close_to_source(item, english_text):
        print("[analyzer] english analysis too close to source text; skipping")
        return None
    if _has_generic_filler(english_text):
        print("[analyzer] english analysis still generic after retry; skipping rather than posting flat text")
        return None

    translated = _translate_to_kannada(item.title, english_text)
    if not translated:
        print("[analyzer] translation to kannada failed; skipping")
        return None

    kannada_title, kannada_body = translated
    cache[key] = {"title": kannada_title, "body": kannada_body}
    _save_cache(cache)
    return kannada_title, kannada_body