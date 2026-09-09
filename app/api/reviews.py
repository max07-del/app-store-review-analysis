import httpx
from fastapi import APIRouter

from app.schemas.reviews import CollectReviewsRequest, CollectReviewsResponse
from app.services.apple_client import AppleClient
from app.services.review_collector import ReviewCollector

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


@router.post("/collect", response_model=CollectReviewsResponse)
async def collect_reviews(request: CollectReviewsRequest) -> CollectReviewsResponse:
    timeout = httpx.Timeout(10.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as http_client:
        collector = ReviewCollector(AppleClient(http_client))
        return await collector.collect(request)
