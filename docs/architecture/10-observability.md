# Observability

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **Scope.** Logging, request IDs, health/liveness/readiness, metrics, and diagnostics, including redaction rules for anything derived from secrets or provider internals. Observability fields (logs, metrics, health flags) must never become authoritative domain state unless explicitly promoted and documented as such.

> **Primary dependencies:** `06-runtime.md`

> **Status.** Unless a section explicitly states otherwise with a concrete repository reference (file path, commit, or CI run), everything below is **DESIGNED** or **PROPOSED** architecture, not implemented code. This document was migrated from the original `docs/architecture.md` monolith; section order is preserved from that document, numbering has been dropped in favor of descriptive headings, and some very long single sections in the monolith may appear here still bearing internal editorial framing (e.g. first-person design narration) that predates the doc-split.

## Sections in this document

- [Observability](#observability)
- [Health endpoint](#health-endpoint)
- [But don't call this release-ready yet](#but-don't-call-this-release-ready-yet)
- [Observability](#observability)
- [Metrics](#metrics)
- [Health versus readiness](#health-versus-readiness)
- [Source health](#source-health)
- [Request IDs](#request-ids)
- [Metrics do not become evidence of correctness](#metrics-do-not-become-evidence-of-correctness)
- [Source health versus candidate health](#source-health-versus-candidate-health)
- [Do not leak internal diagnostics through Stremio](#do-not-leak-internal-diagnostics-through-stremio)
- [This is where observability becomes evidence architecture](#this-is-where-observability-becomes-evidence-architecture)
- [Runtime health](#runtime-health)
- [Don't make readiness depend on all providers](#don't-make-readiness-depend-on-all-providers)
- [Reliability becomes measurable](#reliability-becomes-measurable)
- [Health state machine](#health-state-machine)
- [Source Health Must Not Become Authorization](#source-health-must-not-become-authorization)
- [Health Endpoints Are Separate](#health-endpoints-are-separate)
- [Liveness](#liveness)
- [Readiness](#readiness)
- [Observability Contract](#observability-contract)
- [Structured Logging](#structured-logging)
- [Metrics](#metrics)
- [Metadata observability](#metadata-observability)
- [Request-level correlation](#request-level-correlation)
- [Diagnostic CLI](#diagnostic-cli)

---

## Observability

For every resolution:

```text
request_id
media_id
media_type
source
start_time
duration_ms
result
candidate_count
failure_reason
```

Example:

```json
{
  "request_id": "01J...",
  "media": "tt1234567",
  "source": "public-domain",
  "duration_ms": 312,
  "result": "success",
  "candidate_count": 3
}
```

Never log:

```text
API passwords
API keys
authorization headers
user tokens
private source credentials
```

## Health endpoint

Separate addon health from source health.

```text
GET /health

{
  "status": "ok",
  "version": "1.0.0",
  "sources": {
    "public-domain": "healthy",
    "licensed-api": "degraded",
    "user-library": "disabled"
  }
}
```

The Stremio protocol doesn't require this endpoint; it is purely
operational.

## But don't call this release-ready yet

There are still important missing gates:

```text
G0  Domain contract              ✓
G1  Adapter contract             ✓
G2  Resolver                     ✓
G3  Validation                   ✓
G4  Policy                       ✓
G5  Dedup                        ✓
G6  Deterministic ranking        ✓
G7  Stremio boundary             ✓

G8  Timeout cancellation         TODO
G9  Concurrency limiter          TODO
G10 Circuit breaker              TODO
G11 Cache                        TODO
G12 SSRF boundary                TODO
G13 Rate limiting                TODO
G14 Observability                TODO
G15 Health endpoint              TODO
G16 Metadata                     TODO
G17 Subtitles                    TODO
G18 Deployment                   TODO
G19 Integration tests            TODO
G20 Release evidence             TODO
```

The next important piece is **not another source adapter**.

It is runtime reliability.

## Observability

Define structured events.

```ts
interface ResolutionEvent {
  readonly requestId: string;

  readonly mediaId: string;

  readonly mediaType: string;

  readonly adapterId?: string;

  readonly status: string;

  readonly durationMs: number;

  readonly candidateCount?: number;
}
```

Log JSON rather than prose.

Example:

```json
{
  "event": "adapter.resolve",
  "requestId": "01K...",
  "adapterId": "user-library",
  "status": "success",
  "durationMs": 184,
  "candidateCount": 2
}
```

## Metrics

Minimum metrics:

```text
resolver_requests_total
resolver_success_total
resolver_empty_total
resolver_failure_total

adapter_requests_total
adapter_success_total
adapter_timeout_total
adapter_rate_limit_total
adapter_error_total

adapter_latency_ms

cache_hit_total
cache_miss_total
cache_stale_total

candidate_seen_total
candidate_rejected_total
candidate_emitted_total
```

Dimensions should be bounded.

Good:

```text
adapter=user-library
```

Bad:

```text
url=https://random-user-generated-url...
```

Never allow unbounded user data to become metric labels.

## Health versus readiness

Use two concepts.

### Liveness

Is the process alive?

```text
GET /health/live
```

Response:

```json
{
  "status": "ok"
}
```

### Readiness

Can this instance serve requests?

```text
GET /health/ready
```

Example:

```json
{
  "status": "ready",
  "version": "0.1.0"
}
```

A temporary source failure should generally **not** make the entire
addon unready.

That's an important distinction.

## Source health

Expose operational state:

```json
{
  "sources": {
    "user-library": {
      "state": "healthy"
    },
    "public-domain": {
      "state": "degraded"
    }
  }
}
```

But don't leak:

```text
API credentials
private endpoint URLs
user account IDs
authorization headers
```

## Request IDs

Every inbound request gets:

```text
request_id
```

Then:

```text
Stremio request
    │
    ├── adapter A
    ├── adapter B
    └── adapter C
          │
          └── same request_id
```

This makes a production failure traceable:

```text
request 01K...
  adapter A: 180ms success
  adapter B: 3500ms timeout
  adapter C: 240ms success
```

## Metrics do not become evidence of correctness

This distinction matters:

```text
"source succeeded 99.2%"
```

is operational evidence.

It does **not** prove:

```text
"source is authorized."
```

Likewise:

```text
HTTP 200
```

doesn't prove:

```text
media exists
```

and:

```text
stream URL returned
```

doesn't prove:

```text
playback succeeds
```

Keep those semantics separate.

## Source health versus candidate health

Another important separation:

```text
Source health
    = provider operational condition

Candidate validity
    = this particular stream's properties
```

A healthy provider can return a broken candidate.

A degraded provider can still return a valid candidate.

Do not conflate them.

## Do not leak internal diagnostics through Stremio

This distinction matters.

Internal:

```text
adapter errors
URLs
request IDs
authorization evidence
timings
```

should not automatically become public Stremio metadata.

The addon protocol is a presentation boundary.

## This is where observability becomes evidence architecture

We can now formalize:

```text
Protocol result
    ≠ Resolver result
    ≠ Adapter result
    ≠ HTTP result
```

For example:

```text
HTTP: 200
Adapter: success
Resolver: partial
Policy: 3 candidates rejected
Final: 2 streams
```

That's much more useful than a single boolean:

```text
success: true
```

## Runtime health

Minimal native Node server:

```ts
import { createServer } from "node:http";

export function startHealthServer(port: number) {
  const server = createServer((req, res) => {
    if (req.url === "/health/live") {
      res.writeHead(200, {
        "content-type": "application/json"
      });

      res.end(JSON.stringify({ status: "ok" }));

      return;
    }

    if (req.url === "/health/ready") {
      res.writeHead(200, {
        "content-type": "application/json"
      });

      res.end(JSON.stringify({ status: "ready" }));

      return;
    }

    res.writeHead(404);
    res.end();
  });

  server.listen(port);

  return server;
}
```

## Don't make readiness depend on all providers

This would be a mistake:

```text
provider B down
     ↓
addon NOT READY
```

if provider B is optional.

Instead:

```text
required runtime dependency down
       ↓
NOT READY

optional source unavailable
       ↓
DEGRADED
```

That distinction matters enormously once you have multiple sources.

## Reliability becomes measurable

We should eventually maintain:

> **Renamed by `ADR-004` (2026-09-29):** this type was originally also
> called `SourceHealth`, colliding with a differently-shaped
> runtime-internal counters type of the same name in `04-providers.md`.
> It is renamed `SourceHealthSnapshot` here to make clear this is a
> derived, exportable observability view (fed by
> `SourceHealthCounters`), distinct from the runtime-internal counters
> and from `HealthResult`'s on-demand adapter probe. See
> [`ADR-004`](../decisions/ADR-004-health-model-layering.md).

```ts
export interface SourceHealthSnapshot {
  readonly adapterId: string;

  readonly requests: number;
  readonly successes: number;
  readonly empty: number;
  readonly failures: number;

  readonly timeoutCount: number;

  readonly consecutiveFailures: number;

  readonly latency: Readonly<{
    p50?: number;
    p95?: number;
    p99?: number;
  }>;
}
```

But **health must never silently mutate semantic eligibility**.

For example:

```text
authorization = authorized
health = poor
```

means:

```text
authorized but currently unhealthy
```

not:

```text
unauthorized
```

## Health state machine

```text
                 success
                     │
                     ▼
                ┌─────────┐
           ┌────│ CLOSED  │────┐
           │    └─────────┘    │
           │ failure            │
           │ threshold          │
           ▼                    │
       ┌─────────┐              │
       │  OPEN   │              │
       └────┬────┘              │
            │ cooldown          │
            ▼                   │
       ┌───────────┐            │
       │ HALF-OPEN │────────────┘
       └─────┬─────┘
             │ failure
             ▼
           OPEN
```

This state machine belongs to runtime health, not source policy.

## Source Health Must Not Become Authorization

Consider:

```text
Source A:
  authorization = authorized
  health = unhealthy
```

That means:

```text
authorized
+
temporarily unavailable
```

not:

```text
unauthorized
```

Likewise:

```text
authorization = unknown
health = excellent
```

must remain:

```text
not eligible
```

So the state space is at least:

```text
AUTHORIZATION
                ┌───────────────┐
                │ authorized    │
                │ unknown       │
                │ unauthorized  │
                └───────┬───────┘
                        │
                        +
                     HEALTH
                        │
                ┌───────┴────────┐
                │ healthy        │
                │ degraded       │
                │ unhealthy      │
                │ circuit-open   │
                └────────────────┘
```

These dimensions must not collapse into one boolean.

## Health Endpoints Are Separate

The application should expose:

```text
GET /health/live
GET /health/ready
```

but these are **deployment endpoints**, not Stremio protocol resources.

```text
Stremio
  │
  ├── /manifest.json
  └── /stream/...

Orchestrator
  │
  ├── /health/live
  └── /health/ready
```

Do not put health information into the Stremio manifest.

## Liveness

Liveness answers:

Is the process alive?

Minimal response:

```json
{
  "status": "ok"
}
```

It should not require:

```text
source A
source B
database
external API
```

Otherwise a dependency outage can cause a healthy process to be
restarted unnecessarily.

## Readiness

Readiness answers:

Should this process receive traffic?

For v0.1:

```text
configuration valid
+ application initialized
+ registry constructed
= ready
```

Optional source outages should not necessarily make the whole addon
unready.

Again:

```text
source unhealthy ≠ application unhealthy
```

## Observability Contract

Every request gets:

```text
request_id
```

Example:

```text
req_01J8...
```

Then:

```text
request
  │
  ├── parse
  ├── identity
  ├── route
  ├── source-a
  ├── source-b
  ├── validate
  ├── authorize
  ├── dedupe
  ├── rank
  └── present
```

All events carry the same request ID.

This gives us causal reconstruction:

```text
request_id
    ↓
all events
    ↓
resolution history
```

without pretending the final dashboard is itself the source of truth.

## Structured Logging

Use structured events:

```ts
logger.info(
  {
    requestId,
    media,
    sourceId,
    candidateCount,
    durationMs
  },
  "source resolution completed"
);
```

Avoid logs like:

```text
"source worked!"
```

because they discard machine-readable semantics.

The log should answer:

```text
WHO?
WHAT?
WHEN?
WHICH SOURCE?
WHICH MEDIA?
HOW LONG?
WHAT OUTCOME?
```

## Metrics

Derived metrics can include:

```text
resolution_requests_total
resolution_success_total
resolution_empty_total
resolution_partial_total
resolution_failed_total

source_requests_total{source}
source_failures_total{source}
source_timeouts_total{source}

resolution_duration_ms
source_duration_ms

circuit_open_total{source}
```

But remember:

```text
metrics = derived observations
```

not canonical evidence.

The event ledger remains the more fundamental fact layer.

## Metadata observability

Events:

```ts
interface MetadataEvent {
  readonly requestId: string;
  readonly providerId?: string;

  readonly stage: "selected" | "started" | "completed" | "failed" | "rejected";

  readonly outcome: "success" | "empty" | "partial" | "failure" | "ambiguous";

  readonly durationMs?: number;

  readonly fieldCount?: number;
}
```

Metrics:

```text
metadata_requests_total
metadata_success_total
metadata_empty_total
metadata_partial_total
metadata_failed_total
metadata_provider_failures_total
metadata_provider_duration_ms
metadata_conflicts_total
```

Again, these are derived observations.

They are not the metadata authority.

## Request-level correlation

One Stremio request may now generate:

```text
requestId = req-123

identity:
    observation-1
    observation-2

metadata:
    provider-A
    provider-B

source:
    owned-library

subtitles:
    provider-C
```

A single request receipt can connect them:

```text
ResolutionReceipt
    │
    ├── identity receipts
    ├── metadata receipts
    ├── source receipts
    └── subtitle receipts
```

This gives us an execution graph rather than a flat log stream.

## Diagnostic CLI

A particularly useful command set:

```text
media-platform identity inspect ...
media-platform metadata inspect ...
media-platform streams resolve ...
media-platform subtitles resolve ...
media-platform catalog inspect ...
media-platform provider list
media-platform provider inspect
media-platform evidence inspect
media-platform replay ...
```

This gives us a human-accessible interface to the same architecture.
