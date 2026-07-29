from __future__ import annotations

import math
import re
from collections import Counter

from .models import (
    CompetitorTitleAnalysis,
    KeywordEntry,
    SizeScenarioAnalysis,
    TitleCandidate,
    TitleGenerateRequest,
    TitleGenerateResult,
    TitleKeywordAnalysis,
)

STOPWORDS = {
    "a", "an", "and", "for", "from", "in", "of", "on", "the", "to", "with",
    "rug", "rugs", "carpet", "mat", "floor", "room",
}
FEATURES = [
    ("arch pattern", "Arch Pattern"),
    ("wave pattern", "Wave Pattern"),
    ("high low pile", "High-Low Pile"),
    ("high-low pile", "High-Low Pile"),
    ("cut and loop", "Cut-and-Loop"),
    ("machine washable", "Machine Washable"),
    ("washable", "Washable"),
    ("non slip", "Non-Slip"),
    ("non-slip", "Non-Slip"),
    ("stain resistant", "Stain-Resistant"),
    ("low pile", "Low Pile"),
    ("textured", "Textured"),
    ("tufted", "Tufted"),
    ("geometric", "Geometric"),
    ("abstract", "Abstract"),
    ("fluffy", "Plush"),
    ("soft", "Soft"),
    ("minimalist", "Minimalist"),
    ("modern", "Modern"),
    ("polyester", "Polyester"),
]
IRRELEVANT_RUG_TERMS = {
    "cleaner", "machine cleaner", "vacuum", "tape", "gripper", "pad", "pads",
    "shampoo", "repair", "outdoor", "door mat", "bath mat",
}
LOW_VALUE_CONNECTORS = {"with", "and", "for"}
SCENE_WORDS = {
    "living room", "bedroom", "dining room", "kitchen", "hallway",
    "entryway", "nursery", "home office", "bathroom", "laundry room",
}


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


def _extract_size(value: str) -> str | None:
    match = re.search(
        r"(\d+(?:\.\d+)?\s*(?:'|ft|feet)?\s*[x×]\s*\d+(?:\.\d+)?\s*(?:'|ft|feet)?)",
        value,
        re.I,
    )
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else None


def _dimensions(size: str | None) -> tuple[float, float] | None:
    if not size:
        return None
    numbers = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", size)]
    return (numbers[0], numbers[1]) if len(numbers) >= 2 else None


def _scenario(size: str | None, fallback_category: str | None = None) -> SizeScenarioAnalysis:
    dims = _dimensions(size)
    if not dims:
        category = fallback_category.strip() if fallback_category else "Area Rug"
        return SizeScenarioAnalysis(
            size=size, product_type=category,
            primary_scenes=["Living Room", "Bedroom"],
            secondary_scenes=["Dining Room"],
            reasoning="尺寸未识别，场景按本品类目与竞品常见用途给出，定稿前需人工确认。",
        )
    short, long = sorted(dims)
    if short <= 3 and long >= short * 1.8:
        return SizeScenarioAnalysis(
            size=size, product_type="Runner Rug",
            primary_scenes=["Hallway", "Kitchen"],
            secondary_scenes=["Entryway", "Laundry Room"],
            reasoning="窄长比例适合通道型空间；市场标题通常使用 Runner Rug，并优先表达 Hallway / Kitchen。",
        )
    if long <= 4:
        return SizeScenarioAnalysis(
            size=size, product_type="Accent Rug",
            primary_scenes=["Entryway", "Bathroom"],
            secondary_scenes=["Bedside", "Kitchen"],
            reasoning="小尺寸更适合局部落脚与装饰区域，使用 Accent Rug 比 Area Rug 更符合消费者预期。",
        )
    if long <= 7:
        return SizeScenarioAnalysis(
            size=size, product_type="Area Rug",
            primary_scenes=["Bedroom", "Home Office"],
            secondary_scenes=["Small Living Room", "Dining Nook"],
            reasoning="中小尺寸适合卧室、书房及小型起居空间；场景词应避免写成 Hallway Runner。",
        )
    if long <= 10:
        return SizeScenarioAnalysis(
            size=size, product_type="Area Rug",
            primary_scenes=["Living Room", "Bedroom"],
            secondary_scenes=["Dining Room"],
            reasoning="主流大尺寸可覆盖沙发区、床区或餐桌区，市场通常以 Living Room / Bedroom 为主要场景。",
        )
    return SizeScenarioAnalysis(
        size=size, product_type="Large Area Rug",
        primary_scenes=["Living Room", "Dining Room"],
        secondary_scenes=["Large Bedroom", "Open-Plan Space"],
        reasoning="9'×12'及以上属于大面积覆盖规格，应写 Area Rug / Large Area Rug，不应写 Runner Rug 或 Bathroom Rugs。",
    )


