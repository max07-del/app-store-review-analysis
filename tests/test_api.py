from pathlib import Path

import httpx

from app.main import app
from app.repository import AnalysisRepository
from app.schemas.reviews import AppSummary, CollectReviewsResponse, Review
from app.services.text_analysis import ReviewAnalyzer


async def test_health() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_rejects_invalid_country() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/reviews/collect",
            json={"app": "389801252", "country": "USA"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_reads_and_downloads_saved_analysis(tmp_path: Path) -> None:
    repository = AnalysisRepository(tmp_path / "api.db")
    collection = CollectReviewsResponse(
        app=AppSummary(id="123", name="Example", country="us"),
        requested_count=1,
        collected_count=1,
        available_pool_size=1,
        is_partial=False,
        reviews=[
            Review(
                id="review-1",
                title="Bad update",
                text="It crashes every time.",
                rating=1,
                country="us",
            )
        ],
    )
    analysis, reviews = ReviewAnalyzer().analyze(collection)
    repository.save(analysis, reviews)
    app.state.analysis_repository = repository

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        analysis_response = await client.get(f"/api/v1/analyses/{analysis.analysis_id}")
        csv_response = await client.get(
            f"/api/v1/analyses/{analysis.analysis_id}/reviews/download?format=csv"
        )
        report_response = await client.get(f"/api/v1/analyses/{analysis.analysis_id}/report")

    assert analysis_response.status_code == 200
    assert analysis_response.json()["metrics"]["average_rating"] == 1.0
    assert csv_response.status_code == 200
    assert "Bad update" in csv_response.text
    assert report_response.status_code == 200
    assert "Rating distribution" in report_response.text


async def test_missing_analysis_returns_404(tmp_path: Path) -> None:
    app.state.analysis_repository = AnalysisRepository(tmp_path / "empty.db")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/analyses/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"
