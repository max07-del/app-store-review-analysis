# Architecture and design decisions

## Request flow

```text
Client
  -> FastAPI route
  -> input validation
  -> iTunes Lookup API
  -> App Store web review endpoint (paginated)
  -> normalization and deduplication
  -> deterministic random sampling when seed is supplied
  -> text cleaning and VADER sentiment
  -> aggregate metrics, phrases, and issue taxonomy
  -> SQLite persistence
  -> JSON, CSV, or HTML response
```

## Boundaries

`AppleClient` contains all assumptions about external response formats.
`ReviewCollector` owns sampling and page traversal. `ReviewAnalyzer` is a pure,
synchronous transformation that can be tested without the network. The
repository persists complete API models as JSON so schema evolution remains
simple for this test-task scale.

## Trade-offs

The public App Store website endpoint supports arbitrary public applications but
is not a documented developer API. App Store Connect is more stable but only
provides reviews for applications owned by the authenticated organization.

SQLite is appropriate for a local demonstration. A production deployment would
use a background queue, PostgreSQL, object storage, caching, and a scheduled
refresh policy.
