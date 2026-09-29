# Testing & Verification

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **Scope.** Unit, contract, integration, protocol, property, failure, and replay testing strategy, plus the CI gates (`GATE-*`) and release-gate checklists (R1–R4, V0.1) referenced throughout the rest of the documentation set. Governing rule: **no evidence, no VERIFIED claim** — local inspection or design review is not the same as an actual CI execution, and this document must never claim a gate passed without a real run.

> **Primary dependencies:** `*`

> **Status.** Unless a section explicitly states otherwise with a concrete repository reference (file path, commit, or CI run), everything below is **DESIGNED** or **PROPOSED** architecture, not implemented code. This document was migrated from the original `docs/architecture.md` monolith; section order is preserved from that document, numbering has been dropped in favor of descriptive headings, and some very long single sections in the monolith may appear here still bearing internal editorial framing (e.g. first-person design narration) that predates the doc-split.

## Sections in this document

- [Testing strategy](#testing-strategy)
- [Property tests](#property-tests)
- [Conformance tests](#conformance-tests)
- [Golden test](#golden-test)
- [Security test matrix](#security-test-matrix)
- [The next implementation gate](#the-next-implementation-gate)
- [Test adapter](#test-adapter)
- [Resolver test](#resolver-test)
- [Add the failure test](#add-the-failure-test)
- [Add the authorization test](#add-the-authorization-test)
- [Release gate R1](#release-gate-r1)
- [Safe HTTP + cache + Stremio conformance](#safe-http-+-cache-+-stremio-conformance)
- [End-to-end test](#end-to-end-test)
- [Failure isolation test](#failure-isolation-test)
- [Runtime test matrix](#runtime-test-matrix)
- [Conformance properties](#conformance-properties)
- [R2 release gate](#r2-release-gate)
- [R3 release gate](#r3-release-gate)
- [Test: episode isolation](#test-episode-isolation)
- [Stremio integration test](#stremio-integration-test)
- [Manifest contract test](#manifest-contract-test)
- [Stream contract test](#stream-contract-test)
- [Contract fixtures](#contract-fixtures)
- [Golden protocol fixtures](#golden-protocol-fixtures)
- [Canonical JSON](#canonical-json)
- [Adapter conformance suite](#adapter-conformance-suite)
- [R4 — Protocol Conformance Gate](#r4-—-protocol-conformance-gate)
- [Test the vertical slice before adding anything else](#test-the-vertical-slice-before-adding-anything-else)
- [Determinism test](#determinism-test)
- [Timeout test](#timeout-test)
- [Concurrency test](#concurrency-test)
- [Integration test](#integration-test)
- [CI becomes execution authority](#ci-becomes-execution-authority)
- [First CI workflow](#first-ci-workflow)
- [The first genuine release gate](#the-first-genuine-release-gate)
- [First protocol integration test](#first-protocol-integration-test)
- [Then test the rejection path](#then-test-the-rejection-path)
- [Source adapter conformance suite](#source-adapter-conformance-suite)
- [Next gate: executable evidence](#next-gate-executable-evidence)
- [Verification Matrix](#verification-matrix)
- [Conformance Harness](#conformance-harness)
- [Parser Conformance](#parser-conformance)
- [Authorization Tests](#authorization-tests)
- [Deduplication Test](#deduplication-test)
- [Deterministic Ranking Test](#deterministic-ranking-test)
- [Resolver Partial-Success Test](#resolver-partial-success-test)
- [Timeout Test](#timeout-test)
- [Semaphore Test](#semaphore-test)
- [Circuit Breaker Tests](#circuit-breaker-tests)
- [Adapter Conformance](#adapter-conformance)
- [Manifest Test](#manifest-test)
- [Protocol Handler Test](#protocol-handler-test)
- [HTTP-Level Test](#http-level-test)
- [Important: Do Not Test Only the Handler](#important-do-not-test-only-the-handler)
- [First Release Gate](#first-release-gate)
- [CI Becomes the Authority](#ci-becomes-the-authority)
- [Container Gate](#container-gate)
- [Reconciliation Tests](#reconciliation-tests)
- [Identity Layer Release Gate](#identity-layer-release-gate)
- [Adapter conformance suite v2](#adapter-conformance-suite-v2)
- [New release gate: `GATE-SOURCE-ADMISSION-01`](#new-release-gate-gate-source-admission-01)
- [New runtime gate](#new-runtime-gate)
- [End-to-end example](#end-to-end-example)
- [New tests](#new-tests)
- [Integration test that actually matters](#integration-test-that-actually-matters)
- [Metadata release gate](#metadata-release-gate)
- [New conformance layer](#new-conformance-layer)
- [New release gate](#new-release-gate)
- [Updated release gates](#updated-release-gates)
- [Contract testing](#contract-testing)
- [Stremio becomes a compatibility test](#stremio-becomes-a-compatibility-test)
- [Control-plane gate](#control-plane-gate)

---

## Testing strategy

This project benefits enormously from contract testing.

### Manifest

```text
manifest.json
    │
    ├── valid ID
    ├── valid version
    ├── resources
    ├── types
    └── catalogs
```

### Resolver

```text
given:
  A → 1080p
  B → 720p
  C → timeout

expect:
  A
  B

not:
  C
```

### Dedup

```text
A → URL X
B → URL X
C → URL Y

expect:
  X
  Y
```

### Identity

```text
movie: tt123

series: tt123:2:7
```

### Failure

```text
all adapters fail
       ↓
valid Stremio response
       ↓
streams: []
```

### Partial success

```text
A → success
B → timeout
C → malformed

expect: A
```

## Property tests

There are useful invariants here.

```text
Invariant 1
Every emitted stream must have a valid URL.
```

```text
Invariant 2
No unauthorized candidate can reach the Stremio boundary.
```

```text
Invariant 3
Deduplication never produces duplicate canonical URLs.
```

```text
Invariant 4
A failing adapter cannot prevent successful adapters from producing results.
```

```text
Invariant 5
Ranking never changes eligibility.
```

That last one is important:

```text
eligibility
    ↓
  filter

ranking
    ↓
 ordering
```

not:

```text
ranking
    ↓
somehow decide legality
```

## Conformance tests

Now we can make the architecture enforceable.

### Adapter contract

Every adapter must satisfy:

```ts
describe("SourceAdapter contract", () => {
  it("has a stable identifier");

  it("returns candidates matching requested media");

  it("does not emit malformed URLs");

  it("does not throw on empty results");

  it("respects AbortSignal");

  it("does not mutate the MediaRef");
});
```

### Resolver contract

```ts
describe("resolver", () => {
  it("isolates source failures");

  it("deduplicates candidates");

  it("never emits unauthorized candidates");

  it("produces deterministic ordering");

  it("preserves partial success");
});
```

## Golden test

Create:

```text
test/fixtures/
└── resolution-case-001.json
```

```json
{
  "media": {
    "type": "movie",
    "id": "tt0000000"
  },

  "sources": [
    {
      "source": "a",
      "resolution": [1920, 1080],
      "authorized": true
    },
    {
      "source": "b",
      "resolution": [1280, 720],
      "authorized": true
    },
    {
      "source": "c",
      "resolution": [3840, 2160],
      "authorized": false
    }
  ],

  "expected": ["a", "b"]
}
```

This gives you a regression oracle.

The 4K source should not suddenly appear because somebody changed the
ranking implementation.

## Security test matrix

```text
SSRF
  ├── localhost
  ├── 127.0.0.1
  ├── private IPv4
  ├── IPv6 loopback
  ├── IPv6 private ranges
  ├── DNS rebinding
  └── redirect-to-private-address

URL parser
  ├── malformed URL
  ├── unsupported scheme
  ├── credentials embedded in URL
  └── oversized URL

HTTP
  ├── timeout
  ├── redirect chain
  ├── huge response
  └── invalid content-type
```

Especially important if you eventually allow users to configure
arbitrary source endpoints.

## The next implementation gate

I would now freeze the following contract before writing the remaining
adapters:

```text
MEDIA IDENTITY
    ↓
SOURCE ADAPTER
    ↓
SOURCE CANDIDATE
    ↓
ADAPTER EXECUTION
    ↓
NORMALIZATION
    ↓
VALIDATION
    ↓
ELIGIBILITY
    ↓
POLICY
    ↓
DEDUPLICATION
    ↓
RANKING
    ↓
STREMIO STREAM
```

And explicitly prohibit these shortcuts:

```text
Candidate → Stream                 NO
Adapter → Stream                   NO
Ranking → Authorization            NO
Empty[] → "source unavailable"     NO
Unknown → Authorized               NO
Title string → Media identity      NO
Provider-specific fields → Core    NO
```

That gives us a stable foundation for the next layer: **a complete
runnable TypeScript repository, including `package.json`, `tsconfig`,
source registry, resolver, Stremio HTTP server, test suite, Docker
setup, health/metrics, and a first legitimate source adapter**.

## Test adapter

Before connecting any external service, create:

```ts
// test/fixtures/adapter.ts

import type { SourceAdapter } from "../../src/adapters/interface.js";

export function fakeAdapter(candidates: any[]): SourceAdapter {
  return {
    id: "test",
    name: "Test",

    supports() {
      return true;
    },

    async resolve() {
      return candidates;
    }
  };
}
```

Now the resolver can be tested independently.

## Resolver test

```ts
import { describe, expect, it } from "vitest";

import { SourceRegistry } from "../src/adapters/registry.js";

import { resolveMedia } from "../src/resolver/resolver.js";

describe("resolver", () => {
  it("aggregates successful sources", async () => {
    const registry = new SourceRegistry();

    registry.register(
      fakeAdapter([
        makeCandidate({
          sourceId: "a",
          width: 1920,
          height: 1080
        })
      ])
    );

    const result = await resolveMedia(
      {
        type: "movie",
        id: "tt0000000"
      },
      registry,
      testContext()
    );

    expect(result.candidates).toHaveLength(1);
  });
});
```

## Add the failure test

```ts
it("preserves partial success", async () => {
  const registry = new SourceRegistry();

  registry.register(
    fakeAdapter([
      makeCandidate({
        sourceId: "working",
        width: 1920,
        height: 1080
      })
    ])
  );

  registry.register({
    id: "broken",
    name: "Broken",

    supports() {
      return true;
    },

    async resolve() {
      throw new Error("provider_failure");
    }
  });

  const result = await resolveMedia(movie(), registry, testContext());

  expect(result.candidates).toHaveLength(1);

  expect(
    result.executions.find(x => x.adapterId === "broken")?.status
  ).toBe("error");
});
```

That test captures one of the central architectural promises.

## Add the authorization test

```ts
it("does not emit unauthorized candidates", async () => {
  const registry = new SourceRegistry();

  registry.register(
    fakeAdapter([
      makeCandidate({
        sourceId: "blocked",
        authorization: {
          status: "unknown"
        }
      }),

      makeCandidate({
        sourceId: "allowed",
        authorization: {
          status: "authorized"
        }
      })
    ])
  );

  const result = await resolveMedia(movie(), registry, testContext());

  expect(result.candidates.map(x => x.sourceId)).toEqual(["allowed"]);
});
```

This is a release-gate test, not merely a unit test.

## Release gate R1

The first meaningful implementation milestone is now:

```text
R1 — Aggregation Kernel
────────────────────────────────

[✓] MediaRef
[✓] SourceCandidate
[✓] SourceAdapter
[✓] Registry
[✓] Validation
[✓] Policy
[✓] Dedup
[✓] Deterministic ranking
[✓] Failure isolation

[✓] AbortSignal propagation
[✓] Timeout
[✓] Bounded concurrency
[✓] Rate limiting
[✓] Circuit breaker

[ ] Persistent cache
[ ] Safe HTTP client
[ ] SSRF tests
[ ] Metrics
[ ] Health endpoints
[ ] Stremio integration test
[ ] Container smoke test
```

The next gate should therefore be **the safe HTTP/cache subsystem plus
the complete Stremio protocol test harness**.

That is where we can test the full chain:

```text
Stremio request
      ↓
parse
      ↓
resolver
      ↓
adapter
      ↓
safe HTTP
      ↓
candidate
      ↓
policy
      ↓
dedup
      ↓
rank
      ↓
Stremio Stream[]
```

and establish the first genuine **end-to-end conformance baseline**.

## Safe HTTP + cache + Stremio conformance

The next layer closes the gap between the abstract resolver and an
actually deployable addon.

The important boundary is:

```text
                 ┌─────────────────────┐
                 │    Stremio request   │
                 └──────────┬──────────┘
                             │
                             ▼
                     MediaRef parser
                             │
                             ▼
                        Resolver
                             │
                 ┌───────────┴───────────┐
                 │                       │
                 ▼                       ▼
              Cache                 Source runtime
                                         │
                                ┌────────┼────────┐
                                ▼        ▼        ▼
                              limit   breaker   timeout
                                         │
                                         ▼
                                   Safe HTTP
                                         │
                                         ▼
                                   Source API
```

The critical principle remains:

**The HTTP client is a trust boundary, not merely a convenience wrapper
around `fetch()`.**

## End-to-end test

Now construct the first real conformance test.

```ts
it("resolves an eligible candidate into a Stremio stream", async () => {
  const adapter = new FakeAdapter([
    makeCandidate({
      sourceId: "fixture",
      authorization: {
        status: "authorized"
      },
      capabilities: {
        directPlayback: true
      }
    })
  ]);

  registry.register(adapter);

  const result = await resolver.resolve({
    type: "movie",
    id: "tt1234567"
  });

  expect(result.candidates).toHaveLength(1);

  const stream = toStremioStream(result.candidates[0]);

  expect(stream.url).toBe("https://example.test/video.mp4");
});
```

This test proves the **kernel contract**, not real-world source
availability.

## Failure isolation test

```ts
it("does not fail the entire resolution when one adapter times out", async () => {
  registry.register(new TimeoutAdapter());

  registry.register(new SuccessfulAdapter());

  const result = await resolver.resolve(media);

  expect(result.candidates.length).toBeGreaterThan(0);

  expect(result.executions.some(x => x.status === "timeout")).toBe(true);
});
```

This is a critical invariant.

## Runtime test matrix

Freeze this matrix:

| Condition | Expected status |
| --- | --- |
| Valid response | `success` |
| Valid response, zero candidates | `empty` |
| Timeout | `timeout` |
| Parent cancellation | `aborted` |
| Rate limit exhausted | `rate_limited` |
| Breaker open | `circuit_open` |
| Invalid JSON | `invalid_response` |
| HTTP 500 | `http_error` |
| Connection failure | `network_error` |
| Unexpected exception | `error` |

This is far better than:

```text
success / error
```

because the latter destroys operational evidence.

## Conformance properties

The resolver should now satisfy these invariants:

```text
P1  Unauthorized candidates are never emitted.

P2  Unknown authorization is never treated as authorized.

P3  Adapter failure does not erase successful results
    from other adapters.

P4  Timeout cancels the underlying operation.

P5  Global cancellation propagates to active adapters.

P6  Concurrency never exceeds configured capacity.

P7  Circuit-open sources are not executed.

P8  Ranking is deterministic.

P9  Deduplication is deterministic.

P10 Stremio mapping performs no source resolution.

P11 Cached candidates pass through current policy.

P12 Stale cache is distinguishable from live data.

P13 Arbitrary provider URLs are not automatically proxied
    through the addon server.
```

These are more valuable than a large collection of superficial tests.

## R2 release gate

```text
R2 — Safe Resolution Runtime
────────────────────────────────────

DOMAIN
[✓] MediaRef
[✓] SourceCandidate
[✓] Failure model

ADAPTER
[✓] SourceAdapter
[✓] Registry
[✓] External schema validation

RESOLUTION
[✓] Parallel execution
[✓] Failure isolation
[✓] Policy
[✓] Dedup
[✓] Deterministic ranking

RUNTIME
[✓] Abort propagation
[✓] Per-source timeout
[✓] Global timeout
[✓] Concurrency limiter
[✓] Rate limiter
[✓] Circuit breaker
[✓] In-flight deduplication

HTTP
[✓] URL protocol validation
[✓] Credential rejection
[✓] Response-size boundary
[✓] Content-type validation
[✓] Redirect policy
[ ] Production-grade DNS/IP binding

CACHE
[✓] Candidate cache abstraction
[✓] Fresh/stale/dead semantics
[✓] Versioned cache keys
[✓] Current-policy revalidation

STREMIO
[✓] ID parser
[✓] Candidate mapper
[✓] Empty-result behavior
[✓] Protocol boundary

OBSERVABILITY
[✓] Request IDs
[✓] Structured events
[✓] Basic metrics
[✓] Liveness
[✓] Readiness

TESTING
[✓] Failure isolation
[✓] Policy invariant
[✓] Ranking determinism
[✓] Runtime status matrix
[ ] Full integration suite
[ ] Container smoke test
[ ] CI release evidence
```

### Status

**R2 = PARTIALLY VERIFIED / implementation blueprint**

It is not yet a release claim because the actual repository, tests, CI
execution, and container behavior have not been executed here.

The next major layer is **metadata + subtitles + catalog identity
resolution**, because source aggregation is only useful when the addon
can reliably connect:

```text
Stremio catalog item
        ↓
IMDb/TMDB/etc. identity
        ↓
movie / series / season / episode
        ↓
source query
        ↓
eligible streams
        ↓
subtitle tracks
```

That layer introduces a second major problem: **identity resolution is
not the same thing as source discovery**, and conflating them will
eventually produce incorrect matches.

## R3 release gate

```text
R3 — Identity + Resource Model
────────────────────────────────────

IDENTITY
[✓] Namespaced IDs
[✓] Canonical media
[✓] Movie identity
[✓] Episode identity
[✓] Identity evidence
[✓] Ambiguity preservation
[✓] Identity cache semantics

METADATA
[✓] Catalog model
[✓] Meta model
[ ] Metadata adapter implementation

STREAMS
[✓] Candidate model
[✓] Policy
[✓] Ranking
[✓] Stremio mapper

SUBTITLES
[✓] Independent candidate model
[✓] Language semantics
[✓] Policy boundary
[✓] Ranking design
[ ] Adapter implementation
[ ] Stremio subtitle integration

SECURITY
[✓] Server-side proxy avoided by default
[✓] URL credentials rejected
[✓] Redirect boundary defined
[✓] Response-size boundary
[ ] DNS/IP binding implementation

TESTING
[✓] Identity invariants defined
[✓] Stream invariants defined
[ ] Subtitle conformance tests
[ ] Metadata conformance tests
[ ] Full Stremio integration
```

**Status: PROVISIONAL architecture; not execution-verified.**

The next step is to build the **actual Stremio addon surface**:
manifest generation, `/manifest.json`, catalog/meta/stream/subtitle
handlers, deterministic request parsing, and an integration test that
treats Stremio itself as the external protocol contract.

## Test: episode isolation

```ts
it("preserves season and episode", async () => {
  const adapter = new RecordingAdapter();

  registry.register(adapter);

  await resolver.resolve({
    type: "series",
    id: "tt1234567",
    season: 2,
    episode: 7
  });

  expect(adapter.lastQuery).toMatchObject({
    media: {
      season: 2,
      episode: 7
    }
  });
});
```

This catches a surprisingly damaging class of bugs.

## Stremio integration test

Now don't test only internal functions.

Test the actual HTTP boundary.

Conceptually:

```text
test
    ↓
start addon server
    ↓
GET /manifest.json
    ↓
GET /stream/movie/...
    ↓
parse JSON
    ↓
assert protocol shape
```

This is the first test that actually validates:

```text
our code + SDK + HTTP server + manifest + handler
```

## Manifest contract test

```ts
it("serves a valid manifest", async () => {
  const response = await fetch(`${baseUrl}/manifest.json`);

  expect(response.status).toBe(200);

  const manifest = await response.json();

  expect(manifest.id).toBeTruthy();

  expect(manifest.version).toBeTruthy();

  expect(manifest.resources).toContain("stream");

  expect(manifest.types).toContain("movie");
});
```

This should become a release gate.

## Stream contract test

```ts
it("returns Stremio-compatible streams", async () => {
  const response = await fetch(`${baseUrl}/stream/movie/tt1234567.json`);

  expect(response.status).toBe(200);

  const body = await response.json();

  expect(Array.isArray(body.streams)).toBe(true);

  for (const stream of body.streams) {
    expect(typeof stream.url).toBe("string");
  }
});
```

The test deliberately avoids requiring a particular real source.

It tests the protocol contract.

## Contract fixtures

Create:

```text
test/
└── fixtures/
    ├── movie.json
    ├── series.json
    ├── candidate.json
    ├── subtitle.json
    └── manifest.json
```

Fixtures should represent:

```text
valid
invalid
ambiguous
empty
partial
```

not just happy paths.

## Golden protocol fixtures

A powerful approach is:

```text
input fixture
      ↓
resolver
      ↓
normalized output
      ↓
canonical JSON
      ↓
compare
```

For deterministic outputs, this gives a simple regression mechanism.

But don't snapshot volatile values such as:

```text
timestamps
request IDs
latency
```

unless explicitly normalized.

## Canonical JSON

For protocol fixtures, stable serialization helps.

The test should normalize:

```text
object key order
dynamic timestamps
IDs
```

before comparison.

For stronger artifact evidence, use canonical JSON rather than relying
on incidental JavaScript object ordering.

## Adapter conformance suite

Every adapter should pass the same tests.

Define:

```ts
interface AdapterFactory {
  create(): SourceAdapter;
}
```

Then a shared suite:

```text
describeAdapterContract(createAdapter)
```

Tests:

```text
supports()
resolve()
timeout
abort
malformed response
empty result
authorization status
candidate normalization
```

Now adding a source means:

```text
implement adapter + pass conformance suite
```

rather than inventing bespoke tests.

## R4 — Protocol Conformance Gate

```text
R4
────────────────────────────────────────

MANIFEST
[✓] Static capability declaration
[✓] Versioned
[✓] Type declarations
[ ] SDK-version compile verification

PARSING
[✓] Movie IDs
[✓] Series IDs
[✓] Season/episode preservation
[✓] Invalid input rejection

STREAM
[✓] Handler boundary
[✓] Candidate → stream mapping
[✓] Empty result semantics
[ ] Live SDK integration test

CATALOG
[✓] Contract
[ ] Provider implementation

META
[✓] Contract
[ ] Provider implementation

SUBTITLE
[✓] Domain model
[✓] Resolver architecture
[ ] Protocol implementation

ERRORS
[✓] Internal failure taxonomy
[✓] Partial/empty/failed distinction

SECURITY
[✓] No arbitrary source registration
[✓] No automatic media proxy
[✓] Protocol/domain separation

TESTING
[✓] Unit contracts
[✓] End-to-end test design
[ ] Actual CI execution
[ ] Container smoke test
```

### Status

**R4 = ARCHITECTURALLY DEFINED / NOT EXECUTION-VERIFIED**

The next major step is no longer another abstraction layer. It is the
**actual executable reference implementation**:

```text
package.json
tsconfig.json
src/index.ts
manifest
domain
runtime
resolver
one explicitly authorized/public-domain adapter
tests
Dockerfile
compose.yaml
CI
```

Then we can freeze the first **`v0.1.0-conformance` baseline**, run the
entire suite, and only after evidence exists begin adding additional
source adapters.

## Test the vertical slice before adding anything else

### Parser tests

```ts
it("parses a movie", () => {
  expect(parseMediaRef("movie", "tt1234567")).toEqual({
    type: "movie",
    id: "tt1234567"
  });
});
```

Series:

```ts
it("parses an episode", () => {
  expect(parseMediaRef("series", "tt1234567:2:7")).toEqual({
    type: "series",
    id: "tt1234567",
    season: 2,
    episode: 7
  });
});
```

Invalid:

```ts
it("rejects malformed episode IDs", () => {
  expect(() => parseMediaRef("series", "tt1234567:abc:7")).toThrow(
    "invalid_episode_coordinates"
  );
});
```

## Determinism test

Run the same input many times:

```ts
it("produces deterministic ranking", () => {
  const candidates = [
    makeCandidate({ sourceId: "z" }),

    makeCandidate({ sourceId: "a" }),

    makeCandidate({ sourceId: "m" })
  ];

  const first = rankCandidates(candidates);

  for (let i = 0; i < 100; i++) {
    expect(rankCandidates(candidates)).toEqual(first);
  }
});
```

The stronger future version should randomize input order as well.

## Timeout test

```ts
it("aborts a slow adapter", async () => {
  const adapter: SourceAdapter = {
    id: "slow",
    name: "Slow",
    supports: () => true,
    resolve: async (_media, ctx) => {
      await new Promise<void>((_, reject) => {
        const timer = setTimeout(() => {}, 10_000);

        ctx.signal.addEventListener(
          "abort",
          () => {
            clearTimeout(timer);

            reject(new Error("aborted"));
          },
          { once: true }
        );
      });

      return [];
    }
  };

  // Resolver test...
});
```

The exact test implementation should avoid hanging the test runner,
but the invariant is:

```text
timeout
   →
AbortSignal
   →
underlying operation stops
```

## Concurrency test

Create 20 fake adapters.

Each increments:

```ts
active++;
maxActive = Math.max(maxActive, active);
```

and sleeps briefly.

Configure:

```text
capacity = 4
```

Then assert:

```ts
expect(maxActive).toBeLessThanOrEqual(4);
```

This converts a runtime design assumption into executable evidence.

## Integration test

The final test should be:

```text
npm run check
       │
       ├── typecheck
       ├── unit tests
       └── build
```

Then:

```text
start built server
       │
       ├── GET /manifest.json
       │
       └── GET /stream/movie/...
```

This is the first point where:

```text
"the code compiles"
```

and:

```text
"the addon actually speaks its protocol"
```

are independently demonstrated.

## CI becomes execution authority

Given the evidence rule:

**NO EVIDENCE → NO VERIFIED CLAIM**

the repository should eventually have:

```text
CI
│
├── npm ci
├── npm run typecheck
├── npm test
├── npm run build
├── container build
└── integration smoke test
```

Only CI results should create:

```text
VERIFIED
```

status.

A local assistant-generated source tree is merely:

```text
PROVISIONAL
```

until execution evidence exists.

## First CI workflow

```yaml
name: conformance

on:
  push:
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm

      - run: npm ci
      - run: npm run typecheck
      - run: npm test
      - run: npm run build
```

The exact action versions should also be frozen through the repository
lock/configuration process.

## The first genuine release gate

The project should now have:

```text
G0  Domain contracts                 ✓
G1  Adapter contracts                ✓
G2  Resolver                         ✓
G3  Candidate validation             ✓
G4  Authorization policy             ✓
G5  Deduplication                    ✓
G6  Deterministic ranking            ✓

G7  Abort propagation                ✓
G8  Timeout                          ✓
G9  Concurrency limit                ✓
G10 Rate limiting                    PARTIAL
G11 Circuit breaker                  PARTIAL
G12 Cache abstraction                ✓
G13 In-flight dedup                  ✓
G14 Safe HTTP boundary               PARTIAL
G15 Health endpoints                 ✓

G16 Stremio manifest                 ✓
G17 Movie request parsing            ✓
G18 Series request parsing           ✓
G19 Stream mapping                   ✓
G20 Protocol integration test        TODO

G21 Metadata                         TODO
G22 Catalog                          TODO
G23 Subtitles                        TODO

G24 Docker build                     TODO
G25 CI execution                     TODO
G26 Release evidence                 TODO
```

Notice the deliberate wording:

**implemented in blueprint/code ≠ verified by execution.**

## First protocol integration test

The first meaningful integration test should prove the entire chain.

```ts
it("resolves an authorized fixture through Stremio", async () => {
  const registry = new SourceRegistry();

  registry.register(new FixtureAdapter());

  const resolver = new Resolver(registry, {
    timeoutMs: 1_000,
    preferredLanguages: ["en"]
  });

  const handler = createStreamHandler(resolver);

  const response = await handler({
    type: "movie",
    id: "tt1234567"
  });

  expect(response.streams).toHaveLength(1);

  expect(response.streams[0]).toMatchObject({
    name: "fixture-authorized",
    url: "https://media.example.test/movie.mp4"
  });
});
```

This single test establishes:

```text
Stremio syntax
      ↓
parser
      ↓
domain MediaRef
      ↓
registry
      ↓
adapter
      ↓
candidate
      ↓
validation
      ↓
authorization
      ↓
deduplication
      ↓
ranking
      ↓
Stremio representation
```

That is the first **vertical proof obligation**.

## Then test the rejection path

The positive test alone is insufficient.

Add:

```text
authorized candidate
        → accepted

unknown authorization
        → rejected

unauthorized candidate
        → rejected

malformed URL
        → rejected

duplicate candidate
        → one candidate

adapter timeout
        → failure recorded

one adapter fails
        → other adapters continue
```

The most important negative test:

```ts
expect(
  authorizeCandidate({
    // ...
    authorization: {
      status: "unknown"
    }
  }).authorized
).toBe(false);
```

This protects the architectural rule:

**Unknown authorization is not authorization.**

## Source adapter conformance suite

Every future adapter should automatically receive the same contract
tests.

```ts
export function describeSourceAdapter(createAdapter: () => SourceAdapter) {
  describe("SourceAdapter contract", () => {
    it("has a stable ID", () => {
      const adapter = createAdapter();

      expect(adapter.id).toMatch(/^[a-z0-9][a-z0-9-]*$/);
    });

    it("has a name", () => {
      expect(createAdapter().name.length).toBeGreaterThan(0);
    });

    it("supports() is deterministic", () => {
      const adapter = createAdapter();

      const media = {
        type: "movie" as const,
        id: "tt1234567"
      };

      expect(adapter.supports(media)).toBe(adapter.supports(media));
    });
  });
}
```

Later this becomes:

```text
adapter implementation
       │
       ▼
conformance suite
       │
       ├── capability correctness
       ├── authorization semantics
       ├── cancellation
       ├── timeout
       ├── malformed response handling
       ├── deterministic identity
       └── evidence emission
```

## Next gate: executable evidence

The next milestone is no longer architectural.

It is:

```text
GATE V0.1-S1

[ ] repository compiles
[ ] typecheck passes
[ ] unit tests pass
[ ] integration test passes
[ ] Stremio manifest endpoint works
[ ] Stremio stream endpoint works
[ ] fixture authorization is enforced
[ ] unauthorized fixture is rejected
[ ] duplicate candidates collapse
[ ] ranking is deterministic
[ ] timeout is observable
[ ] container builds
[ ] container starts
[ ] health endpoint works
[ ] protocol smoke test passes
[ ] artifact digest recorded
```

Only after these are actually executed should the project state change
from:

```text
DESIGNED
```

to:

```text
IMPLEMENTATION_VERIFIED
```

and eventually:

```text
ARTIFACT_BOUND
```

## Verification Matrix

| Claim | Evidence required | Current |
| --- | --- | --- |
| Manifest conforms | SDK validation + test | OPEN |
| `/stream` works | integration test | OPEN |
| Parser handles IMDb movie | unit test | OPEN |
| Parser handles IMDb episode | unit test | OPEN |
| Unknown authorization rejected | unit test | OPEN |
| Dedup deterministic | unit test | OPEN |
| Ranking deterministic | unit test | OPEN |
| Timeout cancellation works | runtime test | OPEN |
| Concurrent requests bounded | runtime test | OPEN |
| Circuit breaker works | runtime test | OPEN |
| SDK server starts | execution evidence | OPEN |
| Stremio client consumes addon | client smoke test | OPEN |
| Container works | CI execution | OPEN |
| Real source works | adapter evidence | OPEN |
| Release artifact reproducible | digest | OPEN |

Therefore the honest state remains:

> IMPLEMENTATION BLUEPRINT — NOT YET EXECUTION-VERIFIED

The current Stremio protocol assumptions themselves are now externally
verified against the official SDK documentation.

## Conformance Harness

We now freeze the first test contract.

The harness must prove **behavior**, not merely implementation
details.

```text
                    ┌────────────────────┐
                     │   Domain tests     │
                     └─────────┬──────────┘
                               │
                     ┌─────────▼──────────┐
                     │ Resolver tests     │
                     └─────────┬──────────┘
                               │
                     ┌─────────▼──────────┐
                     │ Adapter contract   │
                     └─────────┬──────────┘
                               │
                     ┌─────────▼──────────┐
                     │ Protocol tests     │
                     └─────────┬──────────┘
                               │
                     ┌─────────▼──────────┐
                     │ HTTP smoke test    │
                     └─────────┬──────────┘
                               │
                     ┌─────────▼──────────┐
                     │ CI release gate    │
                     └────────────────────┘
```

The important distinction:

```text
unit test
    ≠ protocol test
    ≠ deployment test
```

All three are necessary.

## Parser Conformance

`test/addon/parser.test.ts`

```ts
import { describe, expect, it } from "vitest";

import {
  parseStreamRequest,
  RequestParseError
} from "../../src/addon/parser.js";

describe("parseStreamRequest", () => {
  it("parses a movie", () => {
    expect(parseStreamRequest("movie", "tt1234567")).toEqual({
      media: {
        type: "movie",
        id: "tt1234567"
      }
    });
  });

  it("parses a series episode", () => {
    expect(parseStreamRequest("series", "tt1234567:2:7")).toEqual({
      media: {
        type: "series",
        id: "tt1234567",
        season: 2,
        episode: 7
      }
    });
  });

  it("rejects invalid series syntax", () => {
    expect(() => parseStreamRequest("series", "tt1234567")).toThrow(
      RequestParseError
    );
  });

  it("rejects season zero", () => {
    expect(() => parseStreamRequest("series", "tt1234567:0:7")).toThrow(
      RequestParseError
    );
  });

  it("rejects episode zero", () => {
    expect(() => parseStreamRequest("series", "tt1234567:2:0")).toThrow(
      RequestParseError
    );
  });

  it("rejects unsupported media types", () => {
    expect(() => parseStreamRequest("channel", "abc")).toThrow(
      RequestParseError
    );
  });
});
```

This establishes the first protocol theorem:

```text
valid Stremio ID
        ⇔ valid MediaRef
```

within the supported request grammar.

## Authorization Tests

`test/resolver/authorization.test.ts`

```ts
import { describe, expect, it } from "vitest";

import { authorizeCandidate } from "../../src/resolver/policy.js";

const candidate = {
  sourceId: "test",

  media: {
    type: "movie" as const,
    id: "tt1234567"
  },

  url: "https://example.test/movie.mp4",

  provenance: {
    adapterId: "test",
    observedAt: "2026-09-28T00:00:00.000Z"
  },

  capabilities: {
    directPlayback: true
  },

  authorization: {
    status: "authorized" as const,
    basis: "fixture"
  }
};

describe("authorizeCandidate", () => {
  it("accepts authorized direct playback", () => {
    expect(authorizeCandidate(candidate).authorized).toBe(true);
  });

  it("rejects unknown authorization", () => {
    expect(
      authorizeCandidate({
        ...candidate,
        authorization: {
          status: "unknown"
        }
      }).authorized
    ).toBe(false);
  });

  it("rejects unauthorized candidates", () => {
    expect(
      authorizeCandidate({
        ...candidate,
        authorization: {
          status: "unauthorized"
        }
      }).authorized
    ).toBe(false);
  });

  it("rejects non-direct playback", () => {
    expect(
      authorizeCandidate({
        ...candidate,
        capabilities: {
          directPlayback: false
        }
      }).authorized
    ).toBe(false);
  });
});
```

This is one of the highest-value tests in the entire project.

If this test disappears, the architecture has lost an important
security boundary.

## Deduplication Test

`test/resolver/dedupe.test.ts`

```ts
import { describe, expect, it } from "vitest";

import { deduplicateCandidates } from "../../src/resolver/dedupe.js";

function candidate(url: string, sourceId = "source-a") {
  return {
    sourceId,

    media: {
      type: "movie" as const,
      id: "tt1234567"
    },

    url,

    provenance: {
      adapterId: sourceId,
      observedAt: "2026-09-28T00:00:00.000Z"
    },

    capabilities: {
      directPlayback: true
    },

    authorization: {
      status: "authorized" as const,
      basis: "fixture"
    }
  };
}

describe("deduplicateCandidates", () => {
  it("removes URL fragments from identity", () => {
    const result = deduplicateCandidates([
      candidate("https://example.test/movie.mp4#one"),
      candidate("https://example.test/movie.mp4#two")
    ]);

    expect(result).toHaveLength(1);
  });

  it("keeps genuinely different URLs", () => {
    const result = deduplicateCandidates([
      candidate("https://a.example/movie.mp4"),
      candidate("https://b.example/movie.mp4")
    ]);

    expect(result).toHaveLength(2);
  });
});
```

## Deterministic Ranking Test

```ts
describe("rankCandidates", () => {
  it("does not depend on input order", () => {
    const candidates = [
      makeCandidate("source-z", "720p", 2_000_000),
      makeCandidate("source-a", "1080p", 5_000_000),
      makeCandidate("source-b", "1080p", 3_000_000)
    ];

    const first = rankCandidates(candidates);

    const second = rankCandidates([...candidates].reverse());

    expect(first).toEqual(second);
  });
});
```

This catches a class of bugs that ordinary example-based tests
frequently miss.

The invariant is:

```text
rank(A) = rank(permutation(A))
```

assuming candidate properties are unchanged.

## Resolver Partial-Success Test

This is more important than another happy-path test.

Create three adapters:

```text
source-a → candidate
source-b → timeout
source-c → candidate
```

Then:

```ts
it("preserves successful candidates when one source fails", async () => {
  const registry = new SourceRegistry();

  registry.register(new SuccessfulAdapter("source-a"));

  registry.register(new FailingAdapter("source-b"));

  registry.register(new SuccessfulAdapter("source-c"));

  const resolver = new Resolver(registry, {
    timeoutMs: 100,
    preferredLanguages: ["en"]
  });

  const result = await resolver.resolve(
    {
      type: "movie",
      id: "tt1234567"
    },
    new AbortController().signal
  );

  expect(result.status).toBe("partial");

  expect(result.candidates).toHaveLength(2);

  expect(result.failures).toHaveLength(1);
});
```

This establishes:

```text
failure isolation
```

as a first-class property.

## Timeout Test

A deliberately slow adapter:

```ts
class SlowAdapter implements SourceAdapter {
  readonly id = "slow";

  readonly name = "Slow Adapter";

  supports(): boolean {
    return true;
  }

  async resolve(_media: MediaRef, ctx: ResolveContext) {
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(resolve, 10_000);

      ctx.signal.addEventListener(
        "abort",
        () => {
          clearTimeout(timer);

          reject(ctx.signal.reason ?? new Error("aborted"));
        },
        { once: true }
      );
    });

    return [];
  }
}
```

Then:

```ts
it("propagates timeout cancellation", async () => {
  const controller = new AbortController();

  const promise = withTimeout(
    signal => slowOperation(signal),
    20,
    controller.signal
  );

  await expect(promise).rejects.toThrow();
});
```

This is a real runtime invariant:

```text
deadline exceeded
       ↓
AbortSignal
       ↓
adapter
       ↓
underlying operation
```

## Semaphore Test

The concurrency test should measure actual overlap.

```ts
it("never exceeds configured concurrency", async () => {
  const limiter = new Semaphore(2);

  let active = 0;
  let maximum = 0;

  const task = async () => {
    await limiter.run(async () => {
      active++;

      maximum = Math.max(maximum, active);

      await delay(20);

      active--;
    });
  };

  await Promise.all(Array.from({ length: 10 }, () => task()));

  expect(maximum).toBeLessThanOrEqual(2);
});
```

The test isn't checking an internal queue.

It checks the actual observable invariant:

```text
maximum simultaneous operations ≤ capacity
```

## Circuit Breaker Tests

Three fundamental tests:

```text
CLOSED
  ↓
repeated failures
OPEN
```

```text
OPEN
  ↓
cooldown
HALF_OPEN
```

```text
HALF_OPEN + success
  ↓
CLOSED
```

And:

```text
HALF_OPEN + failure
  ↓
OPEN
```

Example:

```ts
it("opens after the configured failure threshold", async () => {
  const breaker = new CircuitBreaker({
    failureThreshold: 3,
    cooldownMs: 100
  });

  await expect(
    breaker.execute(() => Promise.reject(new Error("x")))
  ).rejects.toThrow();

  await expect(
    breaker.execute(() => Promise.reject(new Error("x")))
  ).rejects.toThrow();

  await expect(
    breaker.execute(() => Promise.reject(new Error("x")))
  ).rejects.toThrow();

  expect(breaker.state).toBe("open");
});
```

## Adapter Conformance

Instead of writing bespoke tests for every source:

```ts
describeSourceAdapter(() => new FixtureAdapter());
```

Every future adapter must pass:

```text
                    SourceAdapter
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
       identity       capabilities     runtime
           │              │              │
           └──────────────┼──────────────┘
                          ▼
                   conformance suite
```

The suite eventually verifies:

```text
stable ID
capability declaration
supported media types
cancellation
timeout
malformed response handling
authorization semantics
provenance
determinism
```

This turns adapter development into a contract rather than a
collection of conventions.

## Manifest Test

```ts
describe("manifest", () => {
  it("declares the stream capability", () => {
    const manifest = createManifest();

    expect(manifest.resources).toEqual([
      {
        name: "stream",
        types: ["movie", "series"],
        idPrefixes: ["tt"]
      }
    ]);
  });

  it("does not advertise unsupported resources", () => {
    const manifest = createManifest();

    expect(manifest.resources).not.toContainEqual(
      expect.objectContaining({
        name: "catalog"
      })
    );
  });
});
```

This protects against a dangerous class of drift:

```text
manifest says supported
        ↓
implementation doesn't exist
```

A capability must not be advertised before it is actually implemented.

## Protocol Handler Test

```ts
describe("stream handler", () => {
  it("maps candidates into Stremio streams", async () => {
    const resolver = fakeResolver({
      media: {
        type: "movie",
        id: "tt1234567"
      },

      status: "success",

      candidates: [
        {
          sourceId: "source-a",
          media: {
            type: "movie",
            id: "tt1234567"
          },
          url: "https://example.test/movie.mp4",
          mediaInfo: {
            resolution: "1080p",
            container: "mp4"
          },
          provenance: {
            adapterId: "source-a",
            observedAt: "2026-09-28T00:00:00.000Z"
          },
          capabilities: {
            directPlayback: true
          },
          authorization: {
            status: "authorized",
            basis: "test"
          }
        }
      ],

      failures: [],
      sourceCount: 1,
      durationMs: 1
    });

    const handler = createStreamHandler(resolver);

    const result = await handler({
      type: "movie",
      id: "tt1234567"
    });

    expect(result).toEqual({
      streams: [
        {
          name: "source-a",
          title: "1080p · mp4",
          url: "https://example.test/movie.mp4"
        }
      ]
    });
  });
});
```

Now we have tested the presentation boundary independently of the
source implementation.

## HTTP-Level Test

The next layer must start the actual addon interface.

Conceptually:

```text
test
 │
 ▼
HTTP server
 │
 ├── GET /manifest.json
 │
 └── GET /stream/movie/tt1234567.json
```

The test should verify:

```ts
const manifestResponse = await fetch(`${baseUrl}/manifest.json`);

expect(manifestResponse.status).toBe(200);

const manifest = await manifestResponse.json();

expect(manifest.id).toBe("org.authorized.sourceaggregator");
```

Then:

```ts
const response = await fetch(`${baseUrl}/stream/movie/tt1234567.json`);

expect(response.status).toBe(200);

const body = await response.json();

expect(body.streams).toHaveLength(1);
```

This is the first test that proves the HTTP boundary.

## Important: Do Not Test Only the Handler

This:

```text
handler()
```

can pass while:

```text
HTTP routing
SDK registration
manifest serialization
server startup
```

is broken.

Therefore:

```text
                 UNIT
                   │
            ┌──────┴──────┐
            ▼             ▼
         handler        resolver
            │             │
            └──────┬──────┘
                   ▼
               INTEGRATION
                   │
                   ▼
               HTTP server
                   │
                   ▼
              protocol test
```

Both layers are required.

## First Release Gate

At this point the v0.1 gate can be formalized:

```text
GATE-V0.1-S1
```

### Contract

```text
[ ] package installs reproducibly
[ ] TypeScript typecheck passes
[ ] domain tests pass
[ ] resolver tests pass
[ ] runtime tests pass
[ ] adapter conformance passes
[ ] manifest test passes
[ ] stream handler test passes
[ ] HTTP integration test passes
[ ] fixture adapter passes
[ ] unauthorized candidate is rejected
[ ] empty result is represented correctly
[ ] partial result is represented correctly
[ ] ranking is deterministic
[ ] deduplication is deterministic
[ ] cancellation works
[ ] concurrency bound works
[ ] circuit breaker works
[ ] health endpoints work
```

Only then:

```text
GATE-V0.1-S1 = PASSED
```

But until those commands actually execute in CI:

```text
GATE-V0.1-S1 = OPEN
```

That distinction remains mandatory.

## CI Becomes the Authority

The workflow should eventually be:

```yaml
name: conformance

on:
  push:
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm

      - run: npm ci
      - run: npm run typecheck
      - run: npm test
      - run: npm run build
```

Then:

```text
developer inspection
       ↓
diagnostic evidence

CI execution
       ↓
verification authority
```

A green editor is not a release gate.

A successful local command is useful evidence, but the project rule
remains:

**CI is execution authority.**

## Container Gate

After CI passes:

```text
source tree
    ↓
npm ci
    ↓
build
    ↓
dist/
    ↓
runtime image
```

The final image should contain only what the runtime needs.

Conceptually:

```dockerfile
FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY tsconfig.json ./
COPY src ./src

RUN npm run build


FROM node:22-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production

COPY package*.json ./

RUN npm ci --omit=dev

COPY --from=build /app/dist ./dist

USER node

EXPOSE 7000

CMD ["node", "dist/index.js"]
```

The build environment and runtime environment are therefore separate.

## Reconciliation Tests

Test:

```text
one exact mapping
    → resolved

two agreeing mappings
    → resolved

conflicting mappings
    → ambiguous

all NOT_FOUND
    → not_found

all temporary failures
    → not_resolved

one NOT_FOUND + one temporary failure
    → not_resolved
```

The last case is especially important.

If one provider says:

```text
NOT_FOUND
```

while another provider simply timed out, we cannot safely conclude:

```text
NOT_FOUND
```

because the failed provider may have contained the answer.

Therefore:

```text
explicit negative evidence + incomplete observation = not fully resolved
```

## Identity Layer Release Gate

Before identity becomes part of a release:

```text
GATE-ID-01
```

must require:

```text
[ ] identity normalization tested
[ ] identity keys collision-safe
[ ] provider contract defined
[ ] NOT_FOUND preserved
[ ] NOT_RESOLVED preserved
[ ] AMBIGUOUS preserved
[ ] reconciliation pure
[ ] conflicting mappings tested
[ ] negative-cache semantics tested
[ ] identity evidence recorded
[ ] routing refuses insufficient identity
[ ] identity cache does not become authorization
[ ] deterministic reconciliation verified
```

Only after this passes should a real TMDB/TVDB/etc. adapter be
admitted.

## Adapter conformance suite v2

Every admitted adapter must pass structural tests.

```ts
interface AdapterConformanceContext {
  readonly adapter: SourceAdapter;
  readonly declaration: SourceDeclaration;
}
```

Tests:

```text
ADAPTER-CONFORMANCE

[ ] unique ID
[ ] declaration matches implementation
[ ] declared media types are supported
[ ] unsupported media rejected
[ ] required identities enforced
[ ] authorization declaration valid
[ ] stream capability consistent
[ ] timeout respected
[ ] AbortSignal respected
[ ] candidate URLs satisfy network policy
[ ] candidate authorization preserved
[ ] candidate sourceId correct
[ ] malformed provider data rejected
[ ] candidate count bounded
[ ] deterministic output
[ ] no hidden global state
```

## New release gate: `GATE-SOURCE-ADMISSION-01`

```text
SOURCE ADMISSION
────────────────────────────────────────

[ ] SourceDeclaration exists
[ ] declaration schema validated
[ ] capability consistency validated
[ ] authorization mode explicit
[ ] authorization evidence required
[ ] unknown authorization rejected
[ ] expired evidence rejected
[ ] required identities declared
[ ] insufficient identity blocks routing
[ ] network policy declared
[ ] outbound hosts constrained
[ ] redirect policy declared
[ ] source limits declared
[ ] adapter cannot self-authorize
[ ] admission decision is deterministic
[ ] rejection reasons are machine-readable
[ ] admission != health
[ ] admission != circuit state
[ ] adapter execution requires admission
[ ] rejected adapter cannot enter executable registry
[ ] conformance suite passes
```

Current status:

```text
GATE-SOURCE-ADMISSION-01 = OPEN
```

because this is still architecture/code specification, not executed
repository evidence.

## New runtime gate

Introduce:

```text
GATE-SOURCE-RUNTIME-01
```

```text
[ ] raw fetch unavailable to adapters
[ ] SourceHttpClient boundary exists
[ ] timeout enforced
[ ] AbortSignal propagated
[ ] retry policy explicit
[ ] retry cancellation tested
[ ] rate limit per source
[ ] concurrency per source
[ ] circuit checked before execution
[ ] response-size limit
[ ] redirect limit
[ ] redirect policy revalidated
[ ] HTTPS policy enforced
[ ] embedded credentials rejected
[ ] sensitive headers redacted
[ ] secrets absent from candidates
[ ] provider HTTP semantics remain adapter-specific
[ ] network failures classified
[ ] media body not proxied by default
[ ] DNS/IP policy defined
[ ] deterministic failure mapping tested
```

Status:

```text
GATE-SOURCE-RUNTIME-01 = OPEN
```

No execution evidence exists yet.

## End-to-end example

Request:

```text
GET /stream/movie/tt1234567.json
```

Pipeline:

```text
Stremio
  │
  ▼
parse
  │
  ▼
MediaRef(tt1234567)
  │
  ▼
identity resolver
  │
  ▼
CanonicalMedia(media:movie-001)
  │
  ▼
source router
  │
  ▼
owned-media-library
  │
  ▼
admitted?
  │
  ▼
library.findAssets(movie-001)
  │
  ▼
1080p asset
2160p asset
  │
  ▼
SourceCandidate[]
  │
  ▼
validate
  │
  ▼
authorize
  │
  ▼
dedupe
  │
  ▼
rank
  │
  ▼
Stremio DTO
```

Final protocol representation:

```json
{
  "streams": [
    {
      "name": "owned-media-library",
      "title": "2160p · mp4",
      "url": "https://media.example.org/library/movie-001-2160p.mp4"
    },
    {
      "name": "owned-media-library",
      "title": "1080p · mp4",
      "url": "https://media.example.org/library/movie-001-1080p.mp4"
    }
  ]
}
```

The exact URLs above are illustrative only.

## New tests

The first real adapter now gets a dedicated suite:

```text
test/adapters/owned-media/
├── declaration.test.ts
├── schema.test.ts
├── library.test.ts
├── adapter.test.ts
├── authorization.test.ts
├── series.test.ts
├── url-policy.test.ts
└── conformance.test.ts
```

Minimum assertions:

```text
[ ] valid movie asset resolves
[ ] absent movie produces empty
[ ] valid episode resolves
[ ] wrong episode does not resolve
[ ] duplicate asset IDs rejected
[ ] malformed library JSON rejected
[ ] unknown authorization rejected
[ ] unauthorized asset rejected
[ ] embedded credentials rejected
[ ] unsupported URL scheme rejected
[ ] candidate sourceId correct
[ ] canonicalId preserved
[ ] multiple assets preserved
[ ] adapter does not perform ranking
[ ] AbortSignal propagates
[ ] adapter cannot bypass admission
```

## Integration test that actually matters

The highest-value test is no longer merely:

```text
adapter.resolve(...)
```

It is:

```text
HTTP request
    ↓
real Stremio SDK
    ↓
stream handler
    ↓
application resolver
    ↓
identity
    ↓
admission
    ↓
owned library
    ↓
candidate validation
    ↓
authorization
    ↓
ranking
    ↓
HTTP response
```

The test should assert the actual wire contract:

```text
GET /manifest.json
```

and:

```text
GET /stream/movie/tt1234567.json
```

with the actual SDK server.

That is the point where the protocol contract becomes **execution
evidence**.

## Metadata release gate

Introduce:

```text
GATE-METADATA-01
```

```text
[ ] MetadataProvider contract defined
[ ] MetadataObservation defined
[ ] field-level provenance preserved
[ ] provider capability declarations
[ ] identity requirements explicit
[ ] metadata does not become identity authority
[ ] NOT_FOUND preserved
[ ] NOT_RESOLVED preserved
[ ] AMBIGUOUS preserved
[ ] reconciliation is pure
[ ] conflicts preserved
[ ] cache states preserved
[ ] cache miss != not_found
[ ] artwork URL policy defined
[ ] series/episode model defined
[ ] metadata independent from playback
[ ] provider runtime limits
[ ] provider circuit breakers
[ ] provider rate limits
[ ] Stremio mapping isolated
[ ] integration tests
```

Status:

```text
GATE-METADATA-01 = OPEN
```

## New conformance layer

We now need three provider conformance suites:

```text
Provider Conformance
│
├── SourceProvider
│
├── MetadataProvider
│
└── SubtitleProvider
```

Shared tests:

```text
[ ] unique provider ID
[ ] declaration valid
[ ] capabilities consistent
[ ] cancellation respected
[ ] timeout respected
[ ] malformed response handled
[ ] authorization preserved
[ ] network policy respected
[ ] deterministic semantics
```

Specialized tests then cover domain behavior.

## New release gate

```text
GATE-SUBTITLE-01
────────────────────────────────

[ ] subtitle domain model
[ ] language normalization
[ ] original language preserved
[ ] episode matching
[ ] provider capability declaration
[ ] authorization evidence
[ ] URL policy
[ ] deduplication
[ ] deterministic ranking
[ ] forced subtitle semantics
[ ] hearing-impaired semantics
[ ] timeout
[ ] cancellation
[ ] rate limiting
[ ] circuit breaker
[ ] empty result semantics
[ ] failure semantics
[ ] Stremio mapper
[ ] HTTP integration
```

Status:

```text
GATE-SUBTITLE-01 = OPEN
```

## Updated release gates

The release tree now becomes:

```text
GATE-V0.1
│
├── GATE-CORE
├── GATE-IDENTITY-01
├── GATE-SOURCE-ADMISSION-01
├── GATE-SOURCE-RUNTIME-01
├── GATE-METADATA-01
├── GATE-SUBTITLE-01
└── GATE-CATALOG-01
```

`GATE-CATALOG-01`:

```text
[ ] CatalogProvider contract
[ ] catalog capabilities
[ ] bounded pagination
[ ] deterministic ordering
[ ] CatalogObservation
[ ] identity separation
[ ] catalog index
[ ] search contract
[ ] search normalization
[ ] deterministic ranking
[ ] catalog dedupe
[ ] freshness model
[ ] stale policy
[ ] rebuildable index
[ ] authorization/visibility policy
[ ] protocol mapper
[ ] integration tests
[ ] manifest capability validated
```

Status:

```text
GATE-CATALOG-01 = OPEN
```

And the global project remains:

```text
IMPLEMENTATION STATUS = NOT VERIFIED
RELEASE STATUS        = OPEN
ARTIFACT STATUS       = NOT BOUND
```

because none of these gates has yet been demonstrated by an actual CI
execution in this conversation.

## Contract testing

Now we can introduce:

```text
API Contract Tests
```

Tests verify:

```text
request schema
response schema
error schema
required fields
field types
compatibility
```

This protects external consumers from accidental refactoring.

## Stremio becomes a compatibility test

The Stremio adapter should now be tested as:

```text
Stremio Request
      ↓
Stremio Adapter
      ↓
Application API
      ↓
Domain
      ↓
Stremio Adapter
      ↓
Stremio Response
```

This creates a clean compatibility boundary.

## Control-plane gate

Introduce:

```text
GATE-CONTROL-PLANE-01
────────────────────────────

[ ] configuration schema
[ ] policy schema
[ ] provider declaration loading
[ ] deterministic admission
[ ] immutable runtime snapshot
[ ] generation identity
[ ] configuration digest
[ ] atomic publication
[ ] old-generation isolation
[ ] secret separation
[ ] secret redaction
[ ] control/public boundary
[ ] operator authentication boundary
[ ] configuration compatibility
[ ] generation provenance
[ ] reload tests
[ ] failed-generation rollback
```

Status:

```text
GATE-CONTROL-PLANE-01 = OPEN
```
