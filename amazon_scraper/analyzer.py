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
PAIN_STOPWORDS = STOPWORDS - {"not", "too"}
CONTRAST_SPLIT = re.compile(
    r"(?:[,;]\s*|\bbut\b|\bhowever\b|\balthough\b|\bthough\b|\byet\b|\bpero\b|\bsin embargo\b)",
    re.I,
)
NEGATIVE_SIGNAL = re.compile(
    r"\b(?:"
    r"not|never|no|cannot|can't|won't|wouldn't|didn't|doesn't|isn't|aren't|"
    r"bad|poor|cheap|flimsy|thin|rough|stiff|disappointed|disappointing|"
    r"slip|slips|slipped|sliding|slide|slides|trip|tripped|dangerous|unsafe|"
    r"move|moves|moving|curl|curled|crease|wrinkle|wrinkled|"
    r"smell|odor|stink|stain|faded|fade|shed|shedding|fray|frayed|"
    r"tear|torn|broken|break|returned|returning|wrong|smaller|shorter|"
    r"hard to|difficult|does not|do not|did not|will not|"
    r"nunca|jam[aá]s|malo|mala|peligroso|resbala|desliza|no lleg[oó]"
    r")\b",
    re.I,
)


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if len(part.strip()) >= 18]


def _phrases(text: str, stopwords: set[str] = STOPWORDS) -> set[str]:
    tokens = [
        token for token in re.findall(r"[a-z][a-z'-]{2,}", text.lower())
        if token not in stopwords
    ]
    phrases: set[str] = set()
    for size in (2, 3):
        for i in range(len(tokens) - size + 1):
            phrases.add(" ".join(tokens[i:i + size]))
    return phrases


def _negative_segments(text: str) -> list[str]:
    result: list[str] = []
    for sentence in _sentences(text) or [text]:
        segments = [part.strip(" .!?:-") for part in CONTRAST_SPLIT.split(sentence) if part.strip()]
        matched = [segment for segment in segments if NEGATIVE_SIGNAL.search(segment)]
        if matched:
            result.extend(matched)
        elif NEGATIVE_SIGNAL.search(sentence):
            result.append(sentence.strip())
    return result


def _summarize(reviews: list[Review], positive: bool, limit: int = 5) -> list[Insight]:
    eligible = [r for r in reviews if r.rating is not None and (r.rating >= 4 if positive else r.rating <= 3)]
    counts: Counter[str] = Counter()
    evidence: dict[str, list[str]] = defaultdict(list)
    for review in eligible:
        seen: set[str] = set()
        passages = (_sentences(review.body) or [review.body]) if positive else _negative_segments(review.body)
        for sentence in passages:
            for phrase in _phrases(sentence, STOPWORDS if positive else PAIN_STOPWORDS):
                if phrase in seen:
                    continue
                seen.add(phrase)
                counts[phrase] += 1
                if len(evidence[phrase]) < 2:
                    prefix = f"[{review.rating:g}★] " if review.rating is not None else ""
                    evidence[phrase].append(f"{prefix}{sentence[:230]}")
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