def _features(request: TitleGenerateRequest) -> list[str]:
    corpus = " ".join([
        request.product_title, *request.bullets, request.material or "",
        request.style or "", request.use_case or "", *request.must_have,
    ]).lower().replace("-", " ")
    found: list[str] = []
    for phrase, label in FEATURES:
        if phrase.replace("-", " ") in corpus and label not in found:
            found.append(label)
    competitor_corpus = " ".join(request.competitor_titles).lower().replace("-", " ")
    original_order = {label: index for index, label in enumerate(found)}
    found.sort(key=lambda label: (
        -competitor_corpus.count(label.lower().replace("-", " ")),
        original_order[label],
    ))
    for improvement in request.verified_improvements:
        label = re.sub(r"\s+", " ", improvement).strip(" ,|-")
        if label and label.lower() not in {item.lower() for item in found}:
            found.append(label)
    return found


def _keyword_analysis(
    request: TitleGenerateRequest,
    scenarios: list[SizeScenarioAnalysis],
    features: list[str],
) -> list[TitleKeywordAnalysis]:
    reference = _tokens(" ".join([
        request.product_title, *request.bullets, request.category or "",
        request.material or "", request.style or "", request.use_case or "",
        *request.must_have, *features,
    ]))
    verified_style_tokens = _tokens(request.style or "")
    allowed_scenes = {
        scene.lower()
        for scenario in scenarios
        for scene in [*scenario.primary_scenes, *scenario.secondary_scenes]
    }
    product_types = " ".join(scenario.product_type for scenario in scenarios).lower()
    negatives = {
        re.sub(r"\s+", " ", term).strip().lower()
        for term in request.negative_terms if term.strip()
    }
    max_volume = max((item.volume or 0 for item in request.keywords), default=0)
    ranked: list[tuple[float, TitleKeywordAnalysis]] = []
    for item in request.keywords:
        term = re.sub(r"\s+", " ", item.term).strip()
        lower = term.lower()
        if not term or len(term) > 80 or not re.search(r"\b(rug|rugs|carpet)\b", lower):
            continue
        if any(blocked in lower for blocked in IRRELEVANT_RUG_TERMS):
            continue
        if any(re.search(rf"\b{re.escape(blocked)}\b", lower) for blocked in negatives):
            continue
        if re.search(r"\b\d+\s*[x×]\s*\d+\b", lower):
            continue
        if "runner" in lower and "runner" not in product_types:
            continue
        if any(scene in lower for scene in ("bathroom", "kitchen", "hallway")):
            if not any(scene in lower for scene in allowed_scenes):
                continue
        meaningful = _tokens(term)
        overlap = len(meaningful & reference)
        category_match = bool(re.search(r"\b(area rug|area rugs|runner rug|runner rugs|accent rug|accent rugs)\b", lower))
        scene_match = any(scene in lower for scene in allowed_scenes)
        feature_match = any(feature.lower().replace("-", " ") in lower.replace("-", " ") for feature in features)
        style_match = bool(meaningful & verified_style_tokens)
        relevance = min(100, 45 + overlap * 13 + category_match * 35 + scene_match * 12 + feature_match * 17 + style_match * 12)
        if relevance < 80:
            continue
        if category_match and style_match:
            role = "主标题风格词"
            reason = "同时覆盖准确类目和本品已确认风格，优先放在主标题。"
        elif category_match:
            role = "主标题类目词"
            reason = "直接说明消费者正在浏览的商品类型，优先放在主标题前部。"
        elif feature_match:
            role = "卖点词"
            reason = "与本品已验证属性一致，可自然融入主标题或 Highlight。"
        elif scene_match:
            role = "场景词"
            reason = "与该尺寸的市场使用场景匹配，适合放在 Highlight 后半段。"
        else:
            role = "辅助流量词"
            reason = "与本品相关，但应以自然表达为先，不强行重复埋词。"
        purchase_intent = min(100, 45 + category_match * 25 + feature_match * 20 + scene_match * 10 + style_match * 10)
        click_value = min(100, 35 + feature_match * 35 + scene_match * 20 + category_match * 10 + style_match * 25)
        volume_score = round(100 * math.log1p(item.volume or 0) / math.log1p(max_volume)) if max_volume else 0
        total_score = round(
            relevance * .40 + volume_score * .30 + purchase_intent * .15
            + click_value * .10 + min(100, purchase_intent + 10) * .05
        )
        placement = "main" if category_match or style_match or (scene_match and volume_score >= 60) else "highlight" if feature_match or scene_match else "ads"
        cluster_tokens = sorted(_tokens(term))
        cluster = " ".join(cluster_tokens[:5])
        score = total_score
        ranked.append((score, TitleKeywordAnalysis(
            term=term, volume=item.volume, month=item.month, rank=item.rank,
            relevance=relevance, role=role, reason=reason, cluster=cluster,
            recommended_placement=placement, purchase_intent=purchase_intent,
            click_value=click_value, total_score=total_score,
        )))
    ranked.sort(key=lambda pair: (-pair[0], pair[1].rank or 10**9, pair[1].term.lower()))
    result: list[TitleKeywordAnalysis] = []
    seen_clusters: list[set[str]] = []
    for _, item in ranked:
        tokens = _tokens(item.term)
        if any(len(tokens & seen) / max(1, min(len(tokens), len(seen))) >= .8 for seen in seen_clusters):
            continue
        seen_clusters.append(tokens)
        result.append(item)
        if len(result) >= 20:
            break
    return result


