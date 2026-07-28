from __future__ import annotations

import asyncio
import base64
import math
import re
from io import BytesIO
from urllib.parse import quote_plus

import httpx
from PIL import Image, ImageChops, ImageFilter, ImageStat
from playwright.async_api import BrowserContext

from .models import CompetitorCandidate, CompetitorDiscoverResult
from .scraper import (
    MARKETPLACES, _challenge, _extract_variants, _monthly_sales_estimate,
    _number, _parent_asin, _rating, _snapshot, _text,
)

STOPWORDS = {
    "a", "an", "and", "for", "from", "in", "of", "on", "the", "to", "with",
    "new", "pack", "inch", "inches", "amazon", "black", "white", "beige",
    "brown", "blue", "green", "grey", "gray", "red", "large", "small",
    "runner", "runners", "feet", "foot", "ft", "inch", "inches",
}
CATEGORY_FAMILIES = {
    "rug": {"rug", "rugs", "carpet", "carpets", "runner", "runners"},
    "bag": {"bag", "bags", "backpack", "backpacks", "tote", "purse", "handbag"},
    "bedding": {"sheet", "sheets", "duvet", "comforter", "blanket", "bedding"},
    "curtain": {"curtain", "curtains", "drape", "drapes"},
    "furniture": {"chair", "chairs", "table", "desk", "sofa", "cabinet"},
    "clothing": {"dress", "shirt", "pants", "jacket", "coat", "sweater"},
    "kitchen": {"pan", "pot", "knife", "cookware", "utensil", "container"},
}
CATEGORY_QUERY = {
    "rug": "area rug", "bag": "bag", "bedding": "bedding",
    "curtain": "curtain", "furniture": "furniture",
    "clothing": "clothing", "kitchen": "kitchen",
}
ATTRIBUTE_GROUPS = {
    "可水洗": {"washable", "machine washable", "easy clean", "easy to clean"},
    "防滑": {"non slip", "non-slip", "nonslip", "anti slip"},
    "高低绒": {"high low", "high-low", "textured", "tufted"},
    "低绒": {"low pile", "thin"},
    "柔软": {"soft", "fluffy", "plush", "cozy"},
    "材质": {"polyester", "cotton", "wool", "jute", "nylon", "microfiber"},
    "风格": {"modern", "abstract", "boho", "vintage", "geometric", "minimalist"},
}
FEATURE_PHRASES = [
    # Construction / texture: usually more discriminating than room names.
    ("high low pile", "High Low Pile", 10), ("high-low pile", "High Low Pile", 10),
    ("cut and loop", "Cut and Loop", 10), ("raised pattern", "Raised Pattern", 10),
    ("3d", "3D Texture", 9), ("5d", "5D Texture", 9), ("tufted", "Tufted", 8),
    ("textured", "Textured", 7), ("shaggy", "Shaggy", 9), ("fluffy", "Fluffy", 8),
    ("faux wool", "Faux Wool", 9), ("low pile", "Low Pile", 7),
    # Visual motifs / style.
    ("arch pattern", "Arch Pattern", 11), ("arch", "Arch Pattern", 11),
    ("arc pattern", "Arch Pattern", 11), ("wave pattern", "Wave Pattern", 10),
    ("wavy", "Wavy Pattern", 9), ("geometric", "Geometric", 8),
    ("abstract", "Abstract", 8), ("moroccan", "Moroccan", 9),
    ("boho", "Boho", 8), ("vintage", "Vintage", 8), ("minimalist", "Minimalist", 7),
    ("solid color", "Solid Color", 8),
    # Functional and material attributes.
    ("machine washable", "Machine Washable", 8), ("washable", "Washable", 6),
    ("non slip", "Non Slip", 7), ("non-slip", "Non Slip", 7),
    ("stain resistant", "Stain Resistant", 6), ("polyester", "Polyester", 5),
    ("soft", "Soft", 4), ("pet friendly", "Pet Friendly", 4),
]


