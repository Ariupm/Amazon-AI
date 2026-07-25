from __future__ import annotations

import asyncio
import json
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


async def _auth_pending(page: Page) -> bool:
    """Return True for every known step in Amazon's sign-in/MFA flow."""
    if page.is_closed():
        return False
    url = page.url.lower()
    auth_selectors = (
        "#ap_email, #ap_password, #auth-mfa-otpcode, #cvf-input-code, "
        "input[name='otpCode'], input[name='code'], "
        "input[autocomplete='one-time-code'], form[name='signIn']"
    )
    if "/ap/" in url or "/ax/" in url or await page.locator(auth_selectors).count() > 0:
        return True
    body = (await page.locator("body").inner_text()).lower()
    code_prompts = (
        "enter the code",
        "enter code",
        "verification code",
        "one-time password",
        "one time password",
        "approve the notification",
    )
    title = (await page.title()).lower()
    return ("verify" in title or "authentication" in title) and any(prompt in body for prompt in code_prompts)


async def _challenge(page: Page, headless: bool, purpose: str = "商品页面") -> None:
    title = (await page.title()).lower()
    body = (await page.locator("body").inner_text()).lower()
    challenged = "robot check" in title or "enter the characters you see below" in body or "sorry, we just need to make sure" in body
    auth_pending = await _auth_pending(page)
    if not challenged and not auth_pending:
        return
    if headless:
        raise ScrapeError(f"Amazon 的{purpose}要求验证码或登录，请使用可见浏览器模式并手动完成。")
    print(f"Amazon 的{purpose}要求验证码/登录。Chrome 会保持打开，登录完成后程序才会继续。")
    while True:
        await asyncio.sleep(2)
        if page.is_closed():
            raise ScrapeError("等待登录期间浏览器页面被关闭，任务已停止。")
        title = (await page.title()).lower()
        body = (await page.locator("body").inner_text()).lower()
        auth_pending = await _auth_pending(page)
        if "robot check" not in title and "enter the characters you see below" not in body and not auth_pending:
            # Authentication pages can briefly disappear between the password
            # and OTP redirects. Require a short stable non-authenticated period.
            await asyncio.sleep(2)
            if await _auth_pending(page):
                continue
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(1000)
            return


async def _extract_variants(page: Page, base_url: str) -> list[Variant]:
    variants: dict[str, Variant] = {}
    # Never query [data-csa-c-asin] globally: Amazon uses it for carousels,
    # recommendations and sponsored products across the entire page.
    nodes = page.locator(
        "#twister li[data-asin], "
        "#twister_feature_div li[data-asin], "
        "#twister_feature_div [data-csa-c-asin], "
        "#variation_color_name li[data-asin], "
        "#variation_size_name li[data-asin]"
    )
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
    # Amazon frequently embeds this exact child map when not every option is rendered.
    html = await page.content()
    dimension_names: list[str] = []
    values_match = re.search(r'"variationValues"\s*:\s*(\{.*?\})\s*,\s*"', html)
    if values_match:
        try:
            raw_dimensions = json.loads(values_match.group(1))
            dimension_names = [
                name.replace("_name", "").replace("_", " ").title()
                for name in raw_dimensions.keys()
            ]
        except json.JSONDecodeError:
            pass

    match = re.search(r'"dimensionValuesDisplayData"\s*:\s*(\{.*?\})\s*,\s*"', html)
    if match:
        try:
            for asin, values in json.loads(match.group(1)).items():
                if not re.fullmatch(r"[A-Z0-9]{10}", asin):
                    continue
                attributes = {
                    (dimension_names[index] if index < len(dimension_names) else f"Option {index + 1}"): str(value)
                    for index, value in enumerate(values)
                }
                attributes["option"] = " / ".join(str(value) for value in values)
                if asin in variants:
                    # The DOM often exposes only the currently rendered dimension.
                    # Embedded data contains the complete size/color combination.
                    variants[asin].attributes.update(attributes)
                    variants[asin].color = attributes.get("Color")
                    variants[asin].size = attributes.get("Size")
                else:
                    variants[asin] = Variant(
                        asin=asin,
                        attributes=attributes,
                        color=attributes.get("Color"),
                        size=attributes.get("Size"),
                        url=f"{base_url}/dp/{asin}",
                    )
        except json.JSONDecodeError:
            pass
    return list(variants.values())


