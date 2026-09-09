from app.schemas.reviews import (
    AppSummary,
    CollectReviewsResponse,
    Review,
)
from app.services.text_analysis import ReviewAnalyzer


def _collection() -> CollectReviewsResponse:
    return CollectReviewsResponse(
        app=AppSummary(id="123", name="Example", country="us"),
        requested_count=4,
        collected_count=4,
        available_pool_size=4,
        is_partial=False,
        reviews=[
            Review(
                id="1",
                title="Excellent",
                text="I love this useful and wonderful app!",
                rating=5,
                country="us",
            ),
            Review(
                id="2",
                title="Broken update",
                text="The app crashes and support never answers.",
                rating=1,
                country="us",
            ),
            Review(
                id="3",
                title="Login problem",
                text="Terrible login bug. I cannot access my account.",
                rating=1,
                country="us",
            ),
            Review(
                id="4",
                title="Information",
                text="Version 2.0 was installed today.",
                rating=3,
                country="us",
            ),
        ],
    )


def test_analysis_calculates_metrics_and_insights() -> None:
    result, reviews = ReviewAnalyzer().analyze(_collection())

    assert result.metrics.total_reviews == 4
    assert result.metrics.average_rating == 2.5
    assert result.metrics.rating_distribution["1"].count == 2
    assert result.metrics.rating_distribution["5"].percentage == 25.0
    assert sum(item.count for item in result.metrics.sentiment_distribution.values()) == 4
    assert result.negative_keywords
    assert any(item.area == "stability_and_performance" for item in result.insights)
    assert len(reviews) == 4
    assert all(review.cleaned_text for review in reviews)


def test_clean_text_normalizes_urls_and_whitespace() -> None:
    cleaned = ReviewAnalyzer.clean_text("  Read\nhttps://example.com   this  ")

    assert cleaned == "Read this"