def _tokens(value: str) -> list[str]:
    return [
        token.lower() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9'+-]*", value)
        if (
            len(token) > 1
            and token.lower() not in STOPWORDS
            and not re.fullmatch(r"\d+(?:[x×]\d+)+", token.lower())
            and not re.fullmatch(r"\d+(?:\.\d+)?(?:x|ft|in)", token.lower())
            and not re.fullmatch(r"\d+", token)
        )
    ]


def _family(value: str) -> tuple[str | None, set[str]]:
    tokens = set(_tokens(value))
    for name, words in CATEGORY_FAMILIES.items():
        if tokens & words:
            return name, words
    return None, set()


def _unique_words(*values: str | None, limit: int = 7) -> str:
    words: list[str] = []
    for value in values:
        for token in _tokens(value or ""):
            if token not in words:
                words.append(token)
    return " ".join(words[:limit])


def _feature_profile(value: str) -> list[str]:
    normalized = value.lower().replace("-", " ")
    matches: dict[str, int] = {}
    for phrase, label, weight in FEATURE_PHRASES:
        if phrase.replace("-", " ") in normalized:
            matches[label] = max(matches.get(label, 0), weight)
    return [label for label, _ in sorted(matches.items(), key=lambda item: (-item[1], item[0]))]


def _queries(title: str, evidence: str, category: str | None, material: str | None,
             style: str | None, use_case: str | None, features: list[str]) -> tuple[list[str], list[str]]:
    family_name, family_words = _family(f"{category or ''} {title}")
    # Prefer a reader-facing category supplied by the user. Otherwise use the
    # family noun identified on the real page.
    category_seed = _unique_words(category, CATEGORY_QUERY.get(family_name or ""), limit=3) if family_name else _unique_words(category, title, limit=3)
    detected = _feature_profile(" ".join([title, evidence, material or "", style or "", *features]))
    explicit = [value.strip() for value in [material, style, *features] if value and value.strip()]
    profile = list(dict.fromkeys([*detected, *explicit]))
    construction = [item for item in profile if item in {
        "High Low Pile", "Cut and Loop", "Raised Pattern", "3D Texture", "5D Texture",
        "Tufted", "Textured", "Shaggy", "Fluffy", "Faux Wool", "Low Pile", "Polyester",
    }]
    visual = [item for item in profile if item in {
        "Arch Pattern", "Wave Pattern", "Wavy Pattern", "Geometric", "Abstract",
        "Moroccan", "Boho", "Vintage", "Minimalist", "Solid Color",
    }]
    function = [item for item in profile if item not in set(construction + visual)]
    detected_set = set(detected)
    priority = [
        "Arch Pattern", "Wave Pattern", "Wavy Pattern", "Raised Pattern",
        "High Low Pile", "Textured", "3D Texture", "5D Texture", "Fluffy",
        "Geometric", "Abstract", "Moroccan", "Cut and Loop", "Tufted",
        "Machine Washable", "Non Slip", "Polyester",
    ]
    signals = [label for label in priority if label in detected_set or label in explicit]
    queries = [
        _unique_words(category_seed, " ".join(signals[:3]), limit=8),
        _unique_words(category_seed, " ".join(signals[1:4]), limit=8),
        _unique_words(category_seed, " ".join(signals[3:6]), limit=8),
        _unique_words(category_seed, " ".join(signals[-3:]), limit=8),
    ]
    result = [query for query in dict.fromkeys(queries) if query and len(query.split()) >= 2]
    # If the real page exposes few useful attributes, preserve one focused
    # title-derived fallback instead of a long, noisy title query.
    if len(result) < 2:
        result.append(_unique_words(category_seed, title, limit=6))
    return list(dict.fromkeys(result)), profile[:10]


async def _visual_fingerprint(
    client: httpx.AsyncClient, url: str | None,
) -> dict[str, list[float]] | None:
    if not url:
        return None
    try:
        response = await client.get(url, timeout=15)
        response.raise_for_status()
        return _visual_fingerprint_bytes(response.content)
    except Exception:
        return None


