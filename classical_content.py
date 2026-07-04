"""Generate original, evergreen Kannada content mapped to classical Indian
knowledge systems, rotating through specific topics, genres, and safe literary
style modes.

Why this exists: the old pipeline (see analyzer.py's English-source analysis
section) picked a daily-news story and ran it through a "dharmic lens" — useful
for a fast-news channel, but the brand's own Facebook page
(vedavidhya.astrology.tantra) needs content that is actually ABOUT Vedic
Astrology, Tantra, Vedic Science, Ayurveda, Ganita, Tarka, Nyaya, Vedanta,
Mimamsa, Vyakarana, Smriti, Dharmashastra, Arthashastra, Agama, Itihasa,
Panchatantra, and classical arts/literature — not current-affairs commentary
wearing a Sanatan costume.

This module is decoupled from the news cycle entirely: it picks a
(classical system, specific angle, content genre, writing style) combination,
generates a short English draft with Gemini, and reuses analyzer.py's existing
translation pipeline (Groq-first, Gemini fallback) to produce the final Kannada
post — same cost model as before, just a different source of what gets written
about.

Cadence and repeat-avoidance are handled by the caller (main.py) via
content_state.py, which is passed in here as `recent_history` so the topic,
genre, and style rotation does not repeat the same angle back-to-back across
runs.
"""

from __future__ import annotations

import random

import config
from analyzer import (
    _DISABLED_PROVIDERS,
    _has_generic_filler,
    _is_quota_error,
    _normalized_words,
    _parse_translation,
    _translate_to_kannada,
)
from style_corpus import load_style_context


# -----------------------------------------------------------------------------
# Topic bank
# -----------------------------------------------------------------------------
# Each key is a classical system. Subtopics are specific enough to give the model
# a real angle instead of a vague topic name. That is what keeps output from
# reading like generic "spiritual content".

