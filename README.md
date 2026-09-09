# App Store Review Analysis API

A local Python REST API that collects Apple App Store reviews for a specified
application, cleans and analyzes their text, calculates metrics, identifies
recurring negative themes, and produces downloadable data and an HTML report.

## Features

- accepts a numeric App Store ID or an `apps.apple.com` URL;
- verifies the app with Apple's iTunes Lookup API;
- collects up to 200 storefront-specific reviews and randomly selects up to 100;
- validates input, retries temporary upstream failures, and deduplicates reviews;
- cleans review text and performs positive/neutral/negative sentiment analysis;
- calculates average rating, rating distribution, and sentiment distribution;
- extracts frequent words and phrases from negative reviews;
- generates actionable product insights with evidence counts;
- stores completed analyses in SQLite;
- downloads processed reviews as JSON or CSV;
- renders a responsive HTML report with rating and sentiment visualizations;
- exposes interactive OpenAPI/Swagger documentation.

## Technology

- Python 3.11+
- FastAPI and Uvicorn
- HTTPX and Pydantic
- VADER Sentiment
- SQLite from the Python standard library
- pytest and Ruff

## Local setup

```bash
cd app-store-review-analysis
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn app.main:app --reload
```

Windows activation command:

```powershell
.venv\Scripts\activate
```

After startup:

- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>
- health check: <http://127.0.0.1:8000/health>

## Main workflow

Create a complete analysis:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyses \
  -H 'Content-Type: application/json' \
  -d '{
    "app": "https://apps.apple.com/us/app/nebula-horoscope-astrology/id1459969523",
    "country": "us",
    "count": 100,
    "seed": 42
  }'
```

The response contains `analysis_id`. Use it in subsequent requests:

```bash
curl http://127.0.0.1:8000/api/v1/analyses/ANALYSIS_ID
curl http://127.0.0.1:8000/api/v1/analyses/ANALYSIS_ID/reviews
curl -OJ 'http://127.0.0.1:8000/api/v1/analyses/ANALYSIS_ID/reviews/download?format=csv'
```

Open the visual report in a browser:

```text
http://127.0.0.1:8000/api/v1/analyses/ANALYSIS_ID/report
```

To collect raw reviews without running NLP:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/reviews/collect \
  -H 'Content-Type: application/json' \
  -d '{"app":"1459969523","country":"us","count":100,"seed":42}'
```

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/reviews/collect` | Collect a random sample without saving it |
| `POST` | `/api/v1/analyses` | Collect, analyze, and save reviews |
| `GET` | `/api/v1/analyses/{id}` | Return saved metrics and insights |
| `GET` | `/api/v1/analyses/{id}/reviews` | Return processed review records |
| `GET` | `/api/v1/analyses/{id}/reviews/download?format=json` | Download JSON |
| `GET` | `/api/v1/analyses/{id}/reviews/download?format=csv` | Download CSV |
| `GET` | `/api/v1/analyses/{id}/report` | Render visual HTML report |

## Input contract

```json
{
  "app": "1459969523",
  "country": "us",
  "count": 100,
  "seed": 42
}
```

- `app`: numeric ID or full `https://apps.apple.com/.../id...` URL;
- `country`: two-letter storefront code such as `us`, `gb`, `ua`, or `br`;
- `count`: 1–100, default 100;
- `seed`: optional integer that makes random sampling reproducible.

## Error handling

Errors have one consistent shape:

```json
{
  "error": {
    "code": "APP_NOT_FOUND",
    "message": "Application 123 was not found in the us storefront"
  }
}
```

Handled cases include:

- `422 INVALID_APP_IDENTIFIER`: invalid ID or non-Apple URL;
- `404 APP_NOT_FOUND`: app is unavailable in the requested storefront;
- `404 ANALYSIS_NOT_FOUND`: saved analysis does not exist;
- `502 INVALID_SOURCE_RESPONSE`: Apple changed or corrupted its response;
- `503 REVIEW_SOURCE_UNAVAILABLE`: timeout, rate limit, network error, or Apple outage;
- partial `200/201` response with `INSUFFICIENT_REVIEWS` when fewer reviews exist.

## Data collection decisions

The iTunes Lookup API is used for app validation and metadata. Review text is
read from the same-origin JSON endpoint used by the public App Store website.
The older iTunes customer-review RSS feed was deliberately not used because it
returned empty feeds during live verification in September 2026.

The web endpoint is not a documented, versioned public developer contract. Its
parsing is isolated in `AppleClient`, failures are surfaced explicitly, and the
client retries HTTP 429 and server errors with exponential backoff.

Reviews are storefront-specific. The collector reads up to ten pages (up to 200
unique records), deduplicates by review ID, and samples the requested number.
Consequently, "100 random reviews" means 100 random reviews from the available
public window, not from the application's complete lifetime history.

## NLP approach and limitations

VADER produces a text compound score. To handle mixed reviews such as a
one-star complaint that begins with praise, the final score combines 50% VADER
text signal with 50% normalized star-rating signal. It is classified as:

- `>= 0.05`: positive;
- `<= -0.05`: negative;
- otherwise: neutral.

Frequent negative terms are extracted from normalized unigrams and bigrams.
Actionable insights use transparent issue dictionaries for stability, accounts,
support, billing, privacy, ads, and usability, and include the number and share
of negative reviews supporting each recommendation.

VADER is optimized for English. For a production multilingual system, replace
it with a multilingual transformer model or translate reviews before analysis.
The current implementation is intentionally lightweight and easy to run locally.

## Persistence

SQLite data is stored at `data/app_store_reviews.db`. Override it when needed:

```bash
APP_DATABASE_PATH=/tmp/reviews.db uvicorn app.main:app --reload
```

## Tests and linting

```bash
pytest
ruff check .
```

Tests do not call Apple and therefore remain deterministic. A manual smoke test
through `POST /api/v1/analyses` verifies the live integration.

## Included demo report

`reports/nebula/` contains a reproducible analysis of 100 reviews sampled from
200 public Nebula reviews in the GB storefront:

- `analysis.json`: metrics, keywords, and insights;
- `reviews.csv`: processed review-level data;
- `report.html`: visual report that can be opened directly in a browser.

The report can be regenerated from a saved SQLite analysis:

```bash
python scripts/export_analysis.py ANALYSIS_ID
```

## Docker

```bash
docker build -t app-store-review-analysis .
docker run --rm -p 8000:8000 app-store-review-analysis
```

## Project structure

```text
app/
├── api/                 # HTTP routes
├── schemas/             # Pydantic request/response contracts
├── services/
│   ├── apple_client.py  # Apple integration and normalization
│   ├── review_collector.py
│   ├── text_analysis.py # sentiment, metrics, keywords, insights
│   └── report.py        # HTML visualization
├── exceptions.py
├── repository.py        # SQLite persistence
└── main.py
tests/                   # unit and API tests
docs/                    # design notes and video script
reports/                 # sample report artifacts
scripts/                 # repeatable report export utility
```

## Suggested production improvements

- replace the undocumented web endpoint with a supported provider or App Store
  Connect API when analyzing applications owned by the organization;
- run collection jobs in a queue rather than holding an HTTP request open;
- add caching and stricter distributed rate limiting;
- use PostgreSQL and object storage;
- use a multilingual sentiment/topic model and evaluate it on labeled data;
- add authentication, observability, and scheduled refreshes.
