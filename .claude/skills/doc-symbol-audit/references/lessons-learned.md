# Lessons learned (from real audit mistakes)

These are real mistakes made during the documentation-contract
normalization work this skill set was extracted from. Both were caught
by re-checking evidence rather than trusting a prior summary — that
re-checking habit is the actual lesson, not just the two specific bugs.

## 1. "Identical" claims must be verified character-by-character

An early pass claimed two occurrences of an `AdapterStatus` enum-like
`type` alias in the same file were "identical duplication," and wrote
that claim into a decision record (an ADR) and a normative contract file.
A later, closer re-read — diffing the two value lists line-by-line —
found they were **not** identical: one had 10 union members, the other
had 9 (one added an `http_error` value the other didn't have).

**Lesson:** never write "these are identical" into a decision record
without actually diffing the full bodies side-by-side (e.g. with `diff`
on two extracted blocks, or by eye against both printed in full). A
summary from an earlier pass, even your own, is not evidence — re-derive
it. This mistake, once caught, was corrected everywhere it had already
propagated (the ADR text, a contract file's "known variants" table, and
two inline annotations) rather than left in place.

## 2. Not every group of similarly-named/similarly-shaped types is one duplicated concept

A family of receipt/evidence types (`ReceiptEnvelope`, `EvidenceRecord<T>`,
`IdentityReceipt`, `MetadataReceipt`, `SourceExecutionReceipt`) shared
several field names across types (`receiptId`, timestamps, an
outcome/status field) and could have been mistaken for redundant,
overlapping definitions of "the same thing." A field-by-field read found
they were **three legitimate layers** (a generic evidence envelope, a
family of domain-specific fact-recording receipts, and an outer
transport/storage envelope), with two deliberately-distinct timestamp
conventions (`observedAt` for point-in-time evidence vs.
`startedAt`/`completedAt` for a duration vs. `createdAt` for when the
wrapper object itself was created) that should **not** be collapsed into
one field name.

The same read did find one real, narrow inconsistency worth recording
(two different field names — `sourceId` vs. `adapterId` — for what is
provably the same underlying identifier) and one genuine specification
gap (how exactly the outer envelope composes with the domain-specific
receipt payloads was never actually shown anywhere in the source
material) — both were recorded as an explicit, low-severity `OPEN` item
rather than either silently merged away or silently ignored.

**Lesson:** when auditing a family of similarly-shaped types, resist
both failure modes:
- Don't merge them into one type just because they share field names or
  general shape — check whether the sharing reflects genuinely different
  responsibilities/layers first.
- Don't wave away every difference as "probably fine, they're just
  different layers" without actually checking whether any of the
  differences are unintentional naming drift or an unresolved
  specification gap.

## General pattern

Both mistakes were caught by the same discipline: **treat any claim
about documentation content as unverified until you've extracted and
read the actual text, not a summary of it** — including summaries you
wrote yourself in an earlier session or an earlier pass of the same
audit. This is the same "no evidence, no verified claim" principle
applied to the audit process itself, not just to the subject matter being
audited.
