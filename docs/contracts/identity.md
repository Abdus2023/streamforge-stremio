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

## Known variants (audit findings, not part of the frozen shape)

Re-auditing `02-domain.md` on 2026-09-29 found that both `MediaRef` and
`CanonicalMedia` have multiple, non-identical historical drafts. None are
deleted; they are classified here.

**`MediaRef`** — 3 earlier drafts embed `imdbId?: string` and
`tmdbId?: string` directly on `MediaRef` itself, mixing "a reference to a
piece of media" with "external identifiers for that media." The frozen
shape above deliberately does not do this — external identifiers live in
`ExternalIdentity` instead, each with its own `source`/`observedAt`
provenance. This is recorded as `OPEN-5` (see `docs/decisions/README.md`):
the identifier-bearing drafts are almost certainly superseded by the
identity-as-evidence model, but no section in the monolith explicitly
says so, so it is recorded as an explicit decision here rather than
silently assumed.

**`CanonicalMedia`** — 3 earlier drafts exist beyond the frozen shape:
one conflates identity with presentation fields (`title`, `year`,
`imdbId`, `tmdbId` all on `CanonicalMedia` directly); one represents
`identities` as a `ReadonlyMap<IdentityKind, string>` (losing per-identity
provenance — no `source`, no `observedAt`); the frozen shape uses
`readonly ExternalIdentity[]`, which is the only variant that preserves
full provenance per identity. Recorded as `OPEN-6`.

**Confidence is not missing from the architecture — it is unreconciled.**
`OPEN-2` (previously "CanonicalMedia confidence... may need to be added")
is now backed by concrete evidence: `docs/architecture/07-evidence.md`
defines a *separate*, more detailed identity-evidence model —
`MediaIdentity { canonical, aliases, evidence: readonly IdentityEvidence[] }`
and `IdentityEvidence { provider, matchedBy, confidence: "verified" |
"probable" | "ambiguous" }` — that already carries a confidence concept,
but it has never been wired into `CanonicalMedia`/`ExternalIdentity`
above. Compounding this, `07-evidence.md` also restates a *minimal*
`ExternalIdentity { kind; value }` (dropping `source`/`observedAt`)
immediately before introducing `MediaIdentity`/`IdentityEvidence` — that
restatement is superseded by the frozen `ExternalIdentity` above and
should be read as scaffolding for the `MediaIdentity` discussion, not as
a competing frozen shape. The open question is not "should confidence exist" (it already
does, in `07-evidence.md`) but "which type owns it": does `ExternalIdentity`
gain a `confidence` field, does `CanonicalMedia` gain an `evidence` array
of `IdentityEvidence`, or do `CanonicalMedia` and `MediaIdentity` need to
be merged/reconciled into one identity model? See `OPEN-2` in
`docs/decisions/README.md` for the updated framing.

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
