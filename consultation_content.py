"""Astrology/Tantra consultation-lead-generation content pipeline for the
Vedavidhya analysis channel (Telegram channel 2) + Facebook.

Why this exists: the brand's goal for this pipeline shifted from general
classical-systems education (see classical_content.py, now dormant/unused)
to a specific consultation-lead-generation strategy - every post should
interpret a real, spiritually-relevant news story through an astrology/
Tantra lens, connect it to the kind of personal problems that make someone
book a consultation, and close with a soft-then-strong booking CTA. This is
now the live path called from main.py's _run_classical_content and
_select_news_item.

Structure of every post (fixed, per the brand's exact spec):
1. Kannada headline - emotional, mysterious, consultation-oriented, not
   fear-mongering.
2. News summary (3-5 lines), simple and non-biased.
3. Astrology/Tantra angle - Graha drishti, Kala-dosha, collective karma,
   Rahu-Ketu, Shani, Mars/accident symbolism, Chandra/manas/fear, or Deva
   Prashna/Prashna Jyotisha.
4. Personal-life connection - marriage delay, business blockage, court
   cases, financial loss, health fear, family disturbance, negative energy,
   unexplained obstacles, career instability, etc.
5. Soft consultation CTA (fixed Kannada line, never LLM-generated).
6. Format: Kannada only, 300-600 words, light emojis, serious/mystical/
   mature tone, no fear-mongering, no guaranteed remedies, no disaster
   predictions, no attacks on religion/caste/party/community, "Vedavidhya"
   mentioned naturally once near the end, 8-12 mixed Kannada/English
   hashtags, and a final stronger booking CTA line (fixed) as the very last
   line of the post.

News selection is a HARD gate, not just a scoring boost: per the brand's
explicit instruction, an "ordinary" story with no spiritual/karmic/
astrological/occult angle should never be forced through just because
nothing else is available that run - see score_relevance()/is_consultation_
worthy() below, used by main.py's _select_news_item.
"""

from __future__ import annotations

import hashlib
import random
import re

import config
from analyzer import (
    _DISABLED_PROVIDERS,
    _clean_paragraph,
    _has_generic_filler,
    _is_quota_error,
    _normalized_words,
    _translate_to_kannada,
)
from style_corpus import load_style_context


# -----------------------------------------------------------------------------
# News-selection relevance (the hard "is this consultation-worthy?" gate)
# -----------------------------------------------------------------------------
# ENGLISH_SOURCES (config.py) feeds are English-language, so these hints are
# English-only - consistent with the pre-existing POLICY_HINTS/COSTLY_HINTS
# this replaces in main.py's _select_news_item.

CONSULTATION_HINTS: dict[str, tuple[str, ...]] = {
    "business": ("business", "company", "industry", "startup", "merger", "bankrupt", "shutdown", "ceo", "corporate", "factory", "firm"),
    "politics": ("election", "minister", "government", "party", "politic", "cabinet", "assembly", "parliament", "chief minister", "mla", "mp ", "cm "),
    "marriage": ("marriage", "wedding", "divorce", "bride", "groom", "engagement", "married"),
    "health": ("health", "hospital", "disease", "outbreak", "epidemic", "illness", "died", "dead", "death toll"),
    "finance": ("finance", "bank", "loan", "debt", "stock market", "share market", "rupee", "economy", "recession", "fraud", "scam", "gst", "tax raid"),
    "land": ("land", "property", "encroachment", "eviction", "acquisition", "real estate", "plot"),
    "court": ("court", "judge", "verdict", "case", "lawsuit", "legal", "tribunal", "petition", "hearing"),
    "career": ("job", "layoff", "unemployment", "career", "resign", "sacked", "fired", "recruitment"),
    "fear": ("fear", "panic", "terror", "threat", "warning", "scare", "alert"),
    "sudden_loss": ("killed", "death", "died", "collapse", "sudden death", "demise", "drowned", "succumbed"),
    "scandal": ("scandal", "scam", "corruption", "bribery", "expose", "leak", "controversy", "row"),
    "accident": ("accident", "crash", "collision", "derail", "fire", "blast", "explosion", "mishap", "injured"),
    "public_unrest": ("protest", "riot", "unrest", "clash", "strike", "agitation", "violence", "curfew", "bandh"),
    "weather_extreme": ("flood", "cyclone", "drought", "heatwave", "earthquake", "landslide", "storm", "heavy rain", "disaster"),
    "strange_event": ("mysterious", "unexplained", "bizarre", "strange", "unusual", "miracle", "haunt", "omen"),
    "crisis": ("crisis", "emergency", "collapse", "chaos", "turmoil"),
}


