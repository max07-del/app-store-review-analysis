# Architecture and design decisions

## Request flow

```text
Client
  → FastAPI route
  → input validation (Pydantic)
  → iTunes Lookup API                    validate app, read metadata
  → App Store web review endpoint        paginated, up to 10 pages
  → normalization and deduplication      by review ID
  → deterministic random sampling        seeded when a seed is supplied
  → text cleaning and VADER sentiment
  → aggregate metrics, phrases, issue taxonomy
  → Claude insight layer                 optional; themes + recommendations
  → SQLite persistence
  → JSON, CSV, HTML, or Markdown response
```

## Boundaries

| Module | Responsibility |
|---|---|
| `AppleClient` | Every assumption about Apple's response shapes, retries, error mapping |
| `ReviewCollector` | Page traversal, deduplication, sampling |
| `ReviewAnalyzer` | Pure synchronous transformation: cleaning, sentiment, metrics, keywords |
| `LLMInsightGenerator` | Claude integration; isolated, optional, never fatal |
| `AnalysisRepository` | Persistence of complete API models as JSON |
| `report` | HTML and Markdown rendering |

`ReviewAnalyzer` is deliberately pure and synchronous, so the whole analytical
core is testable without a network or an event loop. `LLMInsightGenerator` is
the only component that can fail without failing the request; its contract is
`(report, error)` where exactly one side is populated, which forces every caller
to handle degradation explicitly rather than by catching exceptions.

## Why two analysis layers

The rule-based layer answers *what* happened and must always be available:
deterministic, free, instant, and reproducible for a given seed. It is the
contract the API guarantees.

The LLM layer answers *why* and *what to do next* — clustering free-text
complaints into themes nobody enumerated in advance, quoting evidence, judging
severity. A keyword dictionary cannot discover a theme that is not already in
the dictionary; this is the part of the problem that genuinely needs a model.

Keeping them separate means an outage, rate limit, or missing key degrades the
response rather than breaking it, and it keeps the deterministic guarantees the
metrics endpoint makes.

## Treating review text as untrusted input

Review bodies are written by anonymous users and flow straight into a model
prompt, so they are handled as an injection vector:

1. Reviews are fenced between `<reviews>` and `</reviews>` markers.
2. The system prompt states that content inside the fence is data and must never
   be followed as instructions.
3. Any occurrence of those markers *inside* a review is rewritten before the
   prompt is assembled, so review text cannot close the block and escape into
   the instruction context.
4. Model output is re-validated: severity and priority labels outside the
   allowed sets are coerced to safe defaults, counts are clamped, and evidence
   quote lists are truncated.

Steps 3 and 4 are covered by tests — the defense is verified, not assumed.

## Structured output over parsing

The insight call uses `messages.parse` with a Pydantic schema, so the model is
constrained to valid JSON at generation time. There is no regex extraction, no
"repair the JSON" retry loop, and no free-form parsing to break when the model
phrases something differently. The internal payload models are separate from the
public API schemas, so the model's output shape and the API contract can evolve
independently.

## Cost and latency

The system prompt is stable across every request and marked cacheable; only the
review block varies, so repeated analyses read the instructions from cache. The
review sample sent to the model is capped and sorted by rating ascending — the
lowest-rated reviews carry the complaint signal, so the cap costs little
information. Sentiment stays on VADER rather than the model: 100 per-review
classifications would be the dominant cost and latency term for a job that a
lexicon does well enough and deterministically.

## Trade-offs accepted

**Undocumented source.** The public App Store website endpoint covers arbitrary
public apps but is not a versioned developer contract and can change without
notice. App Store Connect is stable but only serves apps the caller owns. For a
test task analyzing a third-party app, the web endpoint is the only option that
works; the risk is contained by isolating it behind `AppleClient` and failing
loudly.

**Synchronous collection.** Fetching 200 reviews takes a few seconds inside the
request. Acceptable for a demo, wrong for production — collection belongs in a
background queue with job-status endpoints.

**SQLite with whole-model JSON.** Right for a single-node demo and schema
evolution at this scale; would become PostgreSQL with proper columns and object
storage for artifacts in production.

**English-tuned sentiment.** VADER misreads non-English reviews. A production
system would evaluate a multilingual model against a labeled set rather than
assuming either option is better.