async def _image_urls(page: Page) -> list[str]:
    images: list[str] = []
    for node in await page.locator("#landingImage, #imgTagWrapperId img, #altImages img").all():
        candidates = [
            await node.get_attribute("data-old-hires"),
            await node.get_attribute("data-a-hires"),
            await node.get_attribute("src"),
        ]
        dynamic = await node.get_attribute("data-a-dynamic-image")
        if dynamic:
            try:
                candidates = list(json.loads(dynamic).keys()) + candidates
            except json.JSONDecodeError:
                pass
        for src in candidates:
            if not src or "sprite" in src or "play-button" in src:
                continue
            src = re.sub(r"\._[^.]+_\.", ".", src)
            if src not in images:
                images.append(src)
    return images


async def _variation_attributes(page: Page) -> tuple[str | None, str | None, dict[str, str]]:
    attributes: dict[str, str] = {}
    for feature in ["color_name", "size_name", "style_name", "pattern_name", "item_package_quantity"]:
        value = await _text(page, [
            f"#variation_{feature} .selection",
            f"#variation_{feature} .a-dropdown-prompt",
        ])
        if value:
            attributes[feature.replace("_name", "").replace("_", " ").title()] = value
    color = attributes.get("Color")
    size = attributes.get("Size")
    # Some layouts expose selected attributes only in the product details table.
    if not color or not size:
        rows = page.locator("#productDetails_detailBullets_sections1 tr, #productDetails_techSpec_section_1 tr")
        for index in range(await rows.count()):
            row = rows.nth(index)
            key = re.sub(r"\s+", " ", (await row.locator("th").inner_text())).strip() if await row.locator("th").count() else ""
            value = re.sub(r"\s+", " ", (await row.locator("td").inner_text())).strip() if await row.locator("td").count() else ""
            if key and value:
                if not color and "color" in key.lower():
                    color = value
                    attributes["Color"] = value
                if not size and ("size" in key.lower() or "dimension" in key.lower()):
                    size = value
                    attributes["Size"] = value
    return color, size, attributes


async def _parent_asin(page: Page) -> str | None:
    if await page.locator("input[name='parentASIN']").count():
        value = await page.locator("input[name='parentASIN']").first.get_attribute("value")
        if value and re.fullmatch(r"[A-Z0-9]{10}", value):
            return value
    html = await page.content()
    for pattern in [r'"parentAsin"\s*:\s*"([A-Z0-9]{10})"', r'"parentASIN"\s*:\s*"([A-Z0-9]{10})"']:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    return None


async def _snapshot(page: Page, base_url: str, asin: str) -> dict:
    title = await _text(page, ["#productTitle", "#title"])
    if not title:
        raise ScrapeError(f"未识别到子体 {asin} 的商品标题。")
    asin_nodes = page.locator("form#addToCart input#ASIN, #buybox input#ASIN, input#ASIN")
    actual_asin = await asin_nodes.first.get_attribute("value") if await asin_nodes.count() else asin
    actual_asin = actual_asin or asin
    price = await _text(page, [".priceToPay .a-offscreen", "#corePrice_feature_div .a-offscreen", "#priceblock_ourprice", "#price_inside_buybox"])
    list_price = await _text(page, [
        "#corePriceDisplay_desktop_feature_div .basisPrice .a-offscreen",
        "#corePrice_feature_div .a-price.a-text-price .a-offscreen",
        ".a-price[data-a-strike='true'] .a-offscreen",
        ".basisPrice .a-offscreen",
    ])
    if not list_price:
        typical = page.get_by_text(re.compile(r"Typical price:", re.I)).first
        if await typical.count():
            container = typical.locator("xpath=..")
            list_price = await _text(container, [".a-offscreen"])  # type: ignore[arg-type]
    color, size, attributes = await _variation_attributes(page)
    sales = await _text(page, ["#social-proofing-faceout-title-tk_bought", "#social-proofing-faceout-title"])
    if not sales:
        sales_node = page.get_by_text(re.compile(r"(bought|purchased).*(past|last) month", re.I)).first
        if await sales_node.count():
            sales = re.sub(r"\s+", " ", (await sales_node.inner_text())).strip()
    images = await _image_urls(page)
    rating_text = await _text(page, ["#acrPopover", "[data-hook='rating-out-of-text']"])
    rating_count_text = await _text(page, ["#acrCustomerReviewText"])
    availability = await _text(page, ["#availability", "#outOfStock"])
    return {
        "asin": actual_asin, "title": title, "price": price, "list_price": list_price,
        "discount": await _text(page, [".savingsPercentage", "#regularprice_savings"]),
        "promotion": await _text(page, ["#couponTextpctch", "#promoPriceBlockMessage_feature_div", "#dealBadge_feature_div"]),
        "availability": availability, "rating": _rating(rating_text),
        "rating_count": _number(rating_count_text), "recent_sales_signal": sales,
        "image": images[0] if images else None, "images": images,
        "bullets": await _texts(page, "#feature-bullets li span.a-list-item"),
        "color": color, "size": size, "attributes": attributes,
        "url": f"{base_url}/dp/{actual_asin}",
    }


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
    login_attempted = False
    try:
        for number in range(1, pages + 1):
            review_url = f"{base_url}/product-reviews/{asin}/?sortBy=recent&pageNumber={number}"
            await page.goto(review_url, wait_until="domcontentloaded", timeout=60_000)
            await _challenge(page, headless, "评论页面")
            await page.wait_for_timeout(900)
            page_reviews = await _reviews_on_page(page)
            # Amazon often returns an empty review shell to signed-out users instead
            # of redirecting to /ap/signin. In visible mode, open login and wait.
            account_text = await _text(page, ["#nav-link-accountList-nav-line-1"])
            signed_out = bool(account_text and "sign in" in account_text.lower())
            if not page_reviews and signed_out and not headless and not login_attempted:
                login_attempted = True
                await page.locator("#nav-link-accountList").click()
                await page.wait_for_load_state("domcontentloaded")
                await _challenge(page, headless, "Amazon 登录")
                await page.goto(review_url, wait_until="domcontentloaded", timeout=60_000)
                await _challenge(page, headless, "评论页面")
                await page.wait_for_timeout(1000)
                page_reviews = await _reviews_on_page(page)
            for review in page_reviews:
                collected[f"{review.title}|{review.body}"] = review
            if not await page.locator("li.a-last:not(.a-disabled) a").count():
                break
            await page.wait_for_timeout(700)
    finally:
        await page.close()
    return list(collected.values())


