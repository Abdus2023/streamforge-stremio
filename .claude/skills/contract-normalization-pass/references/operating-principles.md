# Operating principles for a contract-normalization pass

Standing constraints that apply across the whole pass, not just to one
skill. Re-read this before starting, and again before writing the final
report.

1. **No evidence, no verified claim.** Every claim in a final report must
   trace to something actually inspected this session — a file read, a
   command run, a diff performed. Do not carry forward a conclusion from
   memory of a previous session without re-verifying it if the report
   depends on it being current.

2. **Inspect the current branch/HEAD before making any claim about
   repository state.** Never assume the state described in a prior
   session's notes is still accurate — branches move, files change.

3. **Don't treat a historical/explanatory document as normative merely
   because it exists.** A documentation set typically has exactly one
   normative location per concept (see the Documentation Partition
   principle); everything else is explanatory narrative that may contain
   stale or superseded examples.

4. **Keep these concepts distinct when writing any decision or claim:**
   representation, semantics, evidence, truth, authority, authorization,
   admission, execution, success, canonicality, durability. Conflating
   any two of these is a common source of documentation contradictions
   (e.g. treating "admitted into a registry" as equivalent to "will
   successfully execute," or "well-typed" as equivalent to "true").

5. **Prefer exactly one canonical contract per concept.** Historical
   alternatives should stay in the documentation (deleting them usually
   breaks the surrounding narrative) but must be explicitly marked
   non-normative — a blockquote pointing to the canonical location plus
   an inline comment in any code example.

6. **Don't implement anything until the contract layer is internally
   consistent.** A freeze gate exists precisely to make this an explicit,
   checkable gate rather than an implicit judgment call.

7. **Don't silently broaden or narrow an agreed scope while "just
   normalizing documentation."** If normalization reveals scope should
   change, surface it explicitly (e.g. a roadmap scope-lock section
   listing what's newly in/out of scope and why) rather than letting a
   side effect of an edit change scope quietly.

8. **Preserve any stated legal/safety boundary exactly as given** (e.g.
   "authorized/public-domain/licensed/user-owned content only, no
   mechanisms for unauthorized distribution") — a normalization pass must
   never loosen this kind of boundary as a side effect of tidying up
   language.

9. **Never claim tests, CI, execution, or implementation exist or ran
   without concrete repository evidence.** If no test suite exists, no
   report may say tests "passed" or even "failed" — the correct label is
   `NOT EXECUTED` / `BLOCKED`, not a guess in either direction.

10. **State status using the two separate label sets** defined in
    `adr-writer/references/status-discipline.md` — claim-strength
    (`PROVED`/`ARGUMENT`/`CONJECTURE`/`OPEN`) for statements about what
    the documentation says, and verification-strength (`VERIFIED`/
    `PARTIALLY_VERIFIED`/`PROVISIONAL`/`BLOCKED`/`NOT EXECUTED`) for
    statements about what was actually executed/checked this session.
    Never let one imply the other.

11. **When a directive gives a literal shape/interface**, treat it as
    binding for the decision, but still document explicitly if it
    conflicts with a previously-recorded ADR or repository evidence —
    don't silently override prior decisions without a visible trail
    explaining the change.
