# Contract: Identity Types

[⇧ Architecture index](../architecture.md) · [⇆ Document map](../architecture/README.md)

> **Normative.** The single authoritative definition of `MediaRef`,
> `ExternalIdentity`, and `CanonicalMedia`. `docs/architecture/02-domain.md`
> and `docs/architecture/03-resolution.md` explain the semantics and the
> resolution process around these types; they link here rather than
> redefining the shapes.
>
> **Status:** DESIGNED. No implementation exists in the repository as of
> this revision.

## `MediaRef`

The minimal, protocol-neutral reference to "a piece of media" used
throughout the core application. Deliberately has **no** Stremio
dependency, provider dependency, or HTTP dependency.

```ts
export type MediaType = "movie" | "series";

export interface MediaRef {
  readonly type: MediaType;
  readonly id: string;
  readonly season?: number;
  readonly episode?: number;
}
```

## `ExternalIdentity`

A single observed mapping between a piece of media and an identifier from
some external namespace (IMDb, TMDB, TVDB, or an internal source-local ID).
An `ExternalIdentity` is **evidence**, not a fact — see
`docs/architecture/07-evidence.md` for the general evidence model this
fits into.

```ts
export type IdentityKind = "imdb" | "tmdb" | "tvdb" | "internal";

export interface ExternalIdentity {
  readonly kind: IdentityKind;
  readonly value: string;
  readonly source: string;
  readonly observedAt: string;
}
```

## `CanonicalMedia`

The system's own canonical identity record: an internally minted
`canonicalId` plus the set of external identities that have been
reconciled onto it.

```ts
export interface CanonicalMedia {
  readonly canonicalId: string;
  readonly media: MediaRef;
  readonly identities: readonly ExternalIdentity[];
  readonly resolvedAt: string;
}
```

Example:

```json
{
  "canonicalId": "media:01J...",
  "media": { "type": "movie", "id": "tt1234567" },
  "identities": [
    { "kind": "imdb", "value": "tt1234567", "source": "cinemeta", "observedAt": "2026-09-28T20:00:00Z" },
    { "kind": "tmdb", "value": "550", "source": "tmdb", "observedAt": "2026-09-28T20:00:01Z" }
  ],
  "resolvedAt": "2026-09-28T20:00:01Z"
}
```

## Binding invariants

- The canonical ID (`canonicalId`) is minted by StreamForge itself and is
  never equal to, or a bare passthrough of, any single external ID.
- External identifiers remain provenance-bearing observations; they are
  never silently promoted to canonical fact (see
  `docs/architecture/07-evidence.md`).
- Identity ambiguity or conflict is represented explicitly — it is never
  silently resolved to a single guess (see `docs/architecture/02-domain.md`,
  "Never silently resolve ambiguity").
- The *algorithm* that produces a `CanonicalMedia` from raw `MediaRef` +
  provider observations lives in `docs/architecture/03-resolution.md`
  ("Identity Resolution Algorithm"); this file only fixes the shapes.
- Identity resolution is a distinct pipeline stage from authorization and
  from provider admission — see `docs/architecture/05-policy.md` for why
  those must never be collapsed.

## Related contracts

- Candidates that reference a `MediaRef`: `docs/contracts/stream.md`
- Adapter interface that receives a `MediaRef`: `docs/contracts/source-adapter.md`
- Evidence levels applied to identity observations: `docs/contracts/evidence.md`