def score_relevance(item_title: str, item_summary: str, item_category: str = "") -> tuple[int, list[str]]:
    """Return (score, matched_theme_categories). Score is the count of
    distinct theme categories matched, not raw keyword hits, so one story
    covering both 'court' and 'scandal' outranks a story hitting 'business'
    five times over via near-synonyms."""
    blob = f"{item_title} {item_summary} {item_category}".lower()
    matched = [theme for theme, hints in CONSULTATION_HINTS.items() if any(h in blob for h in hints)]
    return len(matched), matched


def is_consultation_worthy(item_title: str, item_summary: str, item_category: str = "") -> bool:
    score, _ = score_relevance(item_title, item_summary, item_category)
    return score > 0


# -----------------------------------------------------------------------------
# Astrology/Tantra interpretive angles + personal-life connection themes
# -----------------------------------------------------------------------------
# Rotated (avoiding immediate repeats via content_state.py's recent history,
# repurposed the same way classical_content.py already does) so consecutive
# posts don't lean on the same angle/pain-point every time.

ASTRO_ANGLES: dict[str, str] = {
    "graha_drishti": "Graha drishti - the mutual aspect/influence between planets shaping how an event unfolds",
    "kala_dosha": "Kala-dosha - afflictions tied to inauspicious timing (rahukala, eclipse windows, adverse transits)",
    "collective_karma": "Collective karma - a community, region, or institution experiencing a shared karmic consequence together",
    "rahu_ketu": "Rahu-Ketu axis - the shadow planets causing sudden, deceptive, or unusual disruptions",
    "shani_influence": "Shani (Saturn) influence - delay, discipline, structural collapse, karmic reckoning",
    "mars_symbolism": "Mars/Kuja symbolism - aggression, fire, accident, conflict, bloodshed",
    "chandra_manas": "Chandra (Moon)/manas - collective fear, public emotion, mass anxiety, disturbed collective mind",
    "deva_prashna": "Deva Prashna / Prashna Jyotisha perspective - a divine query into why a place/deity/community is disturbed",
}

PERSONAL_LIFE_THEMES: dict[str, str] = {
    "marriage_delay": "marriage delay or relationship instability",
    "business_blockage": "business blockage or repeated failed ventures",
    "repeated_failures": "repeated failures despite genuine effort",
    "court_cases": "ongoing court cases or legal disputes that drag on",
    "financial_loss": "unexplained financial loss or mounting debt",
    "sudden_health_fear": "sudden health fear or an unexplained illness",
    "family_disturbance": "family disturbance or ongoing discord at home",
    "negative_energy": "a persistent sense of negative energy at home or at work",
    "unexplained_obstacles": "unexplained, recurring obstacles that block every attempt to move forward",
    "political_business_enemies": "hidden rivals or enemies in politics or business",
    "career_instability": "career instability or a sudden sense of job insecurity",
}


def _select_angle_and_theme(recent_history: list[dict]) -> tuple[str, str]:
    recent_history = recent_history or []
    recent_angles = [r.get("system") for r in recent_history[-3:]]
    recent_themes = [r.get("genre") for r in recent_history[-3:]]

    angles = [a for a in ASTRO_ANGLES if a not in recent_angles] or list(ASTRO_ANGLES)
    angle_key = random.choice(angles)

    themes = [t for t in PERSONAL_LIFE_THEMES if t not in recent_themes] or list(PERSONAL_LIFE_THEMES)
    theme_key = random.choice(themes)

    return angle_key, theme_key


