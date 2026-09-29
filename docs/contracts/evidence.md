# Contract: Evidence Levels & Receipts

[⇧ Architecture index](../architecture.md) · [⇆ Document map](../architecture/README.md)

> **Normative.** The single authoritative definition of the four evidence
> levels and the receipt/evidence-graph shapes built from them.
> `docs/architecture/07-evidence.md` explains the full philosophy
> (representation ≠ semantics ≠ evidence ≠ truth ≠ authority ≠
> authorization ≠ admission ≠ execution ≠ success ≠ canonicality ≠
> durability); it links here rather than redefining the levels.
>
> **Status:** DESIGNED. No implementation exists in the repository as of
> this revision.

## The four evidence levels

```text
OBSERVED
DERIVED
VERIFIED
ANNOTATED
```

| Level | Meaning |
|---|---|
| `OBSERVED` | A provider directly returned this value. |
| `DERIVED` | The system computed this value from other data. |
| `VERIFIED` | An explicit verification procedure succeeded for this value. |
| `ANNOTATED` | A human/operator supplied this value as additional context. |

**These four levels must never be silently collapsed into one another.**
A `DERIVED` value must never be presented as `VERIFIED`; an `ANNOTATED`
value must never be presented as `OBSERVED`. Collapsing a level is exactly
the kind of silent status-inflation this whole documentation set exists to
prevent (see the DESIGNED/PROPOSED/IMPLEMENTED/VERIFIED discipline in
`docs/architecture.md`).

### Worked example

- Provider returns `title = "Example Movie"` → **OBSERVED**
- System computes `normalizedTitle = "example movie"` → **DERIVED**
- An identity resolver establishes `IMDb tt1234567 ↔ TMDB 999` → **VERIFIED**
- An operator supplies `source is operator-owned` → **ANNOTATED**, or
  **VERIFIED** if and only if an actual verification procedure ran —
  the level recorded must reflect what actually happened, not what was
  hoped for.

## Evidence graph (conceptual shape)

```text
                         REQUEST
                            │
                            ▼
                       OBSERVATION
                            │
                  ┌─────────┼─────────┐
                  ▼         ▼         ▼
              Identity   Metadata   Source
              Evidence   Evidence   Evidence
                  │         │         │
                  └─────────┼─────────┘
                            ▼
                        DERIVATION
                            │
                 ┌──────────┼──────────┐
                 ▼          ▼          ▼
              Canonical   Catalog   Candidates
```

Field-level provenance matters: different fields on the same record can
carry different evidence levels, and the system must preserve those
per-field distinctions rather than collapsing a whole record to its
lowest or highest common level (see `docs/architecture/07-evidence.md`,
"But do not share mutable conclusions blindly").

## Binding invariants

- An evidence level is a property of a *fact*, not of a *record* — a
  single `CanonicalMedia` or `SourceCandidate` can (and usually does) mix
  evidence levels across its fields.
- Evidence levels are never inferred implicitly from where data came from;
  they are recorded explicitly at the point of observation/derivation/
  verification/annotation.
- Replay of a receipt/evidence graph is not the same as re-fetching from
  the original provider — see `docs/architecture/07-evidence.md`
  ("Replay ≠ re-fetch") — and must not silently change previously recorded
  evidence levels.
- "No evidence, no VERIFIED claim" applies uniformly across the domain
  model and the testing/CI process itself — see
  `docs/architecture/11-testing.md`.

## Related contracts

- Identity observations that carry these levels: `docs/contracts/identity.md`
- Candidate fields that carry these levels: `docs/contracts/stream.md`