def _visual_fingerprint_bytes(content: bytes) -> dict[str, list[float]] | None:
    try:
        image = Image.open(BytesIO(content)).convert("RGB")
        # Remove near-white marketplace background before comparing shape, texture and color.
        background = Image.new("RGB", image.size, (255, 255, 255))
        difference = ImageChops.difference(image, background).convert("L")
        mask = difference.point(lambda value: 255 if value > 18 else 0)
        box = mask.getbbox()
        if box:
            image = image.crop(box)
        image = image.resize((24, 24))
        gray = image.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        mean = ImageStat.Stat(gray).mean[0]
        structure = [(pixel - mean) / 255 for pixel in gray.getdata()]
        edge_mean = ImageStat.Stat(edges).mean[0]
        edge_values = [(pixel - edge_mean) / 255 for pixel in edges.getdata()]
        # A small RGB histogram stops two differently coloured products with the
        # same room layout from receiving an unrealistically high visual score.
        histogram = []
        for channel in image.split():
            raw = channel.histogram()
            histogram.extend(sum(raw[start:start + 32]) / (24 * 24) for start in range(0, 256, 32))
        return {"structure": structure, "edges": edge_values, "color": histogram}
    except Exception:
        return None


def _decode_reference_image(data_url: str | None) -> bytes | None:
    if not data_url:
        return None
    try:
        header, encoded = data_url.split(",", 1)
        if ";base64" not in header or not header.lower().startswith("data:image/"):
            return None
        content = base64.b64decode(encoded, validate=True)
        return content if 0 < len(content) <= 8 * 1024 * 1024 else None
    except Exception:
        return None


def _cosine(left: list[float] | None, right: list[float] | None) -> float | None:
    if not left or not right or len(left) != len(right):
        return None
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left) * sum(b * b for b in right))
    # Do not shift cosine into the 50-100 range. That old mapping made unrelated
    # room scenes look highly similar merely because both contained a rug.
    return max(0, min(1, dot / norm)) if norm else None


def _visual_score(
    left: dict[str, list[float]] | None,
    right: dict[str, list[float]] | None,
) -> int | None:
    if not left or not right:
        return None
    structure = _cosine(left["structure"], right["structure"])
    edges = _cosine(left["edges"], right["edges"])
    color = sum(min(a, b) for a, b in zip(left["color"], right["color"])) / 3
    if structure is None or edges is None:
        return None
    return round(max(0, min(1, structure * .55 + edges * .25 + color * .20)) * 100)


def _clean_brand(value: str | None) -> str | None:
    cleaned = re.sub(
        r"^(Visit the |Brand:\s*)| Store$",
        "",
        value or "",
        flags=re.I,
    ).strip()
    return cleaned or None


def _title_brand(title: str) -> str | None:
    # Amazon titles conventionally lead with the brand. This is only a fast
    # pre-grouping hint; the detail-page byline replaces it afterwards.
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9&'._-]{1,30})\b", title)
    return match.group(1).strip() if match else None


def _title_size(title: str) -> str | None:
    patterns = [
        r"\b\d+(?:\.\d+)?\s*(?:feet|foot|ft|')\s*[x×]\s*\d+(?:\.\d+)?\s*(?:feet|foot|ft|inches|inch|in|\"|')?(?=\s|$|[,;|])",
        r"\b\d+(?:\.\d+)?\s*[x×]\s*\d+(?:\.\d+)?\s*(?:feet|foot|ft|inches|inch|in)?\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, title, re.I)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return None


def _normalize_size(value: str | None) -> str:
    normalized = (value or "").lower().replace("×", "x")
    normalized = re.sub(r"\b(feet|foot|ft|inches|inch|in)\b", "", normalized)
    return re.sub(r"[\s'\"-]+", "", normalized)


def _phrases(value: str) -> set[str]:
    lower = value.lower().replace("-", " ")
    found: set[str] = set()
    for label, phrases in ATTRIBUTE_GROUPS.items():
        if any(phrase.replace("-", " ") in lower for phrase in phrases):
            found.add(label)
    return found


def _price(value: str | None) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)", value or "")
    return float(match.group(1)) if match else None


