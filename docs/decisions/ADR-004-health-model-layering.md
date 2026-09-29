# ADR-004: `HealthResult`, `SourceHealthCounters`, and `SourceHealthSnapshot` are three distinct layers

[⇧ Back to the decision ledger](./README.md)

- **Status:** ACCEPTED
- **Date:** 2026-09-29
- **Resolves:** `OPEN-1` in `docs/decisions/README.md`
- **Affects:** `docs/contracts/source-adapter.md`, `docs/architecture/04-providers.md`, `docs/architecture/10-observability.md`

## Context

Three "is this provider okay" shapes exist:

1. `HealthResult` (`docs/contracts/source-adapter.md`) — `{ healthy,
   checkedAt, detail? }`. Returned by an adapter's own optional `health()`
   probe — adapter-authored, point-in-time.
2. `SourceHealth` (`docs/architecture/04-providers.md`) — `{ successes,
   failures, timeouts, latencyMs }`. Runtime-maintained running counters.
3. `SourceHealth` (`docs/architecture/10-observability.md`) — `{
   adapterId, requests, successes, empty, failures, timeoutCount,
   consecutiveFailures, latency: {p50, p95, p99} }`. A richer, exported
   metrics snapshot.

**Two different interfaces share the identical name `SourceHealth`.** Per
Phase 9's own framing, this is "demonstrably harmful" — an implementer
grepping for `SourceHealth` will find two incompatible shapes with no way
to tell from the name alone which one a given piece of code means.

## Problem

Are these one duplicated concept, or three legitimate layers? If three
layers, the naming collision must be fixed so they cannot be confused.

## Decision

**These are three legitimate, distinct layers**, not duplicates:

| Layer | Type (renamed where needed) | Role | Produced by | Consumed by |
|---|---|---|---|---|
| Point-in-time probe | `HealthResult` (unchanged) | An adapter's own self-report at the moment it's asked | `SourceAdapter.health()` | Runtime health checks, `/health/ready` |
| Running runtime state | `SourceHealthCounters` (renamed from `SourceHealth` in `04-providers.md`) | Rolling counters the runtime keeps per adapter to decide circuit-breaker transitions | The runtime (circuit breaker), updated after every call | The circuit breaker itself |
| Exported observability snapshot | `SourceHealthSnapshot` (renamed from `SourceHealth` in `10-observability.md`) | A derived, point-in-time-exportable view for metrics/dashboards | The observability layer, reading `SourceHealthCounters` | Metrics endpoints, operators |

Rationale for keeping three types rather than merging: each has a
different producer, a different consumer, and a different update
cadence (probe = on-demand; counters = updated per-call, internal;
snapshot = derived, exported, potentially less frequently refreshed).
Merging them would force the runtime's internal per-call bookkeeping
structure to also be the public metrics contract, coupling an
implementation detail to an external interface.

## Rejected alternatives

- Merging all three into one `HealthResult` — rejected: would force
  every adapter's `health()` return value to also carry rolling counters
  it has no way to compute (those live in the runtime, not the adapter).
- Leaving both `SourceHealth` names as-is — rejected: this is the literal
  naming collision the phase asked to check for; leaving it allows silent
  misuse (e.g., a metrics exporter accidentally typed against the
  provider-internal counters struct).

## Migration implications

Purely a rename in documentation; no implementation exists to migrate.
`docs/architecture/04-providers.md`'s `SourceHealth` becomes
`SourceHealthCounters`; `docs/architecture/10-observability.md`'s
`SourceHealth` becomes `SourceHealthSnapshot`.

## Affected contracts

- `docs/contracts/source-adapter.md` — `HealthResult` unchanged; add a
  cross-reference to the other two layers now that they have distinct
  names.

## Status

ACCEPTED. `OPEN-1` is now `RESOLVED` (see `docs/decisions/README.md`).
