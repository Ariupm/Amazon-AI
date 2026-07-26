from __future__ import annotations

import asyncio
import math
import re
from io import BytesIO
from urllib.parse import quote_plus

import httpx
from PIL import Image
from playwright.async_api import BrowserContext

from .models import CompetitorCandidate, CompetitorDiscoverResult
from .scraper import MARKETPLACES, _challenge, _number, _rating, _snapshot, _text

STOPWORDS = {
    "a", "an", "and", "for", "from", "in", "of", "on", "the", "to", "with",
    "new", "pack", "inch", "inches", "amazon", "black", "white", "beige",
}


def _tokens(value: str) -> list[str]:
    return [
        token.lower() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9'+-]*", value)
        if len(token) > 1 and token.lower() not in STOPWORDS
    ]


def _query_from_title(title: str) -> str:
    tokens = _tokens(title)
    # Remove an apparent leading brand and keep the strongest early category/features.
    if len(tokens) > 5:
        tokens = tokens[1:]
    return " ".join(list(dict.fromkeys(tokens))[:9])


async def _fingerprint(client: httpx.AsyncClient, url: str | None) -> list[float] | None:
    if not url:
        return None
    try:
        response = await client.get(url, timeout=15)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content)).convert("RGB").resize((12, 12))
        values: list[float] = []
        for red, green, blue in image.getdata():
            values.extend((red / 255, green / 255, blue / 255))
        return values
    except Exception:
        return None


def _cosine(left: list[float] | None, right: list[float] | None) -> int | None:
    if not left or not right or len(left) != len(right):
        return None
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left) * sum(b * b for b in right))
    return round(max(0, min(1, dot / norm)) * 100) if norm else None


async def discover_competitors(
    context: BrowserContext,
    asin: str,
    marketplace: str,
    limit: int,
    headless: bool,
) -> CompetitorDiscoverResult:
    base_url, _ = MARKETPLACES[marketplace]
    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto(f"{base_url}/dp/{asin.upper()}", wait_until="domcontentloaded", timeout=60_000)
    await _challenge(page, headless, "本品页面")
    target = await _snapshot(page, base_url, asin.upper())
    query = _query_from_title(target["title"])
    await page.goto(f"{base_url}/s?k={quote_plus(query)}", wait_until="domcontentloaded", timeout=60_000)
    await _challenge(page, headless, "竞品搜索页面")
    await page.wait_for_timeout(1000)

    cards = page.locator("[data-component-type='s-search-result'][data-asin]")
    raw: list[dict] = []
    seen = {asin.upper()}
    for index in range(min(await cards.count(), limit * 3)):
        card = cards.nth(index)
        candidate_asin = (await card.get_attribute("data-asin") or "").upper()
        if not re.fullmatch(r"[A-Z0-9]{10}", candidate_asin) or candidate_asin in seen:
            continue
        title = await _text(card, ["h2 span", "h2 a span"])  # type: ignore[arg-type]
        if not title:
            continue
        seen.add(candidate_asin)
        image = None
        image_node = card.locator("img.s-image").first
        if await image_node.count():
            image = await image_node.get_attribute("src")
        sales = await _text(card, ["[aria-label*='bought in past month']", ".a-row.a-size-base"])  # type: ignore[arg-type]
        if sales and not re.search(r"bought.*month", sales, re.I):
            sales = None
        raw.append({
            "asin": candidate_asin,
            "title": title,
            "url": f"{base_url}/dp/{candidate_asin}",
            "image": image,
            "price": await _text(card, [".a-price .a-offscreen"]),  # type: ignore[arg-type]
            "rating_text": await _text(card, [".a-icon-alt"]),  # type: ignore[arg-type]
            "rating_count_text": await _text(card, ["[data-csa-c-slot-id='alf-reviews'] span", ".s-underline-text"]),  # type: ignore[arg-type]
            "sales": sales,
        })
        if len(raw) >= limit:
            break

    target_tokens = set(_tokens(target["title"]))
    async with httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True) as client:
        target_fp = await _fingerprint(client, target["image"])
        candidate_fps = await asyncio.gather(*[_fingerprint(client, item["image"]) for item in raw])

    candidates: list[CompetitorCandidate] = []
    for item, fingerprint in zip(raw, candidate_fps):
        other_tokens = set(_tokens(item["title"]))
        union = target_tokens | other_tokens
        text_similarity = round(len(target_tokens & other_tokens) / len(union) * 100) if union else 0
        image_similarity = _cosine(target_fp, fingerprint)
        overall = round(text_similarity * 0.7 + (image_similarity or text_similarity) * 0.3)
        candidates.append(CompetitorCandidate(
            asin=item["asin"], title=item["title"], url=item["url"], image=item["image"],
            price=item["price"], rating=_rating(item["rating_text"]),
            rating_count=_number(item["rating_count_text"]),
            recent_sales_signal=item["sales"], text_similarity=text_similarity,
            image_similarity=image_similarity, overall_similarity=overall,
        ))
    candidates.sort(key=lambda item: (-item.overall_similarity, item.asin))
    return CompetitorDiscoverResult(
        target_asin=asin.upper(), target_title=target["title"],
        target_image=target["image"], search_query=query, candidates=candidates,
    )