TOPIC_BANK: dict[str, list[str]] = {
    "Jyotisha (Vedic Astrology)": [
        "Why a horoscope should be read through lagna, moon, dasha, and gochara together",
        "Why marriage delay is not always caused by one single dosha",
        "How dasha decides timing while yoga decides potential",
        "Why Saturn delays but does not always deny",
        "How Rahu creates unusual life patterns without being purely evil",
        "Why remedies work only when karma, effort, and timing cooperate",
        "How muhurta protects an action by choosing the right doorway of time",
        "Why Prashna Jyotisha is different from birth-chart astrology",
        "How Arudha Lagna shows public image and social perception",
        "Why Navamsha cannot be read like a second independent birth chart",
        "How Gulika and Mandi are used carefully in Kerala Jyotisha",
        "Why blanket online predictions fail without desha, kala, and patra",
    ],
    "Tantra, Sadhana & Shakti": [
        "What Shakti means as conscious power, not merely feminine symbolism",
        "Why mantra is not sound alone but sound plus adhikara, sankalpa, and shuddhi",
        "The difference between authentic Tantra and market sensationalism",
        "Why nyasa transforms the body into a ritual field",
        "How yantra works as geometry, concentration, and devata-bhava together",
        "Why guru-parampara matters in mantra sadhana",
        "The role of diksha and why self-randomized mantras can be dangerous spiritually",
        "Why kavacha is not superstition but a ritual psychology of protection",
        "How Shakta worship balances bhakti, mantra, kriya, and jnana",
        "Why Kali is misunderstood when seen only as a fierce goddess",
        "Why some sadhanas are tied to tithi, nakshatra, and night divisions",
    ],
    "Ayurveda": [
        "Ayurveda's tridosha model as a systems-thinking framework of the body",
        "Why prakriti and vikriti must be understood separately",
        "How agni explains digestion, immunity, clarity, and disease formation",
        "Why ama is more than indigestion in Ayurvedic reasoning",
        "How dinacharya prevents disease before symptoms become serious",
        "Why ritucharya changes food, sleep, and activity according to season",
        "The logic behind pathya and apathya in healing",
        "Why Ayurveda treats food as medicine but not every food as medicine for everyone",
        "How rasa, guna, virya, vipaka, and prabhava shape herbal action",
        "Why classical kitchen spices are not casual flavoring but digestive intelligence",
        "How South Indian cooking preserves many Ayurvedic principles silently",
        "Why Ayurveda should be practiced responsibly alongside modern medical care when needed",
    ],
    "Ganita & Indian Mathematics": [
        "What the Sulba Sutras reveal about geometry before temple and yajna construction",
        "How Indian mathematics treated number, measure, proportion, and infinity",
        "Why zero was not just a digit but a conceptual revolution",
        "How place-value notation changed the history of calculation",
        "The mathematical structure behind tala in Indian classical music",
        "How combinatorics appears in Sanskrit prosody and chandas",
        "Why Pingala's work matters in the history of binary-like thinking",
        "How temple architecture uses proportion, symmetry, and sacred measurement",
        "Why ganita was tied to astronomy, calendar, ritual, trade, and architecture",
        "How practical arithmetic shaped ancient commerce and statecraft",
    ],
    "Tarka & Logic": [
        "Why tarka means disciplined reasoning, not casual argument",
        "How classical debate separates truth-seeking from ego-winning",
        "Why a good objection is respected in Indian philosophical traditions",
        "How purvapaksha trains intellectual honesty",
        "Why refuting an opponent requires first understanding them properly",
        "The difference between doubt, objection, contradiction, and conclusion",
        "How tarka protects spiritual life from blind belief",
        "Why debate without maryada becomes intellectual violence",
        "How traditional logic can improve modern social-media thinking",
    ],
    "Nyaya Shastra": [
        "The Nyaya model of pramana and why valid knowledge still matters",
        "How perception, inference, comparison, and testimony function as knowledge sources",
        "Why not all testimony is accepted blindly in Nyaya",
        "How Nyaya identifies fallacies in argument",
        "Why inference needs vyapti, not mere guesswork",
        "How Nyaya protects dharma from superstition and emotional manipulation",
        "The difference between genuine reasoning and rhetorical cleverness",
        "Why Nyaya is essential for interpreting scripture responsibly",
        "How Nyaya can train students to think clearly in modern education",
    ],
    "Vedanta": [
        "Why Vedanta begins with inquiry, not blind belief",
        "The difference between Atman and ego in Vedantic teaching",
        "How the Upanishadic method uses listening, reflection, and contemplation",
        "Why vairagya is not hatred of life but freedom from slavery to craving",
        "How karma, bhakti, and jnana can support each other",
        "Why Vedanta is not escapism but a disciplined search for reality",
        "How the Gita balances action and inner detachment",
        "Why self-knowledge is not intellectual information alone",
        "The difference between temporary peace and true inner freedom",
        "How Vedanta speaks to anxiety, identity, and modern restlessness",
    ],
    "Mimamsa": [
        "Why Mimamsa treats Vedic words as precise instruments of action",
        "How vidhi, nishedha, mantra, and arthavada guide ritual interpretation",
        "Why ritual is not empty performance when understood through Mimamsa",
        "How adhikara decides who should perform which action",
        "Why intention alone is not enough without correct procedure",
        "How Mimamsa explains the unseen result of action through apurva",
        "Why scriptural interpretation requires rules, not personal imagination",
        "How Mimamsa protects tradition from careless distortion",
        "Why mantra pronunciation and sequence matter in ritual grammar",
    ],
    "Vyakarana & Sanskrit": [
        "Why Sanskrit grammar is a knowledge system, not merely language rules",
        "How Panini created one of the most precise linguistic systems in history",
        "Why akshara-shuddhi matters in mantra and recitation",
        "How sandhi changes sound without destroying meaning",
        "Why wrong Sanskrit can distort both mantra and philosophy",
        "How dhatu, pratyaya, and pada reveal layered meaning",
        "Why Vyakarana is considered a Vedanga",
        "How grammar protects scripture from casual misinterpretation",
        "The difference between poetic liberty and grammatical corruption",
        "Why mantra creators should not invent pseudo-Sanskrit carelessly",
    ],
    "Smriti & Dharmashastra": [
        "Why Smriti texts apply dharma according to context, role, and circumstance",
        "How dharma changes under apad-dharma during crisis",
        "Why Smriti is not one frozen rulebook but a layered legal-ethical tradition",
        "How family, inheritance, duty, conduct, and purification are treated in Smriti literature",
        "Why selective quotation of Smriti creates misunderstanding",
        "How prayashchitta works as moral correction, not fear-based punishment",
        "Why dharma needs both principle and practical judgment",
        "How achara, sadachara, and loka-sangraha shape social conduct",
        "Why traditional law cannot be understood without desha, kala, and patra",
    ],
    "Arthashastra & Rajaneeti": [
        "Kautilya's taxation principle and why the state must not crush productivity",
        "How mandala theory explains alliances, rivals, and strategic geography",
        "Why intelligence-gathering was treated as ordinary statecraft",
        "How leadership requires discipline, secrecy, timing, and counsel",
        "Why wealth creation and social order are linked in Arthashastra",
        "How punishment and welfare are both tools of governance",
        "Why emotional politics fails without institutional thinking",
        "How ancient rajaneeti can inform modern political strategy ethically",
    ],
    "Agama & Temple Tradition": [
        "Why Agama is central to temple worship and murti-pratishtha",
        "How temple ritual differs from domestic puja",
        "Why daily temple worship follows a precise sequence",
        "The meaning of avahana, upachara, alankara, naivedya, and arati",
        "How Agama connects mantra, murti, mandala, and sacred space",
        "Why temple architecture is theology expressed in stone",
        "How Shiva, Shakti, Vishnu, and Subrahmanya Agamas differ in emphasis",
        "Why temple priests preserve living ritual science, not mere custom",
        "How utsava brings divine presence into community life",
    ],
    "Vastu, Shilpa & Temple Architecture": [
        "Why Vastu is about alignment, proportion, function, and energy flow",
        "How mandala principles shape temple and home design",
        "Why measurement is sacred in Shilpa Shastra",
        "How prana-pratishtha changes a sculpture into a worshipped murti",
        "Why traditional architecture cares about entrance, light, water, and movement",
        "How iconography encodes philosophy through posture, weapon, mudra, and vehicle",
        "Why temple towers are not decoration but symbolic ascent",
        "How vastu mistakes should be corrected practically, not fearfully",
    ],
    "Yoga Shastra": [
        "Why Yoga is chitta-vritti-nirodha, not only physical exercise",
        "How yama and niyama prepare the mind before higher practice",
        "Why pranayama must be approached with discipline and guidance",
        "How asana originally supports steadiness, not body-display culture",
        "The difference between concentration, meditation, and samadhi",
        "Why Yoga and Ayurveda complement each other in lifestyle discipline",
        "How mantra, breath, posture, and attention work together",
        "Why spiritual practice without ethical foundation becomes unstable",
    ],
    "Itihasa - Ramayana & Mahabharata": [
        "What Rama teaches about duty under personal suffering",
        "Why Sita's strength is often misunderstood as passive endurance",
        "How Hanuman represents intelligence, devotion, courage, and humility together",
        "Why Arjuna's confusion is the beginning of wisdom, not weakness",
        "How Krishna teaches action without inner slavery to results",
        "Why Vidura represents fearless counsel to power",
        "What Bhishma teaches about the danger of vows without dharmic flexibility",
        "Why Karna's tragedy is not simple heroism or simple villainy",
        "How Draupadi's question in the court exposes the collapse of dharma",
        "Why the Mahabharata refuses simplistic moral storytelling",
    ],
    "Puranas": [
        "Why Purana uses story to teach metaphysics, ethics, and devotion",
        "How Shiva Purana presents destruction as transformation",
        "Why Devi Mahatmya is a psychology of inner and outer battle",
        "How Bhagavata Purana turns devotion into a path of knowledge",
        "Why Ganesha stories encode intelligence, humility, and removal of obstacles",
        "How Skanda traditions preserve martial, yogic, and spiritual symbolism",
        "Why Puranic stories should not be read as childish fantasy alone",
        "How avatar stories respond to different kinds of adharma",
    ],
    "Niti Shastra & Panchatantra": [
        "Why Panchatantra teaches political intelligence through animal stories",
        "How flattery becomes a weapon in the wrong hands",
        "Why friendship must be tested before trust is given",
        "How greed makes even intelligent people foolish",
        "Why weak people need strategy more than anger",
        "How timing matters more than brute strength",
        "Why Panchatantra is not children's literature alone",
        "How niti differs from moral preaching",
    ],
    "Indian Classical Arts": [
        "Why raga is not merely melody but mood, time, and discipline",
        "How tala teaches mathematical awareness through rhythm",
        "Why mudras in dance are a language of meaning",
        "How Natya Shastra unites drama, music, emotion, and spirituality",
        "Why rasa theory is still relevant to cinema, storytelling, and marketing",
        "How classical art trains attention and emotional refinement",
        "Why sacred art is not entertainment alone",
    ],
    "Classical Literature & Kavya": [
        "What Kalidasa teaches about restraint, beauty, and emotional suggestion",
        "How kavya uses dhvani to say more than the literal sentence",
        "Why subhashitas survive because they compress life-wisdom into memorable lines",
        "How classical poetry trains taste, patience, and subtlety",
        "Why Meghaduta is not just romance but disciplined longing",
        "How Sanskrit and Kannada literary traditions preserve dharma through aesthetics",
    ],
    "South Indian Sacred Knowledge": [
        "How temple food, seasonal cooking, and ritual timing preserve embodied wisdom",
        "Why South Indian kitchens quietly carry Ayurveda, mantra, and samskara",
        "How local devata traditions preserve ecological memory",
        "Why village rituals should not be dismissed as superstition without study",
        "How serpent worship connects land, fertility, fear, and reverence",
        "Why Tulu, Kannada, Tamil, Malayalam, and Telugu traditions preserve regional forms of Sanatana Dharma",
        "How Agama, Tantra, Jyotisha, and Ayurveda meet in living temple culture",
    ],
}


