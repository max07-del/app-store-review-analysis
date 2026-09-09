from html import escape

from app.schemas.reviews import AnalysisResponse


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
  <section class="panel" style="margin-top:18px"><h2>Actionable insights</h2>
    <div class="insights">{insights}</div></section>
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
