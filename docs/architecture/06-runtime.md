# Runtime Architecture

[⇧ Architecture index](../architecture.md) · [⇆ Document map](./README.md)

> **Scope.** Request context, deadlines, cancellation (`AbortSignal`), concurrency limiting, rate limiting, circuit breakers, retries, provider isolation, caching, and the immutable-generation/hot-reload model for runtime state. This is the *execution* machinery, kept separate from control-plane configuration lifecycle (see `09-control-plane.md`), and separate from the network/SSRF safety rules it enforces at the HTTP layer.

> **Primary dependencies:** `../contracts/runtime.md`, `09-control-plane.md`

> **Status.** Unless a section explicitly states otherwise with a concrete repository reference (file path, commit, or CI run), everything below is **DESIGNED** or **PROPOSED** architecture, not implemented code. This document was migrated from the original `docs/architecture.md` monolith; section order is preserved from that document, numbering has been dropped in favor of descriptive headings, and some very long single sections in the monolith may appear here still bearing internal editorial framing (e.g. first-person design narration) that predates the doc-split.

## Sections in this document

- [Timeout isolation](#timeout-isolation)
- [Circuit breaker](#circuit-breaker)
- [Cache layers](#cache-layers)
- [URL validation](#url-validation)
- [Rate limiting](#rate-limiting)
- [Concurrency control](#concurrency-control)
- [Latency budget](#latency-budget)
- [Fast path](#fast-path)
- [Don't hide stale data](#don't-hide-stale-data)
- [Runtime reliability architecture](#runtime-reliability-architecture)
- [Runtime substrate: make source resolution production-grade](#runtime-substrate-make-source-resolution-production-grade)
- [Cancellation first](#cancellation-first)
- [Per-adapter timeout](#per-adapter-timeout)
- [Global versus source timeout](#global-versus-source-timeout)
- [Global cancellation](#global-cancellation)
- [Concurrency limiter](#concurrency-limiter)
- [Why the semaphore belongs outside adapters](#why-the-semaphore-belongs-outside-adapters)
- [Per-source concurrency](#per-source-concurrency)
- [Rate limiter](#rate-limiter)
- [Circuit breaker](#circuit-breaker)
- [Don't count every failure equally](#don't-count-every-failure-equally)
- [Execution guard](#execution-guard)
- [Cache architecture](#cache-architecture)
- [Cache key](#cache-key)
- [Cache state](#cache-state)
- [Stale-while-revalidate](#stale-while-revalidate)
- [Cache stampede protection](#cache-stampede-protection)
- [HTTP client boundary](#http-client-boundary)
- [SSRF protection](#ssrf-protection)
- [Runtime composition](#runtime-composition)
- [Final runtime tree](#final-runtime-tree)
- [Safe HTTP contract](#safe-http-contract)
- [URL validation](#url-validation)
- [SSRF policy](#ssrf-policy)
- [DNS rebinding](#dns-rebinding)
- [Safer baseline](#safer-baseline)
- [Redirects](#redirects)
- [Response-size limit](#response-size-limit)
- [HTTP failure taxonomy](#http-failure-taxonomy)
- [Never collapse HTTP status into success](#never-collapse-http-status-into-success)
- [Cache interface](#cache-interface)
- [Don't cache authorization assumptions](#don't-cache-authorization-assumptions)
- [Cache candidates, not final Stremio streams](#cache-candidates-not-final-stremio-streams)
- [Cache key versioning](#cache-key-versioning)
- [Stale cache policy](#stale-cache-policy)
- [Stale data must remain marked stale](#stale-data-must-remain-marked-stale)
- [In-flight request deduplication](#in-flight-request-deduplication)
- [Important cancellation caveat](#important-cancellation-caveat)
- [Don't download arbitrary subtitle URLs through the addon](#don't-download-arbitrary-subtitle-urls-through-the-addon)
- [Metadata cache](#metadata-cache)
- [Identity cache](#identity-cache)
- [Identity failure cache](#identity-failure-cache)
- [Timeout implementation](#timeout-implementation)
- [Semaphore](#semaphore)
- [Circuit breaker](#circuit-breaker)
- [Source execution status](#source-execution-status)
- [In-flight deduplication](#in-flight-deduplication)
- [In-flight cache](#in-flight-cache)
- [Cache semantics](#cache-semantics)
- [Don't cache authorization blindly](#don't-cache-authorization-blindly)
- [Cache layers](#cache-layers)
- [SSRF boundary](#ssrf-boundary)
- [Redirects are part of SSRF](#redirects-are-part-of-ssrf)
- [DNS rebinding](#dns-rebinding)
- [Runtime Timeout](#runtime-timeout)
- [Caller Cancellation vs Shared Work](#caller-cancellation-vs-shared-work)
- [In-flight Resolution Object](#in-flight-resolution-object)
- [Circuit Breaker](#circuit-breaker)
- [Concurrency Must Be Explicit](#concurrency-must-be-explicit)
- [SSRF Boundary](#ssrf-boundary)
- [Identity Cache](#identity-cache)
- [Negative Cache](#negative-cache)
- [Identity Cache Semantics](#identity-cache-semantics)
- [Network admission](#network-admission)
- [Source limits](#source-limits)
- [Failure semantics become richer](#failure-semantics-become-richer)
- [Source Runtime: from admitted adapter to controlled execution](#source-runtime-from-admitted-adapter-to-controlled-execution)
- [Never give adapters the raw HTTP client](#never-give-adapters-the-raw-http-client)
- [Source HTTP contract](#source-http-contract)
- [Response limits](#response-limits)
- [HTTP error taxonomy](#http-error-taxonomy)
- [Retry policy](#retry-policy)
- [Retry must respect cancellation](#retry-must-respect-cancellation)
- [Retry classification](#retry-classification)
- [Rate limiter](#rate-limiter)
- [Ordering of runtime gates](#ordering-of-runtime-gates)
- [Source execution context](#source-execution-context)
- [Capability-based runtime access](#capability-based-runtime-access)
- [Header policy](#header-policy)
- [URL policy and credentials](#url-policy-and-credentials)
- [Redirect security](#redirect-security)
- [DNS rebinding](#dns-rebinding)
- [Candidate URL policy](#candidate-url-policy)
- [Candidate URL validation](#candidate-url-validation)
- [No credential-bearing playback URLs](#no-credential-bearing-playback-urls)
- [Source runtime wrapper](#source-runtime-wrapper)
- [`404` is not automatically failure](#404-is-not-automatically-failure)
- [Metadata cache](#metadata-cache)
- [Cache TTL policy](#cache-ttl-policy)
- [Do not download artwork unnecessarily](#do-not-download-artwork-unnecessarily)
- [Parallelism](#parallelism)
- [Independent runtime pools](#independent-runtime-pools)
- [Unified request context](#unified-request-context)
- [Subtitle URL validation](#subtitle-url-validation)
- [Subtitle content size](#subtitle-content-size)
- [One runtime, different semantics](#one-runtime-different-semantics)
- [Stale-while-revalidate](#stale-while-revalidate)
- [Cancellation hierarchy](#cancellation-hierarchy)
- [Request deadline](#request-deadline)
- [Deadline propagation](#deadline-propagation)
- [Provider sandboxing](#provider-sandboxing)
- [Dependency injection](#dependency-injection)
- [Clock boundary](#clock-boundary)
- [Randomness boundary](#randomness-boundary)

---

## Timeout isolation

A particularly important property for a multi-source addon:

```text
global timeout = 4s

Source A ─────── 300ms ─── OK
Source B ─────── 900ms ─── OK
Source C ─────── 4s ────── TIMEOUT
Source D ─────── 500ms ─── OK
```

Source C should not prevent A/B/D from appearing.

```ts
export async function withTimeout<T>(
  promise: Promise<T>,
  ms: number
): Promise<T> {
  return Promise.race([
    promise,

    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new Error("source_timeout")), ms)
    )
  ]);
}
```

In production, use `AbortController` so the underlying HTTP request is
actually cancelled.

## Circuit breaker

Without one, an unavailable provider can consume resources on every
request.

```text
CLOSED
  │
  │ repeated failures
  ▼
OPEN
  │
  │ cooldown
  ▼
HALF_OPEN
  │
  ├── success → CLOSED
  │
  └── failure → OPEN
```

Example:

```ts
class CircuitBreaker {
  private failures = 0;
  private openedAt = 0;

  constructor(
    private threshold = 5,
    private cooldownMs = 30_000
  ) {}

  canRequest(): boolean {
    if (this.failures < this.threshold) {
      return true;
    }

    return Date.now() - this.openedAt > this.cooldownMs;
  }

  success() {
    this.failures = 0;
    this.openedAt = 0;
  }

  failure() {
    this.failures++;

    if (this.failures >= this.threshold) {
      this.openedAt = Date.now();
    }
  }
}
```

## Cache layers

Use three different caches.

```text
L1: identity cache
    IMDb → canonical metadata

L2: source-result cache
    media + source → candidates

L3: health cache
    source → operational state
```

Don't cache everything for the same duration.

Example:

```text
Identity metadata      24h
Source resolution       5m
Source health           30s
Negative resolution     30s
```

The Stremio protocol itself supports HTTP caching semantics for addon
responses.

## URL validation

Do not accept arbitrary protocols.

```ts
const ALLOWED_PROTOCOLS = new Set(["http:", "https:"]);

export function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);

    return ALLOWED_PROTOCOLS.has(url.protocol);
  } catch {
    return false;
  }
}
```

For a user-owned local media adapter, you can explicitly support
additional protocols later.

Don't make the first implementation permissive and attempt to "secure
it later."

## Rate limiting

A public addon should have two independent limits:

```text
                    Request
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
       per-IP limiter       source limiter
              │                   │
              ▼                   ▼
         addon abuse          provider abuse
```

Do not solve provider rate limits by simply making your entire addon
slower.

Use:

```text
concurrency limit + per-source rate limit + cache + circuit breaker
```

## Concurrency control

If you eventually have 30 adapters, this:

```ts
await Promise.all(adapters.map(...));
```

can become excessive.

Use a bounded scheduler:

```text
30 adapters
    │
    ▼
┌──────────────┐
│ concurrency  │
│     = 6      │
└──────┬───────┘
       │
       ├── A
       ├── B
       ├── C
       ├── D
       ├── E
       └── F
```

Then:

```text
A completes → G starts
C completes → H starts
```

This matters particularly for low-resource deployments.

## Latency budget

Define the budget before optimizing.

For example:

```text
total = 4 seconds

identity       500 ms
source queries 3000 ms
normalization   100 ms
ranking          50 ms
serialization    50 ms
buffer          300 ms
```

The exact numbers should be measured rather than assumed.

The important thing is that the budget exists.

## Fast path

A mature implementation should eventually have:

```text
Request
   │
   ▼
cache lookup
   │
   ├── fresh → return
   │
   └── miss
        │
        ▼
     resolver
```

And potentially:

```text
stale cache
    │
    ├── return stale immediately
    │
    └── background refresh
```

But stale serving should be an explicit policy.

## Don't hide stale data

Internally distinguish:

```text
FRESH
STALE_REVALIDATING
STALE
UNKNOWN
```

A stale result is not equivalent to a freshly observed result.

That matters for diagnostics.

## Runtime reliability architecture

The execution path should become:

```text
                 Adapter
                     │
                     ▼
               Circuit breaker
                     │
                     ▼
               Rate limiter
                     │
                     ▼
              Concurrency gate
                     │
                     ▼
                Timeout
                     │
                     ▼
               HTTP request
                     │
                     ▼
                 Parser
                     │
                     ▼
              SourceCandidate
```

Each layer has one responsibility.

```text
Circuit breaker → should we call?
Rate limiter    → may we call now?
Concurrency     → do we have capacity?
Timeout         → how long may it run?
Parser          → what did it return?
Validator       → is it structurally valid?
Policy          → may it be emitted?
```

This is much easier to reason about than a giant `resolve()` function.

## Runtime substrate: make source resolution production-grade

The next layer should make the resolver **bounded, cancellable,
observable, and resistant to a bad source**.

The execution contract becomes:

```text
                   resolve(media)
                         │
                         ▼
                 ┌──────────────┐
                 │ Source       │
                 │ Registry     │
                 └──────┬───────┘
                        │
                  applicable[]
                        │
                        ▼
               ┌─────────────────┐
               │ Execution Guard │
               └────────┬────────┘
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
    concurrency     rate limit     breaker
         │              │              │
         └──────────────┼──────────────┘
                        ▼
                     timeout
                        │
                        ▼
                  adapter.resolve()
                        │
                        ▼
                     result
```

The key rule:

**A source adapter gets a bounded opportunity to produce evidence. It
does not get control over the resolver.**

## Cancellation first

A timeout without cancellation is incomplete.

This is bad:

```ts
await Promise.race([adapter.resolve(), timeout()]);
```

because `adapter.resolve()` may continue running after the resolver has
already moved on.

Instead, propagate `AbortSignal`.

```ts
export interface ResolveContext {
  readonly signal: AbortSignal;
  readonly timeoutMs: number;
  readonly preferredLanguages: readonly string[];
}
```

HTTP requests should receive it:

```ts
const response = await fetch(url, { signal: ctx.signal });
```

## Per-adapter timeout

Create:

```text
src/runtime/timeout.ts
```

```ts
export async function withTimeout<T>(
  operation: (signal: AbortSignal) => Promise<T>,
  timeoutMs: number,
  parentSignal?: AbortSignal
): Promise<T> {
  const controller = new AbortController();

  const onAbort = () => controller.abort(parentSignal?.reason);

  if (parentSignal) {
    if (parentSignal.aborted) {
      controller.abort(parentSignal.reason);
    } else {
      parentSignal.addEventListener("abort", onAbort, { once: true });
    }
  }

  const timer = setTimeout(() => {
    controller.abort(new Error("timeout"));
  }, timeoutMs);

  try {
    return await operation(controller.signal);
  } finally {
    clearTimeout(timer);

    parentSignal?.removeEventListener("abort", onAbort);
  }
}
```

Now:

```text
request cancellation
        │
        ├── client disconnects
        │
        ├── global timeout
        │
        └── source timeout
               │
               ▼
           AbortSignal
               │
               ▼
           HTTP request
```

## Global versus source timeout

Don't use one timeout for everything.

Define:

```ts
export interface RuntimeLimits {
  readonly totalMs: number;
  readonly perSourceMs: number;
  readonly maxSources: number;
}
```

For example:

```text
Total request budget         4000 ms
           │
      ┌─────┴─────┐
      │           │
  source A      source B
   1200ms        1200ms
```

The source timeout should be smaller than the overall request budget.

## Global cancellation

At the resolver level:

```ts
const controller = new AbortController();

const timer = setTimeout(
  () => controller.abort(new Error("resolution_timeout")),
  config.totalTimeoutMs
);

try {
  // resolve
} finally {
  clearTimeout(timer);
}
```

Now every source receives the same upper-level cancellation.

## Concurrency limiter

Suppose you eventually have:

```text
25 source adapters
```

Calling all 25 simultaneously is unnecessary.

Implement a bounded scheduler.

```ts
export class Semaphore {
  private active = 0;

  private readonly queue: (() => void)[] = [];

  constructor(private readonly capacity: number) {}

  async acquire(): Promise<() => void> {
    if (this.active < this.capacity) {
      this.active++;
      return () => this.release();
    }

    await new Promise<void>(resolve => this.queue.push(resolve));

    this.active++;

    return () => this.release();
  }

  private release(): void {
    this.active--;

    const next = this.queue.shift();

    next?.();
  }
}
```

Usage:

```ts
const release = await semaphore.acquire();

try {
  return await adapter.resolve(media, ctx);
} finally {
  release();
}
```

## Why the semaphore belongs outside adapters

The adapter should not know:

```text
"I am source #7 and the process allows six concurrent requests."
```

That's runtime policy.

Therefore:

```text
Adapter
    ↓
pure source-specific operation

Runtime
    ↓
global resource governance
```

This preserves adapter portability.

## Per-source concurrency

You may eventually need both:

```text
global concurrency
        +
per-source concurrency
```

Example:

```text
Global = 8

Source A = max 2
Source B = max 2
Source C = max 1
Source D = max 3
```

This prevents one popular adapter from consuming the entire process.

## Rate limiter

Rate limiting is different from concurrency.

```text
Concurrency: "How many requests may be running?"

Rate limit: "How frequently may requests start?"
```

A simple token bucket is appropriate.

```ts
export class TokenBucket {
  private tokens: number;

  private lastRefill = Date.now();

  constructor(
    private readonly capacity: number,
    private readonly refillPerSecond: number
  ) {
    this.tokens = capacity;
  }

  tryConsume(): boolean {
    this.refill();

    if (this.tokens < 1) {
      return false;
    }

    this.tokens--;

    return true;
  }

  private refill(): void {
    const now = Date.now();

    const elapsed = (now - this.lastRefill) / 1000;

    this.tokens = Math.min(
      this.capacity,
      this.tokens + elapsed * this.refillPerSecond
    );

    this.lastRefill = now;
  }
}
```

For the first release, returning a controlled `rate_limited` result is
preferable to an uncontrolled queue that can inflate latency.

## Circuit breaker

Now make the earlier breaker production-safe.

```ts
type BreakerState = "closed" | "open" | "half-open";

export class CircuitBreaker {
  private state: BreakerState = "closed";

  private failures = 0;

  private openedAt = 0;

  constructor(
    private readonly threshold = 5,
    private readonly cooldownMs = 30_000
  ) {}

  getState(): BreakerState {
    this.transitionIfReady();

    return this.state;
  }

  allowRequest(): boolean {
    this.transitionIfReady();

    if (this.state === "open") {
      return false;
    }

    if (this.state === "half-open") {
      this.state = "open";
      return true;
    }

    return true;
  }

  success(): void {
    this.state = "closed";
    this.failures = 0;
    this.openedAt = 0;
  }

  failure(): void {
    this.failures++;

    if (this.failures >= this.threshold) {
      this.state = "open";
      this.openedAt = Date.now();
    }
  }

  private transitionIfReady(): void {
    if (
      this.state === "open" &&
      Date.now() - this.openedAt >= this.cooldownMs
    ) {
      this.state = "half-open";
    }
  }
}
```

The semantics are:

```text
CLOSED
  │
  │ repeated failures
  ▼
OPEN
  │
  │ cooldown
  ▼
HALF-OPEN
  │
  ├── success → CLOSED
  │
  └── failure → OPEN
```

## Don't count every failure equally

A malformed provider response is different from a temporary network
failure.

Define:

```ts
type FailureClass =
  | "timeout"
  | "network"
  | "rate_limit"
  | "server"
  | "invalid_response"
  | "authorization"
  | "empty";
```

Then configure breaker behavior.

For example:

```text
timeout          → breaker failure
network          → breaker failure
HTTP 500         → breaker failure
invalid response → breaker failure

empty            → NOT breaker failure
authorization    → NOT necessarily breaker failure
```

An empty catalog doesn't mean the provider is broken.

## Execution guard

Now combine the pieces.

```ts
interface SourceRuntime {
  readonly semaphore: Semaphore;
  readonly bucket: TokenBucket;
  readonly breaker: CircuitBreaker;
}
```

Execution:

```ts
async function executeGuarded(
  adapter: SourceAdapter,
  runtime: SourceRuntime,
  media: MediaRef,
  ctx: ResolveContext
) {
  if (!runtime.breaker.allowRequest()) {
    return {
      status: "circuit_open" as const,
      candidates: []
    };
  }

  if (!runtime.bucket.tryConsume()) {
    return {
      status: "rate_limited" as const,
      candidates: []
    };
  }

  const release = await runtime.semaphore.acquire();

  try {
    const candidates = await withTimeout(
      signal =>
        adapter.resolve(media, {
          ...ctx,
          signal
        }),
      ctx.timeoutMs,
      ctx.signal
    );

    runtime.breaker.success();

    return {
      status: "success" as const,
      candidates
    };
  } catch (error) {
    runtime.breaker.failure();

    return {
      status: classifyFailure(error),
      candidates: []
    };
  } finally {
    release();
  }
}
```

Now the source cannot bypass runtime governance.

## Cache architecture

Caching should happen at two levels.

```text
                   Resolver
                       │
              ┌────────┴────────┐
              ▼                 ▼
        Identity cache     Source cache
              │                 │
           metadata        candidates
```

A third cache is operational:

```text
health cache
```

## Cache key

Never use just:

```text
"movie:tt123"
```

for source results.

Include relevant configuration:

```ts
interface SourceCacheKey {
  readonly adapterId: string;
  readonly mediaId: string;
  readonly season?: number;
  readonly episode?: number;
  readonly language: string;
}
```

Serialize deterministically:

```ts
function cacheKey(key: SourceCacheKey): string {
  return [
    key.adapterId,
    key.mediaId,
    key.season ?? "",
    key.episode ?? "",
    key.language
  ].join(":");
}
```

## Cache state

Don't make cache semantics binary.

```ts
type CacheState = "miss" | "fresh" | "stale";
```

A record:

```ts
interface CacheEntry<T> {
  readonly value: T;

  readonly createdAt: number;

  readonly expiresAt: number;

  readonly staleUntil: number;
}
```

Then:

```text
created
    │
    ├──────── fresh ────────┐
    │                       │
    ▼                       ▼
expires                 stale
                            │
                            ▼
                        staleUntil
                            │
                            ▼
                          dead
```

## Stale-while-revalidate

For a source query:

```text
cache fresh
    │
    └── return immediately

cache stale
    │
    ├── return stale
    │
    └── refresh asynchronously

cache dead
    │
    └── synchronous source query
```

This can significantly reduce perceived latency.

But expose freshness internally:

```ts
interface CachedResolution<T> {
  readonly value: T;
  readonly state: "fresh" | "stale";
}
```

Never pretend stale evidence is fresh.

## Cache stampede protection

Without protection:

```text
100 users
    │
    ▼
same uncached movie
    │
    ▼
100 requests to provider
```

Instead maintain an in-flight map:

```ts
const inflight = new Map<string, Promise<unknown>>();
```

Conceptually:

```text
Request A ──┐
Request B ──┤
Request C ──┼──→ same promise
Request D ──┤
Request E ──┘
```

Only one provider request occurs.

## HTTP client boundary

Don't allow adapters to use arbitrary `fetch()` everywhere.

Provide:

```ts
interface SafeHttpClient {
  getJson<T>(url: string, options?: RequestOptions): Promise<T>;

  head(url: string, options?: RequestOptions): Promise<ResponseMetadata>;
}
```

Then centralize:

```text
timeouts
redirect rules
maximum response size
headers
logging
SSRF protection
abort handling
```

This is a major security boundary.

## SSRF protection

If your addon ever accepts user-configured endpoints, distinguish:

```text
trusted configured origin
```

from:

```text
arbitrary URL returned by provider
```

Never assume:

```text
"the provider gave me this URL"
```

means it is safe for your server to fetch.

A server-side fetcher must consider:

```text
127.0.0.1
localhost
RFC1918 ranges
link-local
IPv6 loopback
IPv6 private ranges
metadata endpoints
DNS rebinding
redirects
```

A strong architecture is:

```text
Provider API
     │
     ▼
metadata only
     │
     ▼
Stremio
     │
     ▼
client-side playback
```

whenever direct playback makes server-side proxying unnecessary.

That substantially reduces your attack surface.

## Runtime composition

Now `index.ts` becomes dependency composition rather than business
logic.

```text
index.ts

config
   ↓
logger
   ↓
HTTP client
   ↓
registry
   ↓
runtime managers
   ↓
resolver
   ↓
Stremio adapter
   ↓
server
```

The business logic is elsewhere.

This makes testing much easier.

## Final runtime tree

```text
src/
├── addon/
│   ├── manifest.ts
│   ├── parser.ts
│   └── stream-handler.ts
│
├── domain/
│   ├── media.ts
│   ├── candidate.ts
│   ├── failure.ts
│   └── result.ts
│
├── adapters/
│   ├── interface.ts
│   ├── registry.ts
│   └── ...
│
├── resolver/
│   ├── resolver.ts
│   ├── execute.ts
│   ├── normalize.ts
│   ├── validate.ts
│   ├── policy.ts
│   ├── dedupe.ts
│   └── rank.ts
│
├── runtime/
│   ├── semaphore.ts
│   ├── limiter.ts
│   ├── breaker.ts
│   ├── timeout.ts
│   ├── cache.ts
│   └── http.ts
│
├── observability/
│   ├── logger.ts
│   ├── metrics.ts
│   └── health.ts
│
└── config/
    └── config.ts
```

At this point the architecture has a very clean separation:

```text
DOMAIN
   ↓
What is a media source?

ADAPTERS
   ↓
How does a particular provider expose it?

RUNTIME
   ↓
How do we safely execute providers?

RESOLVER
   ↓
How do we combine results?

POLICY
   ↓
What is eligible?

RANKER
   ↓
What order?

STREMIO
   ↓
How do we present the result?
```

## Safe HTTP contract

Create:

```text
src/runtime/http.ts
```

The adapter should not receive raw `fetch`.

```ts
export interface SafeHttpClient {
  getJson<T>(url: string, options?: HttpOptions): Promise<T>;

  getText(url: string, options?: HttpOptions): Promise<string>;
}

export interface HttpOptions {
  readonly signal?: AbortSignal;
  readonly headers?: Record<string, string>;
  readonly maxBytes?: number;
  readonly maxRedirects?: number;
}
```

This gives us one place to enforce:

```text
URL validation
redirect validation
timeouts
response-size limits
content-type checks
header policy
abort propagation
logging
```

## URL validation

Start conservatively.

```ts
const ALLOWED_PROTOCOLS = new Set(["http:", "https:"]);

export function validateHttpUrl(input: string): URL {
  const url = new URL(input);

  if (!ALLOWED_PROTOCOLS.has(url.protocol)) {
    throw new Error("unsupported_url_protocol");
  }

  if (url.username || url.password) {
    throw new Error("url_credentials_forbidden");
  }

  return url;
}
```

Reject:

```text
file:
ftp:
data:
javascript:
blob:
ssh:
```

and URLs containing embedded credentials.

## SSRF policy

The first version should explicitly classify addresses.

```ts
type AddressClass =
  | "public"
  | "loopback"
  | "private"
  | "link_local"
  | "reserved"
  | "unknown";
```

Do not blindly implement:

```ts
if (hostname === "localhost")
```

because:

```text
localhost
127.0.0.1
127.0.0.2
::1
0.0.0.0
10.x.x.x
172.16.x.x
192.168.x.x
169.254.x.x
```

are not the complete problem.

## DNS rebinding

The difficult case is:

```text
evil.example
     │
     ├── DNS lookup #1 → public IP
     │
     └── DNS lookup #2 → 127.0.0.1
```

Therefore:

validating the hostname string alone is not SSRF protection.

And:

resolving the hostname once and then using a separate HTTP stack can
still leave a race.

For production, the HTTP implementation should control DNS resolution
and connection establishment.

That is a **deployment-security requirement**, not something the
domain layer should pretend to solve.

## Safer baseline

For the first public release, adopt this policy:

```text
Server-side fetching:
    only explicitly configured/trusted origins

Provider-returned URLs:
    emitted to Stremio
    NOT automatically proxied by addon
```

This is substantially safer than allowing arbitrary remote URLs to
become server-side fetch targets.

## Redirects

A safe client must not validate only the initial URL.

Bad:

```text
GET https://trusted.example
        ↓
302 http://127.0.0.1
```

Therefore either:

```text
automatic redirects = disabled
```

or manually validate every redirect.

For v0.1:

```text
redirect: "manual"
```

is preferable.

Then:

```text
response.status = 3xx
        │
        ▼
Location header
        │
        ▼
validateHttpUrl()
        │
        ▼
SSRF policy
        │
        ▼
next request
```

## Response-size limit

Never assume an API response is small.

```ts
const MAX_JSON_BYTES = 2 * 1024 * 1024;
```

A malicious or broken source returning:

```text
500 MB JSON
```

should not consume the addon process.

The HTTP layer should enforce a byte ceiling while reading.

Conceptually:

```ts
async function readLimited(
  response: Response,
  maxBytes: number
): Promise<Uint8Array> {
  if (!response.body) {
    return new Uint8Array();
  }

  const reader = response.body.getReader();

  const chunks: Uint8Array[] = [];

  let total = 0;

  while (true) {
    const { value, done } = await reader.read();

    if (done) break;

    total += value.byteLength;

    if (total > maxBytes) {
      await reader.cancel();

      throw new Error("response_too_large");
    }

    chunks.push(value);
  }

  const result = new Uint8Array(total);

  let offset = 0;

  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }

  return result;
}
```

## HTTP failure taxonomy

> **Historical (standalone, not paired with its own `AdapterExecution`),
> per `ADR-007` (2026-09-29, second session).** This 10-value expansion
> (adding `http_error`) was not adopted as canonical — the canonical
> `AdapterStatus` (9 values, without `http_error`) is defined further
> below in this file's "Source execution status" section and mirrored in
> [`docs/contracts/result.md`](../contracts/result.md). `http_error` is
> recorded as a plausible future refinement, not silently discarded.

Expand the previous status model:

```ts
// HISTORICAL variant — see note above and docs/contracts/result.md
export type AdapterStatus =
  | "success"
  | "empty"
  | "timeout"
  | "aborted"
  | "rate_limited"
  | "circuit_open"
  | "invalid_response"
  | "http_error"
  | "network_error"
  | "error";
```

This gives the observability layer useful semantics.

## Never collapse HTTP status into success

This:

```ts
if (response.ok) {
  return response.json();
}
```

is insufficient.

You need:

```text
HTTP status
+ content type
+ body validity
+ schema validity
```

before producing source candidates.

The pipeline becomes:

```text
HTTP response
    │
    ▼
transport validation
    │
    ▼
content validation
    │
    ▼
schema validation
    │
    ▼
adapter normalization
    │
    ▼
SourceCandidate[]
```

## Cache interface

Now define:

```text
src/runtime/cache.ts
```

```ts
export interface CacheStore<T> {
  get(key: string): Promise<CacheEntry<T> | null>;

  set(key: string, entry: CacheEntry<T>): Promise<void>;

  delete(key: string): Promise<void>;
}
```

Start with memory.

```ts
export class MemoryCache<T> implements CacheStore<T> {
  private readonly map = new Map<string, CacheEntry<T>>();

  async get(key: string) {
    return this.map.get(key) ?? null;
  }

  async set(key: string, entry: CacheEntry<T>) {
    this.map.set(key, entry);
  }

  async delete(key: string) {
    this.map.delete(key);
  }
}
```

## Don't cache authorization assumptions

This is important.

Avoid:

```text
cache: "URL X is authorized"
```

unless the authorization evidence itself has a defined validity
period.

Instead cache the source observation:

```text
source record
observedAt
provider evidence
```

and derive current policy separately.

Why?

Because:

```text
observation
```

and:

```text
authorization decision
```

have different lifetimes.

## Cache candidates, not final Stremio streams

Prefer:

```text
cache
    ↓
SourceCandidate[]
    ↓
current policy
    ↓
current deduplication
    ↓
current ranking
    ↓
Stremio
```

instead of caching:

```text
Stremio Stream[]
```

This allows policy/ranking changes without invalidating the entire
cache.

## Cache key versioning

Add a namespace:

```ts
const CACHE_VERSION = "candidate-v1";
```

Then:

```ts
function makeCacheKey(key: SourceCacheKey): string {
  return [
    CACHE_VERSION,
    key.adapterId,
    key.mediaId,
    key.season ?? "",
    key.episode ?? "",
    key.language
  ].join("|");
}
```

When the candidate schema changes:

```text
candidate-v1
    ↓
candidate-v2
```

instead of silently interpreting old data under the new schema.

## Stale cache policy

Use:

```ts
export interface CachePolicy {
  readonly freshMs: number;
  readonly staleMs: number;
}
```

Example:

```text
fresh = 5 minutes
stale = 30 minutes
```

Then:

```text
0 ───────── 5m ───────────── 30m
│            │                 │
│  FRESH     │     STALE       │ DEAD
│            │                 │
└────────────┴─────────────────┘
```

## Stale data must remain marked stale

Never:

```ts
return candidates;
```

without indicating their age internally.

Instead:

```ts
interface ResolutionSource {
  readonly candidates: readonly SourceCandidate[];

  readonly freshness: "live" | "fresh_cache" | "stale_cache";
}
```

This preserves evidence provenance.

## In-flight request deduplication

Add:

```ts
class InflightRegistry<T> {
  private readonly map = new Map<string, Promise<T>>();

  async run(key: string, factory: () => Promise<T>): Promise<T> {
    const existing = this.map.get(key);

    if (existing) {
      return existing;
    }

    const promise = factory();

    this.map.set(key, promise);

    try {
      return await promise;
    } finally {
      this.map.delete(key);
    }
  }
}
```

Now ten simultaneous requests can share one source call.

## Important cancellation caveat

Do not let request A cancel the shared operation needed by requests
B–J.

This is a subtle bug.

Bad:

```text
A ─┐
B ─┤
C ─┼── shared operation
D ─┤
E ─┘

A disconnects
     ↓
ABORT
     ↓
everyone loses
```

The shared operation needs its **own lifecycle**.

Then each caller decides whether it still wants the result.

This is another reason not to blindly pass one HTTP request's
`AbortSignal` into a globally shared cache operation.

## Don't download arbitrary subtitle URLs through the addon

The same security rule applies:

```text
provider
    ↓
subtitle URL
```

does not automatically mean:

```text
addon server
    ↓
download URL
```

unless that origin is permitted by the HTTP policy.

Prefer returning a direct URL to the client when possible.

## Metadata cache

Metadata has a different TTL from stream candidates.

For example conceptually:

```text
catalog: long TTL

metadata: long TTL

source candidates: short TTL

health: very short TTL
```

Therefore don't use one universal cache.

```ts
interface CacheNamespace {
  readonly name: string;
  readonly freshMs: number;
  readonly staleMs: number;
}
```

## Identity cache

Identity resolution is especially suitable for caching.

```text
"tt1234567"
    ↓
canonical identity
```

The result changes much less frequently than:

```text
available stream URLs
```

Therefore identity results can use a long-lived cache namespace,
separate from and much longer than the source-candidate cache.

## Identity failure cache

Be careful caching:

```text
NOT_FOUND
```

forever.

A temporary provider outage could masquerade as:

```text
media doesn't exist
```

Instead classify:

```text
NOT_FOUND
PROVIDER_UNAVAILABLE
INVALID_INPUT
AMBIGUOUS
```

and use different cache policies.

## Timeout implementation

```ts
export async function withTimeout<T>(
  operation: (signal: AbortSignal) => Promise<T>,
  timeoutMs: number,
  parentSignal?: AbortSignal
): Promise<T> {
  const controller = new AbortController();

  const abortFromParent = () => {
    controller.abort(parentSignal?.reason);
  };

  if (parentSignal) {
    if (parentSignal.aborted) {
      abortFromParent();
    } else {
      parentSignal.addEventListener("abort", abortFromParent, {
        once: true
      });
    }
  }

  const timer = setTimeout(() => {
    controller.abort(new Error("timeout"));
  }, timeoutMs);

  try {
    return await operation(controller.signal);
  } finally {
    clearTimeout(timer);

    parentSignal?.removeEventListener("abort", abortFromParent);
  }
}
```

## Semaphore

```ts
export class Semaphore {
  private active = 0;

  private readonly queue: Array<() => void> = [];

  constructor(private readonly capacity: number) {
    if (capacity < 1) {
      throw new Error("invalid_semaphore_capacity");
    }
  }

  async acquire(): Promise<() => void> {
    if (this.active < this.capacity) {
      this.active++;

      return () => this.release();
    }

    await new Promise<void>(resolve => this.queue.push(resolve));

    this.active++;

    return () => this.release();
  }

  private release(): void {
    this.active--;

    const next = this.queue.shift();

    next?.();
  }
}
```

## Circuit breaker

Use the previously defined state machine, but make `half-open` a
controlled probe.

```ts
export type BreakerState = "closed" | "open" | "half-open";

export class CircuitBreaker {
  private state: BreakerState = "closed";

  private failures = 0;

  private openedAt = 0;

  constructor(
    private readonly threshold = 5,
    private readonly cooldownMs = 30_000
  ) {}

  state(): BreakerState {
    this.refresh();

    return this.state;
  }

  allow(): boolean {
    this.refresh();

    if (this.state === "open") {
      return false;
    }

    if (this.state === "half-open") {
      this.state = "open";
      return true;
    }

    return true;
  }

  success(): void {
    this.state = "closed";
    this.failures = 0;
    this.openedAt = 0;
  }

  failure(): void {
    this.failures++;

    if (this.failures >= this.threshold) {
      this.state = "open";
      this.openedAt = Date.now();
    }
  }

  private refresh(): void {
    if (
      this.state === "open" &&
      Date.now() - this.openedAt >= this.cooldownMs
    ) {
      this.state = "half-open";
    }
  }
}
```

## Source execution status

> **Canonical source, per `ADR-007` (2026-09-29, second session).** This
> `AdapterExecution`/`AdapterStatus` pair is mirrored verbatim as the
> normative contract in
> [`docs/contracts/result.md`](../contracts/result.md).

```ts
export type AdapterStatus =
  | "success"
  | "empty"
  | "timeout"
  | "aborted"
  | "rate_limited"
  | "circuit_open"
  | "invalid_response"
  | "network_error"
  | "error";

export interface AdapterExecution {
  readonly adapterId: string;
  readonly status: AdapterStatus;
  readonly durationMs: number;
  readonly candidates: readonly SourceCandidate[];
  readonly error?: string;
}
```

Now the resolver can preserve partial failures.

## In-flight deduplication

There is another important optimization.

Suppose ten Stremio requests arrive simultaneously:

```text
R1 ─┐
R2 ─┤
R3 ─┤
R4 ─┼──→ same media
R5 ─┤
R6 ─┤
R7 ─┘
```

Without coordination:

```text
7 × provider queries
```

With in-flight deduplication:

```text
             ┌── R1
             ├── R2
             ├── R3
media ───────┼── R4
             ├── R5
             ├── R6
             └── R7
                  │
                  ▼
             one resolution
```

## In-flight cache

```ts
export class Inflight<T> {
  private readonly active = new Map<string, Promise<T>>();

  getOrCreate(key: string, operation: () => Promise<T>): Promise<T> {
    const existing = this.active.get(key);

    if (existing) {
      return existing;
    }

    const promise = operation();

    this.active.set(key, promise);

    void promise.finally(() => {
      if (this.active.get(key) === promise) {
        this.active.delete(key);
      }
    });

    return promise;
  }
}
```

One subtle point: callers can cancel their own request without
necessarily cancelling the shared underlying resolution.

That requires a later distinction between:

```text
caller cancellation
```

and:

```text
shared operation cancellation
```

## Cache semantics

The cache must not be:

```text
"whatever was returned last time"
```

Instead define:

```text
CacheKey
CacheValue
Freshness
Stale policy
Invalidation
Provenance
```

For example:

```ts
export interface CacheEntry<T> {
  readonly value: T;

  readonly createdAt: number;
  readonly expiresAt: number;

  readonly sourceGeneration?: string;
}
```

## Don't cache authorization blindly

This is another important boundary.

You can cache:

```text
metadata
```

for relatively long periods.

But an authorization-sensitive candidate may require:

```text
short TTL
```

or revalidation.

Otherwise:

```text
authorized yesterday
```

could become:

```text
implicitly authorized forever
```

through cache persistence.

## Cache layers

A practical hierarchy:

```text
L1 in-flight
milliseconds → seconds

L2 memory cache
seconds → minutes

L3 persistent cache
minutes → hours/days

L4 external metadata
provider-dependent
```

Each layer has different semantics.

Don't call them all simply:

```text
cache
```

in diagnostics.

## SSRF boundary

Any future URL-fetching component must assume:

```text
provider URL = untrusted
```

Do not permit arbitrary access to:

```text
127.0.0.1
localhost
RFC1918 ranges
link-local addresses
cloud metadata endpoints
Unix sockets
```

and equivalent IPv6 forms.

The safer architecture is:

```text
provider response
       │
       ▼
URL parser
       │
       ▼
network policy
       │
       ├── deny
       │
       ▼
HTTP client
```

not:

```ts
fetch(providerReturnedUrl);
```

## Redirects are part of SSRF

Even if:

```text
https://approved.example/
```

is allowed,

the response could redirect to:

```text
http://127.0.0.1/
```

Therefore the policy must be applied **per redirect**.

Conceptually:

```text
URL₀
 ↓
policy
 ↓
HTTP
 ↓
Location
 ↓
policy again
 ↓
HTTP
```

Never treat the initial hostname as sufficient authorization.

## DNS rebinding

Hostname validation alone is insufficient.

A hostile hostname could resolve differently later.

The production network client therefore needs:

```text
hostname policy
+ DNS resolution policy
+ IP range policy
+ redirect policy
```

This is another reason not to use the default fetch path blindly for
arbitrary provider URLs.

## Runtime Timeout

The adapter context should receive an actual deadline.

```ts
export interface ResolveContext {
  readonly signal: AbortSignal;
  readonly timeoutMs: number;
  readonly preferredLanguages: readonly string[];
}
```

The resolver should create a bounded operation:

```ts
export async function withTimeout<T>(
  operation: (signal: AbortSignal) => Promise<T>,
  timeoutMs: number,
  parentSignal?: AbortSignal
): Promise<T> {
  const controller = new AbortController();

  const timeout = setTimeout(() => {
    controller.abort(new Error("operation timed out"));
  }, timeoutMs);

  const onAbort = () => {
    controller.abort(parentSignal?.reason);
  };

  parentSignal?.addEventListener("abort", onAbort, { once: true });

  try {
    return await operation(controller.signal);
  } finally {
    clearTimeout(timeout);

    parentSignal?.removeEventListener("abort", onAbort);
  }
}
```

Now cancellation has a real propagation path:

```text
Stremio request
      │
      ▼
application
      │
      ▼
resolver
      │
      ▼
adapter
      │
      ▼
HTTP request
```

An upstream cancellation must be capable of reaching the bottom.

## Caller Cancellation vs Shared Work

This becomes important once in-flight deduplication is enabled.

Suppose:

```text
Request A ─┐
           ├── shared resolution
Request B ─┘
```

Then:

```text
A cancels
```

must not automatically mean:

```text
shared operation cancels
```

because B may still require it.

The correct model is:

```text
shared operation
             /               \
        subscriber A       subscriber B
             │                  │
          cancel             active
```

The shared operation is cancelled only when:

```text
active subscribers = 0
```

This is the next runtime-level correctness requirement.

## In-flight Resolution Object

Instead of:

```ts
Map<string, Promise<Result>>
```

we should eventually use:

```ts
interface InFlight<T> {
  promise: Promise<T>;
  controller: AbortController;
  subscribers: number;
}
```

Then:

```text
acquire(key)
   ↓
subscribers++

release(key)
   ↓
subscribers--

if subscribers === 0
   ↓
abort shared operation
```

This avoids a subtle cancellation bug.

## Circuit Breaker

The runtime state machine remains:

```text
failures ≥ threshold
 CLOSED ─────────────────────────► OPEN
   ▲                                  │
   │                                  │ cooldown
   │                                  ▼
   │                              HALF_OPEN
   │                                  │
   │                         ┌────────┴────────┐
   │                         │                 │
   │                       success           failure
   │                         │                 │
   └─────────────────────────┘                 └──► OPEN
```

The breaker answers:

> Should we attempt this source now?

It does not answer:

> Is this source authorized?

That distinction should be enforced in code.

## Concurrency Must Be Explicit

If 20 adapters exist:

```text
20 adapters
    ↓
Promise.all(...)
```

is not automatically acceptable.

It creates:

```text
20 simultaneous external operations
```

The runtime needs a bounded semaphore:

```text
MAX_CONCURRENCY = 5

A B C D E
│ │ │ │ │
└─┴─┴─┴─┘
    ↓
capacity = 5

F waits
G waits
H waits
...
```

The limit belongs to the runtime, not individual adapters.

## SSRF Boundary

The moment a real adapter consumes external metadata, the returned URL
becomes untrusted.

The safe path is:

```text
remote provider
      │
      ▼
untrusted JSON
      │
      ▼
extract URL
      │
      ▼
URL syntax validation
      │
      ▼
network policy
      │
      ├── forbidden
      │
      └── allowed
             │
             ▼
          HTTP client
```

The HTTP client must not simply do:

```ts
fetch(candidate.url);
```

because candidate URLs may target:

```text
127.0.0.1
localhost
::1
private IPv4 ranges
private IPv6 ranges
link-local addresses
cloud metadata endpoints
internal DNS names
```

And redirects create a second validation point:

```text
allowed URL
   ↓
redirect
   ↓
new URL
   ↓
validate again
```

## Identity Cache

Identity results can be cached, but the cache must preserve semantic
state.

Bad:

```text
Map<string, CanonicalMedia | null>
```

Better:

```ts
type IdentityCacheValue =
  | {
      status: "resolved";
      media: CanonicalMedia;
    }
  | {
      status: "not_found";
    }
  | {
      status: "ambiguous";
      observations: readonly IdentityObservation[];
    }
  | {
      status: "not_resolved";
    };
```

Then:

```text
cache miss ≠ not found
```

This is critical.

## Negative Cache

Negative results may be cached, but with different TTLs.

For example:

```text
RESOLVED
  → longer TTL

NOT_FOUND
  → moderate TTL

AMBIGUOUS
  → shorter TTL

NOT_RESOLVED
  → very short TTL
```

Why?

Because:

```text
NOT_FOUND
```

is an explicit provider observation.

Whereas:

```text
NOT_RESOLVED
```

may simply mean:

```text
provider unavailable
timeout
rate limit
temporary failure
```

Caching them identically could suppress future successful resolution.

## Identity Cache Semantics

Therefore:

```text
id="cache-key"
identity cache key
    ↓
result
    + observedAt
    + expiresAt
    + source evidence
```

Example:

```json
{
  "status": "not_resolved",
  "observedAt": "2026-09-28T20:30:00Z",
  "expiresAt": "2026-09-28T20:31:00Z",
  "source": "tmdb"
}
```

This says:

We did not resolve this at that observation point.

It does **not** say:

This media does not exist.

## Network admission

A source can be authorized while its network behavior is prohibited.

Define:

```ts
interface NetworkDeclaration {
  readonly outboundHosts: readonly string[];

  readonly allowHttp: boolean;
  readonly allowHttps: boolean;

  readonly allowRedirects: boolean;

  readonly maxRedirects: number;
}
```

For example:

```json
{
  "outboundHosts": ["media.example.org"],
  "allowHttp": false,
  "allowHttps": true,
  "allowRedirects": true,
  "maxRedirects": 3
}
```

Then every extracted URL must pass:

```text
candidate URL
     │
     ▼
parse
     │
     ▼
scheme policy
     │
     ▼
hostname policy
     │
     ▼
IP policy
     │
     ▼
redirect policy
     │
     ▼
HTTP client
```

Never:

```ts
fetch(providerReturnedUrl);
```

without policy enforcement.

## Source limits

An adapter must not be allowed to consume unlimited runtime resources.

```ts
interface SourceLimits {
  readonly timeoutMs: number;

  readonly maxConcurrentRequests: number;

  readonly requestsPerMinute: number;

  readonly maxCandidates: number;
}
```

These are **operational constraints**, not authorization.

For example:

```text
authorization     = licensed

timeout     = 5000 ms
concurrency     = 2
rate     = 30/minute
maxCandidates     = 20
```

This prevents an otherwise valid adapter from becoming an uncontrolled
resource consumer.

## Failure semantics become richer

At this point a resolution can produce:

```text
Identity:     RESOLVED

Source A:     admitted     success
Source B:     admitted     timeout
Source C:     rejected     missing authorization evidence
```

The user-facing Stremio response might simply be:

```json
{
  "streams": [
    {
      "name": "owned-library",
      "title": "1080p · mp4",
      "url": "https://..."
    }
  ]
}
```

But internally the evidence ledger records:

```text
A → SUCCESS
B → TIMEOUT
C → REJECTED
```

This preserves the distinction between:

```text
no stream exists
```

and:

```text
stream existed but source was unavailable
```

and:

```text
source was deliberately excluded
```

## Source Runtime: from admitted adapter to controlled execution

We have established that:

```text
admitted ≠ executable
```

and:

```text
healthy ≠ authorized
```

The next boundary is the **source runtime**.

Its job is not to decide whether a source is lawful or authoritative.
That was handled by admission.

Its job is to ensure:

**An already-admitted source executes inside explicit operational
limits.**

```text
AdmissionDecision
       │
       ▼
ExecutableAdapter
       │
       ▼
SourceRuntime
       │
       ├── timeout
       ├── cancellation
       ├── concurrency
       ├── rate limit
       ├── circuit breaker
       ├── network policy
       ├── response limits
       └── validation
              │
              ▼
        Adapter Execution
```

## Never give adapters the raw HTTP client

A tempting design is:

```ts
class MyAdapter {
  async resolve(media) {
    return fetch("https://...");
  }
}
```

That creates several problems:

- SSRF protection becomes adapter-specific.
- timeouts become inconsistent.
- redirects may bypass policy.
- response limits may differ.
- retries may amplify traffic.
- instrumentation becomes fragmented.
- cancellation becomes unreliable.
- one adapter can accidentally ignore global limits.

Instead:

```ts
interface SourceHttpClient {
  request(
    request: SourceHttpRequest,
    context: SourceHttpContext
  ): Promise<SourceHttpResponse>;
}
```

The adapter receives a **constrained client**, not unrestricted
network access.

## Source HTTP contract

```ts
interface SourceHttpRequest {
  readonly method: "GET" | "HEAD";
  readonly url: string;

  readonly headers?: Readonly<Record<string, string>>;
}
```

Context:

```ts
interface SourceHttpContext {
  readonly signal: AbortSignal;
  readonly sourceId: string;
}
```

Response:

```ts
interface SourceHttpResponse {
  readonly status: number;
  readonly headers: Readonly<Record<string, string>>;

  readonly body: Uint8Array;

  readonly finalUrl: string;
}
```

The important design decision is that the adapter does not receive a
Node-specific `Response`.

The runtime owns the transport representation.

## Response limits

A source must not be allowed to return an arbitrarily large response.

Define:

```ts
interface HttpLimits {
  readonly maxResponseBytes: number;
  readonly maxHeaderBytes: number;
  readonly maxRedirects: number;
}
```

For metadata APIs, perhaps:

```text
maxResponseBytes = 2 MiB
```

For a source manifest:

```text
maxResponseBytes = 512 KiB
```

These values are configuration decisions, not universal truths.

The invariant is:

```text
response_size > limit
        ↓
reject
```

before unbounded buffering occurs.

## HTTP error taxonomy

Do not map every non-200 response into:

```text
source_network_error
```

Use a richer taxonomy.

```ts
type SourceHttpFailure =
  | "timeout"
  | "aborted"
  | "dns_failure"
  | "connection_failure"
  | "tls_failure"
  | "response_too_large"
  | "too_many_redirects"
  | "blocked_host"
  | "unsupported_scheme"
  | "rate_limited"
  | "server_error"
  | "client_error"
  | "invalid_response";
```

Then the resolver can make meaningful decisions.

For example:

```text
429 → rate_limited
503 → server_error
404 → source_empty / identity_not_found
timeout → source_timeout
```

But these mappings should be **adapter-aware**.

A `404` from an identity endpoint might mean:

```text
NOT_FOUND
```

while a `404` from a media asset endpoint might mean:

```text
candidate_missing
```

HTTP status is evidence.

It is not itself the domain meaning.

## Retry policy

Retries are dangerous if treated as universally beneficial.

A naive implementation:

```ts
for (let i = 0; i < 5; i++) {
  await fetch(...);
}
```

can turn one failing request into five.

Instead define:

```ts
interface RetryPolicy {
  readonly maxAttempts: number;

  readonly retryable: readonly SourceHttpFailure[];

  readonly baseDelayMs: number;

  readonly maxDelayMs: number;
}
```

Example:

```text
attempt 1
   ↓
temporary failure
   ↓
backoff
   ↓
attempt 2
   ↓
temporary failure
   ↓
backoff
   ↓
attempt 3
   ↓
final outcome
```

## Retry must respect cancellation

This is critical.

If:

```text
caller cancels
```

during backoff:

```text
sleep(1000)
```

must not continue blindly.

Instead:

```ts
await abortableDelay(delayMs, signal);
```

Therefore:

```text
caller cancellation
       │
       ├── HTTP request
       ├── retry delay
       └── adapter execution
```

all terminate through the same cancellation tree.

## Retry classification

A useful initial rule:

```text
Retry:
  timeout
  connection failure
  selected 5xx
  selected 429

Don't retry:
  malformed request
  blocked host
  unsupported scheme
  authorization rejection
  invalid source configuration
  deterministic 4xx
```

But even `429` needs care.

The server may provide:

```text
Retry-After
```

which should be respected where applicable.

## Rate limiter

Each source receives an independent limiter.

```text
              Global
                 │
        ┌────────┼────────┐
        ▼        ▼        ▼
    Source A  Source B  Source C
     limiter   limiter   limiter
```

This prevents one provider from consuming the entire runtime budget.

Conceptual contract:

```ts
interface RateLimiter {
  acquire(sourceId: string, signal: AbortSignal): Promise<void>;
}
```

Then:

```text
adapter request
      │
      ▼
rate limiter
      │
      ▼
semaphore
      │
      ▼
circuit breaker
      │
      ▼
HTTP policy
      │
      ▼
network
```

The ordering should be deliberate.

## Ordering of runtime gates

Recommended execution pipeline:

```text
1. admission
2. identity eligibility
3. circuit check
4. rate-limit acquisition
5. concurrency acquisition
6. timeout scope
7. network-policy validation
8. adapter execution
9. response validation
10. candidate validation
11. authorization
```

Why circuit before waiting?

If the circuit is already open:

```text
OPEN
```

we should fail immediately rather than occupying limiter/semaphore
capacity.

Why network validation before network I/O?

Because:

**A rejected URL should never reach the socket layer.**

## Source execution context

Rather than passing many independent arguments:

```ts
adapter.resolve(media, signal, timeout, languages, logger, metrics, ...);
```

create a constrained context:

```ts
interface SourceExecutionContext {
  readonly signal: AbortSignal;

  readonly sourceId: string;

  readonly preferredLanguages: readonly string[];

  readonly http: SourceHttpClient;

  readonly now: () => string;
}
```

The adapter can therefore perform source-specific operations without
acquiring unrestricted infrastructure.

## Capability-based runtime access

This creates a useful security boundary:

```text
Adapter
  │
  ├── receives canonical media
  ├── receives constrained HTTP client
  ├── receives AbortSignal
  └── receives source identity
```

It does **not** receive:

```text
filesystem
database
process.env
raw fetch
shell
arbitrary sockets
```

unless those capabilities are explicitly part of the adapter contract.

This dramatically reduces accidental coupling.

## Header policy

Do not blindly forward every configured header.

A source may have:

```text
Authorization
Cookie
X-API-Key
```

Those are sensitive.

Therefore distinguish:

```ts
interface SensitiveHeader {
  readonly name: string;
  readonly value: string;
  readonly redactInLogs: true;
}
```

Logging must produce:

```text
Authorization: [REDACTED]
```

not the token.

## URL policy and credentials

A dangerous pattern is:

```text
https://user:password@example.org/media.mp4
```

Candidate URLs should normally reject embedded credentials:

```ts
if (url.username || url.password) {
  throw new PolicyViolation("embedded_credentials");
}
```

Credentials belong in controlled transport configuration.

Not in URLs returned to Stremio.

## Redirect security

Suppose:

```text
https://authorized.example/media
```

returns:

```text
302 Location: http://127.0.0.1:8080/admin
```

A generic HTTP client following redirects would create an SSRF
vulnerability.

Therefore each redirect is a new policy decision:

```text
URL₀
 │
 ▼
validate
 │
 ▼
request
 │
 ▼
Location₁
 │
 ▼
validate again
 │
 ▼
request
 │
 ▼
Location₂
```

Never:

```text
validate first URL once
       ↓
follow all redirects
```

## DNS rebinding

Hostname validation alone is insufficient in a hostile network
environment.

Conceptually:

```text
allowed.example.org
       │
       ▼
DNS
       │
       ▼
203.0.113.x
```

Later:

```text
allowed.example.org
       │
       ▼
DNS
       │
       ▼
127.0.0.1
```

A robust network layer should therefore define how DNS resolution and
connection targets are validated.

This is especially important if arbitrary provider-controlled URLs are
ever accepted.

For an initial **operator-owned fixed-host source**, the attack
surface can be substantially reduced by restricting outbound hosts to
configured endpoints.

## Candidate URL policy

Candidate validation should therefore become:

```text
Candidate URL
    │
    ▼
syntax
    │
    ▼
scheme
    │
    ▼
credentials
    │
    ▼
hostname
    │
    ▼
IP / DNS policy
    │
    ▼
source allowlist
    │
    ▼
redirect policy
    │
    ▼
AUTHORIZED PLAYBACK URL
```

The resolver should never confuse:

```text
valid URL
```

with:

```text
safe URL
```

or:

```text
authorized URL
```

## Candidate URL validation

The owned-media adapter must not trust its own library blindly.

Even operator-owned configuration can contain mistakes.

So:

```text
LibraryAsset.playbackUrl
          │
          ▼
Candidate structural validation
          │
          ▼
Network policy
          │
          ▼
Candidate admission
```

For example:

```text
https://media.example.org/a.mp4
```

may pass.

But:

```text
file:///etc/passwd
```

must not.

And:

```text
http://127.0.0.1:8080/
```

should be rejected where the configured network policy disallows it.

## No credential-bearing playback URLs

The library should reject:

```text
https://user:secret@example.org/movie.mp4
```

at ingestion time.

This is stronger than waiting for candidate validation.

```ts
function validatePlaybackUrl(raw: string): URL {
  const url = new URL(raw);

  if (url.protocol !== "https:" && url.protocol !== "http:") {
    throw new Error("Unsupported playback scheme");
  }

  if (url.username || url.password) {
    throw new Error("Embedded credentials are forbidden");
  }

  return url;
}
```

The runtime network policy still remains the final enforcement layer.

## Source runtime wrapper

Now wrap the adapter.

```ts
interface SourceExecutor {
  execute(
    adapter: SourceAdapter,
    media: CanonicalMedia,
    context: ResolveContext
  ): Promise<readonly SourceCandidate[]>;
}
```

Implementation conceptually:

```text
SourceExecutor
     │
     ├── admission check
     ├── circuit check
     ├── limiter
     ├── semaphore
     ├── timeout
     ├── execution
     └── failure classification
```

The adapter itself remains unaware of:

- circuit state,
- global concurrency,
- retry policy,
- metrics,
- request IDs.

That belongs to runtime infrastructure.

## `404` is not automatically failure

For an owned library:

```text
findAssets(...)
       │
       ▼
[]
```

means:

```text
source_empty
```

if the library lookup successfully established that no asset exists.

But:

```text
database unavailable
```

means:

```text
source_network_error
```

or a source-specific infrastructure failure.

And:

```text
lookup timed out
```

means:

```text
source_timeout
```

Thus:

```text
empty ≠ failure
```

remains preserved.

## Metadata cache

Metadata is a strong candidate for caching.

But cache semantics must preserve state.

```ts
type MetadataCacheValue =
  | {
      readonly status: "resolved";
      readonly record: MetadataRecord;
    }
  | {
      readonly status: "not_found";
    }
  | {
      readonly status: "not_resolved";
    }
  | {
      readonly status: "ambiguous";
      readonly conflicts: readonly MetadataConflict[];
    };
```

Therefore:

```text
cache miss
    ≠ not_found
```

and:

```text
expired
    ≠ not_found
```

## Cache TTL policy

Different states should receive different TTLs.

Example policy:

```text
resolved:
    long

not_found:
    medium

ambiguous:
    short

not_resolved:
    very short
```

The exact durations belong in configuration.

The semantic distinction is architectural.

## Do not download artwork unnecessarily

For v0.1:

```text
provider
   ↓
poster URL
   ↓
Stremio meta response
```

is sufficient.

Do not build:

```text
provider
   ↓
addon
   ↓
download image
   ↓
store image
   ↓
serve image
```

unless there is a specific reason.

That would create another unnecessary proxy subsystem.

## Parallelism

Once identity is resolved:

```text
                 CanonicalMedia
                       │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
       metadata     source A    source B
       provider
           │           │           │
           └───────────┼───────────┘
                       ▼
                  aggregation
```

Metadata and stream resolution can run independently.

But only if their resource budgets are separate.

Do not allow a slow metadata provider to consume the entire
source-resolution concurrency budget.

## Independent runtime pools

Use:

```text
Runtime
│
├── identity pool
├── metadata pool
├── source pool
└── auxiliary pool
```

Each may have:

- concurrency limit
- timeout
- rate limiter
- circuit breaker

This prevents:

```text
metadata provider hangs
       ↓
all source requests blocked
       ↓
no playback
```

## Unified request context

At the top level:

```ts
interface ResolutionRequestContext {
  readonly requestId: string;

  readonly signal: AbortSignal;

  readonly preferredLanguages: readonly string[];
}
```

Then derive child contexts:

```text
RequestContext
      │
      ├── IdentityContext
      ├── MetadataContext
      └── SourceContext
```

Each subsystem receives only the capabilities it needs.

## Subtitle URL validation

A subtitle URL goes through the same security pipeline:

```text
provider
   │
   ▼
URL parse
   │
   ▼
scheme validation
   │
   ▼
credential rejection
   │
   ▼
host policy
   │
   ▼
redirect policy
   │
   ▼
candidate
```

A valid subtitle URL is not automatically an authorized subtitle URL.

## Subtitle content size

If the addon only returns URLs:

```text
addon → URL
```

it does not need to download subtitle contents.

If future functionality requires parsing subtitle files, introduce
strict limits:

```text
max subtitle bytes
max lines
max cue count
max processing time
```

Never let a provider-controlled file become an unbounded parser
workload.

## One runtime, different semantics

The runtime knows:

```text
timeout
rate limit
circuit
network
```

The provider knows:

```text
404 means NOT_FOUND
```

or:

```text
response field "tracks" contains subtitles
```

This creates a clean division:

```text
Transport semantics
        │
        ▼
Provider semantics
        │
        ▼
Domain semantics
```

## Stale-while-revalidate

A useful policy:

```text
fresh
   ↓
serve

stale but usable
   ↓
serve
   + schedule refresh

missing
   ↓
empty/error according to protocol
```

The policy should be explicit.

Do not let stale behavior emerge accidentally from cache
implementation details.

## Cancellation hierarchy

A Stremio request creates:

```text
Request AbortSignal
        │
        ├── identity
        ├── metadata
        ├── stream
        └── subtitle
```

But shared operations require care.

If two requests share:

```text
identity lookup
```

then:

```text
Request A cancelled
```

must not necessarily cancel the shared identity lookup for:

```text
Request B
```

Hence the earlier subscriber-counted in-flight abstraction.

## Request deadline

Rather than giving every subsystem an independent full timeout:

```text
request deadline
      │
      ├── identity
      ├── metadata
      └── stream
```

A stronger model is:

```ts
interface Deadline {
  readonly expiresAtMs: number;
}
```

Each subsystem receives:

```text
remainingMs(deadline)
```

This prevents:

```text
5 sec identity + 5 sec metadata + 5 sec stream = 15 sec request
```

when the client expected a bounded request.

## Deadline propagation

The request path becomes:

```text
request
  │
  ▼
deadline = now + budget
  │
  ├── identity: remaining
  ├── metadata: remaining
  ├── stream: remaining
  └── subtitles: remaining
```

Each provider must obey the remaining deadline.

This is more precise than independently setting arbitrary child
timeouts.

## Provider sandboxing

The next architectural question is stronger isolation.

A TypeScript provider running in-process can potentially access
things that the interface does not formally expose if the
implementation is compromised.

Therefore:

```text
Level 1 in-process interfaces
Level 2 restricted runtime
Level 3 worker/process isolation
Level 4 container isolation
```

Do not jump directly to Level 4.

The appropriate isolation level depends on the provider trust model.

## Dependency injection

Provider dependencies should be explicit:

```ts
interface ProviderDependencies {
  readonly http: SourceHttpClient;

  readonly credentials: SourceCredentialProvider;

  readonly clock: Clock;

  readonly logger: ProviderLogger;
}
```

No hidden globals.

No:

```text
process.env
global.fetch
Date.now()
console.log()
```

inside provider implementations.

## Clock boundary

Introduce:

```ts
interface Clock {
  now(): string;
  nowMs(): number;
}
```

Production:

```text
SystemClock
```

Tests:

```text
FakeClock
```

Replay:

```text
ReplayClock
```

This eliminates a major source of nondeterminism.

## Randomness boundary

If ranking or IDs ever require randomness:

```ts
interface RandomSource {
  bytes(length: number): Uint8Array;
}
```

But deterministic core algorithms should preferably require no
randomness at all.

Receipt IDs can be generated at the shell boundary.