# -----------------------------------------------------------------------------
# Content lanes
# -----------------------------------------------------------------------------
# Optional funnel-oriented grouping. The current generator does not require this,
# but callers can use it later to bias topic selection toward page/premium/course
# needs.

CONTENT_LANES: dict[str, list[str]] = {
    "Householder Dharma": [
        "marriage delay and realistic dharmic response",
        "family conflict through dharma and karma",
        "daily puja discipline for busy householders",
        "ancestral duty without fear-based pitru marketing",
        "raising children with samskara in modern life",
    ],
    "Temple & Ritual Culture": [
        "why temple rituals follow sequence",
        "meaning of naivedya, arati, alankara, and pradakshina",
        "how Agama differs from home puja",
        "why festivals are seasonal and psychological resets",
        "how local devata traditions protect community memory",
    ],
    "Ayurveda & Kitchen Wisdom": [
        "South Indian spices as digestive intelligence",
        "why sambar, rasam, buttermilk, and pickles are not random foods",
        "ritucharya through everyday cooking",
        "pathya-apathya in common illness recovery",
        "agni and ama explained through daily eating habits",
    ],
    "Jyotisha for Real Life": [
        "why dasha timing matters more than fear of dosha",
        "how marriage, career, health, and finance need different chart lenses",
        "why remedies fail when lifestyle and karma are ignored",
        "difference between genuine prashna and casual prediction",
        "why muhurta protects important beginnings",
    ],
    "Shastra for Critical Thinking": [
        "Nyaya for identifying bad arguments",
        "Tarka for social media debates",
        "Mimamsa for interpreting scripture responsibly",
        "Vyakarana for protecting mantra meaning",
        "Vedanta for identity, anxiety, and inner clarity",
    ],
    "Cultural Pride Without Fake Claims": [
        "what Indian mathematics genuinely contributed",
        "how Sulba Sutras show geometry without exaggeration",
        "why Sanskrit grammar is intellectually extraordinary",
        "how classical arts encode rasa and discipline",
        "why tradition becomes weak when defended with fake facts",
    ],
    "Paid Group Teasers": [
        "hidden logic behind Lalita Sahasranama names",
        "how one mantra can be read through Jyotisha, Tantra, and Vedanta",
        "why simple rituals have deep shastric structure",
        "how to study dharma without getting lost in internet confusion",
        "why serious sadhana needs method, not excitement",
    ],
}


# -----------------------------------------------------------------------------
# Genres
# -----------------------------------------------------------------------------
# Every genre produces exactly 4 short paragraphs. This gives enough space for
# hook, shastric explanation, modern-life connection, and memorable close.

