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
    allowed_scenes = {
        scene.lower()
        for scenario in scenarios
        for scene in [*scenario.primary_scenes, *scenario.secondary_scenes]
    }
    product_types = " ".join(scenario.product_type for scenario in scenarios).lower()
    ranked: list[tuple[float, TitleKeywordAnalysis]] = []
    for item in request.keywords:
        term = re.sub(r"\s+", " ", item.term).strip()
        lower = term.lower()
        if not term or len(term) > 80 or not re.search(r"\b(rug|rugs|carpet)\b", lower):
            continue
        if any(blocked in lower for blocked in IRRELEVANT_RUG_TERMS):
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
        relevance = min(100, 45 + overlap * 12 + category_match * 18 + scene_match * 12 + feature_match * 15)
        if relevance < 57:
            continue
        if category_match:
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
        score = relevance * 2 + math.log10((item.volume or 0) + 1) * 8
        ranked.append((score, TitleKeywordAnalysis(
            term=term, volume=item.volume, month=item.month, rank=item.rank,
            relevance=relevance, role=role, reason=reason,
        )))
    ranked.sort(key=lambda pair: (-pair[0], pair[1].rank or 10**9, pair[1].term.lower()))
    result: list[TitleKeywordAnalysis] = []
    seen: set[str] = set()
    for _, item in ranked:
        normalized = re.sub(r"[^a-z]", "", item.term.lower())
        if normalized in seen:
            continue
        seen.add(normalized)
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
    return CompetitorTitleAnalysis(
        sample_size=len(titles),
        common_openings=[phrase for phrase, _ in opening_counter.most_common(5)],
        common_features=common_features,
        recommended_structure="Brand + clear category noun + strongest verified differentiator + size/color; then a readable benefit-and-use sentence.",
        consumer_note="美国消费者应能在标题前半段立即确认商品类型、规格和主要差异；关键词服务于理解与广告相关性，而不是堆叠同义词。",
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


def _natural_highlight(features: list[str], scenario: SizeScenarioAnalysis, limit: int = 125) -> str:
    normalized = [feature.lower() for feature in features]
    benefit_parts: list[str] = []
    if "soft" in normalized or "plush" in normalized:
        benefit_parts.append("soft underfoot")
    if "machine washable" in normalized or "washable" in normalized:
        benefit_parts.append("easy to machine wash")
    if "non-slip" in normalized:
        benefit_parts.append("designed with non-slip backing")
    if "stain-resistant" in normalized:
        benefit_parts.append("stain-resistant")
    pattern = next((feature for feature in features if any(
        word in feature.lower() for word in ("arch", "wave", "geometric", "abstract", "textured")
    )), None)
    lead = f"A {pattern.lower()} design" if pattern else "A versatile design"
    benefits = ", ".join(benefit_parts[:2])
    scenes = " and ".join(scene.lower() for scene in scenario.primary_scenes[:2])
    sentence = f"{lead} that is {benefits}, ideal for {scenes}." if benefits else f"{lead} for {scenes}."
    if len(sentence) <= limit:
        return sentence
    return f"{lead} for {scenes}."[:limit].rstrip(" ,") + "."


def generate_titles(request: TitleGenerateRequest) -> TitleGenerateResult:
    brand = _clean_brand(request.brand, request.product_title)
    features = _features(request)
    colors: list[str | None] = request.colors or [None]
    sizes: list[str | None] = request.sizes or [_extract_size(request.product_title)]
    scenarios = [_scenario(size, request.category) for size in sizes]
    keyword_analysis = _keyword_analysis(request, scenarios, features)
    traffic = [
        KeywordEntry(term=item.term, volume=item.volume, month=item.month, rank=item.rank)
        for item in keyword_analysis
    ]
    competitor_analysis = _competitor_analysis(request, features)

    candidates: list[TitleCandidate] = []
    for color in colors:
        for size, scenario in zip(sizes, scenarios):
            category = scenario.product_type
            # These are editorial structures, not keyword permutations.
            structures = [
                [brand, next((f for f in features if f in {"Washable", "Machine Washable"}), None), category, size, color,
                 next((f for f in features if f in {"Textured", "High-Low Pile", "Arch Pattern", "Wave Pattern"}), None)],
                [brand, category, size, color, *features[:2]],
                [brand, next((f for f in features if f in {"Soft", "Plush", "Modern"}), None), category, size, color,
                 next((f for f in features if f in {"Non-Slip", "Stain-Resistant"}), None)],
            ]
            seen: set[str] = set()
            for parts in structures:
                if request.title_format == "split":
                    main = _join_main(parts, 75)
                    highlight = _natural_highlight(features, scenario)
                    full = f"{main} | {highlight}"
                else:
                    highlight = None
                    sentence = _natural_highlight(features, scenario)
                    main = _join_main(parts, 200)
                    if len(f"{main}. {sentence}") <= 200:
                        main = f"{main}. {sentence}"
                    full = main
                if not main or full.lower() in seen:
                    continue
                seen.add(full.lower())
                used = [item.term for item in keyword_analysis if item.term.lower() in full.lower()]
                warnings: list[str] = []
                if not keyword_analysis:
                    warnings.append("最新词库中没有通过类目、属性与尺寸场景校验的候选词，请人工检查类目词。")
                if not features:
                    warnings.append("本品真实资料中未识别到稳定卖点，请补充产品事实后再确认。")
                candidates.append(TitleCandidate(
                    id=str(len(candidates) + 1), color=color, size=size,
                    main_title=main, highlight_item=highlight, full_title=full,
                    main_count=len(main), highlight_count=len(highlight or ""),
                    full_count=len(full), keywords_used=used, warnings=warnings,
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
            "主标题不超过 75 字符，Highlight Item 使用完整自然句且不超过 125 字符",
        ],
    )