class BrowserSession:
    """One Chrome process shared by every ASIN in a batch."""

    def __init__(self, marketplace: str, headless: bool):
        self.marketplace = marketplace
        self.headless = headless
        self.playwright = None
        self.context: BrowserContext | None = None

    async def __aenter__(self) -> "BrowserSession":
        _, locale = MARKETPLACES[self.marketplace]
        chrome = next((path for path in CHROME_PATHS if path.exists()), None)
        if not chrome:
            raise ScrapeError("未找到 Google Chrome。")
        profile = Path(__file__).parent / ".chrome-profile"
        profile.mkdir(exist_ok=True)
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            executable_path=str(chrome),
            headless=self.headless,
            locale=locale,
            viewport={"width": 1440, "height": 1000},
            args=["--disable-blink-features=AutomationControlled"],
        )
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()


async def _scrape_in_context(
    context: BrowserContext,
    asin: str,
    marketplace: str,
    max_review_pages: int,
    headless: bool,
    variant_mode: str,
) -> ProductResult:
    asin = asin.upper()
    if not re.fullmatch(r"[A-Z0-9]{10}", asin):
        raise ScrapeError("ASIN 必须是 10 位字母或数字。")
    base_url, _ = MARKETPLACES[marketplace]
    page = context.pages[0] if context.pages else await context.new_page()
    source_url = f"{base_url}/dp/{asin}"
    warnings: list[str] = []

    await page.goto(source_url, wait_until="domcontentloaded", timeout=60_000)
    await _challenge(page, headless)
    await page.wait_for_timeout(1100)
    initial = await _snapshot(page, base_url, asin)
    parent_asin = await _parent_asin(page)
    is_parent_request = parent_asin == asin
    canonical_node = page.locator("link[rel='canonical']").first
    canonical = await canonical_node.get_attribute("href") if await canonical_node.count() else None
    brand = await _text(page, ["#bylineInfo"])
    if brand:
        brand = re.sub(r"^(Visit the |Brand:\s*)| Store$", "", brand, flags=re.I)

    child_snapshots: list[dict] = []
    fast_variants: list[Variant] | None = None
    expected_child_count = 1
    if is_parent_request:
        candidates = await _extract_variants(page, base_url)
        candidates.sort(key=lambda variant: (
            (variant.size or variant.attributes.get("Size") or "").casefold(),
            (variant.color or variant.attributes.get("Color") or "").casefold(),
            variant.attributes.get("option", "").casefold(),
            variant.asin,
        ))
        child_asins = list(dict.fromkeys(v.asin for v in candidates))
        expected_child_count = len(child_asins)
        if not child_asins:
            warnings.append("识别为父体，但页面未暴露可访问的子体 ASIN。")
        if variant_mode == "fast":
            fast_variants = []
            for candidate in candidates:
                if candidate.asin == initial["asin"]:
                    for key in (
                        "title", "price", "list_price", "discount", "promotion",
                        "availability", "rating", "rating_count",
                        "recent_sales_signal", "image", "images", "bullets",
                    ):
                        setattr(candidate, key, initial[key])
                candidate.data_quality = "partial"
                fast_variants.append(candidate)
            child_snapshots = [initial]
            warnings.append(
                f"已使用极速清单模式读取 {len(fast_variants)} 个子体；"
                "未逐页打开的子体不会编造价格、月销量或高清主图。"
            )
        else:
            collected_actual_asins: set[str] = set()
            for child_asin in child_asins:
                try:
                    await page.goto(
                        f"{base_url}/dp/{child_asin}?th=1&psc=1",
                        wait_until="domcontentloaded", timeout=60_000,
                    )
                    await _challenge(page, headless, f"子体 {child_asin}")
                    await page.wait_for_timeout(750)
                    snapshot = await _snapshot(page, base_url, child_asin)
                    actual_child_asin = snapshot["asin"]
                    if actual_child_asin in collected_actual_asins:
                        warnings.append(
                            f"子体 {child_asin} 被 Amazon 重定向到已采集的 "
                            f"{actual_child_asin}，已跳过重复页面。"
                        )
                        continue
                    if actual_child_asin != child_asin:
                        warnings.append(
                            f"请求子体 {child_asin} 时 Amazon 实际返回 "
                            f"{actual_child_asin}，结果按实际页面记录。"
                        )
                    collected_actual_asins.add(actual_child_asin)
                    child_snapshots.append(snapshot)
                except Exception as error:
                    warnings.append(f"子体 {child_asin} 采集失败：{error}")
    else:
        child_snapshots = [initial]

    variants = fast_variants or [
        Variant(
            asin=item["asin"], attributes=item["attributes"], color=item["color"],
            size=item["size"], title=item["title"], price=item["price"],
            list_price=item["list_price"], discount=item["discount"],
            promotion=item["promotion"], availability=item["availability"],
            rating=item["rating"], rating_count=item["rating_count"],
            recent_sales_signal=item["recent_sales_signal"], image=item["image"],
            images=item["images"], bullets=item["bullets"], url=item["url"],
            data_quality="complete" if item["title"] and item["image"] and (item["price"] or item["availability"]) else "partial",
            warnings=[],
        )
        for item in child_snapshots
    ]
    root = child_snapshots[0] if child_snapshots else initial
    reviews = await _collect_reviews(context, base_url, root["asin"], max_review_pages, headless)
    if not reviews:
        warnings.append("登录后仍未读取到评论；该商品可能暂无可访问评论，或 Amazon 当前限制了评论页。")
    return ProductResult(
        requested_asin=asin, asin=asin if is_parent_request else root["asin"],
        parent_asin=parent_asin, is_parent_request=is_parent_request,
        marketplace=marketplace, source_url=source_url, canonical_url=canonical,
        title=root["title"], brand=brand, price=root["price"], list_price=root["list_price"],
        discount=root["discount"], promotion=root["promotion"], availability=root["availability"],
        rating=root["rating"], rating_count=root["rating_count"],
        recent_sales_signal=root["recent_sales_signal"], images=root["images"], bullets=root["bullets"],
        variants=variants, reviews=reviews, insights=analyze_reviews(reviews),
        collected_at=datetime.now(timezone.utc),
        data_quality="complete" if variants and all(v.data_quality == "complete" for v in variants) else "partial",
        warnings=warnings, expected_child_count=expected_child_count,
    )


async def scrape_product(
    asin: str,
    marketplace: str = "US",
    max_review_pages: int = 2,
    headless: bool = False,
    variant_mode: str = "full",
    context: BrowserContext | None = None,
) -> ProductResult:
    if context is not None:
        return await _scrape_in_context(
            context, asin, marketplace, max_review_pages, headless, variant_mode
        )
    async with BrowserSession(marketplace, headless) as session:
        assert session.context is not None
        return await _scrape_in_context(
            session.context, asin, marketplace, max_review_pages, headless, variant_mode
        )
