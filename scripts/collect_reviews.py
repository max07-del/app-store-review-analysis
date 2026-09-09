"""Command-line entry point for collecting and analyzing App Store reviews.

Covers the same pipeline as ``POST /api/v1/analyses`` without running a server,
and writes the artifacts used for the demo report.

Examples
--------
Collect 100 random reviews and write raw JSON only::

    python scripts/collect_reviews.py 1459969523 --no-analyze -o out/

Full analysis with the LLM layer, into ``reports/nebula``::

    python scripts/collect_reviews.py \\
        https://apps.apple.com/gb/app/id1459969523 \\
        --country gb --count 100 --seed 42 --output reports/nebula
"""

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

import httpx

from app.config import LLMSettings
from app.exceptions import ReviewCollectorError
from app.schemas.reviews import (
    AnalysisResponse,
    AnalyzedReview,
    CollectionWarning,
    CollectReviewsRequest,
    CollectReviewsResponse,
)
from app.services.apple_client import AppleClient
from app.services.llm_insights import LLMInsightGenerator
from app.services.report import render_analysis_report, render_markdown_report
from app.services.review_collector import ReviewCollector
from app.services.text_analysis import ReviewAnalyzer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="collect_reviews",
        description="Collect a random sample of Apple App Store reviews and analyze it.",
    )
    parser.add_argument("app", help="Numeric App Store ID or an apps.apple.com URL")
    parser.add_argument("-c", "--country", default="us", help="Two-letter storefront (default: us)")
    parser.add_argument(
        "-n", "--count", type=int, default=100, help="Reviews to sample, 1-100 (default: 100)"
    )
    parser.add_argument("-s", "--seed", type=int, help="Seed for a reproducible sample")
    parser.add_argument(
        "-o", "--output", type=Path, help="Directory for the artifacts (default: stdout only)"
    )
    parser.add_argument(
        "--no-analyze",
        dest="analyze",
        action="store_false",
        help="Only collect raw reviews; skip metrics, sentiment, and insights",
    )
    parser.add_argument(
        "--no-llm",
        dest="use_llm",
        action="store_false",
        help="Skip the Claude insight layer even when an API key is configured",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress the human-readable summary on stdout"
    )
    return parser


async def run(args: argparse.Namespace) -> int:
    try:
        request = CollectReviewsRequest(
            app=args.app,
            country=args.country,
            count=args.count,
            seed=args.seed,
            use_llm=args.use_llm,
        )
    except ValueError as exc:
        print(f"error: invalid arguments: {exc}", file=sys.stderr)
        return 2

    timeout = httpx.Timeout(15.0, connect=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as http_client:
            collection = await ReviewCollector(AppleClient(http_client)).collect(request)
    except ReviewCollectorError as exc:
        print(f"error: [{exc.code}] {exc.message}", file=sys.stderr)
        return 1

    if not args.analyze:
        _write_collection(collection, args)
        return 0

    analysis, reviews = ReviewAnalyzer().analyze(collection)

    if request.use_llm:
        generator = LLMInsightGenerator(LLMSettings.from_env())
        if not args.quiet and generator.is_available:
            print(f"Requesting insights from {generator.settings.model} ...", file=sys.stderr)
        report, error = await generator.generate(analysis.app, analysis.metrics, collection.reviews)
        analysis.llm_insights = report
        if error is not None:
            analysis.warnings.append(CollectionWarning(code="LLM_UNAVAILABLE", message=error))

    _write_analysis(analysis, reviews, args)
    if not args.quiet:
        _print_summary(analysis)
    return 0


def _write_collection(collection: CollectReviewsResponse, args: argparse.Namespace) -> None:
    if args.output is None:
        print(collection.model_dump_json(indent=2))
        return
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "reviews.json").write_text(
        collection.model_dump_json(indent=2), encoding="utf-8"
    )
    _write_csv(args.output / "reviews.csv", [r.model_dump() for r in collection.reviews])
    if not args.quiet:
        print(
            f"Collected {collection.collected_count} of {collection.available_pool_size} "
            f"available reviews -> {args.output}",
            file=sys.stderr,
        )


def _write_analysis(
    analysis: AnalysisResponse,
    reviews: list[AnalyzedReview],
    args: argparse.Namespace,
) -> None:
    if args.output is None:
        print(analysis.model_dump_json(indent=2))
        return
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "analysis.json").write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
    (args.output / "report.html").write_text(render_analysis_report(analysis), encoding="utf-8")
    (args.output / "REPORT.md").write_text(render_markdown_report(analysis), encoding="utf-8")
    _write_csv(args.output / "reviews.csv", [review.model_dump() for review in reviews])


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        if not rows:
            return
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _flatten(value) for key, value in row.items()})


def _flatten(value: object) -> object:
    return json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value


def _print_summary(analysis: AnalysisResponse) -> None:
    metrics = analysis.metrics
    average = f"{metrics.average_rating:.2f}" if metrics.average_rating is not None else "n/a"
    print(f"\n{analysis.app.name} — {analysis.app.country.upper()} storefront")
    print(f"Analysis ID:    {analysis.analysis_id}")
    print(f"Reviews:        {metrics.total_reviews} (pool: {analysis.available_pool_size})")
    print(f"Average rating: {average}")

    print("\nRatings")
    for stars, item in sorted(metrics.rating_distribution.items()):
        print(f"  {stars}* {'#' * round(item.percentage / 2):<50} {item.percentage:5.1f}%")

    print("\nSentiment")
    for name, item in metrics.sentiment_distribution.items():
        print(f"  {name:<9} {'#' * round(item.percentage / 2):<50} {item.percentage:5.1f}%")

    if analysis.negative_keywords:
        top = ", ".join(f"{k.phrase} ({k.count})" for k in analysis.negative_keywords[:8])
        print(f"\nTop negative terms: {top}")

    if analysis.llm_insights is not None:
        print(f"\nLLM insights ({analysis.llm_insights.model})")
        print(f"  {analysis.llm_insights.executive_summary}")
        for theme in analysis.llm_insights.themes:
            print(f"  [{theme.severity:>8}] {theme.theme} — {theme.affected_reviews} reviews")
        for rec in analysis.llm_insights.recommendations:
            print(f"  [{rec.priority}] {rec.title}")

    for warning in analysis.warnings:
        print(f"\nwarning: [{warning.code}] {warning.message}", file=sys.stderr)


def main() -> None:
    raise SystemExit(asyncio.run(run(build_parser().parse_args())))


if __name__ == "__main__":
    main()
