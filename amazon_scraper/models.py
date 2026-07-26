from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Variant(BaseModel):
    asin: str
    attributes: dict[str, str] = Field(default_factory=dict)
    color: str | None = None
    size: str | None = None
    title: str | None = None
    price: str | None = None
    list_price: str | None = None
    discount: str | None = None
    promotion: str | None = None
    availability: str | None = None
    rating: float | None = None
    rating_count: int | None = None
    recent_sales_signal: str | None = None
    monthly_sales_estimate: int | None = None
    is_suspected_main: bool = False
    main_score: float = 0
    main_reason: str | None = None
    image: str | None = None
    images: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    url: str
    data_quality: Literal["complete", "partial"] = "partial"
    warnings: list[str] = Field(default_factory=list)


class Review(BaseModel):
    rating: float | None = None
    title: str | None = None
    body: str
    date: str | None = None
    verified: bool = False
    variant: str | None = None
    url: str | None = None


class Insight(BaseModel):
    phrase: str
    mentions: int
    evidence: list[str] = Field(default_factory=list)


class ReviewInsights(BaseModel):
    advantages: list[Insight] = Field(default_factory=list)
    pains: list[Insight] = Field(default_factory=list)
    analyzed_reviews: int = 0


class ProductResult(BaseModel):
    requested_asin: str
    asin: str
    parent_asin: str | None = None
    is_parent_request: bool = False
    marketplace: str
    source_url: str
    canonical_url: str | None = None
    title: str
    brand: str | None = None
    price: str | None = None
    list_price: str | None = None
    discount: str | None = None
    promotion: str | None = None
    availability: str | None = None
    rating: float | None = None
    rating_count: int | None = None
    recent_sales_signal: str | None = None
    images: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    variants: list[Variant] = Field(default_factory=list)
    reviews: list[Review] = Field(default_factory=list)
    insights: ReviewInsights = Field(default_factory=ReviewInsights)
    collected_at: datetime
    data_quality: Literal["complete", "partial"]
    warnings: list[str] = Field(default_factory=list)
    expected_child_count: int | None = None
    suspected_main_asin: str | None = None
    suspected_main_confidence: Literal["high", "medium", "low"] | None = None
    suspected_main_reason: str | None = None


class ScrapeRequest(BaseModel):
    asin: str = Field(pattern=r"^[A-Za-z0-9]{10}$")
    marketplace: Literal["US", "UK", "DE", "JP"] = "US"
    max_review_pages: int = Field(default=2, ge=0, le=10)
    headless: bool = False
    variant_mode: Literal["fast", "full"] = "full"


class BatchScrapeRequest(BaseModel):
    asins: list[str] = Field(min_length=1, max_length=100)
    marketplace: Literal["US", "UK", "DE", "JP"] = "US"
    max_review_pages: int = Field(default=2, ge=0, le=10)
    headless: bool = False
    variant_mode: Literal["fast", "full"] = "full"


class BatchItemResult(BaseModel):
    requested_asin: str
    success: bool
    result: ProductResult | None = None
    error: str | None = None


class BatchResult(BaseModel):
    items: list[BatchItemResult]
    total: int
    succeeded: int
    failed: int


class CompetitorDiscoverRequest(BaseModel):
    asin: str = Field(pattern=r"^[A-Za-z0-9]{10}$")
    marketplace: Literal["US", "UK", "DE", "JP"] = "US"
    limit: int = Field(default=12, ge=3, le=24)
    headless: bool = False
    category: str | None = None
    material: str | None = None
    style: str | None = None
    use_case: str | None = None
    features: list[str] = Field(default_factory=list)


class CompetitorCandidate(BaseModel):
    asin: str
    title: str
    url: str
    image: str | None = None
    price: str | None = None
    rating: float | None = None
    rating_count: int | None = None
    recent_sales_signal: str | None = None
    text_similarity: int
    image_similarity: int | None = None
    attribute_similarity: int = 0
    market_similarity: int = 0
    category_match: bool = False
    auto_selected: bool = False
    match_reasons: list[str] = Field(default_factory=list)
    overall_similarity: int
    source: Literal["amazon_search"] = "amazon_search"


class CompetitorDiscoverResult(BaseModel):
    target_asin: str
    target_title: str
    target_image: str | None = None
    search_query: str
    search_queries: list[str] = Field(default_factory=list)
    category_rule: str | None = None
    candidates: list[CompetitorCandidate] = Field(default_factory=list)