def _market_score(target_price: float | None, candidate_price: float | None,
                  rating_count: int | None, sales: str | None) -> int:
    price_score = 50
    if target_price and candidate_price:
        ratio = abs(candidate_price - target_price) / max(target_price, candidate_price)
        price_score = max(0, round((1 - ratio) * 70))
    evidence = 30 if sales else 15 if rating_count else 0
    return min(100, price_score + evidence)


def _dedupe_and_sort_candidates(
    candidates: list[CompetitorCandidate],
) -> tuple[list[CompetitorCandidate], int]:
    representative_by_group: dict[str, CompetitorCandidate] = {}
    for candidate in candidates:
        normalized_brand = (candidate.brand or "").strip().lower()
        group_key = (
            f"brand:{normalized_brand}"
            if normalized_brand
            else f"parent:{candidate.parent_asin or candidate.asin}"
        )
        current = representative_by_group.get(group_key)
        candidate_rank = (
            candidate.monthly_sales_estimate or 0,
            candidate.overall_similarity,
            candidate.image_similarity or 0,
        )
        current_rank = (
            current.monthly_sales_estimate or 0,
            current.overall_similarity,
            current.image_similarity or 0,
        ) if current else None
        if current is None or candidate_rank > current_rank:
            representative_by_group[group_key] = candidate
    collapsed = len(candidates) - len(representative_by_group)
    representatives = list(representative_by_group.values())
    representatives.sort(key=lambda item: (
        -(item.monthly_sales_estimate or 0),
        -item.overall_similarity,
        -(item.image_similarity or 0),
        item.asin,
    ))
    return representatives, collapsed


