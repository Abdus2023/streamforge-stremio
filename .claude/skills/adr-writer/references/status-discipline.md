# Status discipline

Two separate label sets are used across this skill set. Do not mix them
up or use one where the other belongs.

## Claim-strength labels (used inside ADRs, contradiction matrices, ledger
entries — for statements about what the documentation/evidence says)

- **`PROVED`** — settled by explicit, stated, checkable evidence (a
  direct quote, an exact field-by-field diff, an explicit directive from
  whoever commissioned the work). Another reader could re-derive the same
  conclusion from the same evidence.
- **`ARGUMENT`** — the best available reading of evidence that is real
  but not perfectly conclusive (e.g. "3 of 4 independent narrative
  passages describe the pipeline in this order, so this order is treated
  as canonical" — real evidence, but not a literal specification).
  State the argument, don't present it as `PROVED`.
- **`CONJECTURE`** — a plausible guess with insufficient evidence to
  reach `ARGUMENT` strength. Never silently promote a `CONJECTURE` to
  `PROVED` or `ARGUMENT` without new evidence — if none is likely to
  appear, it should probably be an `OPEN` ledger item instead.
- **`OPEN`** — genuinely unresolved; no reconciliation is currently
  justified by available evidence. Leaving something `OPEN` is a valid,
  honest outcome — don't force a decision to avoid an open item.

## Verification-strength labels (used in final reports — for statements
about what was actually executed/checked this session, as opposed to
what the documentation claims)

- **`VERIFIED`** — directly executed/observed this session (a command
  was run, its exact output inspected, e.g. `git rev-parse HEAD`, a
  passing link-check).
- **`PARTIALLY_VERIFIED`** — some but not all of a claim's surface was
  checked (e.g. one of several files was diffed field-by-field, the rest
  only inventoried).
- **`PROVISIONAL`** — a reasonable interpretation was adopted where
  multiple readings were possible; flagged as a judgment call, not a
  fact.
- **`BLOCKED`** — verification could not be completed (e.g. no test
  suite exists to run, so "tests pass" cannot be verified either way).
- **`NOT EXECUTED`** — explicitly not run/attempted this session (e.g.
  no CI exists in the repository, so no CI claim of any kind is made).

**The governing rule connecting both label sets:** no evidence, no
verified claim. Never convert a documentation-inspection finding (a
`PROVED`/`ARGUMENT` claim about what a doc says) into a runtime or test
claim (`VERIFIED` execution) — they answer different questions. A
contract can be `PROVED` consistent on paper while the corresponding
implementation is entirely `NOT EXECUTED`/nonexistent; say both things
plainly rather than letting one imply the other.

## Related operating principles

These were carried as standing constraints across an entire multi-pass
contract-normalization effort and are worth restating for any similar
audit:

- Don't treat a historical/explanatory document as normative merely
  because it exists and looks authoritative — check the documentation
  partition (contracts vs. architecture vs. decisions vs. implementation)
  before trusting any one file's shape.
- Keep these concepts separate and don't conflate them when writing a
  decision: representation, semantics, evidence, truth, authority,
  authorization, admission, execution, success, canonicality, durability.
  A type can be well-formed (representation) without its contents being
  true (truth); a registry can admit a source (authorization) without
  that source ever successfully executing (execution/success).
- Prefer exactly one canonical contract per concept. Historical
  alternatives may stay in the documentation, but must be explicitly
  marked non-normative (a blockquote pointing to the canonical location,
  plus an inline comment in any code block) — never silently left to look
  equally authoritative.
- Don't silently broaden or narrow an agreed scope while "just cleaning
  up documentation." If normalization reveals scope should change,
  surface that explicitly (e.g. in a roadmap scope-lock section) rather
  than letting it happen as a side effect of an edit.
