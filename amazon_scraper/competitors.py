from __future__ import annotations

import asyncio
import math
import re
from io import BytesIO
from urllib.parse import quote_plus

import httpx
from PIL import Image, ImageChops, ImageFilter, ImageStat
from playwright.async_api import BrowserContext

from .models import CompetitorCandidate, CompetitorDiscoverResult
from .scraper import MARKETPLACES, _challenge, _number, _rating, _snapshot, _text

STOPWORDS = {
    "a", "an", "and", "for", "from", "in", "of", "on", "the", "to", "with",
    "new", "pack", "inch", "inches", "amazon", "black", "white", "beige",
    "brown", "blue", "green", "grey", "gray", "red", "large", "small",
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
ATTRIBUTE_GROUPS = {
    "可水洗": {"washable", "machine washable", "easy clean", "easy to clean"},
    "防滑": {"non slip", "non-slip", "nonslip", "anti slip"},
    "高低绒": {"high low", "high-low", "textured", "tufted"},
    "低绒": {"low pile", "thin"},
    "柔软": {"soft", "fluffy", "plush", "cozy"},
    "材质": {"polyester", "cotton", "wool", "jute", "nylon", "microfiber"},
    "风格": {"modern", "abstract", "boho", "vintage", "geometric", "minimalist"},
}


def _tokens(value: str) -> list[str]:
    return [
        token.lower() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9'+-]*", value)
        if len(token) > 1 and token.lower() not in STOPWORDS
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


def _queries(title: str, category: str | None, material: str | None, style: str | None,
             use_case: str | None, features: list[str]) -> list[str]:
    family_name, family_words = _family(f"{category or ''} {title}")
    category_seed = _unique_words(category, " ".join(sorted(family_words)[:2])) if family_name else _unique_words(category, title, limit=3)
    feature_text = " ".join(features)
    queries = [
        _unique_words(category_seed, feature_text, limit=7),
        _unique_words(category_seed, material, style, limit=7),
        _unique_words(category_seed, use_case, feature_text, limit=7),
        _unique_words(title, limit=8),
    ]
    return [query for query in dict.fromkeys(queries) if query]


async def _visual_fingerprint(client: httpx.AsyncClient, url: str | None) -> list[float] | None:
    if not url:
        return None
    try:
        response = await client.get(url, timeout=15)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content)).convert("RGB")
        # Remove near-white marketplace background before comparing shape, texture and color.
        background = Image.new("RGB", image.size, (255, 255, 255))
        difference = ImageChops.difference(image, background).convert("L")
        mask = difference.point(lambda value: 255 if value > 18 else 0)
        box = mask.getbbox()
        if box:
            image = image.crop(box)
        image = image.resize((20, 20))
        gray = image.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        mean = ImageStat.Stat(gray).mean[0]
        values = [(pixel - mean) / 255 for pixel in gray.getdata()]
        values.extend(pixel / 255 for pixel in edges.getdata())
        # Compact color histogram adds palette similarity without letting white dominate.
        for channel in image.split():
            histogram = channel.histogram()
            values.extend(sum(histogram[index:index + 32]) / 400 for index in range(0, 256, 32))
        return values
    except Exception:
        return None


def _cosine(left: list[float] | None, right: list[float] | None) -> int | None:
    if not left or not right or len(left) != len(right):
        return None
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left) * sum(b * b for b in right))
    return round(max(0, min(1, (dot / norm + 1) / 2)) * 100) if norm else None


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