GENRES: dict[str, dict[str, str]] = {
    "critique": {
        "label": "ವಿಮರ್ಶೆ",
        "instructions": (
            "Genre: CRITIQUE. Pick a common misconception, distortion, or lazy modern take about the topic "
            "below and dismantle it directly. Paragraph 1: state the misconception plainly. Paragraph 2: "
            "give the sharper, more accurate reading with one concrete supporting detail. Paragraph 3: connect "
            "it to daily life or present-day confusion. Paragraph 4: land on a firm corrective stance."
        ),
    },
    "debate": {
        "label": "ಚರ್ಚೆ",
        "instructions": (
            "Genre: DEBATE. Present a genuine tension or open question connected to the topic below. Paragraph "
            "1: state both sides fairly. Paragraph 2: argue the classical/traditional position with its strongest "
            "reasoning. Paragraph 3: acknowledge the reasonable modern concern. Paragraph 4: give a considered "
            "final synthesis without dismissing the other side as foolish."
        ),
    },
    "elaboration": {
        "label": "ವಿವರಣೆ",
        "instructions": (
            "Genre: ELABORATION. Explain one specific concept from the topic below in real depth. Paragraph 1: "
            "introduce the concept with a concrete, relatable analogy. Paragraph 2: unpack the mechanics or logic "
            "behind it. Paragraph 3: show how it appears in daily life today. Paragraph 4: state why it still matters."
        ),
    },
    "story": {
        "label": "ಕಥೆ",
        "instructions": (
            "Genre: STORY. Retell ONE well-known, genuinely documented episode connected to the topic below. "
            "Never invent a fictitious episode and present it as canon. Paragraph 1: set the scene briefly. "
            "Paragraph 2: tell the key turn. Paragraph 3: draw the dharmic meaning. Paragraph 4: give one practical "
            "lesson for a modern reader."
        ),
    },
    "correlation": {
        "label": "ಸಂಬಂಧ",
        "instructions": (
            "Genre: CORRELATION. Connect the topic below to a real, defensible modern parallel — a documented "
            "historical fact, a genuine scientific principle, or a real modern practice. Paragraph 1: state the "
            "modern fact/parallel. Paragraph 2: state the classical concept and the genuine common thread. Paragraph "
            "3: clarify the limits of the comparison. Paragraph 4: what this correlation should change about how the "
            "reader sees either side."
        ),
    },
    "guidance": {
        "label": "ಮಾರ್ಗದರ್ಶನ",
        "instructions": (
            "Genre: GUIDANCE. Offer one specific, safe, traditional practice or orientation tied to the topic below. "
            "Paragraph 1: name the situation or need this addresses. Paragraph 2: describe the practice plainly and "
            "why it is traditionally recommended. Paragraph 3: explain how to approach it responsibly. Paragraph 4: "
            "if the practice touches health, legal, or psychological matters, include one plain line noting it is "
            "traditional/spiritual guidance, not a substitute for professional care."
        ),
    },
    "lifestyle": {
        "label": "ಜೀವನಶೈಲಿ",
        "instructions": (
            "Genre: LIFESTYLE. Show one everyday, practical way an ordinary person applies the topic below in daily "
            "life. Paragraph 1: describe the everyday moment. Paragraph 2: show how the classical principle applies. "
            "Paragraph 3: explain the tangible benefit. Paragraph 4: close with a simple discipline the reader can remember."
        ),
    },
    "myth_busting": {
        "label": "ಭ್ರಮೆ-ಭೇದ",
        "instructions": (
            "Genre: MYTH-BUSTING. Take one popular misunderstanding about the topic and break it clearly. Paragraph "
            "1: state the common false belief in a sharp, relatable way. Paragraph 2: explain what the classical "
            "tradition actually says, with one concrete idea. Paragraph 3: show why the false belief became popular. "
            "Paragraph 4: close with a memorable corrective line."
        ),
    },
    "case_study": {
        "label": "ಉದಾಹರಣೆ",
        "instructions": (
            "Genre: CASE STUDY. Present a realistic but anonymous modern situation connected to the topic. Do not "
            "claim it is a real client case unless provided. Paragraph 1: describe the situation. Paragraph 2: show "
            "how the classical lens diagnoses it. Paragraph 3: give the practical response. Paragraph 4: close without "
            "exaggerated promises."
        ),
    },
    "shastra_vs_modern": {
        "label": "ಶಾಸ್ತ್ರ-ಆಧುನಿಕತೆ",
        "instructions": (
            "Genre: SHASTRA VS MODERNITY. Compare a classical idea with a modern habit, trend, or misconception. "
            "Paragraph 1: describe the modern approach fairly. Paragraph 2: explain the classical approach and its "
            "deeper logic. Paragraph 3: show where modernity has a valid point. Paragraph 4: synthesize both without "
            "blindly rejecting modernity or blindly glorifying the past."
        ),
    },
    "paid_group_teaser": {
        "label": "ಪ್ರೀಮಿಯಂ ಸೂಚನೆ",
        "instructions": (
            "Genre: PAID GROUP TEASER. Write a high-curiosity public post that hints at a deeper teaching. Paragraph "
            "1: open with a strong question or surprising statement. Paragraph 2: reveal one useful insight but do not "
            "give the full framework. Paragraph 3: show why surface understanding is insufficient. Paragraph 4: close by "
            "implying that deeper study requires systematic learning, without sounding salesy."
        ),
    },
    "practical_sadhana": {
        "label": "ಸಾಧನಾ ಮಾರ್ಗ",
        "instructions": (
            "Genre: PRACTICAL SADHANA. Give a simple, safe, non-secret, traditional practice connected to the topic. "
            "Paragraph 1: name the type of person or situation this practice helps. Paragraph 2: describe the practice "
            "in a simple way without restricted ritual details. Paragraph 3: explain the attitude needed. Paragraph 4: "
            "include a grounded caution that this is traditional guidance, not a substitute for professional help where needed."
        ),
    },
    "deep_explainer": {
        "label": "ಆಳವಾದ ವಿವರಣೆ",
        "instructions": (
            "Genre: DEEP EXPLAINER. Explain the inner structure of one classical concept. Paragraph 1: define the idea "
            "through a vivid example. Paragraph 2: unpack its technical logic without becoming dry. Paragraph 3: show "
            "why this idea still matters in family, health, career, ritual, or spiritual life. Paragraph 4: end with a "
            "compact insight."
        ),
    },
    "controversy_balanced": {
        "label": "ಸಮತೋಲನ ವಿಮರ್ಶೆ",
        "instructions": (
            "Genre: BALANCED CONTROVERSY. Address a sensitive or debated topic without hate, fear, or exaggeration. "
            "Paragraph 1: state why the topic is controversial. Paragraph 2: give the classical view and the reasonable "
            "modern concern. Paragraph 3: separate misuse from authentic principle. Paragraph 4: offer a mature position "
            "rooted in respect, clarity, and responsibility."
        ),
    },
}


