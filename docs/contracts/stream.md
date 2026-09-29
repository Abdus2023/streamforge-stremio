# Contract: `SourceCandidate` / `Stream` / Subtitle Types

[⇧ Architecture index](../architecture.md) · [⇆ Document map](../architecture/README.md)

> **Normative.** The single authoritative definition of the internal
> candidate/evidence object (`SourceCandidate`) and the external,
> protocol-facing `Stream` shape it is mapped to. `docs/architecture/02-domain.md`
> explains the type's place in the domain model; `docs/architecture/08-protocols.md`
> explains the Stremio-facing mapping; neither redefines the shapes below.
>
> **Status:** DESIGNED. No implementation exists in the repository as of
> this revision.

## `SourceCandidate` (internal evidence object)

`SourceCandidate` is the central internal object of the whole system —
every adapter produces these, every ranking/dedup/policy stage consumes
them, and only a small, deliberately narrowed subset of these fields is
ever mapped into a protocol-facing `Stream`.

```ts
export interface SourceCandidate {
  readonly sourceId: string;

  readonly media: MediaRef;

  readonly location: {
    readonly url: string;
  };

  readonly mediaInfo: {
    readonly container?: string;
    readonly videoCodec?: string;
    readonly audioCodec?: string;
    readonly width?: number;
    readonly height?: number;
    readonly bitrate?: number;
    readonly sizeBytes?: number;
    readonly durationSeconds?: number;
  };

  readonly language: {
    readonly audio?: readonly string[];
    readonly subtitle?: readonly string[];
  };

  readonly provenance: {
    readonly adapter: string;
    readonly sourceRecordId?: string;
    readonly observedAt: string;
  };

  readonly capabilities: {
    readonly directPlayback: boolean;
    readonly seekable?: boolean;
    readonly live?: boolean;
  };

  readonly authorization: {
    readonly status: "authorized" | "unknown" | "denied";
    readonly basis?: string;
  };
}
```

## Known variants (audit findings, not part of the frozen shape)

Re-auditing `02-domain.md` and `03-resolution.md` on 2026-09-29 found two
earlier `SourceCandidate` drafts that do not match the frozen shape above:

- An early draft uses a flat `quality?: { width?, height?, label? }`
  block, string-array `language?`/`subtitles?` fields, an embedded
  `metadata: { title?, releaseYear? }` block, and — most importantly —
  `capabilities: { directPlayback, authorized: boolean, stableUrl }`.
  **`authorized: boolean` cannot represent `"unknown"`.** This directly
  conflicts with the tri-state `authorized | unknown | denied`
  authorization model that is treated as a core, repeated invariant
  everywhere else in the documentation set (including `README.md` and
  `docs/architecture/05-policy.md`). This draft is classified
  **SUPERSEDED**, not merely historical, precisely because keeping it
  live would silently violate a load-bearing invariant. Recorded as
  `OPEN-7` in `docs/decisions/README.md` for visibility, with a strong
  recommendation (not yet a formal ADR) that it stay superseded.
- An intermediate draft matches the frozen `location`/`mediaInfo`/
  `language`/`provenance`/`capabilities` structure exactly, but omits the
  `authorization` block entirely. This is classified **HISTORICAL** — it
  looks like a snapshot taken mid-way through adding the authorization
  block, not a competing design.

## `Stream` (Stremio-facing, protocol output)

```json
{
  "streams": [
    {
      "name": "authorized-fixture",
      "title": "1080p · mp4",
      "url": "https://media.example.test/movie.mp4"
    }
  ]
}
```

The internal evidence model (`SourceCandidate`, with provenance,
authorization status, capability flags, etc.) is deliberately **not** the
same shape as the external Stremio presentation model. This boundary is a
core invariant:

```text
internal evidence model  ≠  Stremio presentation model
```

Only candidates that have passed policy filtering (see
`docs/architecture/05-policy.md`) and ranking/deduplication (see
`docs/architecture/03-resolution.md`) are ever mapped to a `Stream`, and
the mapping is one-directional and lossy by design — provenance,
authorization basis, and raw provider identifiers are never leaked to the
protocol layer (see `docs/architecture/08-protocols.md`, "Do not leak
provider internals").

## Subtitle candidate — DEFERRED, out of V0.1 freeze scope

**RESOLVED by `ADR-005` (2026-09-29).** `docs/architecture/13-roadmap.md`
explicitly places `/subtitles` under `NOT YET ADVERTISED` for V0.1 — no
V0.1 component requires a frozen subtitle contract, and
`SourceCandidate.language.subtitle` above is a plain `readonly string[]`
of language codes, not a reference to a subtitle candidate object, so
nothing in this file's frozen V0.1 shapes depends on it.

The four non-identical `SubtitleCandidate` drafts in
`docs/architecture/02-domain.md` remain as PROPOSED/EXPLORATORY material
for a future V0.2+ subtitle contract; none is chosen as canonical here.
See [`ADR-005`](../decisions/ADR-005-subtitle-v0.1-scope.md) for the full
reasoning. **No V0.1 implementer needs to read further to build
`/manifest` or `/stream`.**

## `ResolutionResult` / `AdapterExecution`

The canonical request-level outcome and per-adapter execution evidence are
defined in [`docs/contracts/result.md`](./result.md), which was added by
ADR-007.

This file intentionally does not redefine those types. The semantic boundary
is:

```
ResolutionResult    = final request-level outcome
AdapterExecution[]  = execution-level evidence used to derive that outcome
```

The older `ResolutionResult` draft in `docs/architecture/03-resolution.md`
that embedded `executions` directly is historical/superseded.

## Binding invariants

- Deduplication and ranking of `SourceCandidate[]` are deterministic, with
  `sourceId` as an explicit tiebreaker (see `docs/architecture/03-resolution.md`).
- A candidate's `authorization.status` defaults to `"unknown"`; `"unknown"`
  is never treated as `"authorized"` (see `docs/architecture/05-policy.md`).
- Candidates, and anything derived from them that reaches a log, metric,
  receipt, or manifest, must never contain secrets (see
  `docs/architecture/06-runtime.md` and `docs/architecture/10-observability.md`
  on redaction).

## Related contracts

- The adapter that produces these candidates: `docs/contracts/source-adapter.md`
- The `MediaRef` embedded in every candidate: `docs/contracts/identity.md`
- Evidence-level semantics for candidate fields: `docs/contracts/evidence.md`
