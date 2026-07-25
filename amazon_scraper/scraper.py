from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import BrowserContext, Page, async_playwright

from .analyzer import analyze_reviews
from .models import ProductResult, Review, Variant

MARKETPLACES = {
    "US": ("https://www.amazon.com", "en-US"),
    "UK": ("https://www.amazon.co.uk", "en-GB"),
    "DE": ("https://www.amazon.de", "de-DE"),
    "JP": ("https://www.amazon.co.jp", "ja-JP"),
}
CHROME_PATHS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]


class ScrapeError(RuntimeError):
    pass


async def _text(page: Page, selectors: list[str]) -> str | None:
    for selector in selectors:
        node = page.locator(selector).first
        if await node.count():
            text = re.sub(r"\s+", " ", (await node.inner_text())).strip()
            if text:
                return text
    return None


async def _texts(page: Page, selector: str) -> list[str]:
    result: list[str] = []
    for text in await page.locator(selector).all_inner_texts():
        cleaned = re.sub(r"\s+", " ", text).strip()
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _number(text: str | None) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


def _rating(text: str | None) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)", text or "")
    return float(match.group(1).replace(",", ".")) if match else None


async def _challenge(page: Page, headless: bool) -> None:
    title = (await page.title()).lower()
    body = (await page.locator("body").inner_text()).lower()
    challenged = "robot check" in title or "enter the characters you see below" in body or "sorry, we just need to make sure" in body
    if not challenged:
        return
    if headless:
        raise ScrapeError("Amazon 返回验证码，请改用可见浏览器模式并手动完成验证。")
    print("Amazon 要求验证码/登录，请在 Chrome 中完成；程序最多等待 5 分钟。")
    for _ in range(150):
        await asyncio.sleep(2)
        title = (await page.title()).lower()
        body = (await page.locator("body").inner_text()).lower()
        if "robot check" not in title and "enter the characters you see below" not in body:
            return
    raise ScrapeError("等待人工验证超时。")


async def _extract_variants(page: Page, base_url: str) -> list[Variant]:
    variants: dict[str, Variant] = {}
    nodes = page.locator("#twister li[data-asin], #twister_feature_div li[data-asin], [data-csa-c-asin]")
    for index in range(await nodes.count()):
        node = nodes.nth(index)
        asin = (await node.get_attribute("data-asin") or await node.get_attribute("data-csa-c-asin") or "").strip()
        if not re.fullmatch(r"[A-Z0-9]{10}", asin):
            continue
        label = (await node.get_attribute("title") or await node.get_attribute("aria-label") or "").strip()
        image_node = node.locator("img").first
        image = await image_node.get_attribute("src") if await image_node.count() else None
        variants[asin] = Variant(
            asin=asin,
            attributes={"option": re.sub(r"^Click to select ", "", label)} if label else {},
            image=image,
            url=f"{base_url}/dp/{asin}",
        )
    # Amazon frequently embeds variation maps in page JSON even when not all choices are rendered.
    html = await page.content()
    for match in re.finditer(r'"([A-Z0-9]{10})"\s*:\s*\[([^\]]*)\]', html):
        asin, values = match.groups()
        if asin not in variants:
            options = [part.strip(' "') for part in values.split(",") if part.strip(' "')]
            variants[asin] = Variant(
                asin=asin,
                attributes={"option": " / ".join(options)} if options else {},
                url=f"{base_url}/dp/{asin}",
            )
    return list(variants.values())


async def _reviews_on_page(page: Page) -> list[Review]:
    result: list[Review] = []
    cards = page.locator('[data-hook="review"]')
    for index in range(await cards.count()):
        card = cards.nth(index)
        body_node = card.locator('[data-hook="review-body"]').first
        if not await body_node.count():
            continue
        body = re.sub(r"\s+", " ", (await body_node.inner_text())).strip()
        if not body:
            continue

        async def card_text(selector: str) -> str | None:
            node = card.locator(selector).first
            return re.sub(r"\s+", " ", (await node.inner_text())).strip() if await node.count() else None

        title = await card_text('[data-hook="review-title"]')
        date = await card_text('[data-hook="review-date"]')
        variant = await card_text('[data-hook="format-strip"]')
        rating_text = await card_text('[data-hook="review-star-rating"], [data-hook="cmps-review-star-rating"]')
        link_node = card.locator('a[data-hook="review-title"]').first
        link = await link_node.get_attribute("href") if await link_node.count() else None
        result.append(Review(
            rating=_rating(rating_text),
            title=title,
            body=body,
            date=date,
            verified=await card.locator('[data-hook="avp-badge"]').count() > 0,
            variant=variant,
            url=urljoin(page.url, link) if link else None,
        ))
    return result


