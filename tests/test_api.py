from pathlib import Path

import httpx

from app.main import app
from app.repository import AnalysisRepository
from app.schemas.reviews import (
    AppSummary,
    CollectReviewsResponse,
    LLMInsightReport,
    LLMRecommendation,
    LLMTheme,
    Review,
)
from app.services.review_collector import ReviewCollector
from app.services.text_analysis import ReviewAnalyzer


async def test_health() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_insights"] in {"enabled", "disabled"}


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


class StubGenerator:
    """Stands in for the Claude insight layer in endpoint tests."""

    def __init__(self, report: LLMInsightReport | None, error: str | None) -> None:
        self.report = report
        self.error = error
        self.calls = 0

    @property
    def is_available(self) -> bool:
        return self.report is not None

    async def generate(self, app_summary, metrics, reviews):  # noqa: ANN001, ARG002
        self.calls += 1
        return self.report, self.error


def _collection() -> CollectReviewsResponse:
    return CollectReviewsResponse(
        app=AppSummary(id="123", name="Example", country="us"),
        requested_count=1,
        collected_count=1,
        available_pool_size=1,
        is_partial=False,
        reviews=[
            Review(
                id="review-1",
                title="Charged twice",
                text="They billed me after I cancelled.",
                rating=1,
                country="us",
            )
        ],
    )


REPORT = LLMInsightReport(
    model="claude-opus-5",
    executive_summary="Billing is the dominant complaint.",
    themes=[
        LLMTheme(
            theme="Charged after cancelling",
            severity="critical",
            affected_reviews=1,
            summary="Billed after cancelling.",
            evidence_quotes=["billed me after I cancelled"],
        )
    ],
    recommendations=[
        LLMRecommendation(
            title="Audit the cancellation flow",
            priority="P0",
            rationale="The only review in the sample reports it.",
            expected_impact="Fewer refund requests.",
        )
    ],
    reviews_considered=1,
)


async def _create_analysis(tmp_path: Path, generator: StubGenerator, use_llm: bool) -> dict:
    app.state.analysis_repository = AnalysisRepository(tmp_path / "llm.db")
    app.state.llm_insight_generator = generator

    async def fake_collect(self, request):  # noqa: ANN001, ARG001
        return _collection()

    original = ReviewCollector.collect
    ReviewCollector.collect = fake_collect
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/analyses",
                json={"app": "123", "country": "us", "count": 1, "use_llm": use_llm},
            )
    finally:
        ReviewCollector.collect = original

    assert response.status_code == 201
    return response.json()


async def test_analysis_includes_llm_insights(tmp_path: Path) -> None:
    generator = StubGenerator(REPORT, None)

    body = await _create_analysis(tmp_path, generator, use_llm=True)

    assert generator.calls == 1
    assert body["llm_insights"]["themes"][0]["severity"] == "critical"
    assert body["llm_insights"]["recommendations"][0]["priority"] == "P0"
    assert body["warnings"] == []

    # The report is persisted alongside the rule-based analysis.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        saved = await client.get(f"/api/v1/analyses/{body['analysis_id']}")
        rendered = await client.get(f"/api/v1/analyses/{body['analysis_id']}/report")

    assert saved.json()["llm_insights"]["model"] == "claude-opus-5"
    assert "LLM insight layer" in rendered.text
    assert "Charged after cancelling" in rendered.text


async def test_llm_failure_degrades_to_a_warning(tmp_path: Path) -> None:
    generator = StubGenerator(None, "The Claude API rate limit was reached")

    body = await _create_analysis(tmp_path, generator, use_llm=True)

    assert body["llm_insights"] is None
    assert body["warnings"][0]["code"] == "LLM_UNAVAILABLE"
    # The deterministic analysis is unaffected.
    assert body["metrics"]["average_rating"] == 1.0
    assert body["insights"]


async def test_use_llm_false_skips_the_model(tmp_path: Path) -> None:
    generator = StubGenerator(REPORT, None)

    body = await _create_analysis(tmp_path, generator, use_llm=False)

    assert generator.calls == 0
    assert body["llm_insights"] is None
    assert body["warnings"] == []