# -----------------------------------------------------------------------------
# Safe literary style modes
# -----------------------------------------------------------------------------
# These are broad tonal families inspired by Kannada literary traditions. They
# are not imitation prompts and must not copy any named writer's signature voice.

STYLE_BANK: dict[str, dict[str, str]] = {
    "philosophical_novelistic": {
        "label": "ತತ್ತ್ವಚಿಂತನೆಯ ಕಥನಶೈಲಿ",
        "inspired_by": "Serious Kannada philosophical fiction; not imitation of any author",
        "instructions": (
            "Use a reflective, layered, novel-like Kannada voice. Show inner conflict, moral weight, family tension, "
            "karma, memory, and social consequence. Sentences may be slightly longer than usual, but must remain readable. "
            "Avoid direct imitation of any named novelist, signature phrases, or recognizable authorial mannerisms."
        ),
    },
    "epic_poetic": {
        "label": "ಮಹಾಕಾವ್ಯಮಯ ಕಾವ್ಯಶೈಲಿ",
        "inspired_by": "Classical Kannada epic and national-poetic imagination",
        "instructions": (
            "Use elevated, expansive, poetic Kannada. Bring in nature, dharma, cosmic rhythm, light, river, mountain, sky, "
            "fire, and inner awakening as imagery. The tone should feel grand and uplifting, but not vague or over-decorated. "
            "Avoid copying any specific poet's diction or famous phrasing."
        ),
    },
    "folk_lyrical": {
        "label": "ಜನಪದ-ಲಾಲಿತ್ಯ ಶೈಲಿ",
        "inspired_by": "Kannada folk lyricism and emotional simplicity",
        "instructions": (
            "Use musical, earthy, emotionally warm Kannada. Prefer village images, rain, field, mother, lamp, temple bell, "
            "cow, river, and ordinary human feeling. The writing should feel intimate and memorable, like wisdom sung softly "
            "rather than argued loudly. Avoid direct imitation of any named poet's meter, phrases, or signature imagery."
        ),
    },
    "shastra_pravachana": {
        "label": "ಶಾಸ್ತ್ರ-ಪ್ರವಚನ ಶೈಲಿ",
        "inspired_by": "Traditional pravachana and shastra explanation",
        "instructions": (
            "Use the voice of a learned teacher explaining shastra to serious householders. Define the concept clearly, "
            "give one example, then connect it to daily life. Use Sanskrit terms only when useful, and immediately explain "
            "them in Kannada. Avoid dry academic writing and vague devotional filler."
        ),
    },
    "sharp_social_critique": {
        "label": "ತೀಕ್ಷ್ಣ ಸಾಮಾಜಿಕ ವಿಮರ್ಶೆ",
        "inspired_by": "Kannada critical essay tradition",
        "instructions": (
            "Use a sharp, fearless, but dignified critical voice. Expose shallow modern thinking, fake scholarship, "
            "pseudo-spirituality, and cultural self-hatred. Criticize ideas and habits, not communities or individuals. "
            "Keep the tone strong but not hateful, sarcastic but not abusive."
        ),
    },
    "vachana_like": {
        "label": "ವಚನಸಹಜ ಸರಳತೆ",
        "inspired_by": "Direct spiritual Kannada aphoristic tradition",
        "instructions": (
            "Use short, piercing, simple Kannada sentences. The tone should feel direct, spiritual, and practical. Avoid "
            "ornamentation and long explanations. Make every paragraph land like a clear inner instruction."
        ),
    },
    "grand_puranic": {
        "label": "ಪುರಾಣಿಕ ಕಥನ ಶೈಲಿ",
        "inspired_by": "Puranic storytelling and temple narration",
        "instructions": (
            "Use a sacred storytelling voice suitable for Itihasa, Purana, Agama, temple culture, and vrata topics. Set the "
            "scene vividly, explain the turning point, and draw dharmic meaning. The language may be elevated, but it should "
            "remain understandable to modern Kannada readers. Do not invent scriptural episodes or fake textual references."
        ),
    },
    "modern_explainer": {
        "label": "ಆಧುನಿಕ ವಿವರಣಾತ್ಮಕ ಶೈಲಿ",
        "inspired_by": "Clear educational writing for Facebook and course audiences",
        "instructions": (
            "Use crisp, modern Kannada. Explain classical ideas through health, family, career, money, education, relationships, "
            "and social-media examples. Keep paragraphs short and readable. This style is best for practical Jyotisha, Ayurveda, "
            "Nyaya, Tarka, and Vedanta content."
        ),
    },
    "premium_paid_group": {
        "label": "ಪ್ರೀಮಿಯಂ ಒಳನೋಟ ಶೈಲಿ",
        "inspired_by": "High-curiosity teaching style for paid spiritual groups",
        "instructions": (
            "Write as if revealing one layer of a deeper teaching. Give enough insight to create value, but leave the full "
            "framework for systematic study. The tone should be serious, confidential, and refined — not cheap clickbait. "
            "Avoid over-selling, fear, or miracle promises."
        ),
    },
}


