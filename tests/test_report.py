from app.schemas.reviews import (
    ActionableInsight,
    AnalysisResponse,
    AppSummary,
    CollectionWarning,
    DistributionItem,
    KeywordPhrase,
    LLMInsightReport,
    LLMRecommendation,
    LLMTheme,
    Metrics,
)
from app.services.report import render_analysis_report, render_markdown_report

LLM_REPORT = LLMInsightReport(
    model="claude-opus-5",
    executive_summary="Billing complaints dominate the negative feedback.",
    themes=[
        LLMTheme(
            theme="Charged after cancelling",
            severity="critical",
            affected_reviews=12,
            summary="Users report being billed after cancelling.",
            evidence_quotes=["they took my money again"],
        )
    ],
    recommendations=[
        LLMRecommendation(
            title="Audit the cancellation flow",
            priority="P0",
            rationale="Twelve reviews describe post-cancellation charges.",
            expected_impact="Fewer refund requests and chargebacks.",
        )
    ],
    reviews_considered=100,
)


def make_analysis(llm: LLMInsightReport | None = None) -> AnalysisResponse:
    return AnalysisResponse(
        analysis_id="analysis-1",
        created_at="2026-09-09T00:00:00+00:00",
        app=AppSummary(id="1", name="Example App", developer="Example Ltd", country="gb"),
        requested_count=100,
        collected_count=2,
        available_pool_size=2,
        is_partial=False,
        warnings=[CollectionWarning(code="DEMO", message="A demo warning")],
        metrics=Metrics(
            total_reviews=2,
            average_rating=3.0,
            rating_distribution={
                "1": DistributionItem(count=1, percentage=50.0),
                "5": DistributionItem(count=1, percentage=50.0),
            },
            sentiment_distribution={
                "positive": DistributionItem(count=1, percentage=50.0),
                "negative": DistributionItem(count=1, percentage=50.0),
            },
        ),
        negative_keywords=[KeywordPhrase(phrase="subscription", count=9)],
        insights=[
            ActionableInsight(
                area="billing_and_subscription",
                evidence_count=1,
                share_of_negative_reviews=100.0,
                recommendation="Clarify subscription terms.",
            )
        ],
        llm_insights=llm,
    )


def test_html_report_includes_the_llm_layer() -> None:
    html = render_analysis_report(make_analysis(LLM_REPORT))

    assert "LLM insight layer" in html
    assert "Charged after cancelling" in html
    assert "sev-critical" in html
    assert "they took my money again" in html
    assert "Audit the cancellation flow" in html


def test_html_report_omits_the_llm_layer_when_absent() -> None:
    html = render_analysis_report(make_analysis(None))

    assert "LLM insight layer" not in html
    assert "Rating distribution" in html
    assert "Example App" in html


def test_html_report_escapes_hostile_review_content() -> None:
    analysis = make_analysis(None)
    analysis.negative_keywords = [KeywordPhrase(phrase="<script>alert(1)</script>", count=1)]

    html = render_analysis_report(analysis)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_markdown_report_contains_every_section() -> None:
    markdown = render_markdown_report(make_analysis(LLM_REPORT))

    assert markdown.startswith("# Example App — Example Ltd")
    assert "**Average rating:** 3.00 / 5" in markdown
    assert "| 1★ | 1 | 50.0% |" in markdown
    assert "| Positive | 1 | 50.0% |" in markdown
    assert "| subscription | 9 |" in markdown
    assert "Billing And Subscription" in markdown
    assert "#### Charged after cancelling — `critical` (12 reviews)" in markdown
    assert "#### `P0` Audit the cancellation flow" in markdown
    assert "`DEMO` — A demo warning" in markdown


def test_markdown_report_explains_a_missing_llm_layer() -> None:
    markdown = render_markdown_report(make_analysis(None))

    assert "## LLM insight layer" in markdown
    assert "ANTHROPIC_API_KEY" in markdown


def test_markdown_report_handles_an_empty_analysis() -> None:
    analysis = make_analysis(None)
    analysis.metrics.average_rating = None
    analysis.negative_keywords = []
    analysis.insights = []
    analysis.warnings = []

    markdown = render_markdown_report(analysis)

    assert "**Average rating:** n/a / 5" in markdown
    assert "No recurring terms were found" in markdown
    assert "No recurring issue area was detected." in markdown
    assert "## Warnings" not in markdown
