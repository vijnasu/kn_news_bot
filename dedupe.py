"""Collapse near-duplicate stories reported by multiple sources.

Why this exists: id-based dedup (store.exists() / posted_store) only catches
the exact same URL appearing twice. It does nothing about the very common
case of the same real-world event being covered by several outlets at once -
e.g. Prajavani, TV9 Kannada, Kannada Oneindia, Public TV, and Asianet all
running their own article on the same Karnataka story within the same
15-minute window, each with a different link (and therefore a different
id). Left alone, all of those get treated as "unique" and posted separately,
which reads to a reader as the channel repeating itself even though every
individual link is technically new.

This module clusters items whose title+summary share enough vocabulary to
almost certainly be the same underlying story, and keeps only one
representative per cluster (whichever the caller listed first - callers
should pre-sort by whatever ordering they want to prefer, e.g. recency or
keyword score, before calling this)."""

from __future__ import annotations

from models import NewsItem
from analyzer import _normalized_words

# Containment-style overlap (shared words / smaller item's word count) - more
# robust than plain Jaccard when one outlet's summary is much longer/shorter
# than another's for the same story.
#
# Threshold calibrated against real same-story-different-outlet Kannada
# headlines: independently-written coverage of the identical event measured
# 0.45-0.50 overlap (Kannada is agglutinative, so even the same word appears
# as different surface tokens across outlets - ಬೆಂಗಳೂರಿನಲ್ಲಿ vs ಬೆಂಗಳೂರಿನ,
# ಮಳೆಯಿಂದಾಗಿ vs ಮಳೆಯಿಂದ - which keeps exact-token overlap well below what a
# human would judge as "the same story"), while an unrelated story on a
# similar beat measured 0.11. 0.40 sits with a wide margin below the former
# and well above the latter.
DEFAULT_THRESHOLD = 0.40
# Require an absolute minimum of shared significant words too, so two short
# titles that merely share a couple of generic terms (e.g. both mention
# "ಸರ್ಕಾರ"/government) don't get treated as duplicates just because that's a
# large fraction of a very short title.
MIN_SHARED_WORDS = 4


def _item_words(item: NewsItem) -> set[str]:
    return _normalized_words(f"{item.title} {item.summary}")


def _is_near_duplicate(a_words: set[str], b_words: set[str], threshold: float, min_shared: int) -> bool:
    if not a_words or not b_words:
        return False
    shared = a_words & b_words
    if len(shared) < min_shared:
        return False
    overlap = len(shared) / min(len(a_words), len(b_words))
    return overlap >= threshold


def dedupe_near_duplicates(
    items: list[NewsItem],
    threshold: float = DEFAULT_THRESHOLD,
    min_shared: int = MIN_SHARED_WORDS,
) -> list[NewsItem]:
    """Return items with near-duplicate stories collapsed to one
    representative each, preserving the input order otherwise. Callers should
    sort items into their preferred order (recency/score/etc.) before calling
    this, since the FIRST item encountered in a duplicate cluster is the one
    that survives."""
    kept: list[NewsItem] = []
    kept_words: list[set[str]] = []
    for item in items:
        words = _item_words(item)
        if any(_is_near_duplicate(words, existing, threshold, min_shared) for existing in kept_words):
            continue
        kept.append(item)
        kept_words.append(words)
    return kept