async def discover_competitors(
    context: BrowserContext, asin: str | None, marketplace: str, limit: int, headless: bool,
    category: str | None = None, material: str | None = None, style: str | None = None,
    use_case: str | None = None, features: list[str] | None = None,
    custom_queries: list[str] | None = None,
    confirmed_brand: str | None = None,
    search_pages: int = 1,
    exclude_asins: list[str] | None = None,
    reference_titles: list[str] | None = None,
    reference_bullets: list[str] | None = None,
    target_name: str | None = None,
    reference_image_data: str | None = None,
    verify_detail_pages: bool = False,
) -> CompetitorDiscoverResult:
    features = features or []
    base_url, _ = MARKETPLACES[marketplace]
    page = context.pages[0] if context.pages else await context.new_page()
    if asin:
        await page.goto(f"{base_url}/dp/{asin.upper()}", wait_until="domcontentloaded", timeout=60_000)
        await _challenge(page, headless, "本品页面")
        target = await _snapshot(page, base_url, asin.upper())
    else:
        supplied_title = re.sub(r"\s+", " ", target_name or category or "").strip()
        if not supplied_title or not category:
            raise ValueError("全新商品模式至少需要类目大词和产品名称/特征资料。")
        target = {
            "asin": "NEW-PRODUCT", "title": supplied_title, "image": None,
            "images": [], "price": None, "bullets": list(reference_bullets or []),
        }
    # Build the product profile from the real title + bullets + confirmed facts,
    # not from the title alone.
    family_titles = [value for value in (reference_titles or []) if value]
    family_bullets = [value for value in (reference_bullets or []) if value]
    evidence = " ".join([*(target.get("bullets") or []), *family_titles, *family_bullets])
    generated_queries, target_features = _queries(
        target["title"], evidence, category, material, style, use_case, features,
    )
    custom_queries = [
        re.sub(r"\s+", " ", query).strip() for query in (custom_queries or [])
        if 2 <= len(re.sub(r"\s+", " ", query).strip()) <= 120
    ]
    search_queries = list(dict.fromkeys(custom_queries))[:6] or generated_queries
    family_name, family_words = _family(f"{category or ''} {target['title']}")
    # Exclude the complete target family. Otherwise Amazon search often returns
    # another color/size of the user's own product and it looks like a competitor.
    own_asins = {
        value.upper() for value in (exclude_asins or [])
        if re.fullmatch(r"[A-Za-z0-9]{10}", value)
    }
    if asin:
        own_asins.update({asin.upper(), target["asin"]})
        parent_asin = await _parent_asin(page)
        if parent_asin:
            own_asins.add(parent_asin)
        for variant in await _extract_variants(page, base_url):
            own_asins.add(variant.asin)
    brand_text = await _text(page, ["#bylineInfo"]) if asin else None
    target_brand = _clean_brand(confirmed_brand or brand_text) or ""
    target_brand_token = (_tokens(target_brand) or [None])[0]
    if not target_brand_token:
        first_title_token = (_tokens(target["title"]) or [None])[0]
        category_vocabulary = set().union(*CATEGORY_FAMILIES.values())
        # Amazon occasionally omits the byline on parent pages. A distinctive
        # leading title token is the brand in normal listing title structure.
        if first_title_token and first_title_token not in category_vocabulary:
            target_brand_token = first_title_token

    raw_by_asin: dict[str, dict] = {}
    excluded_same_brand = 0
    for query in search_queries:
        for search_page in range(1, search_pages + 1):
            await page.goto(
                f"{base_url}/s?k={quote_plus(query)}&page={search_page}",
                wait_until="domcontentloaded", timeout=60_000,
            )
            await _challenge(page, headless, "竞品搜索页面")
            await page.wait_for_timeout(500)
            cards = page.locator("[data-component-type='s-search-result'][data-asin]")
            for index in range(await cards.count()):
                card = cards.nth(index)
                candidate_asin = (await card.get_attribute("data-asin") or "").upper()
                if not re.fullmatch(r"[A-Z0-9]{10}", candidate_asin) or candidate_asin in own_asins:
                    continue
                title = await _text(card, ["h2 span", "h2 a span"])  # type: ignore[arg-type]
                if not title:
                    continue
                # Another listing from the user's own brand is not a competitor,
                # even when it belongs to a different parent family.
                title_tokens = _tokens(title)
                if target_brand_token and title_tokens and title_tokens[0] == target_brand_token:
                    excluded_same_brand += 1
                    continue
                image_node = card.locator("img.s-image").first
                image = await image_node.get_attribute("src") if await image_node.count() else None
                sales = await _text(card, ["[aria-label*='bought in past month']", ".a-row.a-size-base"])  # type: ignore[arg-type]
                if sales and not re.search(r"bought.*month", sales, re.I):
                    sales = None
                item = raw_by_asin.setdefault(candidate_asin, {
                    "asin": candidate_asin, "title": title, "url": f"{base_url}/dp/{candidate_asin}",
                    "image": image, "price": await _text(card, [".a-price .a-offscreen"]),
                    "rating_text": await _text(card, [".a-icon-alt"]),
                    "rating_count_text": await _text(card, ["[data-csa-c-slot-id='alf-reviews'] span", ".s-underline-text"]),
                    "sales": sales, "queries": [], "images": [image] if image else [],
                    "parent_asin": None, "brand": _title_brand(title),
                    "size": _title_size(title),
                })
                if query not in item["queries"]:
                    item["queries"].append(query)

    target_text = " ".join([
        target["title"], evidence, category or "", material or "", style or "",
        use_case or "", *features, *target_features,
    ])
    target_tokens, target_attrs = set(_tokens(target_text)), _phrases(target_text)
    target_feature_set = set(target_features)
    eligible = []
    for item in raw_by_asin.values():
        candidate_family, _ = _family(item["title"])
        if family_name and candidate_family != family_name:
            continue
        other_features = set(_feature_profile(item["title"]))
        feature_coverage = (
            len(target_feature_set & other_features) / len(target_feature_set)
            if target_feature_set else 0
        )
        token_overlap = len(target_tokens & set(_tokens(item["title"]))) / max(1, len(target_tokens))
        item["preliminary_score"] = feature_coverage * .75 + token_overlap * .20 + min(len(item["queries"]), 3) / 3 * .05
        eligible.append(item)
    # Detail-page verification is required to know the real parent family.
    # Prioritize the strongest search matches and keep the browser workload bounded.
    eligible.sort(key=lambda item: (-item["preliminary_score"], item["asin"]))
    pregrouped: dict[str, dict] = {}
    for item in eligible:
        brand_key = (item.get("brand") or "").lower()
        key = f"brand:{brand_key}" if brand_key else item["asin"]
        current = pregrouped.get(key)
        item_rank = (
            _monthly_sales_estimate(item.get("sales")) or 0,
            item["preliminary_score"],
            len(item["queries"]),
        )
        current_rank = (
            _monthly_sales_estimate(current.get("sales")) or 0,
            current["preliminary_score"],
            len(current["queries"]),
        ) if current else None
        if current is None or item_rank > current_rank:
            pregrouped[key] = item
    preliminary_collapsed = len(eligible) - len(pregrouped)
    eligible = sorted(
        pregrouped.values(),
        key=lambda item: (
            -(_monthly_sales_estimate(item.get("sales")) or 0),
            -item["preliminary_score"],
            item["asin"],
        ),
    )[: min(max(limit + 6, 12), 60)]

    if verify_detail_pages:
        for item in eligible:
            try:
                await page.goto(item["url"], wait_until="domcontentloaded", timeout=60_000)
                await _challenge(page, headless, "竞品详情页面")
                detail = await _snapshot(page, base_url, item["asin"])
                item["parent_asin"] = await _parent_asin(page)
                item["brand"] = _clean_brand(await _text(page, ["#bylineInfo"])) or item.get("brand")
                item["size"] = detail.get("size") or item.get("size")
                for key in ("title", "price", "image"):
                    if detail.get(key):
                        item[key] = detail[key]
                if detail.get("images"):
                    item["images"] = detail["images"][:4]
                if detail.get("rating") is not None:
                    item["rating"] = detail["rating"]
                if detail.get("rating_count") is not None:
                    item["rating_count"] = detail["rating_count"]
                if detail.get("recent_sales_signal"):
                    item["sales"] = detail["recent_sales_signal"]
            except Exception:
                # Search-card data remains useful when one detail page is blocked.
                pass

    target_image_urls = list(dict.fromkeys(target.get("images") or [target.get("image")]))[:4]
    all_image_urls = list(dict.fromkeys([
        url for item in eligible for url in (item.get("images") or [item.get("image")])[:4] if url
    ]))
    download_urls = list(dict.fromkeys([*target_image_urls, *all_image_urls]))
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True) as client:
        downloaded = await asyncio.gather(*[_visual_fingerprint(client, url) for url in download_urls])
    fingerprint_by_url = dict(zip(download_urls, downloaded))
    target_fingerprints = [
        fingerprint_by_url[url] for url in target_image_urls if fingerprint_by_url.get(url)
    ]
    uploaded_fingerprint = _visual_fingerprint_bytes(_decode_reference_image(reference_image_data) or b"")
    if uploaded_fingerprint:
        target_fingerprints.insert(0, uploaded_fingerprint)

    candidates: list[CompetitorCandidate] = []
    target_price = _price(target.get("price"))
    for item in eligible:
        other_tokens = set(_tokens(item["title"]))
        union = target_tokens | other_tokens
        token_score = len(target_tokens & other_tokens) / len(union) * 100 if union else 0
        other_feature_set = set(_feature_profile(item["title"]))
        feature_coverage = (
            len(target_feature_set & other_feature_set) / len(target_feature_set) * 100
            if target_feature_set else 0
        )
        text_score = round(feature_coverage * .75 + token_score * .25)
        other_attrs = _phrases(item["title"])
        attr_union = target_attrs | other_attrs
        attr_score = round(len(target_attrs & other_attrs) / len(attr_union) * 100) if attr_union else text_score
        candidate_image_urls = (item.get("images") or [item.get("image")])[:4]
        candidate_fingerprints = [
            fingerprint_by_url[url] for url in candidate_image_urls
            if url and fingerprint_by_url.get(url)
        ]
        pair_scores = sorted(
            [
                score for target_fingerprint in target_fingerprints
                for candidate_fingerprint in candidate_fingerprints
                if (score := _visual_score(target_fingerprint, candidate_fingerprint)) is not None
            ],
            reverse=True,
        )
        image_score = round(sum(pair_scores[:2]) / min(2, len(pair_scores))) if pair_scores else None
        compared_pairs = len(pair_scores)
        rating_count = item.get("rating_count") or _number(item["rating_count_text"])
        market_score = _market_score(target_price, _price(item["price"]), rating_count, item["sales"])
        overall = round((image_score or 0) * .20 + attr_score * .30 + text_score * .40 + market_score * .10)
        reasons = []
        if family_name:
            reasons.append(f"同类目：{family_name}")
        shared_attrs = sorted(target_attrs & other_attrs)
        if shared_attrs:
            reasons.append("共同属性：" + "、".join(shared_attrs))
        if image_score is not None:
            reasons.append(f"多图视觉 {image_score}%")
        if item.get("parent_asin"):
            reasons.append(f"父体 {item['parent_asin']}")
        reasons.append(f"命中 {len(item['queries'])} 组搜索")
        sales_estimate = _monthly_sales_estimate(item["sales"])
        visual_reason = (
            f"去白底后比较轮廓55%＋纹理边缘25%＋颜色20%；"
            f"本品{len(target_fingerprints)}张×竞品{len(candidate_fingerprints)}张，取最高两组均值"
            if image_score is not None else "图片不足，未计算视觉分"
        )
        candidates.append(CompetitorCandidate(
            asin=item["asin"], parent_asin=item.get("parent_asin"), brand=item.get("brand"),
            size=item.get("size"),
            title=item["title"], url=item["url"], image=item["image"],
            price=item["price"], rating=item.get("rating") or _rating(item["rating_text"]),
            rating_count=rating_count, recent_sales_signal=item["sales"],
            monthly_sales_estimate=sales_estimate, text_similarity=text_score,
            image_similarity=image_score, visual_images_compared=compared_pairs,
            visual_reason=visual_reason, attribute_similarity=attr_score,
            market_similarity=market_score, category_match=True,
            auto_selected=overall >= 60, match_reasons=reasons,
            overall_similarity=overall,
        ))

    # Keep only one representative per competitor brand. If the brand cannot be
    # inferred from the search title, fall back to parent/ASIN identity.
    candidates, final_collapsed = _dedupe_and_sort_candidates(candidates)
    collapsed_same_parent = preliminary_collapsed + final_collapsed
    # Public monthly-sales evidence is the primary ranking signal requested by
    # the operator. Similarity resolves ties; products without a signal follow.
    candidates = candidates[:limit]
    parent_count = len({item.parent_asin or item.asin for item in candidates})
    brand_count = len({item.brand.lower() for item in candidates if item.brand})
    return CompetitorDiscoverResult(
        target_asin=asin.upper() if asin else "NEW-PRODUCT",
        target_title=target["title"], target_image=target["image"],
        search_query=search_queries[0], search_queries=search_queries,
        category_rule=f"同一细分类目：{family_name}" if family_name else "未识别到稳定类目，需人工确认",
        target_features=target_features, excluded_own_asins=len(own_asins),
        excluded_same_brand=excluded_same_brand,
        collapsed_same_parent=collapsed_same_parent,
        collapsed_same_brand_size=collapsed_same_parent,
        competitor_parent_count=parent_count,
        competitor_brand_count=brand_count,
        candidates=candidates,
    )