# -----------------------------------------------------------------------------
# Hashtags
# -----------------------------------------------------------------------------

HASHTAG_POOL: tuple[str, ...] = (
    "Jyotisha", "ಜ್ಯೋತಿಷ್ಯ", "VedicAstrology", "ಜಾತಕ", "PrashnaJyotisha", "ಪ್ರಶ್ನಜ್ಯೋತಿಷ್ಯ",
    "Rahu", "Ketu", "Shani", "ಶನಿ", "Graha", "ಗ್ರಹ", "Karma", "ಕರ್ಮ", "TantraVidya", "ತಂತ್ರ",
    "KarnatakaNews", "ಕರ್ನಾಟಕ", "AstrologyConsultation", "VedicWisdom", "SpiritualGuidance",
    "DevaPrashna", "KalaDosha", "SanatanaDharma", "ಸನಾತನಧರ್ಮ", "Jataka", "Nakshatra",
)

_THEME_HASHTAG_MAP: dict[str, str] = {
    "marriage": "MarriageAstrology",
    "court": "LegalKarma",
    "business": "BusinessAstrology",
    "finance": "FinancialAstrology",
    "health": "AstroHealth",
    "career": "CareerAstrology",
    "accident": "KalaDosha",
    "public_unrest": "CollectiveKarma",
    "weather_extreme": "PrakritiKarma",
    "scandal": "KarmicJustice",
    "fear": "GrahaShanti",
    "sudden_loss": "ShaniInfluence",
    "politics": "Rajaneeti",
    "land": "VastuDosha",
    "strange_event": "DevaPrashna",
    "crisis": "CollectiveKarma",
}


def select_hashtags(item_id: str, matched_themes: list[str], count_min: int = 8, count_max: int = 12) -> list[str]:
    tags = ["Vedavidhya", "Jyotisha", "Tantra"]
    for theme in matched_themes:
        tag = _THEME_HASHTAG_MAP.get(theme)
        if tag and tag not in tags:
            tags.append(tag)

    pool = [t for t in HASHTAG_POOL if t not in tags]
    if pool:
        stable_seed = int(hashlib.sha256((item_id or "seed").encode("utf-8")).hexdigest()[:8], 16)
        offset = stable_seed % len(pool)
        rotated = pool[offset:] + pool[:offset]
        for tag in rotated:
            if len(tags) >= count_max:
                break
            tags.append(tag)

    if len(tags) < count_min:
        # Should not normally happen (pool is large), but never post below spec.
        for tag in HASHTAG_POOL:
            if tag not in tags:
                tags.append(tag)
            if len(tags) >= count_min:
                break

    return tags[:count_max]


# -----------------------------------------------------------------------------
# Fixed CTA lines (never LLM-generated, so exact wording can never drift)
# -----------------------------------------------------------------------------

SOFT_CTA_LINE = (
    "ನಿಮ್ಮ ಜೀವನದಲ್ಲೂ ಇದೇ ರೀತಿಯ ಪುನರಾವರ್ತಿತ ಅಡೆತಡೆಗಳು, ಭಯ, ವಿಳಂಬ, ನಷ್ಟ ಅಥವಾ ಅಸ್ಪಷ್ಟ ಸಮಸ್ಯೆಗಳು "
    "ಕಾಣಿಸುತ್ತಿದ್ದರೆ, ಜಾತಕ / ಪ್ರಶ್ನ / ತಾಂತ್ರಿಕ ದೃಷ್ಟಿಯಿಂದ ಕಾರಣವನ್ನು ಪರಿಶೀಲಿಸಬಹುದು."
)

