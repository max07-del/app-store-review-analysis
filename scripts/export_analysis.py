import argparse
import csv
from pathlib import Path

from app.repository import AnalysisRepository
from app.schemas.reviews import CollectReviewsResponse, Review
from app.services.report import render_analysis_report
from app.services.text_analysis import ReviewAnalyzer


def main() -> None:
    parser = argparse.ArgumentParser(description="Reanalyze a saved run and export demo artifacts.")
    parser.add_argument("analysis_id")
    parser.add_argument("--database", default="data/app_store_reviews.db")
    parser.add_argument("--output", default="reports/nebula")
    args = parser.parse_args()

    repository = AnalysisRepository(args.database)
    source = repository.get_analysis(args.analysis_id)
    stored_reviews = repository.get_reviews(args.analysis_id)
    if source is None or stored_reviews is None:
        raise SystemExit(f"Analysis {args.analysis_id} was not found")

    collection = CollectReviewsResponse(
        app=source.app,
        requested_count=source.requested_count,
        collected_count=len(stored_reviews),
        available_pool_size=source.available_pool_size,
        is_partial=source.is_partial,
        warnings=source.warnings,
        reviews=[Review.model_validate(review.model_dump()) for review in stored_reviews],
    )
    analysis, reviews = ReviewAnalyzer().analyze(collection)
    repository.save(analysis, reviews)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis.json").write_text(
        analysis.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (output_dir / "report.html").write_text(
        render_analysis_report(analysis),
        encoding="utf-8",
    )

    rows = [review.model_dump() for review in reviews]
    with (output_dir / "reviews.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    print(analysis.analysis_id)


if __name__ == "__main__":
    main()
