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


def refresh_corpus(urls: list[str] | None = None) -> dict:
    urls = urls or config.STYLE_CORPUS_URLS
    samples = []
    for url in urls:
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "VedavidhyaStyleBot/1.0"})
            resp.raise_for_status()
            text = _clean_page_text(resp.text)
        except Exception as exc:
            samples.append({"url": url, "error": str(exc)})
            continue
        if len(text) >= 200:
            samples.append({"url": url, "text": text[:3000]})

    corpus = dict(DEFAULT_PROFILE)
    corpus["samples"] = samples
    _corpus_path().write_text(json.dumps(corpus, ensure_ascii=False, indent=2), encoding="utf-8")
    return corpus


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Fetch configured source URLs into style_corpus.json")
    args = parser.parse_args()
    corpus = refresh_corpus() if args.refresh else load_corpus()
    print(f"[style] {len(corpus.get('samples', []))} sample(s), corpus={_corpus_path()}")