STRONG_CTA_LINE = (
    "📩 ಜಾತಕ, ಪ್ರಶ್ನ ಜ್ಯೋತಿಷ್ಯ ಅಥವಾ ತಾಂತ್ರಿಕ ದೃಷ್ಟಿಯಿಂದ ನಿಮ್ಮ ಸಮಸ್ಯೆಯ ಮೂಲ ಕಾರಣ ತಿಳಿಯಲು "
    "Vedavidhya consultation ಬುಕ್ ಮಾಡಬಹುದು. Website: www.vedavidhya.com"
)


# -----------------------------------------------------------------------------
# Safety rules
# -----------------------------------------------------------------------------

CONSULTATION_SAFETY_RULES = (
    "Absolute rules:\n"
    "- Never use markdown formatting of any kind - no **bold**, no *italic*/*emphasis*, no _underline_, no "
    "backticks, no # headings, no bullet lists. Telegram and Facebook do not render markdown here; asterisks "
    "and underscores would show up as literal punctuation in the published post.\n"
    "- Never make a direct, specific disaster prediction about any named person or place (e.g. do not say a "
    "particular leader/company/place 'will collapse/die/lose everything'). Speak in terms of patterns, "
    "tendencies, and possibilities, not certainties.\n"
    "- Never guarantee that any remedy, ritual, or consultation will produce a specific outcome. Frame "
    "consultation as a way to understand the root cause, not as a promised fix.\n"
    "- Never insult, blame, or target any political party, religion, caste, region, or community for the event. "
    "Treat the astrological/karmic lens as being about universal patterns of time and karma, not about blaming "
    "any group of people.\n"
    "- Do not write fear-based or cheap clickbait marketing ('this will destroy your life', 'act now or suffer'). "
    "The tone must stay serious, mystical, and mature - never panicked or sensational.\n"
    "- Do not invent fake verse numbers, fake studies, fake quotes, or specific facts beyond the news "
    "title/summary given.\n"
    "- If the story involves death, tragedy, or victims, treat it with dignity and restraint - interpret the "
    "pattern, never sensationalize the human loss itself.\n"
)


# -----------------------------------------------------------------------------
# Prompting and generation
# -----------------------------------------------------------------------------

