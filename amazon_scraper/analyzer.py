from __future__ import annotations

import re
from collections import Counter, defaultdict

from .models import Insight, Review, ReviewInsights

STOPWORDS = {
    "this", "that", "with", "from", "have", "has", "had", "were", "was", "are",
    "the", "and", "for", "but", "not", "you", "your", "its", "very", "really",
    "just", "they", "them", "our", "out", "too", "can", "could", "would", "will",
    "product", "item", "amazon", "bought", "purchase", "use", "used", "using",
    "one", "get", "got", "also", "much", "more", "than", "when", "what", "which",
    "about", "after", "before", "because", "only", "been", "into", "does", "did",
}


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if len(part.strip()) >= 18]


def _phrases(text: str) -> set[str]:
    tokens = [
        token for token in re.findall(r"[a-z][a-z'-]{2,}", text.lower())
        if token not in STOPWORDS
    ]
    phrases: set[str] = set()
    for size in (2, 3):
        for i in range(len(tokens) - size + 1):
            phrases.add(" ".join(tokens[i:i + size]))
    return phrases


def _summarize(reviews: list[Review], positive: bool, limit: int = 5) -> list[Insight]:
    eligible = [r for r in reviews if r.rating is not None and (r.rating >= 4 if positive else r.rating <= 3)]
    counts: Counter[str] = Counter()
    evidence: dict[str, list[str]] = defaultdict(list)
    for review in eligible:
        seen: set[str] = set()
        for sentence in _sentences(review.body) or [review.body]:
            for phrase in _phrases(sentence):
                if phrase in seen:
                    continue
                seen.add(phrase)
                counts[phrase] += 1
                if len(evidence[phrase]) < 2:
                    evidence[phrase].append(sentence[:240])
    ranked: list[str] = []
    for phrase, count in counts.most_common(80):
        if count < 2 and len(eligible) >= 5:
            continue
        if any(phrase in existing or existing in phrase for existing in ranked):
            continue
        ranked.append(phrase)
        if len(ranked) == limit:
            break
    return [Insight(phrase=p, mentions=counts[p], evidence=evidence[p]) for p in ranked]


def analyze_reviews(reviews: list[Review]) -> ReviewInsights:
    return ReviewInsights(
        advantages=_summarize(reviews, positive=True),
        pains=_summarize(reviews, positive=False),
        analyzed_reviews=len(reviews),
    )