def _competitor_analysis(request: TitleGenerateRequest, features: list[str]) -> CompetitorTitleAnalysis:
    titles = [title.strip() for title in request.competitor_titles if title.strip()]
    opening_counter: Counter[str] = Counter()
    for title in titles:
        without_brand = re.sub(r"^\S+\s+", "", title)
        words = without_brand.split()
        if words:
            opening_counter[" ".join(words[:4]).strip(" ,|-")] += 1
    competitor_text = " ".join(titles).lower().replace("-", " ")
    common_features = [
        feature for feature in features
        if competitor_text.count(feature.lower().replace("-", " ")) > 0
    ][:6]
    head_titles = titles[: min(10, len(titles))]
    early_category = sum(bool(re.search(r"\b(?:area|runner|accent)\s+rugs?\b", " ".join(title.split()[:8]), re.I)) for title in head_titles)
    structure = (
        "Brand + high-traffic category/scene phrase + strongest differentiator + style + size/color."
        if early_category >= max(1, len(head_titles) / 2)
        else "Brand + strongest differentiator + high-traffic category/scene phrase + size/color."
    )
    return CompetitorTitleAnalysis(
        sample_size=len(titles),
        common_openings=[phrase for phrase, _ in opening_counter.most_common(5)],
        common_features=common_features,
        recommended_structure=structure,
        consumer_note="前10个已锁定竞品视为头部样本，优先学习类目词位置和信息顺序；不复制品牌、虚假属性或连接词堆叠。",
    )


