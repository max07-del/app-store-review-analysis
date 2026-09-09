# App Store Review Analysis API

A REST API that collects Apple App Store reviews for any public application,
processes them, calculates metrics, and produces actionable product insights —
combining a deterministic NLP baseline with an optional Claude-powered insight
layer.

Built as a test task for the OBRIO AI Engineer position.

---

## What it does

```text
App ID or URL
   ↓  iTunes Lookup API                       validate the app, read metadata
   ↓  App Store review endpoint (paginated)   up to 200 reviews, deduplicated
   ↓  random sampling (optionally seeded)     100 reviews
   ↓  cleaning + VADER sentiment              per-review sentiment, metrics
   ↓  keyword & issue-area extraction         what users complain about
   ↓  Claude insight layer (optional)         why, and what to do about it
   ↓  SQLite
   ↓  JSON · CSV · HTML report · Markdown report
```

## Features

- accepts a numeric App Store ID or an `apps.apple.com` URL;
- verifies the app through Apple's iTunes Lookup API;
- collects up to 200 storefront-specific reviews and randomly samples up to 100;
- validates input, retries transient upstream failures, and deduplicates reviews;
- cleans review text and classifies sentiment as positive / neutral / negative;
- calculates average rating, rating distribution, and sentiment distribution;
- extracts frequent words and phrases from negative reviews;
- **clusters complaints into named themes with verbatim evidence and prioritized,
  severity-scored recommendations via Claude** (optional, degrades gracefully);
- stores completed analyses in SQLite;
- serves processed reviews as JSON or CSV downloads;
- renders a responsive HTML report and a Markdown report;
- ships a standalone CLI so the pipeline runs without a server;
- exposes interactive OpenAPI/Swagger documentation.

## Technology

Python 3.11+ · FastAPI · Uvicorn · HTTPX · Pydantic v2 · VADER Sentiment ·
Anthropic SDK (Claude) · SQLite · pytest · Ruff

---

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
python -m pip install -e '.[dev]'
uvicorn app.main:app --reload
```

After startup:

| | |
|---|---|
| Swagger UI | <http://127.0.0.1:8000/docs> |
| OpenAPI JSON | <http://127.0.0.1:8000/openapi.json> |
| Health check | <http://127.0.0.1:8000/health> |

### Enabling the LLM insight layer (optional)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

**The API is fully functional without a key.** Without one, requests return the
complete rule-based analysis plus an `LLM_UNAVAILABLE` warning; nothing fails.
`GET /health` reports which mode is active.

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(unset)* | Enables the LLM insight layer |
| `APP_LLM_MODEL` | `claude-opus-5` | Model used for insights |
| `APP_LLM_MAX_REVIEWS` | `120` | Cap on reviews sent to the model |
| `APP_LLM_EFFORT` | `medium` | Reasoning effort: `low`–`max` |
| `APP_LLM_TIMEOUT_SECONDS` | `120` | Claude request timeout |
| `APP_DATABASE_PATH` | `data/app_store_reviews.db` | SQLite location |

---

## Quick start

### Command line

The CLI runs the whole pipeline without starting a server — this is the
"script to collect 100 random reviews" from the task requirements.

```bash
# Collect and analyze 100 random reviews, write all artifacts
python scripts/collect_reviews.py 1459969523 --country gb --count 100 --seed 42 \
    --output reports/nebula

# Raw reviews only, no analysis
python scripts/collect_reviews.py 1459969523 --no-analyze --output out/

# Skip the LLM layer even when a key is configured
python scripts/collect_reviews.py 1459969523 --no-llm
```

Writes `analysis.json`, `reviews.csv`, `report.html`, and `REPORT.md` into the
output directory, and prints a summary. Exit codes: `0` success, `1` upstream
failure, `2` invalid arguments.

### HTTP API

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyses \
  -H 'Content-Type: application/json' \
  -d '{
    "app": "https://apps.apple.com/us/app/id1459969523",
    "country": "us",
    "count": 100,
    "seed": 42,
    "use_llm": true
  }'
```

The response contains `analysis_id`. Use it for the follow-up requests:

```bash
curl http://127.0.0.1:8000/api/v1/analyses/ANALYSIS_ID
curl http://127.0.0.1:8000/api/v1/analyses/ANALYSIS_ID/reviews
curl -OJ 'http://127.0.0.1:8000/api/v1/analyses/ANALYSIS_ID/reviews/download?format=csv'
open http://127.0.0.1:8000/api/v1/analyses/ANALYSIS_ID/report
```

To collect raw reviews without running any analysis:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/reviews/collect \
  -H 'Content-Type: application/json' \
  -d '{"app":"1459969523","country":"us","count":100,"seed":42}'