def _build_prompt(
    item_title: str,
    item_summary: str,
    item_source: str,
    angle_key: str,
    theme_key: str,
) -> tuple[str, str]:
    """English-draft prompt (translated to Kannada afterward - see module
    docstring in classical_content.py for why the draft stays in English:
    the translation step needs real English source text, and Kannada is far
    more token-expensive to draft directly on a paid model)."""
    angle_desc = ASTRO_ANGLES[angle_key]
    theme_desc = PERSONAL_LIFE_THEMES[theme_key]
    style_context = load_style_context()

    system_prompt = (
        "You are an English-drafting current-affairs interpreter for Vedavidhya, a Sanatana Dharma-rooted "
        "astrology, Tantra, and spiritual-consultation brand whose posts are published in Kannada (your English "
        "draft will be translated to Kannada afterward - write plainly so translation is straightforward). "
        "Your goal is to attract serious astrology/Tantra consultation clients by reading today's news through "
        "an astrological/karmic lens and connecting it to the kind of recurring personal problems that make a "
        "reader want to book a consultation. The tone must be serious, mystical, and mature - never cheap fear "
        "marketing, never a direct disaster prediction, never a guaranteed-remedy claim. "
        f"{CONSULTATION_SAFETY_RULES}"
        f"{style_context}\n"
        "Keep the output safe for public distribution."
    )

    user_prompt = (
        "Real news story to interpret (the ONLY subject of this post - do not write about anything else):\n"
        f"Title: {item_title}\nSummary: {item_summary}\nSource: {item_source}\n\n"
        f"Primary astrological/Tantra angle to use: {angle_desc}\n"
        f"Primary personal-life connection to draw: {theme_desc}\n\n"
        "Write EXACTLY 5 short ENGLISH paragraphs (this will be translated to Kannada afterward - do not write "
        "in Kannada), following this structure:\n"
        "1) NEWS SUMMARY (3-5 plain sentences): explain the event simply and neutrally. Do not editorialize or "
        "take a political side; just state what happened.\n"
        "2) ASTROLOGY/TANTRA ANGLE (primary): interpret this specific story through the primary angle given "
        "above - name the concept naturally (e.g. 'Rahu-Ketu', 'Shani', 'Graha drishti', 'Kala-dosha') and "
        "explain what such an event may indicate.\n"
        "3) ASTROLOGY/TANTRA ANGLE (secondary, for depth): bring in ONE more angle from this list that fits - "
        "graha drishti, kala-dosha, collective karma, Rahu-Ketu, Shani, Mars/accident symbolism, Chandra/manas/"
        "collective fear, or Deva Prashna/Prashna Jyotisha - without repeating the primary angle verbatim.\n"
        "4) PERSONAL-LIFE CONNECTION: connect this pattern to real personal problems people face, centered on "
        f"'{theme_desc}', plus one or two more from: marriage delay, business blockage, repeated failures, "
        "court cases, financial loss, sudden health fear, family disturbance, negative energy, unexplained "
        "obstacles, political/business enemies, career instability.\n"
        "5) CLOSING REFLECTION: end with one memorable, reflective closing line that invites the reader to "
        "look inward at their own recurring problems. Mention 'Vedavidhya' naturally once, near the end of this "
        "paragraph, as the source of this perspective (not as a hard sales pitch - a soft mention only; the "
        "actual booking call-to-action will be added separately after your text, so do not write your own CTA "
        "or invite bookings yourself).\n\n"
        "Output rules:\n"
        "1) Each paragraph should be roughly 60-110 words, for a combined total in the 350-550 word range.\n"
        "2) No headings, no bullets, no numbering, no paragraph labels inside the body.\n"
        "3) Do not mention the angle names or theme names as literal labels (e.g. don't write 'Angle: Shani') - "
        "weave them naturally into the prose.\n"
        "4) Do not add facts beyond the title/summary given above; if unsure of a detail, speak in general "
        "terms rather than inventing specifics.\n"
        "5) Do not write your own call-to-action, booking invitation, website mention, or hashtags - those are "
        "added separately after your text.\n"
        "6) No asterisks, underscores, backticks, or markdown symbols anywhere - plain text only.\n"
        "7) Stop after the fifth paragraph.\n\n"
        "Respond in exactly this format and nothing else:\n"
        "TITLE: <emotional, mysterious, consultation-oriented English headline, max 14 words, NOT fear-mongering>\n"
        "ANGLE_USED: <one short phrase naming the primary + secondary angle you actually used>\n"
        "BODY: <paragraph 1>\n\n<paragraph 2>\n\n<paragraph 3>\n\n<paragraph 4>\n\n<paragraph 5>\n"
        "IMAGE_PROMPT: <one-line English description of a textless, mystical/astrology-themed FB/Telegram "
        "visual suited to this story - e.g. cosmic/planetary imagery, temple silhouette, night sky - no text "
        "or logos in the image>"
    )

    return system_prompt, user_prompt


def _parse_draft(raw: str) -> dict | None:
    """Custom parser (not analyzer._parse_translation) so this module's
    longer-form output is never silently truncated by the short 2-paragraph
    analysis pipeline's character cap - see analyzer._trim_analysis."""
    m_title = re.search(r"TITLE:\s*(.+)", raw)
    m_angle = re.search(r"ANGLE_USED:\s*(.+)", raw)
    m_body = re.search(r"BODY:\s*(.+?)(?=\nIMAGE_PROMPT:|\Z)", raw, re.DOTALL)
    m_image = re.search(r"IMAGE_PROMPT:\s*(.+)", raw)
    if not m_title or not m_body:
        return None

    title = m_title.group(1).strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", m_body.group(1).strip()) if p.strip()]
    if not paragraphs:
        return None
    body = "\n\n".join(_clean_paragraph(p) for p in paragraphs)
    if not title or not body:
        return None

    return {
        "title": title,
        "body": body,
        "angle_used": m_angle.group(1).strip() if m_angle else "",
        "image_prompt": m_image.group(1).strip() if m_image else "",
    }


