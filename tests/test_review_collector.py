from app.schemas.reviews import AppSummary, CollectReviewsRequest, Review
from app.services.review_collector import ReviewCollector


class StubAppleClient:
    @staticmethod
    def extract_app_id(value: str) -> str:
        return value

    async def lookup_app(self, app_id: str, country: str) -> AppSummary:
        return AppSummary(id=app_id, name="Example", country=country)

    async def fetch_reviews_page(
        self,
        app_id: str,
        country: str,
        page: int,
    ) -> list[Review]:
        del app_id
        if page > 2:
            return []
        start = (page - 1) * 60
        return [
            Review(
                id=str(index),
                title=f"Review {index}",
                text="Example text",
                rating=index % 5 + 1,
                country=country,
            )
            for index in range(start, start + 60)
        ]


async def test_collects_reproducible_random_sample() -> None:
    collector = ReviewCollector(StubAppleClient())  # type: ignore[arg-type]
    request = CollectReviewsRequest(app="123", country="us", count=100, seed=42)

    first = await collector.collect(request)
    second = await collector.collect(request)

    assert first.collected_count == 100
    assert first.available_pool_size == 120
    assert not first.is_partial
    assert [review.id for review in first.reviews] == [review.id for review in second.reviews]


async def test_returns_partial_result_when_fewer_reviews_are_available() -> None:
    collector = ReviewCollector(StubAppleClient(), max_pages=1)  # type: ignore[arg-type]
    request = CollectReviewsRequest(app="123", country="us", count=100)

    result = await collector.collect(request)

    assert result.collected_count == 60
    assert result.is_partial
    assert result.warnings[0].code == "INSUFFICIENT_REVIEWS"