```

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check and LLM availability |
| `POST` | `/api/v1/reviews/collect` | Collect a random sample without saving it |
| `POST` | `/api/v1/analyses` | Collect, analyze, and save |
| `GET` | `/api/v1/analyses/{id}` | Saved metrics and insights |
| `GET` | `/api/v1/analyses/{id}/reviews` | Processed review records |
| `GET` | `/api/v1/analyses/{id}/reviews/download?format=json\|csv` | Raw data download |
| `GET` | `/api/v1/analyses/{id}/report` | Visual HTML report |

### Request contract

```json
{
  "app": "1459969523",
  "country": "us",
  "count": 100,
  "seed": 42,
  "use_llm": true
}
```

- `app` — numeric ID or a full `https://apps.apple.com/.../id...` URL;
- `country` — two-letter storefront code (`us`, `gb`, `ua`, `br`, …), default `us`;
- `count` — 1–100, default 100;
- `seed` — optional integer making the random sample reproducible;
- `use_llm` — default `true`; ignored with a warning when no key is configured.

### Error handling

Every error shares one shape:

```json
{ "error": { "code": "APP_NOT_FOUND", "message": "Application 123 was not found in the us storefront" } }
```

| Status | Code | Cause |
|---|---|---|
| 422 | `VALIDATION_ERROR` | Malformed request body |
| 422 | `INVALID_APP_IDENTIFIER` | Not a numeric ID or an Apple URL |
| 404 | `APP_NOT_FOUND` | App unavailable in that storefront |
| 404 | `ANALYSIS_NOT_FOUND` | Unknown analysis ID |
| 502 | `INVALID_SOURCE_RESPONSE` | Apple returned unparseable data |
| 503 | `REVIEW_SOURCE_UNAVAILABLE` | Timeout, rate limit, or Apple outage |

Two conditions are **non-fatal** and returned as `warnings` on a successful
response: `INSUFFICIENT_REVIEWS` (fewer reviews exist than requested) and
`LLM_UNAVAILABLE` (the insight layer could not run).

---

## Approach and design decisions

### Where the reviews come from

The iTunes Lookup API validates the app and supplies metadata. Review text
comes from the same-origin JSON endpoint that powers the public App Store
website. The older iTunes customer-review RSS feed was deliberately **not**
used: it returned empty feeds during live verification in September 2026.

That endpoint is not a documented, versioned developer contract, so all
assumptions about its shape are isolated in `AppleClient`; parse failures
surface as explicit `INVALID_SOURCE_RESPONSE` errors rather than silent empty
results, and the client retries HTTP 429 and 5xx with exponential backoff,
honouring `Retry-After`.

Reviews are storefront-specific. The collector reads up to ten pages (200 unique
records), deduplicates by review ID, then samples. **"100 random reviews"
therefore means 100 random reviews from the public window Apple exposes**, not
from the app's entire history — a limitation of the source, stated explicitly
rather than hidden.

### Two analysis layers, on purpose

| | Rule-based layer | LLM layer |
|---|---|---|
| Answers | *What* happened | *Why*, and what to do |
| Output | Ratings, sentiment split, frequent terms | Named themes, evidence, prioritized actions |
| Cost / latency | Free, milliseconds | ~1 API call per analysis |
| Determinism | Fully reproducible | Reproducible only in shape |
| Required | Always runs | Optional |

**Per-review sentiment stays deterministic.** VADER scores the cleaned text; the
final score is `0.5 × VADER + 0.5 × normalized rating`, which correctly handles
the common one-star review that opens with praise. Classification thresholds are
`≥ 0.05` positive, `≤ −0.05` negative, neutral otherwise. This runs on 100
reviews instantly, costs nothing, and gives identical results on every run —
properties worth more here than marginal accuracy.

**The LLM handles what rules genuinely cannot:** grouping free-text complaints
into themes nobody enumerated in advance, quoting the evidence for each, judging
severity, and turning that into prioritized actions. Hand-written keyword
dictionaries cannot discover a theme that is not already in the dictionary.

Both layers ship, and the rule-based one is never skipped — so the API keeps
working when the model is unavailable, rate-limited, or unfunded.

### LLM layer engineering

- **Structured output.** The response is constrained to a JSON schema generated
  from a Pydantic model (`messages.parse`), so there is no free-form parsing and
  no repair loop. Out-of-range severity or priority labels are coerced to safe
  defaults rather than trusted blindly.
- **Prompt injection is treated as a real threat.** Review bodies are
  attacker-controlled text. They are fenced between `<reviews>` markers, the
  system prompt states that everything inside is data and never instructions,
  and any marker occurring inside a review is neutralized before the prompt is
  assembled — so a review cannot close the block and issue commands. This is
  covered by a test.
- **Grounding.** The prompt requires verbatim quotes and counted occurrences,
  and instructs the model to state low confidence on thin samples instead of
  overstating. Evidence quotes are capped so a verbose response cannot bloat the
  stored payload.