STYLE_COMPATIBILITY: dict[str, list[str]] = {
    "Vedanta": ["philosophical_novelistic", "shastra_pravachana", "vachana_like", "epic_poetic"],
    "Nyaya Shastra": ["modern_explainer", "shastra_pravachana", "sharp_social_critique"],
    "Tarka & Logic": ["sharp_social_critique", "modern_explainer", "shastra_pravachana"],
    "Mimamsa": ["shastra_pravachana", "modern_explainer", "deep_explainer"],
    "Vyakarana & Sanskrit": ["sharp_social_critique", "shastra_pravachana", "modern_explainer"],
    "Ayurveda": ["modern_explainer", "folk_lyrical", "shastra_pravachana"],
    "Ganita & Indian Mathematics": ["modern_explainer", "shastra_pravachana", "epic_poetic"],
    "Itihasa - Ramayana & Mahabharata": ["grand_puranic", "philosophical_novelistic", "epic_poetic"],
    "Puranas": ["grand_puranic", "folk_lyrical", "epic_poetic"],
    "Tantra, Sadhana & Shakti": ["shastra_pravachana", "premium_paid_group", "grand_puranic"],
    "Jyotisha (Vedic Astrology)": ["modern_explainer", "shastra_pravachana", "premium_paid_group"],
    "Smriti & Dharmashastra": ["shastra_pravachana", "sharp_social_critique", "philosophical_novelistic"],
    "Agama & Temple Tradition": ["grand_puranic", "shastra_pravachana", "folk_lyrical"],
    "South Indian Sacred Knowledge": ["folk_lyrical", "grand_puranic", "modern_explainer"],
}


# -----------------------------------------------------------------------------
# Emoji and hashtags
# -----------------------------------------------------------------------------

CLASSICAL_SYSTEM_EMOJI: dict[str, str] = {
    "Jyotisha (Vedic Astrology)": "🔮",
    "Tantra, Sadhana & Shakti": "🕉️",
    "Ayurveda": "🌿",
    "Ganita & Indian Mathematics": "🔢",
    "Tarka & Logic": "🧠",
    "Nyaya Shastra": "📐",
    "Vedanta": "🪔",
    "Mimamsa": "📖",
    "Vyakarana & Sanskrit": "🔤",
    "Smriti & Dharmashastra": "⚖️",
    "Arthashastra & Rajaneeti": "🏛️",
    "Agama & Temple Tradition": "🛕",
    "Vastu, Shilpa & Temple Architecture": "🏯",
    "Yoga Shastra": "🧘",
    "Itihasa - Ramayana & Mahabharata": "📜",
    "Puranas": "🐚",
    "Niti Shastra & Panchatantra": "🦁",
    "Indian Classical Arts": "🎭",
    "Classical Literature & Kavya": "📚",
    "South Indian Sacred Knowledge": "🌾",
}

CLASSICAL_HASHTAGS: dict[str, list[str]] = {
    "Jyotisha (Vedic Astrology)": ["Jyotisha", "VedicAstrology", "Vedavidhya"],
    "Tantra, Sadhana & Shakti": ["Tantra", "Sadhana", "Shakti", "Vedavidhya"],
    "Ayurveda": ["Ayurveda", "KitchenWisdom", "Vedavidhya"],
    "Ganita & Indian Mathematics": ["IndianMathematics", "Ganita", "Vedavidhya"],
    "Tarka & Logic": ["Tarka", "IndianLogic", "Vedavidhya"],
    "Nyaya Shastra": ["Nyaya", "Pramana", "IndianPhilosophy"],
    "Vedanta": ["Vedanta", "Upanishads", "SanatanaDharma"],
    "Mimamsa": ["Mimamsa", "VedicTradition", "Shastra"],
    "Vyakarana & Sanskrit": ["Sanskrit", "Vyakarana", "Panini"],
    "Smriti & Dharmashastra": ["Dharmashastra", "Dharma", "Smriti"],
    "Arthashastra & Rajaneeti": ["Arthashastra", "Chanakya", "Rajaneeti"],
    "Agama & Temple Tradition": ["Agama", "TempleTradition", "SanatanaDharma"],
    "Vastu, Shilpa & Temple Architecture": ["Vastu", "ShilpaShastra", "TempleArchitecture"],
    "Yoga Shastra": ["Yoga", "YogaShastra", "Sadhana"],
    "Itihasa - Ramayana & Mahabharata": ["Itihasa", "Ramayana", "Mahabharata"],
    "Puranas": ["Purana", "Bhakti", "SanatanaDharma"],
    "Niti Shastra & Panchatantra": ["Panchatantra", "Niti", "Wisdom"],
    "Indian Classical Arts": ["ClassicalArts", "Rasa", "NatyaShastra"],
    "Classical Literature & Kavya": ["Kavya", "ClassicalLiterature", "Sanskrit"],
    "South Indian Sacred Knowledge": ["SouthIndianTradition", "TempleCulture", "Vedavidhya"],
}


# -----------------------------------------------------------------------------
# Safety and authenticity rules
# -----------------------------------------------------------------------------

