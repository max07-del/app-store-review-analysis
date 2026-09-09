from app.repository import AnalysisRepository
from app.schemas.reviews import AppSummary, CollectReviewsResponse, Review
from app.services.text_analysis import ReviewAnalyzer


def test_repository_round_trip(tmp_path) -> None:
    collection = CollectReviewsResponse(
        app=AppSummary(id="123", name="Example", country="us"),
        requested_count=1,
        collected_count=1,
        available_pool_size=1,
        is_partial=False,
        reviews=[
            Review(
                id="review-1",
                title="Great",
                text="A great experience.",
                rating=5,
                country="us",
            )
        ],
    )
    analysis, reviews = ReviewAnalyzer().analyze(collection)
    repository = AnalysisRepository(tmp_path / "test.db")

    repository.save(analysis, reviews)

    assert repository.get_analysis(analysis.analysis_id) == analysis
    assert repository.get_reviews(analysis.analysis_id) == reviews
    assert repository.get_analysis("missing") is None
