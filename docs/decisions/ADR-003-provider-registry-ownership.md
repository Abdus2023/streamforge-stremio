# ADR-003: `SourceRegistry` is the V0.1 registry; `ProviderRegistry<T>` is a deferred generalization

[⇧ Back to the decision ledger](./README.md)

- **Status:** ACCEPTED
- **Date:** 2026-09-29
- **Resolves:** `OPEN-4` in `docs/decisions/README.md`
- **Affects:** `docs/contracts/source-adapter.md`, `docs/architecture/04-providers.md`, `docs/architecture/13-roadmap.md`

## Context

`docs/architecture/04-providers.md`, "Provider registry" section, states
the choice explicitly in the monolith's own words:

> "The original `SourceRegistry` can eventually become: `interface
> ProviderRegistry { readonly sources: SourceRegistry; readonly metadata:
> MetadataProviderRegistry; readonly subtitles: SubtitleProviderRegistry }`
> Or a typed generic registry: `ProviderRegistry<SourceProvider>`,
> `ProviderRegistry<MetadataProvider>`, `ProviderRegistry<SubtitleProvider>`.
> Avoid one untyped registry containing arbitrary plugin objects."

This already frames `SourceRegistry` as the starting point and both
composite and generic registries as things it "can eventually become" —
i.e., the monolith itself treats this as an evolution question, not a
genuine either/or contradiction.

## Problem

Should V0.1 freeze `SourceRegistry` (sources only) or the generic
`ProviderRegistry<T>`?

## Observed evidence

`docs/architecture/13-roadmap.md`'s V0.1 freeze scope lists exactly one
`PROVIDER` line: `operator-owned media library` (a source), and explicitly
places `/catalog`, `/meta`, `/subtitles` under `NOT YET ADVERTISED`. There
are no metadata, subtitle, or catalog providers in V0.1 at all — so there
is nothing for a generalized, multi-kind `ProviderRegistry<T>` to
register beyond sources in V0.1.

## Decision

- **V0.1 freezes `SourceRegistry`** (sources only, from
  `docs/contracts/source-adapter.md`), unchanged in role: register,
  enumerate, and (per `ADR-001`) filter adapters in two stages
  (`supportsMedia` pre-identity, `supportsIdentity` post-identity).
- **`ProviderRegistry<T>`** is explicitly marked **PROPOSED / DEFERRED to
  V0.2+**, for when metadata, subtitle, and/or catalog providers are
  introduced (see `ADR-005` for subtitles specifically). It is preserved
  in `docs/contracts/source-adapter.md` as documented future direction,
  not as a competing V0.1 contract.
- **The composite-registry shape** (`ProviderRegistry { sources, metadata,
  subtitles }`) is also deferred and not chosen over the generic form —
  no evidence was found preferring one over the other, and the decision is
  not needed until V0.2 scoping happens, at which point it should be
  revisited with the metadata/subtitle designs in hand.

## Rejected alternatives

- Freezing `ProviderRegistry<T>` now, ahead of need — rejected because it
  would be freezing a shape with no V0.1 consumer, guessing at ergonomics
  that should instead be settled once a second provider kind actually
  exists.
- An untyped, single generic-object registry — explicitly rejected by the
  monolith's own text ("would weaken compile-time guarantees").

## Migration implications

None for V0.1. When V0.2 introduces a second provider kind, this ADR
should be revisited (not silently superseded) to choose between the
composite and generic shapes using the concrete metadata/subtitle designs
available at that time.

## Affected contracts

- `docs/contracts/source-adapter.md` — `SourceRegistry` marked as the
  V0.1-frozen registry; `ProviderRegistry<T>` marked PROPOSED/DEFERRED.

## Status

ACCEPTED. `OPEN-4` is now `RESOLVED` (see `docs/decisions/README.md`).