def _join_main(parts: list[str | None], limit: int) -> str:
    result = ""
    for raw in parts:
        part = re.sub(r"\s+", " ", raw or "").strip(" ,|-")
        if not part or part.lower() in result.lower():
            continue
        proposed = f"{result}, {part}" if result else part
        if len(proposed) <= limit:
            result = proposed
    return result


def _display_phrase(value: str) -> str:
    small = {"a", "an", "the", "and", "or", "for", "of", "in", "to"}
    words = value.replace(" rugs", " Rugs").replace(" rug", " Rug").split()
    return " ".join(word.lower() if index and word.lower() in small else word.capitalize() for index, word in enumerate(words))


def _compact_highlight(parts: list[str], limit: int = 125) -> str:
    result = ""
    for raw in parts:
        part = re.sub(r"\s+", " ", raw).strip(" ,.|-")
        if not part or part.lower() in result.lower():
            continue
        proposed = f"{result}, {part}" if result else part
        if len(proposed) <= limit:
            result = proposed
    return result


def _selected_keywords(
    request: TitleGenerateRequest,
    analysis: list[TitleKeywordAnalysis],
) -> dict[str, list[TitleKeywordAnalysis]]:
    by_term = {item.term.lower(): item for item in analysis}
    result: dict[str, list[TitleKeywordAnalysis]] = {"main": [], "highlight": [], "ads": []}
    if request.keyword_selections:
        for selected in request.keyword_selections:
            item = by_term.get(selected.term.lower())
            if selected.enabled and item and selected.placement in result:
                result[selected.placement].append(item)
    else:
        for item in analysis:
            result[item.recommended_placement].append(item)
    return result


def _style_parts(value: str | None) -> list[str]:
    result: list[str] = []
    for raw in re.split(r"[,/|;，]+", value or ""):
        part = re.sub(r"\s+", " ", raw).strip(" ,|-")
        if part and part.lower() not in {item.lower() for item in result}:
            result.append(part)
    return result


