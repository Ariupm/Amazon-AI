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
    asin: str | None = Field(default=None, pattern=r"^[A-Za-z0-9]{10}$")
    target_name: str | None = Field(default=None, max_length=160)
    reference_image_data: str | None = Field(default=None, max_length=12_000_000)
    marketplace: Literal["US", "UK", "DE", "JP"] = "US"
    limit: int = Field(default=24, ge=6, le=100)
    search_pages: int = Field(default=1, ge=1, le=3)
    verify_detail_pages: bool = False
    headless: bool = False
    category: str | None = None
    material: str | None = None
    style: str | None = None
    use_case: str | None = None
    brand: str | None = None
    features: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list, max_length=6)
    search_query_weights: dict[str, int] = Field(default_factory=dict)
    product_type: str | None = Field(default=None, max_length=120)
    direct_competitor_definition: str | None = Field(default=None, max_length=500)
    excluded_terms: list[str] = Field(default_factory=list, max_length=30)
    exclude_asins: list[str] = Field(default_factory=list, max_length=1000)
    reference_titles: list[str] = Field(default_factory=list, max_length=100)
    reference_bullets: list[str] = Field(default_factory=list, max_length=100)


class CompetitorPlanRequest(BaseModel):
    target_name: str | None = Field(default=None, max_length=160)
    category: str | None = None
    material: str | None = None
    style: str | None = None
    use_case: str | None = None
    features: list[str] = Field(default_factory=list, max_length=30)
    reference_titles: list[str] = Field(default_factory=list, max_length=100)
    reference_bullets: list[str] = Field(default_factory=list, max_length=100)


class CompetitorPlanResult(BaseModel):
    product_type: str
    direct_competitor_definition: str
    target_features: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    excluded_terms: list[str] = Field(default_factory=list)
    guidance: list[str] = Field(default_factory=list)


class CompetitorCandidate(BaseModel):
    asin: str
    parent_asin: str | None = None
    brand: str | None = None
    size: str | None = None
    title: str
    url: str
    image: str | None = None
    price: str | None = None
    rating: float | None = None
    rating_count: int | None = None
    recent_sales_signal: str | None = None
    monthly_sales_estimate: int | None = None
    text_similarity: int
    image_similarity: int | None = None
    visual_images_compared: int = 0
    visual_reason: str | None = None
    attribute_similarity: int = 0
    market_similarity: int = 0
    market_value: int = 0
    product_type_similarity: int = 0
    search_weight_score: int = 0
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
    target_features: list[str] = Field(default_factory=list)
    excluded_own_asins: int = 0
    excluded_same_brand: int = 0
    collapsed_same_parent: int = 0
    collapsed_same_brand_size: int = 0
    competitor_parent_count: int = 0
    competitor_brand_count: int = 0
    search_card_count: int = 0
    unique_search_asins: int = 0
    excluded_own_results: int = 0
    excluded_by_terms: int = 0
    excluded_by_product_type: int = 0
    weighted_pool_count: int = 0
    candidates: list[CompetitorCandidate] = Field(default_factory=list)


class CompetitorExportItem(BaseModel):
    selected: bool = False
    asin: str
    parent_asin: str | None = None
    brand: str | None = None
    size: str | None = None
    title: str
    url: str
    image: str | None = None
    price: str | None = None
    rating: float | None = None
    rating_count: int | None = None
    recent_sales_signal: str | None = None
    monthly_sales_estimate: int | None = None
    overall_similarity: int | None = None
    text_similarity: int | None = None
    attribute_similarity: int | None = None
    image_similarity: int | None = None
    visual_images_compared: int = 0
    visual_reason: str | None = None
    market_similarity: int | None = None
    market_value: int | None = None
    product_type_similarity: int | None = None
    search_weight_score: int | None = None
    match_reasons: list[str] = Field(default_factory=list)


class CompetitorExportRequest(BaseModel):
    target_asin: str | None = None
    items: list[CompetitorExportItem] = Field(min_length=1, max_length=200)


class KeywordFileSummary(BaseModel):
    filename: str
    sheet: str
    valid: bool
    rows: int = 0
    keyword_column: str | None = None
    volume_columns: list[str] = Field(default_factory=list)
    month_columns: list[str] = Field(default_factory=list)
    preview: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    keywords: list["KeywordEntry"] = Field(default_factory=list)


class KeywordEntry(BaseModel):
    term: str
    volume: float | None = None
    month: str | None = None
    rank: int | None = None
    source: str = "aba"


class TitleKeywordSelection(BaseModel):
    term: str
    placement: Literal["main", "highlight", "ads", "exclude"]
    enabled: bool = True


class TitleGenerateRequest(BaseModel):
    brand: str | None = None
    product_title: str
    bullets: list[str] = Field(default_factory=list, max_length=20)
    competitor_titles: list[str] = Field(default_factory=list, max_length=100)
    keywords: list[KeywordEntry] = Field(default_factory=list, max_length=10_000)
    keyword_selections: list[TitleKeywordSelection] = Field(default_factory=list, max_length=100)
    negative_terms: list[str] = Field(default_factory=list, max_length=10_000)
    category: str | None = None
    material: str | None = None
    style: str | None = None
    use_case: str | None = None
    must_have: list[str] = Field(default_factory=list, max_length=30)
    verified_improvements: list[str] = Field(default_factory=list, max_length=30)
    colors: list[str] = Field(default_factory=list, max_length=100)
    sizes: list[str] = Field(default_factory=list, max_length=100)
    title_format: Literal["classic", "split"] = "split"


class TitleCandidate(BaseModel):
    id: str
    color: str | None = None
    size: str | None = None
    main_title: str
    highlight_item: str | None = None
    full_title: str
    main_count: int
    highlight_count: int = 0
    full_count: int
    keywords_used: list[str] = Field(default_factory=list)
    strategy: Literal["traffic", "click", "balanced"] = "balanced"
    score: int = 0
    keyword_evidence: list[str] = Field(default_factory=list)
    unused_keywords: list[str] = Field(default_factory=list)
    ad_keywords: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TitleKeywordAnalysis(BaseModel):
    term: str
    volume: float | None = None
    month: str | None = None
    rank: int | None = None
    relevance: int = 0
    role: str
    reason: str
    cluster: str = ""
    recommended_placement: Literal["main", "highlight", "ads", "exclude"] = "ads"
    purchase_intent: int = 0
    click_value: int = 0
    total_score: int = 0


class SizeScenarioAnalysis(BaseModel):
    size: str | None = None
    product_type: str
    primary_scenes: list[str] = Field(default_factory=list)
    secondary_scenes: list[str] = Field(default_factory=list)
    reasoning: str


class CompetitorTitleAnalysis(BaseModel):
    sample_size: int = 0
    common_openings: list[str] = Field(default_factory=list)
    common_features: list[str] = Field(default_factory=list)
    recommended_structure: str
    consumer_note: str


class CompetitorTermAnalysis(BaseModel):
    term: str
    document_frequency: int
    weighted_frequency: int
    coverage_percent: int
    matched_facts: list[str] = Field(default_factory=list)
    recommended_placement: Literal["main", "highlight", "reference"] = "reference"


class TitleGenerateResult(BaseModel):
    candidates: list[TitleCandidate]
    traffic_keywords: list[KeywordEntry] = Field(default_factory=list)
    keyword_analysis: list[TitleKeywordAnalysis] = Field(default_factory=list)
    size_scenarios: list[SizeScenarioAnalysis] = Field(default_factory=list)
    competitor_analysis: CompetitorTitleAnalysis
    competitor_terms: list[CompetitorTermAnalysis] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)
