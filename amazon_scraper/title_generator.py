from __future__ import annotations

import math
import re
from collections import Counter

from .models import (
    CompetitorTermAnalysis,
    CompetitorTitleAnalysis,
    KeywordEntry,
    SizeCompetitorStudy,
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
LOW_VALUE_CONNECTORS = {"with", "and"}
SCENE_WORDS = {
    "living room", "bedroom", "dining room", "kitchen", "hallway",
    "entryway", "nursery", "home office", "bathroom", "laundry room",
}
BASE_CLAIM_ALIASES = {
    "non_slip": r"\b(?:non[- ]?slip|non[- ]?skid|anti[- ]?slip)\b",
    "washable": r"\b(?:machine[- ]?washable|washable)\b",
    "soft": r"\b(?:ultra[- ]?soft|super[- ]?soft|soft)\b",
    "low_pile": r"\b(?:low[- ]?pile|thin[- ]?pile)\b",
    "stain_resistant": r"\bstain[- ]?resistant\b",
    "runner_rug": r"\brunner\s+rugs?\b",
    "area_rug": r"\b(?:large\s+)?area\s+rugs?\b",
    "accent_rug": r"\baccent\s+rugs?\b",
    "scene_kitchen": r"\bkitchen\b",
    "scene_hallway": r"\bhallway\b",
    "scene_living_room": r"\bliving\s+room\b",
    "scene_bedroom": r"\bbedroom\b",
    "scene_dining_room": r"\bdining\s+room\b",
    "scene_entryway": r"\bentryway\b",
    "scene_laundry": r"\blaundry(?:\s+room)?\b",
    "scene_bathroom": r"\bbathroom\b",
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


def _dimensions(size: str | None, category: str | None = None) -> tuple[float, float] | None:
    """Return dimensions in inches; bare rug sizes <=12 are conventionally feet."""
    if not size:
        return None
    parts = re.split(r"\s*[x×]\s*", size.lower(), maxsplit=1)
    if len(parts) != 2:
        return None

    is_rug = bool(re.search(r"\b(?:rug|rugs|carpet|carpets)\b", category or "", re.I))

    def inches(part: str) -> float | None:
        feet_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:'|ft|feet)", part)
        inch_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:\"|''|in|inch|inches)", part)
        if feet_match:
            return float(feet_match.group(1)) * 12 + (float(inch_match.group(1)) if inch_match else 0)
        number = re.search(r"\d+(?:\.\d+)?", part)
        if not number:
            return None
        value = float(number.group())
        if re.search(r"(?:\"|''|\bin(?:ch|ches)?\b)", part):
            return value
        return value * 12 if is_rug and value <= 12 else value

    values = (inches(parts[0]), inches(parts[1]))
    return values if all(value is not None for value in values) else None  # type: ignore[return-value]


SCENE_LABELS = (
    (r"\bkitchen counter(?:top)?s?\b|\bcountertops?\b", "Kitchen Counter"),
    (r"\bsink side\b|\bnext to (?:the )?sink\b|\bby (?:the )?sink\b", "Sink Side"),
    (r"\bcoffee bars?\b|\bcoffee stations?\b", "Coffee Bar"),
    (r"\brv kitchens?\b|\bcampers?\b", "RV Kitchen"),
    (r"\bliving rooms?\b", "Living Room"),
    (r"\bbedrooms?\b", "Bedroom"),
    (r"\bdining rooms?\b", "Dining Room"),
    (r"\bhome offices?\b", "Home Office"),
    (r"\bhallways?\b", "Hallway"),
    (r"\bentryways?\b|\bentrances?\b", "Entryway"),
    (r"\blaundry rooms?\b", "Laundry Room"),
    (r"\bbathrooms?\b", "Bathroom"),
    (r"\bkitchens?\b", "Kitchen"),
)


def _evidence_scenes(evidence: list[str]) -> list[str]:
    corpus = " ".join(evidence).lower()
    ranked: list[tuple[int, int, str]] = []
    for index, (pattern, label) in enumerate(SCENE_LABELS):
        count = len(re.findall(pattern, corpus, re.I))
        if count:
            ranked.append((-count, index, label))
    return [label for _, _, label in sorted(ranked)]


def _scenario(
    size: str | None,
    fallback_category: str | None = None,
    evidence: list[str] | None = None,
) -> SizeScenarioAnalysis:
    category = fallback_category.strip() if fallback_category else "类目待确认"
    dims = _dimensions(size, category)
    evidence_scenes = _evidence_scenes(evidence or [])
    is_rug = bool(re.search(r"\b(?:rug|rugs|carpet|carpets)\b", category, re.I))
    if not dims:
        return SizeScenarioAnalysis(
            size=size, product_type=category,
            primary_scenes=evidence_scenes[:2],
            secondary_scenes=evidence_scenes[2:4],
            reasoning="尺寸或单位未识别；场景仅采用竞品标题与 ABA 词库中能够找到的用途证据，定稿前需人工确认。",
        )
    short, long = sorted(dims)
    if not is_rug:
        defaults: list[str] = []
        if re.search(r"\bdish drying mat\b|\bdrying mat\b", category, re.I):
            defaults = ["Kitchen Counter", "Sink Side", "Coffee Bar", "RV Kitchen"]
        scenes = list(dict.fromkeys([*evidence_scenes, *defaults]))
        area = round(short * long)
        scale = "小尺寸" if area <= 400 else "中等尺寸" if area <= 900 else "大尺寸"
        return SizeScenarioAnalysis(
            size=size, product_type=category,
            primary_scenes=scenes[:2],
            secondary_scenes=scenes[2:4],
            reasoning=(
                f"已按英寸解析为 {short:g} × {long:g} in（{scale}）；"
                "类目保持为已确认商品类型，场景优先按同尺寸竞品和 ABA 用途词频排序。"
            ),
        )
    if short <= 36 and long >= short * 1.8:
        return SizeScenarioAnalysis(
            size=size, product_type="Runner Rug",
            primary_scenes=["Hallway", "Kitchen"],
            secondary_scenes=["Entryway", "Laundry Room"],
            reasoning="窄长比例适合通道型空间；市场标题通常使用 Runner Rug，并优先表达 Hallway / Kitchen。",
        )
    if long <= 48:
        return SizeScenarioAnalysis(
            size=size, product_type="Accent Rug",
            primary_scenes=["Entryway", "Bathroom"],
            secondary_scenes=["Bedside", "Kitchen"],
            reasoning="小尺寸更适合局部落脚与装饰区域，使用 Accent Rug 比 Area Rug 更符合消费者预期。",
        )
    if long <= 84:
        return SizeScenarioAnalysis(
            size=size, product_type="Area Rug",
            primary_scenes=["Bedroom", "Home Office"],
            secondary_scenes=["Small Living Room", "Dining Nook"],
            reasoning="中小尺寸适合卧室、书房及小型起居空间；场景词应避免写成 Hallway Runner。",
        )
    if long <= 120:
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
    for verified in [*request.must_have, *request.verified_improvements]:
        label = re.sub(r"\s+", " ", verified).strip(" ,|-")
        if label and label.lower() not in {item.lower() for item in found}:
            found.append(label)
    return found


def _keyword_analysis(
    request: TitleGenerateRequest,
    scenarios: list[SizeScenarioAnalysis],
    features: list[str],
    competitor_terms: list[CompetitorTermAnalysis],
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
    category_tokens = _tokens(request.category or "")
    is_rug = bool(re.search(
        r"\b(?:rug|rugs|carpet|carpets)\b", request.category or request.product_title, re.I
    ))
    ranked: list[tuple[float, TitleKeywordAnalysis]] = []
    for item in request.keywords:
        term = re.sub(r"\s+", " ", item.term).strip()
        lower = term.lower()
        meaningful = _tokens(term)
        category_overlap = len(meaningful & category_tokens)
        minimum_category_overlap = min(2, len(category_tokens))
        if (
            not term or len(term) > 80
            or (category_tokens and category_overlap < minimum_category_overlap)
        ):
            continue
        if is_rug and any(blocked in lower for blocked in IRRELEVANT_RUG_TERMS):
            continue
        if any(re.search(rf"\b{re.escape(blocked)}\b", lower) for blocked in negatives):
            continue
        if re.search(r"\b\d+\s*[x×]\s*\d+\b", lower):
            continue
        if is_rug and "runner" in lower and "runner" not in product_types:
            continue
        if any(scene in lower for scene in ("bathroom", "kitchen", "hallway")):
            if not any(scene in lower for scene in allowed_scenes):
                continue
        overlap = len(meaningful & reference)
        category_match = bool(
            category_tokens
            and category_overlap >= max(1, minimum_category_overlap)
        )
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
        term_tokens = _tokens(term)
        market_support = max(
            (candidate.coverage_percent for candidate in competitor_terms if len(term_tokens & _tokens(candidate.term)) >= min(2, len(term_tokens))),
            default=0,
        )
        score = total_score + market_support * .08
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


def _competitor_terms(request: TitleGenerateRequest, features: list[str]) -> list[CompetitorTermAnalysis]:
    titles = [re.sub(r"\s+", " ", value).strip() for value in request.competitor_titles if value.strip()]
    if not titles:
        return []
    fact_groups = {
        "类目": request.category or "",
        "材质": request.material or "",
        "风格": request.style or "",
        "场景": request.use_case or "",
        "卖点": " ".join([*request.must_have, *request.verified_improvements, *features]),
    }
    fact_tokens = {name: _tokens(value) for name, value in fact_groups.items() if value}
    documents: list[list[str]] = []
    for title in titles:
        without_brand = re.sub(r"^\S+\s+", "", title.lower())
        without_sizes = re.sub(r"\b\d+(?:\.\d+)?\s*(?:x|×|'|ft|inch|inches)\s*\d*(?:\.\d+)?\b", " ", without_brand)
        documents.append(re.findall(r"[a-z][a-z'-]*", without_sizes))
    phrase_documents: dict[str, set[int]] = {}
    for document_index, words in enumerate(documents):
        seen_in_document: set[str] = set()
        for size in (2, 3, 4):
            for index in range(len(words) - size + 1):
                phrase_words = words[index:index + size]
                meaningful = [word for word in phrase_words if word not in STOPWORDS]
                if len(meaningful) < 2 or phrase_words[0] in {"and", "with", "for", "the"}:
                    continue
                phrase = " ".join(phrase_words)
                if phrase in seen_in_document:
                    continue
                seen_in_document.add(phrase)
                phrase_documents.setdefault(phrase, set()).add(document_index)
    minimum = 1 if len(titles) < 3 else 2
    ranked: list[tuple[int, int, str, list[str]]] = []
    for phrase, document_ids in phrase_documents.items():
        if len(document_ids) < minimum:
            continue
        phrase_tokens = _tokens(phrase)
        matched = [name for name, tokens in fact_tokens.items() if phrase_tokens & tokens]
        if not matched and not re.search(r"\b(?:rug|rugs|runner|carpet)\b", phrase):
            continue
        weighted = sum(3 if index < 10 else 2 if index < 20 else 1 for index in document_ids)
        ranked.append((weighted, len(document_ids), phrase, matched))
    ranked.sort(key=lambda item: (-item[0], -item[1], -len(item[2]), item[2]))
    result: list[CompetitorTermAnalysis] = []
    for weighted, frequency, phrase, matched in ranked:
        if any(phrase in item.term and frequency == item.document_frequency for item in result):
            continue
        placement = "main" if any(name in matched for name in ("类目", "风格")) else "highlight" if matched else "reference"
        result.append(CompetitorTermAnalysis(
            term=phrase, document_frequency=frequency, weighted_frequency=weighted,
            coverage_percent=round(frequency * 100 / len(titles)),
            matched_facts=matched, recommended_placement=placement,
        ))
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
    slot_patterns = {
        "Category": r"\b(?:area|runner|accent)\s+rugs?\b",
        "Feature": r"\b(?:washable|non[- ]?(?:slip|skid)|low[- ]?pile|soft|stain[- ]?resistant|textured)\b",
        "Style": r"\b(?:boho|vintage|modern|traditional|farmhouse|moroccan|persian|abstract|floral|geometric)\b",
        "Material": r"\b(?:polyester|polypropylene|nylon|cotton|wool|jute|chenille|microfiber|viscose)\b",
        "Scene": r"\b(?:living room|bedroom|dining room|kitchen|hallway|entryway|laundry room|bathroom)\b",
        "Size": r"\b\d+(?:\.\d+)?\s*(?:'|ft|feet)?\s*[x×]\s*\d+(?:\.\d+)?\b",
    }
    slot_orders: Counter[str] = Counter()
    slot_positions: dict[str, list[float]] = {slot: [] for slot in slot_patterns}
    lengths = sorted(len(title) for title in titles)
    for title in titles:
        without_brand = re.sub(r"^\S+\s+", "", title)
        positions: list[tuple[int, str]] = []
        for slot, pattern in slot_patterns.items():
            match = re.search(pattern, without_brand, re.I)
            if match:
                positions.append((match.start(), slot))
                slot_positions[slot].append(match.start() / max(1, len(without_brand)))
        order = " → ".join(slot for _, slot in sorted(positions))
        if order:
            slot_orders[order] += 1
    dominant_formula, dominant_count = slot_orders.most_common(1)[0] if slot_orders else ("", 0)
    position_insights = []
    for slot, values in slot_positions.items():
        if not values:
            continue
        average = sum(values) / len(values)
        region = "前段" if average <= .33 else "中段" if average <= .67 else "后段"
        position_insights.append(f"{slot}：{round(len(values) * 100 / max(1, len(titles)))}% 标题出现，通常位于{region}")
    median_length = lengths[len(lengths) // 2] if lengths else 0
    lower = lengths[max(0, round((len(lengths) - 1) * .25))] if lengths else 0
    upper = lengths[min(len(lengths) - 1, round((len(lengths) - 1) * .75))] if lengths else 0
    comma_counts = [title.count(",") for title in titles]
    average_commas = round(sum(comma_counts) / len(comma_counts), 1) if comma_counts else 0
    segmented = sum(count > 0 for count in comma_counts)
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
        consumer_note="前10个已锁定竞品视为头部样本；学习信息槽位和顺序，不复制品牌、虚假属性或高频词堆叠。",
        dominant_formula=f"Brand → {dominant_formula}" if dominant_formula else structure,
        formula_coverage_percent=round(dominant_count * 100 / max(1, len(titles))),
        common_slot_orders=[f"Brand → {value}（{count}个）" for value, count in slot_orders.most_common(3)],
        position_insights=position_insights,
        median_length=median_length,
        length_range=f"{lower}–{upper} 字符" if lengths else "",
        anti_patterns=["同义卖点跨段重复", "连续堆放多个高度重合长尾词", "未经产品事实确认的功能或场景"],
        punctuation_insights=[
            f"{round(segmented * 100 / max(1, len(titles)))}% 标题使用逗号划分信息组",
            f"平均 {average_commas} 个逗号；逗号用于分隔类目识别、差异卖点和规格场景，不用于逐词切割",
        ],
    )


def _flexible_phrase_pattern(value: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", value.lower())
    return r"\b" + r"[-\s]+".join(re.escape(word) for word in words) + r"\b" if words else ""


def _semantic_claim_patterns(
    request: TitleGenerateRequest,
    features: list[str],
) -> tuple[dict[str, str], list[str]]:
    """Build claim clusters from verified facts for this run, plus safe synonym aliases."""
    patterns = dict(BASE_CLAIM_ALIASES)
    corpus = " ".join([
        request.product_title, *request.bullets, *request.must_have,
        *request.verified_improvements, request.material or "", request.style or "",
        request.use_case or "", *[item.term for item in request.keywords],
    ])
    displayed: list[str] = []
    alias_labels = {
        "non_slip": "Non Slip = Non Skid = Anti-Slip",
        "washable": "Machine Washable ⊂ Washable",
        "soft": "Ultra Soft / Super Soft ⊂ Soft",
        "low_pile": "Low Pile = Thin Pile",
    }
    for key, label in alias_labels.items():
        if re.search(patterns[key], corpus, re.I):
            displayed.append(label)
    verified_values = [
        *features, *request.must_have, *request.verified_improvements,
        *re.split(r"[,/|;，]+", request.material or ""),
        *re.split(r"[,/|;，]+", request.style or ""),
    ]
    for value in verified_values:
        phrase = re.sub(r"\s+", " ", value).strip(" ,.|-")
        if len(phrase) < 3:
            continue
        if any(re.search(pattern, phrase, re.I) for pattern in patterns.values()):
            continue
        pattern = _flexible_phrase_pattern(phrase)
        if not pattern:
            continue
        key = "fact_" + "_".join(sorted(_tokens(phrase)))
        patterns[key] = pattern
        displayed.append(f"{phrase}（独立属性，不与其他卖点合并）")
    return patterns, list(dict.fromkeys(displayed))


def _dedupe_semantic_part(
    raw: str | None,
    used_claims: set[str],
    claim_patterns: dict[str, str],
) -> str:
    part = re.sub(r"\s+", " ", raw or "").strip(" ,.|-")
    if not part:
        return ""
    normalized = part
    for claim, pattern in claim_patterns.items():
        if not re.search(pattern, normalized, re.I):
            continue
        if claim in used_claims:
            normalized = re.sub(pattern, " ", normalized, flags=re.I)
        else:
            used_claims.add(claim)
            occurrence = 0
            def keep_first(match: re.Match[str]) -> str:
                nonlocal occurrence
                occurrence += 1
                return match.group(0) if occurrence == 1 else " "
            normalized = re.sub(pattern, keep_first, normalized, flags=re.I)
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s*,\s*,+", ", ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"^(?:with|and)\b|\b(?:with|and)$", "", normalized, flags=re.I)
    return normalized.strip(" ,.|-")


def _join_main(parts: list[str | None], limit: int, claim_patterns: dict[str, str]) -> str:
    result = ""
    used_claims: set[str] = set()
    for raw in parts:
        part = _dedupe_semantic_part(raw, used_claims, claim_patterns)
        if not part or part.lower() in result.lower():
            continue
        proposed = f"{result}, {part}" if result else part
        if len(proposed) <= limit:
            result = proposed
    return result


def _compose_main_blocks(
    blocks: list[list[str | None]],
    limit: int,
    claim_patterns: dict[str, str],
) -> str:
    """Join words inside information blocks; use commas only between blocks."""
    used_claims: set[str] = set()
    rendered: list[str] = []
    for block in blocks:
        block_parts: list[str] = []
        for raw in block:
            part = _dedupe_semantic_part(raw, used_claims, claim_patterns)
            if part and part.lower() not in " ".join(block_parts).lower():
                block_parts.append(part)
        if not block_parts:
            continue
        block_text = " ".join(block_parts)
        proposed = ", ".join([*rendered, block_text])
        if len(proposed) <= limit:
            rendered.append(block_text)
            continue
        for part in block_parts:
            proposed = ", ".join([*rendered, part])
            if len(proposed) <= limit:
                rendered.append(part)
    return ", ".join(rendered)


def _display_phrase(value: str) -> str:
    small = {"a", "an", "the", "and", "or", "for", "of", "in", "to"}
    words = value.replace(" rugs", " Rugs").replace(" rug", " Rug").split()
    return " ".join(word.lower() if index and word.lower() in small else word.capitalize() for index, word in enumerate(words))


def _keyword_scene(value: str) -> str | None:
    lower = value.lower()
    return next((_display_phrase(scene) for scene in SCENE_WORDS if scene in lower), None)


def _clean_variant_value(value: str | None, *, color: bool = False) -> str | None:
    cleaned = re.sub(r"\s*\([^)]*\)\s*", " ", value or "")
    if color:
        cleaned = re.sub(r"\s*/\s*", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,/|-")
    return cleaned or None


def _join_scenes(scenes: list[str]) -> str:
    unique = list(dict.fromkeys(scene for scene in scenes if scene))
    if len(unique) <= 1:
        return unique[0] if unique else ""
    if len(unique) == 2:
        return f"{unique[0]} and {unique[1]}"
    return f"{', '.join(unique[:-1])} and {unique[-1]}"


def _normalize_title_punctuation(value: str) -> str:
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s*,\s*for\s+", " for ", value, flags=re.I)
    value = re.sub(r"\bfor\s+([^|]+)", lambda match: "for " + re.sub(r",\s*", " and ", match.group(1)), value, flags=re.I)
    value = re.sub(r"\s*,\s*,+", ", ", value)
    return value.strip(" ,.|-")


def _market_scene_slots(
    scenario: SizeScenarioAnalysis,
    competitor_titles: list[str],
    keyword_analysis: list[TitleKeywordAnalysis],
) -> tuple[list[str], list[str]]:
    """Use same-size market position and ABA volume to decide scene placement."""
    max_volume = max((item.volume or 0 for item in keyword_analysis), default=0)
    scored: list[tuple[float, str, bool]] = []
    for scene in [*scenario.primary_scenes, *scenario.secondary_scenes]:
        pattern = next((pattern for pattern, label in SCENE_LABELS if label == scene), "")
        positions = []
        for title in competitor_titles:
            match = re.search(pattern, title, re.I) if pattern else None
            if match:
                positions.append(match.start() / max(1, len(title)))
        matching_terms = [
            item for item in keyword_analysis if scene.lower() in item.term.lower()
        ]
        volume = max((item.volume or 0 for item in matching_terms), default=0)
        volume_score = volume / max_volume if max_volume else 0
        coverage = len(positions) / max(1, len(competitor_titles))
        average_position = sum(positions) / len(positions) if positions else 1
        early_market = coverage >= .25 and average_position <= .58
        should_main = volume_score >= .55 or early_market
        score = volume_score * 100 + coverage * 45 + (1 - average_position) * 20
        scored.append((score, scene, should_main))
    scored.sort(reverse=True)
    main = [scene for _, scene, should_main in scored if should_main][:1]
    highlight = [scene for _, scene, _ in scored if scene not in main][:3]
    return main, highlight


def _color_goes_early(
    color: str | None,
    competitor_titles: list[str],
    keyword_analysis: list[TitleKeywordAnalysis],
) -> bool:
    if not color:
        return False
    color_pattern = _flexible_phrase_pattern(color)
    positions = [
        match.start() / max(1, len(title))
        for title in competitor_titles
        if (match := re.search(color_pattern, title, re.I))
    ]
    max_volume = max((item.volume or 0 for item in keyword_analysis), default=0)
    color_volume = max(
        (item.volume or 0 for item in keyword_analysis if re.search(color_pattern, item.term, re.I)),
        default=0,
    )
    return (
        bool(max_volume and color_volume / max_volume >= .55)
        or bool(positions and len(positions) / max(1, len(competitor_titles)) >= .3 and sum(positions) / len(positions) <= .4)
    )


def _best_length_fit(
    required: list[str],
    optional: list[str],
    minimum: int,
    maximum: int,
    claim_patterns: dict[str, str],
    existing: str = "",
) -> str:
    """Keep required order, then choose the longest evidence-backed optional combination."""
    best = _compact_highlight(
        required, limit=maximum, existing=existing, claim_patterns=claim_patterns,
    )
    states = [best]
    for part in optional:
        next_states = list(states)
        for current in states:
            candidate = _compact_highlight(
                [current, part], limit=maximum, existing=existing,
                claim_patterns=claim_patterns,
            )
            candidate = _normalize_title_punctuation(candidate)
            if candidate and candidate not in next_states:
                next_states.append(candidate)
        states = sorted(next_states, key=len, reverse=True)[:80]
    compliant = [state for state in states if minimum <= len(state) <= maximum]
    if compliant:
        return max(compliant, key=len)
    return max((state for state in states if len(state) <= maximum), key=len, default=best)


def _compact_highlight(
    parts: list[str],
    limit: int = 125,
    existing: str = "",
    claim_patterns: dict[str, str] | None = None,
) -> str:
    result = ""
    claim_patterns = claim_patterns or BASE_CLAIM_ALIASES
    used_claims = {
        claim for claim, pattern in claim_patterns.items()
        if re.search(pattern, existing, re.I)
    }
    for raw in parts:
        part = _dedupe_semantic_part(raw, used_claims, claim_patterns)
        if not part or part.lower() in result.lower():
            continue
        separator = " " if part.lower().startswith("for ") else ", "
        proposed = f"{result}{separator}{part}" if result else part
        if len(proposed) <= limit:
            result = proposed
    return _normalize_title_punctuation(result)


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


def _matches_category_phrase(term: str, category: str) -> bool:
    term_tokens = _tokens(term)
    category_tokens = _tokens(category)
    return bool(category_tokens) and len(term_tokens & category_tokens) >= min(2, len(category_tokens))


def generate_titles(request: TitleGenerateRequest) -> TitleGenerateResult:
    brand = _clean_brand(request.brand, request.product_title)
    features = _features(request)
    colors: list[str | None] = request.colors or [None]
    sizes: list[str | None] = request.sizes or [_extract_size(request.product_title)]
    scenarios = []
    max_keyword_volume = max((item.volume or 0 for item in request.keywords), default=0)
    for size in sizes:
        exact_titles = request.competitor_titles_by_size.get(size or "", [])
        weighted_keywords = [
            item.term
            for item in request.keywords
            for _ in range(1 + (round(4 * (item.volume or 0) / max_keyword_volume) if max_keyword_volume else 0))
        ]
        scene_evidence = [
            *(exact_titles or request.competitor_titles),
            *weighted_keywords,
            request.use_case or "",
        ]
        scenarios.append(_scenario(size, request.category, scene_evidence))
    competitor_terms = _competitor_terms(request, features)
    keyword_analysis = _keyword_analysis(request, scenarios, features, competitor_terms)
    selected_keywords = _selected_keywords(request, keyword_analysis)
    traffic = [
        KeywordEntry(term=item.term, volume=item.volume, month=item.month, rank=item.rank)
        for item in keyword_analysis
    ]
    competitor_analysis = _competitor_analysis(request, features)
    claim_patterns, semantic_clusters = _semantic_claim_patterns(request, features)
    size_contexts: dict[str, tuple[
        list[str], list[CompetitorTermAnalysis], list[TitleKeywordAnalysis],
        dict[str, list[TitleKeywordAnalysis]], CompetitorTitleAnalysis,
    ]] = {}
    size_studies: list[SizeCompetitorStudy] = []
    for size, scenario in zip(sizes, scenarios):
        key = size or ""
        exact_titles = request.competitor_titles_by_size.get(key, [])
        local_titles = exact_titles or request.competitor_titles
        local_request = request.model_copy(update={"competitor_titles": local_titles})
        local_terms = _competitor_terms(local_request, features)
        local_keyword_analysis = _keyword_analysis(
            local_request, [scenario], features, local_terms,
        )
        local_selected = _selected_keywords(local_request, local_keyword_analysis)
        local_structure = _competitor_analysis(local_request, features)
        size_contexts[key] = (
            local_titles, local_terms, local_keyword_analysis,
            local_selected, local_structure,
        )
        size_studies.append(SizeCompetitorStudy(
            size=key or "当前尺寸",
            sample_size=len(local_titles),
            dominant_formula=local_structure.dominant_formula,
            formula_coverage_percent=local_structure.formula_coverage_percent,
            frequent_terms=local_terms[:8],
            aba_terms=local_keyword_analysis[:8],
            note=(
                f"使用 {len(exact_titles)} 个同尺寸竞品独立分析。"
                if exact_titles else "未识别到足够同尺寸竞品，暂时回退到全部已锁定竞品；建议人工补充同尺寸 ASIN。"
            ),
        ))

    candidates: list[TitleCandidate] = []
    for color in colors:
        for size, scenario in zip(sizes, scenarios):
            category = scenario.product_type
            cleaned_size = _clean_variant_value(size)
            title_size = None if (cleaned_size or "").strip().lower() in {"尺寸未识别", "unknown", "n/a"} else cleaned_size
            title_color = _clean_variant_value(color, color=True)
            styles = _style_parts(request.style)
            (
                size_competitor_titles, size_competitor_terms, size_keyword_analysis,
                size_selected_keywords, size_competitor_analysis,
            ) = size_contexts[size or ""]
            size_market_phrase = next(
                (
                    item.term for item in size_competitor_terms
                    if item.recommended_placement == "main"
                    and _matches_category_phrase(item.term, category)
                ),
                None,
            )
            main_terms = size_selected_keywords["main"]
            highlight_terms = size_selected_keywords["highlight"]
            primary_keyword = next(
                (item for item in main_terms if _matches_category_phrase(item.term, category)),
                main_terms[0] if main_terms else None,
            )
            scene_keyword = next(
                (item for item in main_terms if any(scene in item.term.lower() for scene in SCENE_WORDS)),
                None,
            )
            main_scenes, highlight_scenes = _market_scene_slots(
                scenario, size_competitor_titles, size_keyword_analysis,
            )
            scene_part = _keyword_scene(scene_keyword.term) if scene_keyword and scene_keyword is not primary_keyword else None
            if not scene_part and main_scenes:
                scene_part = main_scenes[0]
            category_part = _display_phrase(primary_keyword.term) if primary_keyword else category
            if scene_part and scene_part.lower() in category_part.lower():
                scene_part = None
            color_early = _color_goes_early(
                title_color, size_competitor_titles, size_keyword_analysis,
            )
            formula_slots = re.findall(
                r"\b(?:Brand|Category|Feature|Style|Material|Scene|Size)\b",
                size_competitor_analysis.dominant_formula,
            )
            slot_values: dict[str, list[str | None]] = {
                "Brand": [brand],
                "Category": [category_part],
                "Feature": features[:2],
                "Style": styles[:1],
                "Material": [request.material],
                "Scene": [scene_part or (scenario.primary_scenes[0] if scenario.primary_scenes else None)],
                "Size": [title_size, title_color],
            }
            ordered_descriptors = [
                part for slot in formula_slots
                if slot not in {"Brand", "Category", "Size"}
                for part in slot_values.get(slot, [])
            ]
            traffic_blocks = [
                [brand, title_color if color_early else None, category_part],
                [*styles[:1], *features[:1], f"for {scene_part}" if scene_part else None],
                [*features[1:2], request.material],
                [title_size, None if color_early else title_color],
            ]
            click_blocks = [
                [brand, title_color if color_early else None, category_part],
                [features[0] if features else None, *styles[:1], f"for {scene_part}" if scene_part else None],
                [*features[1:2], request.material],
                [title_size, None if color_early else title_color],
            ]
            balanced_blocks = [
                [brand, title_color if color_early else None, category_part],
                [
                    *ordered_descriptors[:3],
                    _display_phrase(size_market_phrase) if size_market_phrase else None,
                    f"for {scene_part}" if scene_part else None,
                ],
                ordered_descriptors[3:5],
                [title_size, None if color_early else title_color],
            ]
            structures = [
                ("traffic", traffic_blocks),
                ("click", click_blocks),
                ("balanced", balanced_blocks),
            ]
            seen: set[str] = set()
            for strategy, blocks in structures:
                if request.title_format == "split":
                    main = _compose_main_blocks(blocks, 75, claim_patterns)
                    main = _normalize_title_punctuation(main)
                    main_optional = [
                        *(_display_phrase(item.term) for item in main_terms),
                        *styles,
                        *features,
                        request.material or "",
                        title_size or "",
                        title_color or "",
                    ]
                    main = _best_length_fit(
                        [main], main_optional, 70, 75, claim_patterns,
                    )
                    material_phrase = " ".join([
                        *_style_parts(request.material),
                        "Surface" if "rug" in category.lower() else "",
                    ]).strip()
                    feature_phrase = " ".join(features).strip()
                    remaining_scenes = highlight_scenes or [
                        scene for scene in [*scenario.primary_scenes, *scenario.secondary_scenes]
                        if scene not in main_scenes
                    ][:3]
                    scene_phrase = f"for {_join_scenes(remaining_scenes)}" if remaining_scenes else ""
                    highlight_required = [material_phrase, feature_phrase]
                    highlight_optional = [
                        *(_display_phrase(item.term) for item in highlight_terms),
                        *request.must_have,
                        *request.verified_improvements,
                        *styles,
                        request.material or "",
                        request.use_case or "",
                        *(_display_phrase(item.term) for item in size_keyword_analysis if item.recommended_placement == "highlight"),
                    ]
                    scene_suffix_length = len(scene_phrase) + 1 if scene_phrase else 0
                    highlight = _best_length_fit(
                        highlight_required, highlight_optional,
                        max(1, 120 - scene_suffix_length),
                        125 - scene_suffix_length,
                        claim_patterns, existing=main,
                    )
                    if scene_phrase:
                        highlight = f"{highlight} {scene_phrase}".strip()
                    highlight = _normalize_title_punctuation(highlight)
                    full = f"{main} | {highlight}"
                else:
                    highlight = None
                    main = _compose_main_blocks(blocks, 200, claim_patterns)
                    material_phrase = " ".join([
                        *_style_parts(request.material),
                        "Surface" if "rug" in category.lower() else "",
                    ]).strip()
                    feature_phrase = " ".join(features[1:]).strip()
                    scenes = list(dict.fromkeys([
                        *scenario.primary_scenes, *scenario.secondary_scenes,
                    ]))[:4]
                    sentence = _compact_highlight([
                        material_phrase,
                        feature_phrase,
                        f"for {_join_scenes(scenes)}" if scenes else "",
                    ], existing=main, claim_patterns=claim_patterns)
                    if sentence and len(f"{main}, {sentence}") <= 200:
                        main = f"{main}, {sentence}"
                    full = main
                if not main or full.lower() in seen:
                    continue
                seen.add(full.lower())
                used = [item.term for item in size_keyword_analysis if item.term.lower() in full.lower()]
                unused = [
                    item.term for item in [*main_terms, *highlight_terms]
                    if item.term.lower() not in full.lower()
                ]
                evidence = [
                    f"{item.term} · 搜索量{int(item.volume):,} · {('精确短语' if item.term.lower() in full.lower() else '未覆盖')}"
                    if item.volume is not None else f"{item.term} · 流量未知"
                    for item in [*main_terms, *highlight_terms][:8]
                ]
                if size_competitor_titles:
                    evidence.append(
                        f"{size or '当前尺寸'} · 参考 {len(size_competitor_titles)} 个同尺寸/近似尺寸竞品标题"
                    )
                warnings: list[str] = []
                if not size_keyword_analysis:
                    warnings.append("最新词库中没有通过类目、属性与尺寸场景校验的候选词，请人工检查类目词。")
                if not features:
                    warnings.append("本品真实资料中未识别到稳定卖点，请补充产品事实后再确认。")
                if styles and not any(style.lower() in full.lower() for style in styles):
                    warnings.append("已确认风格未进入标题，请缩减低优先级属性或人工指定风格关键词。")
                if any(connector in full.lower().split() for connector in LOW_VALUE_CONNECTORS):
                    warnings.append("连接词仅因已选关键词或必要语法保留，请人工确认其流量价值。")
                if request.title_format == "split" and not 70 <= len(main) <= 75:
                    warnings.append("本品可验证事实不足以自然填满 70–75 字符，请补充材质、风格或真实卖点后再定稿。")
                if request.title_format == "split" and not 120 <= len(highlight or "") <= 125:
                    warnings.append("本品可验证事实不足以自然填满 120–125 字符，请补充真实功能或用途证据后再定稿。")
                base_score = {"traffic": 88, "click": 86, "balanced": 90}[strategy]
                coverage_score = min(10, len(used) * 3)
                candidates.append(TitleCandidate(
                    id=str(len(candidates) + 1), color=color, size=size,
                    main_title=main, highlight_item=highlight, full_title=full,
                    main_count=len(main), highlight_count=len(highlight or ""),
                    full_count=len(full), keywords_used=used,
                    strategy=strategy, score=min(100, base_score + coverage_score),
                    keyword_evidence=evidence, unused_keywords=unused,
                    ad_keywords=[item.term for item in size_selected_keywords["ads"]],
                    warnings=warnings,
                ))

    return TitleGenerateResult(
        candidates=candidates,
        traffic_keywords=traffic,
        keyword_analysis=keyword_analysis,
        size_scenarios=scenarios,
        competitor_analysis=competitor_analysis,
        competitor_terms=competitor_terms,
        semantic_clusters=semantic_clusters,
        size_competitor_studies=size_studies,
        rules=[
            "主标题前部必须出现与尺寸一致的类目大词，让消费者立即识别商品类型",
            "词库排名为上传文件最新月份的搜索量排名，不代表 Amazon 自然搜索排名",
            "竞品用于学习自然结构和市场表达，不照抄品牌、未经证实卖点或错误场景",
            "广告词、流量词与标题埋词服从相关性和可读性，同义词不重复堆叠",
            "高流量且事实、尺寸场景匹配的场景词允许进入主标题，并尽量保留完整搜索短语",
            "优先参考前10个已锁定头部竞品的信息顺序；普通文案少用连接词，流量短语中的 for 可保留",
            "父体批量优化时，先按尺寸匹配竞品标题；同尺寸证据不足才回退到全体已锁定竞品",
            "先按头部竞品主导槽位公式组织信息，再填充流量词；同义卖点和相同场景在主标题与 Highlight 合计只表达一次",
            "主标题不超过 75 字符，Highlight Item 使用完整自然句且不超过 125 字符",
        ],
    )
