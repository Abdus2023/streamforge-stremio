# ADR-NNN: <One-sentence title stating the decision, not just the topic>

<!--
Add a "back to the decision ledger" link here once this file is placed in
its real location (e.g. docs/decisions/ADR-NNN-....md), pointing at that
directory's ledger index — a Markdown link whose text is
"Back to the decision ledger" and whose target is the ledger's own
README file, relative to wherever this ADR ends up. Deliberately not
written as a literal Markdown link in this template file itself, so this
template doesn't fail a link-validity check from inside the skill's own
directory (there is no README.md next to this template).
-->


- **Status:** ACCEPTED | PROPOSED | SUPERSEDED (by ADR-MMM)
- **Date:** YYYY-MM-DD
- **Resolves:** `OPEN-N` in `docs/decisions/README.md` (if applicable —
  omit this line if the ADR isn't resolving a previously-recorded ledger
  item)
- **Affects:** <every file whose canonical/historical status changes as a
  result of this decision — contract files, architecture files, and any
  other ADRs that referenced the old, now-superseded shape>

## Context

<What concept is this about, and why does it need a decision? State the
number of competing/ambiguous definitions found and where, in plain
factual terms — no verdict yet.>

## Problem

<The specific question this ADR must answer, phrased so a reader could
in principle answer it "yes/no" or "option A/B/C" — not a restatement of
the context.>

## Observed evidence

<Every piece of evidence found, cited by exact file:line or quoted
verbatim. If two things were compared and found "identical" or
"different," show the actual diff, not just the conclusion — see
`doc-symbol-audit`'s lessons-learned.md for why this matters. If evidence
is genuinely insufficient to prefer one option, say so explicitly rather
than picking one and calling it "the obvious choice.">

## Decision

<The exact shape/rule adopted, stated as literally as possible (e.g. a
full field list, not "the richer of the two"). If this decision was
directed/mandated externally (e.g. a literal shape given by whoever
requested this pass) rather than derived from repository evidence, say so
explicitly — don't present a directive as if it were independently
concluded from the evidence.>

## Rejected alternatives

<For each alternative considered and not chosen, one line stating what it
was and why it lost. If an alternative has real merit and might be worth
revisiting later (e.g. a future refinement), say so explicitly instead of
implying it was simply wrong — see the `http_error` example in
`references/status-discipline.md` for the pattern of "not adopted now,
but preserved as a plausible future direction," which is different from
"discarded.">

## Consequences

- <What becomes canonical/frozen as a result>
- <What existing documents need annotation as historical/superseded, and
  where>
- <What remains open/deferred, if anything, as a direct consequence>

## Status

`RESOLVED` | `OPEN` (state which, and if `OPEN`, exactly what evidence
would be needed to resolve it)
