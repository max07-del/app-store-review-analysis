from html import escape

from app.schemas.reviews import AnalysisResponse, LLMInsightReport


def render_analysis_report(analysis: AnalysisResponse) -> str:
    rating_bars = "".join(
        _bar(f"{rating} stars", item.percentage, item.count)
        for rating, item in analysis.metrics.rating_distribution.items()
    )
    sentiment_bars = "".join(
        _bar(name.title(), item.percentage, item.count, css_class=name)
        for name, item in analysis.metrics.sentiment_distribution.items()
    )
    keywords = (
        "".join(
            f"<li><span>{escape(item.phrase)}</span><strong>{item.count}</strong></li>"
            for item in analysis.negative_keywords
        )
        or "<li>No negative-review keywords were found.</li>"
    )
    insights = (
        "".join(
            "<article class='insight'>"
            f"<h3>{escape(item.area.replace('_', ' ').title())}</h3>"
            f"<p>{escape(item.recommendation)}</p>"
            f"<small>{item.evidence_count} negative reviews · "
            f"{item.share_of_negative_reviews:.1f}% of negative feedback</small>"
            "</article>"
            for item in analysis.insights
        )
        or "<p>No recurring issue area was detected in the negative reviews.</p>"
    )

    llm_section = _llm_section(analysis.llm_insights)

    average_rating = (
        f"{analysis.metrics.average_rating:.2f}"
        if analysis.metrics.average_rating is not None
        else "N/A"
    )
    partial_note = (
        "<p class='warning'>Apple returned fewer reviews than requested; metrics use "
        "all available records.</p>"
        if analysis.is_partial
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(analysis.app.name)} review analysis</title>
  <style>
    :root {{ color-scheme: light; --ink:#172033; --muted:#667085; --line:#e5e7eb;
      --brand:#6d5dfc; --positive:#23a26d; --neutral:#e5a82e; --negative:#dc4c64; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#f5f6fa; color:var(--ink); font:15px/1.55 Inter,Arial,sans-serif; }}
    main {{ max-width:1040px; margin:40px auto; padding:0 24px 60px; }}
    header {{ background:linear-gradient(135deg,#1c2340,#6d5dfc); color:white;
      padding:36px; border-radius:22px; box-shadow:0 16px 40px #27235d24; }}
    header p {{ margin:6px 0 0; opacity:.82; }}
    h1 {{ margin:0; font-size:34px; }} h2 {{ margin:0 0 18px; }} h3 {{ margin:0 0 8px; }}
    .cards {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin:20px 0; }}
    .card,.panel,.insight {{ background:white; border:1px solid var(--line); border-radius:16px; }}
    .card {{ padding:22px; }} .card strong {{ display:block; font-size:30px; }}
    .card span,small {{ color:var(--muted); }}
    .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; margin:18px 0; }}
    .panel {{ padding:24px; }}
    .bar-row {{ display:grid; grid-template-columns:90px 1fr 86px; align-items:center; gap:10px; margin:11px 0; }}
    .track {{ height:11px; background:#edf0f5; border-radius:20px; overflow:hidden; }}
    .fill {{ height:100%; background:var(--brand); border-radius:20px; min-width:2px; }}
    .fill.positive {{ background:var(--positive); }} .fill.neutral {{ background:var(--neutral); }}
    .fill.negative {{ background:var(--negative); }}
    .keywords {{ list-style:none; margin:0; padding:0; columns:2; column-gap:24px; }}
    .keywords li {{ display:flex; justify-content:space-between; border-bottom:1px solid var(--line); padding:9px 0; break-inside:avoid; }}
    .insights {{ display:grid; grid-template-columns:repeat(2,1fr); gap:14px; }}
    .insight {{ padding:20px; border-left:5px solid var(--brand); }}
    .warning {{ background:#fff7df; border:1px solid #f0d98a; padding:12px 16px; border-radius:12px; }}
    .llm {{ margin-top:18px; border-left:5px solid #6d5dfc; }}
    .summary {{ background:#f4f2ff; border:1px solid #ded8ff; border-radius:12px; padding:16px 18px; margin:0 0 18px; }}
    .theme {{ border:1px solid var(--line); border-radius:14px; padding:16px 18px; margin:12px 0; }}
    .theme header {{ background:none; color:inherit; padding:0; border-radius:0; box-shadow:none;
      display:flex; align-items:center; gap:10px; justify-content:space-between; }}
    .theme h3 {{ margin:0; font-size:16px; }}
    .badge {{ font-size:11px; font-weight:700; letter-spacing:.04em; text-transform:uppercase;
      padding:4px 9px; border-radius:999px; white-space:nowrap; }}
    .sev-critical {{ background:#fde3e7; color:#a3102a; }} .sev-high {{ background:#ffeada; color:#9a4a06; }}
    .sev-medium {{ background:#fff5d6; color:#7d5a06; }} .sev-low {{ background:#e6f4ec; color:#166a45; }}
    .p0 {{ background:#fde3e7; color:#a3102a; }} .p1 {{ background:#fff5d6; color:#7d5a06; }}
    .p2 {{ background:#eef0f4; color:#4b5565; }}
    blockquote {{ margin:8px 0 0; padding:6px 0 6px 14px; border-left:3px solid #ded8ff;
      color:var(--muted); font-style:italic; font-size:13.5px; }}
    .rec {{ border:1px solid var(--line); border-radius:14px; padding:16px 18px; margin:12px 0; }}
    .rec-head {{ display:flex; align-items:center; gap:10px; margin-bottom:6px; }}
    .rec-head h3 {{ margin:0; font-size:16px; }}
    .impact {{ color:var(--muted); font-size:13px; margin:6px 0 0; }}
    footer {{ margin-top:20px; color:var(--muted); font-size:13px; }}
    @media(max-width:760px) {{ .cards,.grid,.insights {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body><main>
  <header><h1>{escape(analysis.app.name)}</h1>
    <p>App Store review analysis · {escape(analysis.app.country.upper())} storefront · {escape(analysis.created_at)}</p>
  </header>
  {partial_note}
  <section class="cards">
    <div class="card"><span>Reviews analyzed</span><strong>{analysis.metrics.total_reviews}</strong></div>
    <div class="card"><span>Average rating</span><strong>{average_rating}</strong></div>
    <div class="card"><span>Available sample pool</span><strong>{analysis.available_pool_size}</strong></div>
  </section>
  <section class="grid">
    <div class="panel"><h2>Rating distribution</h2>{rating_bars}</div>
    <div class="panel"><h2>Sentiment distribution</h2>{sentiment_bars}</div>
  </section>
  <section class="panel"><h2>Common phrases in negative reviews</h2>
    <ul class="keywords">{keywords}</ul></section>
  <section class="panel" style="margin-top:18px"><h2>Actionable insights (rule-based)</h2>
    <div class="insights">{insights}</div></section>
  {llm_section}
  <footer>Analysis ID: {escape(analysis.analysis_id)} · Sentiment uses VADER and is optimized for English-language reviews.</footer>
</main></body></html>"""


def _bar(label: str, percentage: float, count: int, css_class: str = "") -> str:
    width = min(max(percentage, 0.0), 100.0)
    return (
        "<div class='bar-row'>"
        f"<span>{escape(label)}</span>"
        f"<div class='track'><div class='fill {escape(css_class)}' style='width:{width:.2f}%'></div></div>"
        f"<strong>{percentage:.1f}% <small>({count})</small></strong>"
        "</div>"
    )


def _llm_section(report: LLMInsightReport | None) -> str:
    """Render the Claude insight layer, or nothing when it did not run."""
    if report is None:
        return ""

    themes = (
        "".join(
            "<article class='theme'>"
            "<header>"
            f"<h3>{escape(theme.theme)}</h3>"
            f"<span class='badge sev-{escape(theme.severity)}'>{escape(theme.severity)}</span>"
            "</header>"
            f"<p>{escape(theme.summary)}</p>"
            f"<small>{theme.affected_reviews} reviews in the sample</small>"
            + "".join(
                f"<blockquote>{escape(quote)}</blockquote>" for quote in theme.evidence_quotes
            )
            + "</article>"
            for theme in report.themes
        )
        or "<p>The model did not identify a recurring theme.</p>"
    )

    recommendations = (
        "".join(
            "<article class='rec'>"
            "<div class='rec-head'>"
            f"<span class='badge {escape(item.priority.lower())}'>{escape(item.priority)}</span>"
            f"<h3>{escape(item.title)}</h3>"
            "</div>"
            f"<p>{escape(item.rationale)}</p>"
            f"<p class='impact'>Expected impact: {escape(item.expected_impact)}</p>"
            "</article>"
            for item in report.recommendations
        )
        or "<p>The model did not propose a recommendation.</p>"
    )

    return f"""<section class="panel llm" style="margin-top:18px">
    <h2>LLM insight layer</h2>
    <p class="summary">{escape(report.executive_summary)}</p>
    <h3 style="margin-top:22px">Themes</h3>
    {themes}
    <h3 style="margin-top:22px">Prioritized recommendations</h3>
    {recommendations}
    <small>Generated by {escape(report.model)} from {report.reviews_considered} reviews.</small>
  </section>"""


def render_markdown_report(analysis: AnalysisResponse) -> str:
    """Render the analysis as a self-contained Markdown demo report."""
    metrics = analysis.metrics
    average = f"{metrics.average_rating:.2f}" if metrics.average_rating is not None else "n/a"
    app_line = analysis.app.name
    if analysis.app.developer:
        app_line += f" — {analysis.app.developer}"

    lines = [
        f"# {app_line}",
        "",
        "App Store review analysis",
        "",
        f"- **Storefront:** {analysis.app.country.upper()}",
        f"- **Reviews analyzed:** {metrics.total_reviews} "
        f"(sampled from {analysis.available_pool_size} available)",
        f"- **Average rating:** {average} / 5",
        f"- **Generated:** {analysis.created_at}",
        f"- **Analysis ID:** `{analysis.analysis_id}`",
        "",
        "## Rating distribution",
        "",
        "| Rating | Reviews | Share | |",
        "|---|---:|---:|---|",
    ]
    for stars, item in sorted(metrics.rating_distribution.items()):
        lines.append(
            f"| {stars}★ | {item.count} | {item.percentage:.1f}% | `{_sparkbar(item.percentage)}` |"
        )

    lines += [
        "",
        "## Sentiment distribution",
        "",
        "| Sentiment | Reviews | Share | |",
        "|---|---:|---:|---|",
    ]
    for name, item in metrics.sentiment_distribution.items():
        lines.append(
            f"| {name.title()} | {item.count} | {item.percentage:.1f}% | "
            f"`{_sparkbar(item.percentage)}` |"
        )

    lines += ["", "## Frequent terms in negative reviews", ""]
    if analysis.negative_keywords:
        lines += ["| Term or phrase | Occurrences |", "|---|---:|"]
        lines += [f"| {item.phrase} | {item.count} |" for item in analysis.negative_keywords]
    else:
        lines.append("No recurring terms were found in the negative reviews.")

    lines += ["", "## Rule-based issue areas", ""]
    if analysis.insights:
        for item in analysis.insights:
            lines += [
                f"### {item.area.replace('_', ' ').title()}",
                "",
                f"{item.recommendation}",
                "",
                f"*Evidence: {item.evidence_count} negative reviews "
                f"({item.share_of_negative_reviews:.1f}% of negative feedback).*",
                "",
            ]
    else:
        lines += ["No recurring issue area was detected.", ""]

    lines += _markdown_llm_section(analysis.llm_insights)

    if analysis.warnings:
        lines += ["## Warnings", ""]
        lines += [f"- `{w.code}` — {w.message}" for w in analysis.warnings]
        lines.append("")

    lines += [
        "---",
        "",
        "Per-review sentiment is computed with VADER combined with the star rating; "
        "it is tuned for English-language reviews.",
    ]
    return "\n".join(lines) + "\n"


def _markdown_llm_section(report: LLMInsightReport | None) -> list[str]:
    if report is None:
        return [
            "## LLM insight layer",
            "",
            "Not included in this run. Set `ANTHROPIC_API_KEY` and regenerate to add "
            "model-generated themes and prioritized recommendations.",
            "",
        ]

    lines = [
        "## LLM insight layer",
        "",
        f"*Generated by `{report.model}` from {report.reviews_considered} reviews.*",
        "",
        f"> {report.executive_summary}",
        "",
        "### Themes",
        "",
    ]
    if report.themes:
        for theme in report.themes:
            lines += [
                f"#### {theme.theme} — `{theme.severity}` ({theme.affected_reviews} reviews)",
                "",
                theme.summary,
                "",
            ]
            lines += [f"> {quote}" for quote in theme.evidence_quotes]
            if theme.evidence_quotes:
                lines.append("")
    else:
        lines += ["The model did not identify a recurring theme.", ""]

    lines += ["### Prioritized recommendations", ""]
    if report.recommendations:
        for item in report.recommendations:
            lines += [
                f"#### `{item.priority}` {item.title}",
                "",
                item.rationale,
                "",
                f"*Expected impact: {item.expected_impact}*",
                "",
            ]
    else:
        lines += ["The model did not propose a recommendation.", ""]
    return lines


def _sparkbar(percentage: float, width: int = 20) -> str:
    filled = round(min(max(percentage, 0.0), 100.0) / 100 * width)
    return "█" * filled + "·" * (width - filled)