async def _collect_reviews(context: BrowserContext, base_url: str, asin: str, pages: int, headless: bool) -> list[Review]:
    if pages <= 0:
        return []
    page = await context.new_page()
    collected: dict[str, Review] = {}
    try:
        for number in range(1, pages + 1):
            await page.goto(f"{base_url}/product-reviews/{asin}/?sortBy=recent&pageNumber={number}", wait_until="domcontentloaded", timeout=60_000)
            await _challenge(page, headless)
            await page.wait_for_timeout(900)
            for review in await _reviews_on_page(page):
                collected[f"{review.title}|{review.body}"] = review
            if not await page.locator("li.a-last:not(.a-disabled) a").count():
                break
            await page.wait_for_timeout(700)
    finally:
        await page.close()
    return list(collected.values())


async def scrape_product(asin: str, marketplace: str = "US", max_review_pages: int = 2, headless: bool = False) -> ProductResult:
    asin = asin.upper()
    if not re.fullmatch(r"[A-Z0-9]{10}", asin):
        raise ScrapeError("ASIN 必须是 10 位字母或数字。")
    base_url, locale = MARKETPLACES[marketplace]
    chrome = next((path for path in CHROME_PATHS if path.exists()), None)
    if not chrome:
        raise ScrapeError("未找到 Google Chrome。")
    profile = Path(__file__).parent / ".chrome-profile"
    profile.mkdir(exist_ok=True)

    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            executable_path=str(chrome),
            headless=headless,
            locale=locale,
            viewport={"width": 1440, "height": 1000},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else await context.new_page()
        source_url = f"{base_url}/dp/{asin}"
        warnings: list[str] = []
        try:
            await page.goto(source_url, wait_until="domcontentloaded", timeout=60_000)
            await _challenge(page, headless)
            await page.wait_for_timeout(1100)
            title = await _text(page, ["#productTitle", "#title"])
            if not title:
                raise ScrapeError(f"未识别到商品 {asin}。请检查 ASIN、站点，或在 Chrome 中完成人工验证。")

            actual_asin = await page.locator("#ASIN").get_attribute("value") if await page.locator("#ASIN").count() else asin
            actual_asin = actual_asin or asin
            parent_asin = await page.locator("input[name='parentASIN']").get_attribute("value") if await page.locator("input[name='parentASIN']").count() else None
            canonical = await page.locator("link[rel='canonical']").get_attribute("href") if await page.locator("link[rel='canonical']").count() else None
            price = await _text(page, [".priceToPay .a-offscreen", "#corePrice_feature_div .a-offscreen", "#priceblock_ourprice", "#price_inside_buybox"])
            list_price = await _text(page, [".basisPrice .a-offscreen", ".a-price.a-text-price .a-offscreen"])
            discount = await _text(page, [".savingsPercentage", "#regularprice_savings"])
            promotion = await _text(page, ["#couponTextpctch", "#promoPriceBlockMessage_feature_div", "#dealBadge_feature_div"])
            availability = await _text(page, ["#availability", "#outOfStock"])
            rating_text = await _text(page, ["#acrPopover", "[data-hook='rating-out-of-text']"])
            rating_count_text = await _text(page, ["#acrCustomerReviewText"])
            recent_sales = await _text(page, ["#social-proofing-faceout-title-tk_bought", "#social-proofing-faceout-title"])
            brand = await _text(page, ["#bylineInfo"])
            if brand:
                brand = re.sub(r"^(Visit the |Brand:\s*)| Store$", "", brand, flags=re.I)

            images: list[str] = []
            for node in await page.locator("#altImages img, #landingImage").all():
                src = await node.get_attribute("data-old-hires") or await node.get_attribute("src")
                if src:
                    src = re.sub(r"\._[^.]+_\.", ".", src)
                    if src not in images:
                        images.append(src)
            bullets = await _texts(page, "#feature-bullets li span.a-list-item")
            variants = await _extract_variants(page, base_url)
            if not variants:
                variants = [Variant(asin=actual_asin, title=title, price=price, availability=availability, image=images[0] if images else None, url=f"{base_url}/dp/{actual_asin}")]
                warnings.append("未检测到父子变体，结果按单 ASIN 返回。")
            for variant in variants:
                if variant.asin == actual_asin:
                    variant.title, variant.price, variant.availability = title, price, availability
                    variant.image = variant.image or (images[0] if images else None)

            reviews = await _collect_reviews(context, base_url, actual_asin, max_review_pages, headless)
            if not reviews:
                warnings.append("未读取到评论；Amazon 可能要求登录，或该商品暂无可访问评论。")
            return ProductResult(
                requested_asin=asin, asin=actual_asin, parent_asin=parent_asin,
                marketplace=marketplace, source_url=source_url, canonical_url=canonical,
                title=title, brand=brand, price=price, list_price=list_price,
                discount=discount, promotion=promotion, availability=availability,
                rating=_rating(rating_text), rating_count=_number(rating_count_text),
                recent_sales_signal=recent_sales, images=images, bullets=bullets,
                variants=variants, reviews=reviews, insights=analyze_reviews(reviews),
                collected_at=datetime.now(timezone.utc),
                data_quality="complete" if price and images and bullets else "partial",
                warnings=warnings,
            )
        finally:
            await context.close()
