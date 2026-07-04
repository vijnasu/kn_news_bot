"""Load or refresh Vedavidhya style context for low-cost prompt grounding."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

import config

DEFAULT_PROFILE = {
    "brand": "",
    "sources": [config.STYLE_SOURCE_URL, config.STYLE_BLOG_URL, config.STYLE_FACEBOOK_URL],
    "style_notes": [
        "Evidence-first interpretation with clear cause, consequence, and watch-point.",
        "Civilizational framing should stay factual and restrained.",
        "Use short Kannada prose, not label-heavy templates.",
        "Avoid sensationalism, legal certainty, and unverifiable insider claims.",
        "When using cultural lenses, apply them naturally inside the analysis.",
    ],
    "samples": [],
}


def _corpus_path() -> Path:
    return Path(config.STYLE_CORPUS_PATH)


def _clean_page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "svg", "noscript", "iframe"]):
        tag.decompose()
    text = soup.get_text(" ")
    return re.sub(r"\s+", " ", text).strip()


def load_corpus() -> dict:
    path = _corpus_path()
    if not path.exists():
        return DEFAULT_PROFILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_PROFILE
    return {**DEFAULT_PROFILE, **data}


def load_style_context(max_chars: int = 1400) -> str:
    corpus = load_corpus()
    notes = "\n".join(f"- {note}" for note in corpus.get("style_notes", []))
    context = f"Analysis rules:\n{notes}"
    return context[:max_chars]


def load_voice_anchors(count: int = 6) -> list[str]:
    """Return real, curated excerpts of the brand's own past writing (e.g.
    pulled from the actual Facebook page export) to use as concrete voice
    anchors in prompts - these are far more effective at steering register
    and rhetorical devices than adjectives like 'punchy' or 'authoritative'.
    Only samples explicitly marked curated=True are used here; scraped
    website samples (see refresh_corpus) are not reliable prose exemplars
    (often nav/boilerplate text) and are excluded."""
    corpus = load_corpus()
    curated = [s.get("text", "") for s in corpus.get("samples", []) if s.get("curated") and s.get("text")]
    return curated[:count]


def refresh_corpus(urls: list[str] | None = None) -> dict:
    """Refresh the scraped-website portion of the corpus from live URLs.

    This intentionally PRESERVES any curated=True samples already in
    style_corpus.json (e.g. real excerpts pulled from the brand's own
    Facebook export) - those are hand-picked voice anchors, not something a
    generic web scrape should be able to silently wipe out. Only the
    non-curated, scraped-from-URL samples are replaced."""
    urls = urls or config.STYLE_CORPUS_URLS
    scraped = []
    for url in urls:
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "VedavidhyaStyleBot/1.0"})
            resp.raise_for_status()
            text = _clean_page_text(resp.text)
        except Exception as exc:
            scraped.append({"url": url, "error": str(exc)})
            continue
        if len(text) >= 200:
            scraped.append({"url": url, "text": text[:3000]})

    existing = load_corpus()
    curated_samples = [s for s in existing.get("samples", []) if s.get("curated")]

    corpus = dict(DEFAULT_PROFILE)
    corpus["brand"] = existing.get("brand") or DEFAULT_PROFILE["brand"]
    corpus["style_notes"] = existing.get("style_notes") or DEFAULT_PROFILE["style_notes"]
    corpus["samples"] = curated_samples + scraped
    _corpus_path().write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")
    return corpus


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Fetch configured source URLs into style_corpus.json")
    args = parser.parse_args()
    corpus = refresh_corpus() if args.refresh else load_corpus()
    print(f"[style] {len(corpus.get('samples', []))} sample(s), corpus={_corpus_path()}")