- **Cost control.** The stable system prompt is marked cacheable; only the review
  block varies between requests. Samples are capped at `APP_LLM_MAX_REVIEWS`,
  keeping the lowest-rated reviews, which carry the signal.
- **Never fatal.** Authentication, rate-limit, connection, status, refusal, and
  empty-payload failures each degrade to an `LLM_UNAVAILABLE` warning on an
  otherwise complete response.

### Known limitations

- VADER is tuned for English; non-English reviews are scored unreliably. A
  production system would use a multilingual model or translate first.
- Collection happens inside the HTTP request. Sampling 200 reviews takes a few
  seconds; in production this belongs in a background queue.
- SQLite and local disk suit a single-node demo, not a scaled deployment.

---

## Sample report

`reports/nebula/` contains a reproducible analysis of 100 reviews sampled from
the 200 public Nebula reviews in the GB storefront:

| File | Contents |
|---|---|
| `REPORT.md` | Readable demo report |
| `report.html` | Visual report with rating and sentiment charts |
| `analysis.json` | Full metrics, keywords, and insights |
| `reviews.csv` | Processed review-level data |

Regenerate it — identical output for the same seed:

```bash
python scripts/collect_reviews.py 1459969523 --country gb --count 100 --seed 42 \
    --output reports/nebula
```

Or re-render from a stored SQLite analysis without re-fetching:

```bash
python scripts/export_analysis.py ANALYSIS_ID
```

---

## Tests and linting

```bash
pytest              # 55 tests
ruff check .
ruff format --check .
```

Tests never touch the network: Apple is stubbed at the HTTP transport layer with
`httpx.MockTransport`, and the Claude client is injected, so the suite is
deterministic, offline, and free to run.

| Area | Covered |
|---|---|
| Apple integration | Retries on 429/5xx, `Retry-After`, timeout exhaustion, non-retryable errors, 404 semantics per endpoint, malformed JSON, partial page parsing |
| Collection | Pagination, deduplication, seeded reproducibility, partial results |
| Analysis | Metrics, distributions, sentiment, keywords, issue areas, text cleaning |
| LLM layer | Success path, every failure mode, refusal, prompt-injection defense, label coercion, sampling cap |
| Reports | HTML and Markdown rendering, HTML escaping, empty-analysis handling |
| API | Every endpoint, error shapes, persistence round-trip, LLM wiring and degradation |

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs lint, format
check, and the suite on Python 3.11–3.14, boots the app to verify `/health` and
the OpenAPI schema, and builds the Docker image and health-checks the container.

Live Apple integration is verified by a manual smoke test through
`POST /api/v1/analyses` and the CLI.

## Docker

```bash
docker build -t app-store-review-analysis .
docker run --rm -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -v "$PWD/data:/data" \
  app-store-review-analysis
```

The image runs as a non-root user, honours `$PORT`, and declares a health check.

## Cloud deployment

Configuration is included for three platforms. Each needs a persistent volume at
`/data` for SQLite, and `ANTHROPIC_API_KEY` set as a secret if the LLM layer
should run.

```bash
# Render — render.yaml blueprint
render blueprint launch

# Fly.io — fly.toml
fly launch --no-deploy --copy-config
fly volumes create analysis_data --size 1
fly secrets set ANTHROPIC_API_KEY=sk-ant-...
fly deploy

# Heroku — Procfile
heroku create && heroku config:set ANTHROPIC_API_KEY=sk-ant-... && git push heroku main
```

## Project structure

```text
.github/workflows/ci.yml     # lint, format, tests on 3.11-3.14, Docker build
app/
├── api/
│   ├── reviews.py           # collection endpoint
│   └── analyses.py          # analysis, retrieval, download, report
├── schemas/reviews.py       # Pydantic request/response contracts
├── services/
│   ├── apple_client.py      # Apple integration, retries, normalization
│   ├── review_collector.py  # pagination, deduplication, sampling
│   ├── text_analysis.py     # cleaning, sentiment, metrics, keywords
│   ├── llm_insights.py      # Claude insight layer
│   └── report.py            # HTML and Markdown renderers
├── config.py                # environment-driven settings
├── exceptions.py            # typed errors mapped to HTTP responses
├── repository.py            # SQLite persistence
└── main.py                  # app factory, exception handlers
scripts/
├── collect_reviews.py       # standalone CLI for the full pipeline
└── export_analysis.py       # re-render a stored analysis
tests/                       # 55 unit, transport, and API tests
docs/                        # architecture notes, video script
reports/nebula/              # sample report artifacts
Dockerfile · render.yaml · fly.toml · Procfile · .env.example
```

## Production roadmap

- replace the undocumented web endpoint with a supported provider, or the App
  Store Connect API for first-party apps;
- move collection into a background queue with job status endpoints;
- add caching, authentication, and distributed rate limiting;
- move to PostgreSQL and object storage;
- evaluate the sentiment model against a labeled set and go multilingual;
- track theme prevalence over time to detect regressions after releases.