CLASSICAL_SAFETY_RULES = (
    "Absolute rules:\n"
    "- Never invent verse numbers, chapter numbers, exact Sanskrit quotations, guru-parampara claims, or textual references.\n"
    "- Never invent fake research studies, fake archaeology, fake NASA claims, fake quantum claims, or fake scientific validation.\n"
    "- Do not claim that Ayurveda replaces emergency medicine, surgery, insulin, psychiatric care, or professional diagnosis.\n"
    "- Do not give secret, restricted, harmful, or manipulative Tantra prayoga details.\n"
    "- Do not write fear-based ritual marketing such as 'this will destroy your life if not done'.\n"
    "- Do not insult other sampradayas, castes, religions, regions, or modern professionals.\n"
    "- When criticizing modernity, criticize shallow thinking, not people or communities.\n"
    "- When praising tradition, use grounded examples, not fantasy superiority claims.\n"
    "- When discussing Smriti or Dharmashastra, mention context, interpretation, and responsible application.\n"
    "- When discussing disputed history or science, say it is debated instead of presenting it as settled.\n"
    "- Keep public guidance safe, general, and non-exploitative.\n"
    "- Treat other schools of thought, other Indian traditions, and rival interpretations with respect even when the genre calls for critique.\n"
    "- If content touches health, legal, or psychological matters, include a plain line noting that it is traditional/spiritual guidance, not a substitute for professional medical, legal, or mental-health care.\n"
    "- Do not imitate any living writer, copyrighted authorial voice, signature phrasing, or recognizable mannerism of a named author.\n"
)


POST_ARCHETYPE = {
    "opening": "Start with a hook: a question, misconception, or striking observation.",
    "middle": "Explain the shastric logic using one concrete example.",
    "depth": "Connect to one branch like Jyotisha, Ayurveda, Nyaya, Mimamsa, Vedanta, or Vyakarana.",
    "closing": "End with a sharp, memorable Kannada line.",
    "avoid": "No generic devotion quotes, no fake Sanskrit, no empty nationalism, no miracle claims.",
}


# -----------------------------------------------------------------------------
# Selection helpers
# -----------------------------------------------------------------------------

def _select_topic_genre_style(recent_history: list[dict]) -> tuple[str, str, str, str]:
    """Pick (system, subtopic, genre, style), avoiding the most recently used
    systems/genres/styles/subtopics so back-to-back posts do not repeat the same
    angle. Falls back to the full pool if everything has been used recently.
    """
    recent_history = recent_history or []

    recent_systems = [r.get("system") for r in recent_history[-3:]]
    recent_genres = [r.get("genre") for r in recent_history[-2:]]
    recent_styles = [r.get("style") for r in recent_history[-3:]]
    recent_subtopics = {r.get("subtopic") for r in recent_history[-15:]}

    systems = [s for s in TOPIC_BANK if s not in recent_systems] or list(TOPIC_BANK)
    system_name = random.choice(systems)

    subtopics = [s for s in TOPIC_BANK[system_name] if s not in recent_subtopics] or TOPIC_BANK[system_name]
    subtopic = random.choice(subtopics)

    genres = [g for g in GENRES if g not in recent_genres] or list(GENRES)
    genre_key = random.choice(genres)

    compatible_styles = [s for s in STYLE_COMPATIBILITY.get(system_name, list(STYLE_BANK)) if s in STYLE_BANK]
    style_pool = compatible_styles or list(STYLE_BANK)
    styles = [s for s in style_pool if s not in recent_styles] or style_pool
    style_key = random.choice(styles)

    return system_name, subtopic, genre_key, style_key


# Backward-compatible wrapper for callers that still expect the old 3-tuple.
def _select_topic_genre(recent_history: list[dict]) -> tuple[str, str, str]:
    system_name, subtopic, genre_key, _style_key = _select_topic_genre_style(recent_history)
    return system_name, subtopic, genre_key


# -----------------------------------------------------------------------------
# Prompting and generation
# -----------------------------------------------------------------------------

