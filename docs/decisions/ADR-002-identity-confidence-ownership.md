# ADR-002: Identity confidence lives in the evidence layer, not on `CanonicalMedia`

[⇧ Back to the decision ledger](./README.md)

- **Status:** ACCEPTED
- **Date:** 2026-09-29
- **Resolves:** `OPEN-2` in `docs/decisions/README.md`
- **Affects:** `docs/contracts/identity.md`, `docs/architecture/04-providers.md` (`IdentityObservation`), `docs/architecture/07-evidence.md` (`MediaIdentity`, `IdentityEvidence`, `IdentityReceipt`)

## Context

Three overlapping identity-outcome shapes exist in the documentation set:

1. `IdentityResolution` (`docs/architecture/03-resolution.md`) — the
   `IdentityResolver.resolve()` return type: a discriminated union
   (`resolved` → `CanonicalMedia`; `ambiguous` → `CanonicalMedia[]`;
   `not_found`). This is the request-time result the rest of the pipeline
   consumes.
2. `IdentityReceipt` (`docs/architecture/07-evidence.md`) — an audit/evidence
   record: `receiptId`, `requestIdentity`, `observations:
   IdentityObservation[]`, `outcome` (a 4-state enum that additionally
   includes `"not_resolved"`, absent from `IdentityResolution`),
   `canonicalId?`, `observedAt`.
3. `MediaIdentity` / `IdentityEvidence` (`docs/architecture/07-evidence.md`,
   a separate section) — `MediaIdentity { canonical?, aliases,
   evidence: IdentityEvidence[] }`, where `IdentityEvidence { provider,
   matchedBy, confidence: "verified"|"probable"|"ambiguous" }`. This is
   the only one of the three that carries a `confidence` concept, and it
   was never wired into `CanonicalMedia`, `IdentityObservation`, or
   `IdentityReceipt`.

`IdentityObservation` (`docs/architecture/04-providers.md`, what an
identity-provider adapter actually returns) has **no** confidence field:

```ts
export interface IdentityObservation {
  readonly status: "resolved" | "not_found" | "ambiguous" | "not_resolved";
  readonly identities: readonly ExternalIdentity[];
  readonly source: string;
  readonly observedAt: string;
}
```

## Problem

Where does identity confidence belong: on the domain type
(`CanonicalMedia`/`ExternalIdentity`), or on the evidence/observation
type (`IdentityObservation`/`IdentityReceipt`)? Leaving this
unanswered means an implementer must guess where to read or write
confidence when building the identity resolver.

## Options considered

**Option 1 — `ExternalIdentity` gains a `confidence` field directly.**
Rejected: `ExternalIdentity` is a domain type representing "an external
identifier the system currently considers linked to this media." Baking a
confidence score into it conflates the *domain state* (what the system
currently believes) with the *evidence* backing that belief — this is
exactly the `evidence ≠ truth` boundary that `07-evidence.md` states as a
governing principle throughout the documentation set. `CanonicalMedia`
and `ExternalIdentity` are meant to be read by every downstream consumer
(resolution, ranking, protocol mapping) without those consumers needing
to interpret a confidence score to use the data.

**Option 2 — `CanonicalMedia` gains an `evidence: IdentityEvidence[]`
field.** Rejected for the same reason as Option 1 — it would make the
domain snapshot carry its own audit trail, duplicating what
`IdentityReceipt` already exists to do, and would make `CanonicalMedia`
mutable-shaped in a way inconsistent with its role as an immutable,
already-resolved snapshot.

**Option 3 — confidence lives on the evidence/observation layer
(`IdentityObservation`, surfaced through `IdentityReceipt`), and
`MediaIdentity`/`IdentityEvidence` are retired as a separate model,
merged into `IdentityObservation`.** Accepted.

## Decision

1. **`CanonicalMedia` and `ExternalIdentity` remain confidence-free.**
   They represent current resolved domain state, not evidence.
2. **`IdentityObservation` gains an optional `confidence` field and a
   `matchedBy` field**, borrowed directly from the now-retired
   `IdentityEvidence`:

   ```ts
   export interface IdentityObservation {
     readonly status: "resolved" | "not_found" | "ambiguous" | "not_resolved";
     readonly identities: readonly ExternalIdentity[];
     readonly source: string;
     readonly observedAt: string;

     /** How this observation was matched, if known. */
     readonly matchedBy?:
       | "exact_id"
       | "external_id"
       | "title_year"
       | "title_episode"
       | "manual";

     /** How much this specific observation should be trusted. */
     readonly confidence?: "verified" | "probable" | "ambiguous";
   }
   ```

3. **`MediaIdentity`/`IdentityEvidence` (the separate model in
   `07-evidence.md`) are marked SUPERSEDED**, not deleted — their content
   is preserved as historical rationale for *why* confidence matters, with
   an explicit pointer to the merged shape above.
4. **`IdentityReceipt.observations` is unchanged in shape** — it already
   holds `readonly IdentityObservation[]`, so it automatically gains
   confidence/matchedBy visibility once `IdentityObservation` is updated,
   with no receipt-shape change required.

## Rationale

This keeps the domain layer (`contracts/identity.md`) and the evidence
layer (`contracts/evidence.md`, `IdentityObservation`/`IdentityReceipt` in
`04-providers.md`/`07-evidence.md`) cleanly separated, consistent with the
`representation ≠ semantics ≠ evidence ≠ truth` boundary chain that is a
governing principle repeated throughout this documentation set. It also
avoids inventing a new type: `IdentityObservation` already exists and is
already the shape adapters return, so adding two optional fields is the
smallest possible change that closes the gap.

## Rejected alternatives

- Options 1 and 2 above (confidence directly on the domain type).
- Introducing a brand-new `IdentityResolutionResult { CanonicalMedia,
  IdentityEvidence[] }` wrapper type, as one plausible design floated in
  the audit request that triggered this ADR — rejected because
  `IdentityResolution` (the resolver's actual return type) and
  `IdentityReceipt` (the evidence record) already jointly cover this need;
  adding a third wrapper type would create a fourth identity-outcome shape
  instead of reducing the existing three to two.

## Migration implications

None for running code (no implementation exists yet). Documentation-only:
`IdentityObservation` gains two optional fields; `MediaIdentity`/
`IdentityEvidence` section in `07-evidence.md` is annotated as superseded.

## Follow-up (non-blocking, recorded not silently fixed)

`IdentityResolution`'s discriminated union has 3 states (`resolved`,
`ambiguous`, `not_found`) while `IdentityReceipt.outcome` has 4
(adds `not_resolved`). This is a real, minor inconsistency, recorded as
`OPEN-10` in `docs/decisions/README.md` rather than silently reconciled,
since picking which of the two should gain/lose a state is not implied by
any evidence gathered for this ADR.

## Affected contracts

- `docs/contracts/identity.md` — annotated with this decision; no field
  changes to `CanonicalMedia`/`ExternalIdentity` themselves (that is the
  point of the decision).

## Status

ACCEPTED. `OPEN-2` is now `RESOLVED` (see `docs/decisions/README.md`).
