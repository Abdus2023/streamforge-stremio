# ADR-005: Subtitles are out of the V0.1 contract-freeze scope

[⇧ Back to the decision ledger](./README.md)

- **Status:** ACCEPTED
- **Date:** 2026-09-29
- **Resolves:** `OPEN-3` in `docs/decisions/README.md`
- **Affects:** `docs/contracts/stream.md`, `docs/architecture/04-providers.md`, `docs/architecture/08-protocols.md`, `docs/architecture/02-domain.md`, `docs/architecture/13-roadmap.md`

## Context

`SubtitleCandidate` is defined **4** different times in
`docs/architecture/02-domain.md` (verified by re-grep during this
normalization pass — the previous audit undercounted this as 3) with
different fields (e.g. `forced` present in 2 of 4 drafts; required vs.
optional `hearingImpaired`; inline vs. named `Provenance`/`Authorization`
types; inline vs. named `SubtitleFormat`; differing `authorization.status`
enums), and none was ever marked canonical.

## Problem

Should V0.1 freeze one of the four `SubtitleCandidate` drafts, or is
subtitle support out of scope for V0.1 entirely?

## Observed evidence

`docs/architecture/13-roadmap.md`'s V0.1 freeze scope is explicit:

```text
NOT YET ADVERTISED
├── /catalog
├── /meta
└── /subtitles
```

Subtitles are explicitly excluded from the V0.1 Stremio surface (only
`/manifest` and `/stream` are advertised). There is no V0.1 requirement to
freeze a subtitle contract at all.

## Decision

**Subtitles are deferred to V0.2+.** No `SubtitleCandidate` shape is
frozen in this revision. The four existing drafts remain in
`docs/architecture/02-domain.md` as PROPOSED/EXPLORATORY material for a
future subtitle contract, explicitly not part of the V0.1 freeze.

**Verified:** no V0.1-core contract requires a `SubtitleCandidate`
reference. `SourceCandidate.language.subtitle` is a `readonly string[]`
of language codes (evidence of which subtitle languages a stream embeds),
not a reference to a `SubtitleCandidate` object — so `contracts/stream.md`
does not need `SubtitleCandidate` to be frozen for `SourceCandidate`/
`Stream` themselves to be usable in V0.1.

## Rejected alternatives

- Picking one of the three existing drafts as canonical "since we're
  auditing anyway" — rejected: doing so would freeze a contract with no
  V0.1 consumer, and none of the three drafts was clearly the intended
  final shape (unlike `MediaRef`/`CanonicalMedia`/`SourceCandidate`, where
  one draft consistently matched the shape used everywhere else).

## Migration implications

None for V0.1 implementation. When subtitle support is scheduled, this
ADR should be revisited together with `ADR-003` (provider registry
generalization), since a subtitle provider is exactly the kind of second
provider kind that would justify generalizing `SourceRegistry` into
`ProviderRegistry<T>`.

## Affected contracts

- `docs/contracts/stream.md` — subtitle section marked DEFERRED, not
  frozen, with a pointer to this ADR.

## Status

ACCEPTED. `OPEN-3` is now `RESOLVED` (deferred, not frozen) — see
`docs/decisions/README.md`.