def generate_titles(request: TitleGenerateRequest) -> TitleGenerateResult:
    brand = _clean_brand(request.brand, request.product_title)
    features = _features(request)
    colors: list[str | None] = request.colors or [None]
    sizes: list[str | None] = request.sizes or [_extract_size(request.product_title)]
    scenarios = [_scenario(size, request.category) for size in sizes]
    keyword_analysis = _keyword_analysis(request, scenarios, features)
    selected_keywords = _selected_keywords(request, keyword_analysis)
    traffic = [
        KeywordEntry(term=item.term, volume=item.volume, month=item.month, rank=item.rank)
        for item in keyword_analysis
    ]
    competitor_analysis = _competitor_analysis(request, features)

    candidates: list[TitleCandidate] = []
    for color in colors:
        for size, scenario in zip(sizes, scenarios):
            category = scenario.product_type
            styles = _style_parts(request.style)
            main_terms = selected_keywords["main"]
            highlight_terms = selected_keywords["highlight"]
            primary_keyword = next(
                (item for item in main_terms if re.search(r"\b(?:area|runner|accent)\s+rugs?\b", item.term, re.I)),
                main_terms[0] if main_terms else None,
            )
            scene_keyword = next(
                (item for item in main_terms if any(scene in item.term.lower() for scene in SCENE_WORDS)),
                None,
            )
            keyword_parts = [_display_phrase(item.term) for item in main_terms[:3]]
            traffic_parts = [
                brand,
                _display_phrase(primary_keyword.term) if primary_keyword else category,
                _display_phrase(scene_keyword.term) if scene_keyword and scene_keyword is not primary_keyword else None,
                *styles[:1], size, color, *features[:2],
            ]
            click_parts = [
                brand, features[0] if features else request.style,
                _display_phrase(primary_keyword.term) if primary_keyword else category,
                *styles[:2], size, color, *features[1:3],
            ]
            balanced_parts = [
                brand, _display_phrase(primary_keyword.term) if primary_keyword else category,
                *keyword_parts[1:2], *styles[:1], *features[:2], color, size,
            ]
            structures = [
                ("traffic", traffic_parts),
                ("click", click_parts),
                ("balanced", balanced_parts),
            ]
            seen: set[str] = set()
            for strategy, parts in structures:
                if request.title_format == "split":
                    main = _join_main(parts, 75)
                    highlight_parts = [
                        *[_display_phrase(item.term) for item in highlight_terms[:3]],
                        request.material or "",
                        *features[2:5],
                        *scenario.primary_scenes[:2],
                    ]
                    highlight = _compact_highlight(highlight_parts)
                    full = f"{main} | {highlight}"
                else:
                    highlight = None
                    sentence = _compact_highlight([
                        *[_display_phrase(item.term) for item in highlight_terms[:3]],
                        request.material or "", *features[2:5], *scenario.primary_scenes[:2],
                    ])
                    main = _join_main(parts, 200)
                    if sentence and len(f"{main}, {sentence}") <= 200:
                        main = f"{main}, {sentence}"
                    full = main
                if not main or full.lower() in seen:
                    continue
                seen.add(full.lower())
                used = [item.term for item in keyword_analysis if item.term.lower() in full.lower()]
                unused = [
                    item.term for item in [*main_terms, *highlight_terms]
                    if item.term.lower() not in full.lower()
                ]
                evidence = [
                    f"{item.term} · 搜索量{int(item.volume):,} · {('精确短语' if item.term.lower() in full.lower() else '未覆盖')}"
                    if item.volume is not None else f"{item.term} · 流量未知"
                    for item in [*main_terms, *highlight_terms][:8]
                ]
                warnings: list[str] = []
                if not keyword_analysis:
                    warnings.append("最新词库中没有通过类目、属性与尺寸场景校验的候选词，请人工检查类目词。")
                if not features:
                    warnings.append("本品真实资料中未识别到稳定卖点，请补充产品事实后再确认。")
                if styles and not any(style.lower() in full.lower() for style in styles):
                    warnings.append("已确认风格未进入标题，请缩减低优先级属性或人工指定风格关键词。")
                if any(connector in full.lower().split() for connector in LOW_VALUE_CONNECTORS):
                    warnings.append("连接词仅因已选关键词或必要语法保留，请人工确认其流量价值。")
                base_score = {"traffic": 88, "click": 86, "balanced": 90}[strategy]
                coverage_score = min(10, len(used) * 3)
                candidates.append(TitleCandidate(
                    id=str(len(candidates) + 1), color=color, size=size,
                    main_title=main, highlight_item=highlight, full_title=full,
                    main_count=len(main), highlight_count=len(highlight or ""),
                    full_count=len(full), keywords_used=used,
                    strategy=strategy, score=min(100, base_score + coverage_score),
                    keyword_evidence=evidence, unused_keywords=unused,
                    ad_keywords=[item.term for item in selected_keywords["ads"]],
                    warnings=warnings,
                ))

    return TitleGenerateResult(
        candidates=candidates,
        traffic_keywords=traffic,
        keyword_analysis=keyword_analysis,
        size_scenarios=scenarios,
        competitor_analysis=competitor_analysis,
        rules=[
            "主标题前部必须出现与尺寸一致的类目大词，让消费者立即识别商品类型",
            "词库排名为上传文件最新月份的搜索量排名，不代表 Amazon 自然搜索排名",
            "竞品用于学习自然结构和市场表达，不照抄品牌、未经证实卖点或错误场景",
            "广告词、流量词与标题埋词服从相关性和可读性，同义词不重复堆叠",
            "高流量且事实、尺寸场景匹配的场景词允许进入主标题，并尽量保留完整搜索短语",
            "优先参考前10个已锁定头部竞品的信息顺序；普通文案少用连接词，流量短语中的 for 可保留",
            "主标题不超过 75 字符，Highlight Item 使用完整自然句且不超过 125 字符",
        ],
    )