async def discover_competitors(
    context: BrowserContext, asin: str, marketplace: str, limit: int, headless: bool,
    category: str | None = None, material: str | None = None, style: str | None = None,
    use_case: str | None = None, features: list[str] | None = None,
) -> CompetitorDiscoverResult:
    features = features or []
    base_url, _ = MARKETPLACES[marketplace]
    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto(f"{base_url}/dp/{asin.upper()}", wait_until="domcontentloaded", timeout=60_000)
    await _challenge(page, headless, "本品页面")
    target = await _snapshot(page, base_url, asin.upper())
    search_queries = _queries(target["title"], category, material, style, use_case, features)
    family_name, family_words = _family(f"{category or ''} {target['title']}")

    raw_by_asin: dict[str, dict] = {}
    for query in search_queries:
        await page.goto(f"{base_url}/s?k={quote_plus(query)}", wait_until="domcontentloaded", timeout=60_000)
        await _challenge(page, headless, "竞品搜索页面")
        await page.wait_for_timeout(600)
        cards = page.locator("[data-component-type='s-search-result'][data-asin]")
        for index in range(min(await cards.count(), max(12, limit))):
            card = cards.nth(index)
            candidate_asin = (await card.get_attribute("data-asin") or "").upper()
            if not re.fullmatch(r"[A-Z0-9]{10}", candidate_asin) or candidate_asin == asin.upper():
                continue
            title = await _text(card, ["h2 span", "h2 a span"])  # type: ignore[arg-type]
            if not title:
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
                "sales": sales, "queries": [],
            })
            item["queries"].append(query)

    target_text = " ".join([target["title"], category or "", material or "", style or "", use_case or "", *features])
    target_tokens, target_attrs = set(_tokens(target_text)), _phrases(target_text)
    eligible = []
    for item in raw_by_asin.values():
        candidate_family, _ = _family(item["title"])
        if family_name and candidate_family != family_name:
            continue
        eligible.append(item)
    eligible = eligible[: max(limit * 3, 24)]

    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True) as client:
        target_fp = await _visual_fingerprint(client, target["image"])
        fingerprints = await asyncio.gather(*[_visual_fingerprint(client, item["image"]) for item in eligible])

    candidates: list[CompetitorCandidate] = []
    target_price = _price(target.get("price"))
    for item, fingerprint in zip(eligible, fingerprints):
        other_tokens = set(_tokens(item["title"]))
        union = target_tokens | other_tokens
        text_score = round(len(target_tokens & other_tokens) / len(union) * 100) if union else 0
        other_attrs = _phrases(item["title"])
        attr_union = target_attrs | other_attrs
        attr_score = round(len(target_attrs & other_attrs) / len(attr_union) * 100) if attr_union else text_score
        image_score = _cosine(target_fp, fingerprint)
        rating_count = _number(item["rating_count_text"])
        market_score = _market_score(target_price, _price(item["price"]), rating_count, item["sales"])
        overall = round((image_score or 50) * .30 + attr_score * .30 + text_score * .25 + market_score * .15)
        reasons = []
        if family_name:
            reasons.append(f"同类目：{family_name}")
        shared_attrs = sorted(target_attrs & other_attrs)
        if shared_attrs:
            reasons.append("共同属性：" + "、".join(shared_attrs))
        if image_score is not None:
            reasons.append(f"去白底视觉 {image_score}%")
        reasons.append(f"命中 {len(item['queries'])} 组搜索")
        candidates.append(CompetitorCandidate(
            asin=item["asin"], title=item["title"], url=item["url"], image=item["image"],
            price=item["price"], rating=_rating(item["rating_text"]), rating_count=rating_count,
            recent_sales_signal=item["sales"], text_similarity=text_score,
            image_similarity=image_score, attribute_similarity=attr_score,
            market_similarity=market_score, category_match=True,
            auto_selected=overall >= 60, match_reasons=reasons,
            overall_similarity=overall,
        ))
    candidates.sort(key=lambda item: (-item.overall_similarity, item.asin))
    candidates = candidates[:limit]
    return CompetitorDiscoverResult(
        target_asin=asin.upper(), target_title=target["title"], target_image=target["image"],
        search_query=search_queries[0], search_queries=search_queries,
        category_rule=f"同一细分类目：{family_name}" if family_name else "未识别到稳定类目，需人工确认",
        candidates=candidates,
    )
