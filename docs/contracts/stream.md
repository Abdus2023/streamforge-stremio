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

## Subtitle candidate

Subtitles follow the same candidate model as source candidates: a
subtitle-specific candidate type, produced by subtitle provider adapters,
deduplicated and ranked before being mapped to the Stremio `/subtitles`
response shape. See `docs/architecture/04-providers.md` and
`docs/architecture/08-protocols.md` for the subtitle-specific provider
contract and protocol mapping respectively; the exact frozen subtitle
candidate field list was not finalized in the source monolith and is
tracked as **OPEN** — see `docs/decisions/README.md`.

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
