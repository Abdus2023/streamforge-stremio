<!--
Use this template for each entry in the decision ledger
(docs/decisions/README.md or equivalent). One entry per contradiction,
whether it ends up OPEN or RESOLVED. Keep the exact field labels below —
they're what a future audit pass will grep for.
-->

### OPEN-N — <short description of the contradiction>

- **Affected documents:** <list>
- **Discovered during:** <which pass/session found this, and how (e.g.
  "a field-level pass across X, Y, Z">
- **Observed contradiction:** <state the concrete conflict — quote both
  sides if it's a text disagreement, or describe the structural mismatch
  if it's a shape disagreement>
- **Why it matters:** <what an implementer would have to guess if this
  stays unresolved>
- **Possible interpretations:** <numbered list of plausible readings,
  each with the evidence for it, if more than one is plausible>
- **Evidence available:** <what was actually checked — cite exact
  file:line or quote>
- **Decision:** <if resolved, the exact decision and a pointer to the ADR
  that made it (e.g. "See ADR-006"); if still open, write "none — left
  explicitly open" and state what would resolve it>
- **Status:** `OPEN` | `RESOLVED` — if `OPEN`, also state a severity
  (e.g. "low severity, non-blocking for `<some scope>` freeze") so a
  freeze-gate check can tell blocking items from non-blocking ones at a
  glance without re-reading the full entry.

<!--
When an item moves from OPEN to RESOLVED, don't delete the entry —
rewrite its Decision/Status fields in place (or rename the heading to
RESOLVED-N if the ledger convention numbers them separately) so the
ledger keeps a record of what was once ambiguous and why it no longer is.
-->
