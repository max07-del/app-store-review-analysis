from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

CountryCode = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[a-zA-Z]{2}$"),
]


class CollectReviewsRequest(BaseModel):
    app: str = Field(
        min_length=1,
        description="Numeric App Store ID or an apps.apple.com URL",
        examples=["https://apps.apple.com/us/app/instagram/id389801252"],
    )
    country: CountryCode = Field(default="us", description="Two-letter App Store storefront")
    count: int = Field(default=100, ge=1, le=100)
    seed: int | None = Field(
        default=None,
        description="Optional seed for a reproducible random sample",
    )

    @field_validator("app")
    @classmethod
    def strip_app(cls, value: str) -> str:
        return value.strip()


class AppSummary(BaseModel):
    id: str
    name: str
    developer: str | None = None
    bundle_id: str | None = None
    country: str
    store_url: str | None = None


class Review(BaseModel):
    id: str
    title: str
    text: str
    rating: int = Field(ge=1, le=5)
    author: str | None = None
    app_version: str | None = None
    created_at: str | None = None
    country: str


class AnalyzedReview(Review):
    cleaned_text: str
    sentiment: str
    sentiment_score: float


class CollectionWarning(BaseModel):
    code: str
    message: str


class CollectReviewsResponse(BaseModel):
    app: AppSummary
    requested_count: int
    collected_count: int
    available_pool_size: int
    is_partial: bool
    warnings: list[CollectionWarning] = Field(default_factory=list)
    reviews: list[Review]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class DistributionItem(BaseModel):
    count: int
    percentage: float


class Metrics(BaseModel):
    total_reviews: int
    average_rating: float | None
    rating_distribution: dict[str, DistributionItem]
    sentiment_distribution: dict[str, DistributionItem]


class KeywordPhrase(BaseModel):
    phrase: str
    count: int


class ActionableInsight(BaseModel):
    area: str
    evidence_count: int
    share_of_negative_reviews: float
    recommendation: str


class AnalysisResponse(BaseModel):
    analysis_id: str
    created_at: str
    app: AppSummary
    requested_count: int
    collected_count: int
    available_pool_size: int
    is_partial: bool
    warnings: list[CollectionWarning]
    metrics: Metrics
    negative_keywords: list[KeywordPhrase]
    insights: list[ActionableInsight]
