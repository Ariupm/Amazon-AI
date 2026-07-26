from __future__ import annotations

import math
import re

from .models import (
    KeywordEntry,
    TitleCandidate,
    TitleGenerateRequest,
    TitleGenerateResult,
)

STOPWORDS = {
    "a", "an", "and", "for", "from", "in", "of", "on", "the", "to", "with",
    "rug", "rugs", "carpet", "mat", "floor", "room",
}
FEATURES = [
    ("arch pattern", "Arch Pattern"),
    ("wave pattern", "Wave Pattern"),
    ("high low pile", "High Low Pile"),
    ("high-low pile", "High Low Pile"),
    ("cut and loop", "Cut and Loop"),
    ("machine washable", "Machine Washable"),
    ("washable", "Washable"),
    ("non slip", "Non Slip"),
    ("non-slip", "Non Slip"),
    ("stain resistant", "Stain Resistant"),
    ("low pile", "Low Pile"),
    ("textured", "Textured"),
    ("tufted", "Tufted"),
    ("geometric", "Geometric"),
    ("abstract", "Abstract"),
    ("fluffy", "Fluffy"),
    ("soft", "Soft"),
    ("minimalist", "Minimalist"),
    ("modern", "Modern"),
    ("polyester", "Polyester"),
]


def _tokens(value: str) -> set[str]:
    return {
        token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9'-]*", value)
        if len(token) > 1 and token.lower() not in STOPWORDS
    }


def _clean_brand(value: str | None, title: str) -> str:
    brand = re.sub(r"^(Visit the |Brand:\s*)| Store$", "", value or "", flags=re.I).strip()
    if brand:
        return brand
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9&'._-]{1,30})", title)
    return match.group(1) if match else ""


def _category(request: TitleGenerateRequest) -> str:
    if request.category and request.category.strip():
        return request.category.strip()
    lower = request.product_title.lower()
    if "runner" in lower:
        return "Runner Rug"
    if "rug" in lower or "carpet" in lower:
        return "Area Rug"
    words = request.product_title.split()
    return " ".join(words[1:4] if len(words) > 3 else words)


def _features(request: TitleGenerateRequest) -> list[str]:
    corpus = " ".join([
        request.product_title,
        *request.bullets,
        request.material or "",
        request.style or "",
        request.use_case or "",
        *request.must_have,
    ]).lower().replace("-", " ")
    found: list[str] = []
    for phrase, label in FEATURES:
        if phrase.replace("-", " ") in corpus and label not in found:
            found.append(label)
    for explicit in request.must_have:
        cleaned = re.sub(r"\s+", " ", explicit).strip()
        if cleaned and cleaned.lower() in corpus and cleaned.title() not in found:
            found.append(cleaned.title())
    competitor_corpus = " ".join(request.competitor_titles).lower().replace("-", " ")
    original_order = {label: index for index, label in enumerate(found)}
    found.sort(key=lambda label: (
        -competitor_corpus.count(label.lower().replace("-", " ")),
        original_order[label],
    ))
    return found


def _traffic_keywords(request: TitleGenerateRequest, category: str) -> list[KeywordEntry]:
    reference = _tokens(" ".join([
        request.product_title,
        *request.bullets,
        request.category or "",
        request.material or "",
        request.style or "",
        request.use_case or "",
        *request.must_have,
    ]))
    category_words = {
        token.lower() for token in re.findall(r"[A-Za-z]+", category)
        if len(token) > 2
    } | {"rug", "rugs", "carpet", "runner"}
    ranked: list[tuple[float, KeywordEntry]] = []
    for item in request.keywords:
        term = re.sub(r"\s+", " ", item.term).strip()
        if not term or len(term) > 80 or re.search(r"\b\d+\s*[x×]\s*\d+\b", term, re.I):
            continue
        raw_tokens = {token.lower() for token in re.findall(r"[A-Za-z]+", term)}
        if not raw_tokens & category_words:
            continue
        meaningful = _tokens(term)
        overlap = len(meaningful & reference)
        # Category-only big words remain eligible; irrelevant high-volume terms do not.
        if overlap == 0 and len(raw_tokens - category_words) > 1:
            continue
        relevance = overlap / max(1, len(meaningful))
        score = relevance * 100 + math.log10((item.volume or 0) + 1) * 7
        ranked.append((score, KeywordEntry(term=term, volume=item.volume, month=item.month)))
    ranked.sort(key=lambda pair: (-pair[0], -(pair[1].volume or 0), pair[1].term.lower()))
    result: list[KeywordEntry] = []
    seen: set[str] = set()
    for _, item in ranked:
        normalized = re.sub(r"[^a-z]", "", item.term.lower())
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(item)
        if len(result) >= 12:
            break
    return result


