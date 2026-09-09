import asyncio
import random

from app.schemas.reviews import (
    CollectionWarning,
    CollectReviewsRequest,
    CollectReviewsResponse,
    Review,
)
from app.services.apple_client import AppleClient


class ReviewCollector:
    def __init__(self, apple_client: AppleClient, *, max_pages: int = 10) -> None:
        self.apple_client = apple_client
        self.max_pages = max_pages

    async def collect(self, request: CollectReviewsRequest) -> CollectReviewsResponse:
        app_id = self.apple_client.extract_app_id(request.app)
        app = await self.apple_client.lookup_app(app_id, request.country)

        reviews_by_id: dict[str, Review] = {}
        for page in range(1, self.max_pages + 1):
            page_reviews = await self.apple_client.fetch_reviews_page(
                app_id,
                request.country,
                page,
            )
            if not page_reviews:
                break
            reviews_by_id.update({review.id: review for review in page_reviews})
            if page < self.max_pages:
                await asyncio.sleep(0.2)

        pool = list(reviews_by_id.values())
        sample_size = min(request.count, len(pool))
        selected = random.Random(request.seed).sample(pool, k=sample_size)

        warnings: list[CollectionWarning] = []
        if sample_size < request.count:
            warnings.append(
                CollectionWarning(
                    code="INSUFFICIENT_REVIEWS",
                    message=(
                        f"Only {sample_size} unique reviews are available in the "
                        f"{request.country} storefront"
                    ),
                )
            )

        return CollectReviewsResponse(
            app=app,
            requested_count=request.count,
            collected_count=sample_size,
            available_pool_size=len(pool),
            is_partial=sample_size < request.count,
            warnings=warnings,
            reviews=selected,
        )