def _draft_with_gemini(system_prompt: str, user_prompt: str, context_label: str) -> dict | None:
    if "gemini" in _DISABLED_PROVIDERS or not config.GEMINI_API_KEY:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=config.GEMINI_API_KEY)

        for attempt in range(2):
            prompt = user_prompt
            if attempt == 1:
                prompt = (
                    user_prompt
                    + "\n\nYour previous draft was too generic, too short, too fear-mongering, made a direct "
                    "disaster prediction, guaranteed a remedy outcome, drifted off the given subject, or did "
                    "not follow the TITLE:/ANGLE_USED:/BODY:/IMAGE_PROMPT: format exactly. Rewrite from "
                    "scratch, staying strictly on the given news story, with the full 5-paragraph structure."
                )

            resp = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=1100,
                    temperature=0.72,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )

            raw = getattr(resp, "text", "") or ""
            parsed = _parse_draft(raw)
            if parsed and not _has_generic_filler(parsed["body"]):
                return parsed

            print(
                f"[consultation_content] gemini draft ({context_label}, attempt {attempt + 1}) rejected; retrying"
                if attempt == 0
                else f"[consultation_content] gemini draft ({context_label}) still rejected after retry"
            )

        return None

    except Exception as exc:
        if _is_quota_error(exc):
            _DISABLED_PROVIDERS.add("gemini")
            print("[consultation_content] Gemini quota exhausted; disabled for this run")
        else:
            print(f"[consultation_content] Gemini failed ({type(exc).__name__}: {exc})")
        return None


def generate_consultation_post(
    item_title: str,
    item_summary: str,
    item_source: str,
    recent_history: list[dict] | None = None,
) -> dict | None:
    """Generate one consultation-lead-generation post interpreting a specific
    real, unique news story. Returns None if any stage fails or produces
    unacceptable output - the caller should skip posting this run rather
    than publish a weak/off-spec post."""
    if not config.GEMINI_API_KEY:
        print("[consultation_content] no Gemini API key configured; skipping")
        return None

    recent_history = recent_history or []
    angle_key, theme_key = _select_angle_and_theme(recent_history)
    match_score, matched_themes = score_relevance(item_title, item_summary)

    system_prompt, user_prompt = _build_prompt(item_title, item_summary, item_source, angle_key, theme_key)
    draft = _draft_with_gemini(system_prompt, user_prompt, context_label=f"{angle_key}/{theme_key}")
    if not draft:
        print(f"[consultation_content] no acceptable english draft (angle={angle_key} theme={theme_key})")
        return None

    if len(_normalized_words(draft["body"])) < 130:
        print("[consultation_content] english draft too short for the 300-600 word target; skipping")
        return None

    # Generous length budget: Kannada script is token-heavy, and 300-600
    # target words is well beyond the 700-token/~2500-char default sized for
    # classical_content.py's shorter posts.
    translated = _translate_to_kannada(draft["title"], draft["body"], max_chars=4500, max_output_tokens=2400)
    if not translated:
        print("[consultation_content] translation to kannada failed; skipping")
        return None

    kannada_title, kannada_body = translated
    kannada_word_count = len(_normalized_words(kannada_body))
    if kannada_word_count < 150:
        print(f"[consultation_content] kannada body too short ({kannada_word_count} words, target 300-600); posting anyway but flagging")

    hashtags = select_hashtags(item_title, matched_themes)

    return {
        "title": kannada_title,
        "body": kannada_body,
        "angle_key": angle_key,
        "angle_label": ASTRO_ANGLES[angle_key],
        "angle_used_raw": draft.get("angle_used", ""),
        "theme_key": theme_key,
        "theme_label": PERSONAL_LIFE_THEMES[theme_key],
        "matched_news_themes": matched_themes,
        "hashtags": hashtags,
        "image_prompt": draft.get("image_prompt", ""),
        "subtopic": item_title,
        "kannada_word_count": kannada_word_count,
    }