def _join_limit(segments: list[str | None], limit: int, first_pair_space: bool = False) -> str:
    result = ""
    used_words: set[str] = set()
    accepted = 0
    for raw in segments:
        segment = re.sub(r"\s+", " ", raw or "").strip(" ,|-")
        if not segment:
            continue
        words = _tokens(segment)
        if words and words <= used_words:
            continue
        separator = " " if first_pair_space and accepted == 1 else ", "
        proposed = f"{result}{separator}{segment}" if result else segment
        if len(proposed) <= limit:
            result = proposed
            used_words |= words
            accepted += 1
    return result


def generate_titles(request: TitleGenerateRequest) -> TitleGenerateResult:
    category = _category(request)
    brand = _clean_brand(request.brand, request.product_title)
    features = _features(request)
    traffic = _traffic_keywords(request, category)
    primary = traffic[0].term if traffic else category
    secondary = traffic[1].term if len(traffic) > 1 else category
    colors: list[str | None] = request.colors or [None]
    sizes: list[str | None] = request.sizes or [None]
    use_case = request.use_case.strip() if request.use_case else None
    material = request.material.strip() if request.material else None
    style = request.style.strip() if request.style else None

    candidates: list[TitleCandidate] = []
    for color in colors:
        for size in sizes:
            primary_opening = (
                [brand, primary.title()]
                if category.lower() in primary.lower()
                else [brand, category, primary.title()]
            )
            secondary_opening = (
                [brand, secondary.title()]
                if category.lower() in secondary.lower()
                else [brand, category, secondary.title()]
            )
            structures = [
                [*primary_opening, *features[:2], size, color],
                [brand, category, *(features[1:4] or features[:2]), size, color],
                [*secondary_opening, *(features[:1] + features[3:5]), size, color],
            ]
            seen_titles: set[str] = set()
            for option_index, main_segments in enumerate(structures, start=1):
                if request.title_format == "split":
                    main = _join_limit(main_segments, 75, first_pair_space=True)
                    remaining = [feature for feature in features if feature.lower() not in main.lower()]
                    use_phrase = f"for {use_case}" if use_case else None
                    highlight = _join_limit([
                        *remaining,
                        material,
                        style,
                        use_phrase,
                    ], 125)
                    full = f"{main} | {highlight}" if highlight else main
                else:
                    main = _join_limit([
                        *main_segments,
                        *features,
                        material,
                        style,
                        f"for {use_case}" if use_case else None,
                    ], 200, first_pair_space=True)
                    highlight = None
                    full = main
                if not main or full.lower() in seen_titles:
                    continue
                seen_titles.add(full.lower())
                used = [
                    item.term for item in traffic
                    if item.term.lower() in full.lower()
                ]
                warnings: list[str] = []
                if not traffic:
                    warnings.append("ABA 词库中未找到与本品高度相关的流量词，当前使用类目词。")
                if not features:
                    warnings.append("本品真实资料中未识别到稳定卖点，请人工补充后再确认。")
                if request.title_format == "split" and not highlight:
                    warnings.append("Highlight Item 信息不足，请人工补充真实卖点。")
                candidates.append(TitleCandidate(
                    id=f"{len(candidates) + 1}",
                    color=color,
                    size=size,
                    main_title=main,
                    highlight_item=highlight,
                    full_title=full,
                    main_count=len(main),
                    highlight_count=len(highlight or ""),
                    full_count=len(full),
                    keywords_used=used,
                    warnings=warnings,
                ))

    return TitleGenerateResult(
        candidates=candidates,
        traffic_keywords=traffic,
        rules=[
            "品牌与类目大词优先放在主标题前部",
            "只使用本品页面或人工确认资料中真实存在的属性",
            "ABA 关键词按相关性优先、搜索量辅助排序",
            "主标题不超过 75 字符，Highlight Item 不超过 125 字符；原标题不超过 200 字符",
        ],
    )