def _build_classical_prompt(
    system_name: str,
    subtopic: str,
    genre_key: str,
    style_key: str | None = None,
) -> tuple[str, str]:
    """Build Gemini system/user prompts for a classical-content post.

    IMPORTANT: this must produce an ENGLISH draft, not Kannada. generate_post()
    unconditionally pipes this function's output through
    analyzer._translate_to_kannada(), which is an English->Kannada translator
    - it asks the model to "translate the following English title and
    analysis". Earlier this prompt asked Gemini to write in Kannada directly,
    so the "translation" step received Kannada text framed as English source
    text, which is enough to make a translation model hallucinate a
    completely unrelated completion instead of translating (reproduced: a
    real Kannada draft about tala/Ganita, run through _translate_to_kannada,
    came back as a fabricated story about a US banking collapse - totally
    unrelated to the input). Keep this prompt in English so the translation
    step gets real English source text to translate.
    """
    genre = GENRES[genre_key]
    style_key = style_key or "shastra_pravachana"
    style = STYLE_BANK[style_key]
    style_context = load_style_context()

    system_prompt = (
        "You are an English-drafting writer for Vedavidhya, a Sanatana Dharma-rooted knowledge brand whose posts are "
        "published in Kannada (your English draft will be translated to Kannada in a later step - write it so that "
        "translation is straightforward, not idiomatic English that resists translation). "
        "The audience includes spiritually curious householders, Jyotisha/Tantra/Ayurveda learners, temple-going families, "
        "Kannada readers who enjoy serious but readable classical knowledge, and people tired of shallow social-media spirituality. "
        "Write with depth, dignity, and clarity. The voice should feel like a learned traditional teacher explaining complex shastra "
        "to intelligent common readers. Use concrete examples from family life, temple life, food, health, marriage, career, village tradition, "
        "ritual practice, debate, and modern confusion. "
        "Cover Indian knowledge systems broadly: Jyotisha, Tantra, Ayurveda, Ganita, Tarka, Nyaya, Vedanta, Mimamsa, Vyakarana, Smriti, "
        "Dharmashastra, Arthashastra, Agama, Vastu, Shilpa, Yoga, Itihasa, Purana, Niti, Panchatantra, Kavya, Sangita, and South Indian sacred traditions. "
        "Important style rule: do not imitate any living writer, copyrighted authorial voice, signature phrasing, or recognizable mannerism of a named author. "
        "Use only broad, high-level literary qualities such as philosophical depth, poetic elevation, folk warmth, shastra clarity, or sharp social critique. "
        f"Selected writing mode: {style['label']}. "
        f"Style guidance: {style['instructions']} "
        f"Overall tone: {config.STYLE_TONE}. "
        "Write in strong English with short, memorable sentences. Use concrete images over abstract preaching. "
        "Avoid generic spiritual filler, fake Sanskrit, fake citations, miracle claims, and empty nationalism. "
        f"{CLASSICAL_SAFETY_RULES}"
        f"{style_context}\n"
        "Keep the output safe for public distribution."
    )

    user_prompt = (
        f"{genre['instructions']}\n\n"
        f"Classical system: {system_name}\n"
        f"Specific angle to write about: {subtopic}\n"
        f"Writing mode: {style['label']}\n\n"
        "Output rules:\n"
        "1) Output exactly 4 short ENGLISH paragraphs, each roughly 35-65 words. This will be translated to Kannada afterward - do not write in Kannada.\n"
        "2) Paragraph 1: strong hook or image.\n"
        "3) Paragraph 2: shastric explanation.\n"
        "4) Paragraph 3: practical modern-life connection.\n"
        "5) Paragraph 4: memorable closing insight.\n"
        "6) No headings, no bullets, no numbering inside the body.\n"
        "7) Do not mention the genre name, system label, or style label in the body.\n"
        "8) Do not imitate any named writer directly.\n"
        "9) Do not add facts you are not confident are accurate; when unsure, speak in general terms rather than invented specifics.\n"
        "10) Stay strictly on the classical system and angle given above - do not drift into an unrelated current-events story.\n"
        "11) Stop after the fourth paragraph.\n\n"
        "Respond in exactly this format and nothing else:\n"
        "TITLE: <short punchy English title, max 12 words>\n"
        "BODY: <paragraph 1>\n\n<paragraph 2>\n\n<paragraph 3>\n\n<paragraph 4>"
    )

    return system_prompt, user_prompt


def _try_gemini_classical(
    system_name: str,
    subtopic: str,
    genre_key: str,
    style_key: str | None = None,
) -> tuple[str, str] | None:
    """Draft a Kannada-ready post with Gemini. Returns (title, body) or None."""
    if "gemini" in _DISABLED_PROVIDERS or not config.GEMINI_API_KEY:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=config.GEMINI_API_KEY)
        system_prompt, user_prompt = _build_classical_prompt(system_name, subtopic, genre_key, style_key)

        for attempt in range(2):
            prompt = user_prompt
            if attempt == 1:
                prompt = (
                    user_prompt
                    + "\n\nYour previous draft was too generic, too vague, too imitative, used banned filler, "
                    "or did not follow the TITLE:/BODY: format exactly. Rewrite from scratch. Use the selected writing mode "
                    "only as broad inspiration. Do not copy any named author. Use a sharper opening, one concrete shastric idea, "
                    "and a memorable closing line."
                )

            resp = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=620,
                    temperature=0.72,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )

            raw = getattr(resp, "text", "") or ""
            parsed = _parse_translation(raw)  # same TITLE:/BODY: format the translation step uses
            if parsed and not _has_generic_filler(parsed[1]):
                return parsed

            print(
                f"[classical_content] gemini draft (attempt {attempt + 1}) rejected; retrying"
                if attempt == 0
                else "[classical_content] gemini draft still rejected after retry"
            )

        return None

    except Exception as exc:
        if _is_quota_error(exc):
            _DISABLED_PROVIDERS.add("gemini")
            print("[classical_content] Gemini quota exhausted; disabled for this run")
        else:
            print(f"[classical_content] Gemini failed ({type(exc).__name__}: {exc})")
        return None


def generate_post(recent_history: list[dict] | None = None) -> dict | None:
    """Generate one classical-content post.

    It picks a (system, subtopic, genre, style) combination, drafts with Gemini,
    then runs analyzer's existing translation pipeline. Returns None if any stage
    fails or produces unacceptable output — callers should skip posting this run
    rather than fall back to a lower-quality template.
    """
    if not config.GEMINI_API_KEY:
        print("[classical_content] no Gemini API key configured; skipping")
        return None

    system_name, subtopic, genre_key, style_key = _select_topic_genre_style(recent_history or [])

    english = _try_gemini_classical(system_name, subtopic, genre_key, style_key)
    if not english:
        print(
            f"[classical_content] no acceptable english draft for "
            f"system={system_name} genre={genre_key} style={style_key}"
        )
        return None

    english_title, english_body = english
    if len(_normalized_words(english_body)) < 45:
        print("[classical_content] english draft too short; skipping")
        return None

    translated = _translate_to_kannada(english_title, english_body)
    if not translated:
        print("[classical_content] translation to kannada failed; skipping")
        return None

    kannada_title, kannada_body = translated

    return {
        "title": kannada_title,
        "body": kannada_body,
        "system": system_name,
        "subtopic": subtopic,
        "genre": genre_key,
        "genre_label": GENRES[genre_key]["label"],
        "style": style_key,
        "style_label": STYLE_BANK[style_key]["label"],
        "emoji": CLASSICAL_SYSTEM_EMOJI.get(system_name, "🕉️"),
        "hashtags": CLASSICAL_HASHTAGS.get(system_name, ["Vedavidhya", "SanatanaDharma"]),
    }
