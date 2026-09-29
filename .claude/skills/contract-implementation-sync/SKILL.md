---
name: contract-implementation-sync
description: Bridges a frozen documentation contract to its actual implementation — verifying the source code matches the contract field-for-field (catching drift automatically), then honestly updating each contract's status line from DESIGNED to IMPLEMENTED to VERIFIED only as real evidence (a written file, a passing typecheck, a passing test run) becomes available. Use whenever implementation work begins after a CONTRACT_FREEZE_READY verdict, whenever new source code is added or changed that implements a previously-frozen contract, or when the user asks "does the code match the docs," "check contract drift," "update the implementation status," or "is this contract actually implemented yet."
---

# Contract Implementation Sync

Once `contract-freeze-gate` has produced a `READY` verdict and
implementation begins, two things need to stay true and checkable: (1)
the code must not silently drift from the frozen contract shape, and (2)
each contract's documented status must always be backed by real, current
evidence — never advanced from `DESIGNED` to `IMPLEMENTED` or from
`IMPLEMENTED` to `VERIFIED` without something concrete to point at.

## The three status levels and what unlocks each one

1. **`DESIGNED`** — a shape exists in a contract file; no source
   implements it yet.
2. **`IMPLEMENTED IN V0.1 CORE`** (or equivalent phrasing) — unlocked the
   moment a source file defines the same shape. State exactly which file
   implements it (e.g. "The executable TypeScript definitions are
   `src/domain/identity.ts`"). **Do not** claim runtime/test verification
   at this point unless you've actually run something — implementation
   existing and implementation being verified to work are different
   claims.
3. **`VERIFIED`** — unlocked only after actually running something and
   observing the result: a passing typecheck, a passing test suite, or
   equivalent. State the exact command and its exact outcome (e.g. "`npm
   run typecheck` exits 0; `npm test` — 5/5 passing"), not just "tests
   pass" as an unsourced assertion.

**Never skip a level based on assumption.** A contract can sit at
`IMPLEMENTED` for a long time with `VERIFIED` genuinely blocked (no test
suite, no CI, dependencies not installed) — that's an honest, valid
state; don't round it up.

## Steps

### When implementing against a frozen contract

1. Copy the contract's exact shape into source verbatim — don't
   paraphrase, don't "improve" field names, don't add fields the contract
   doesn't have (if the implementation genuinely needs a field the
   contract doesn't have, that's a contract change — go back to
   `adr-writer` first, don't let the code quietly become the new source
   of truth).
2. Run the parity checker for every symbol just implemented:
   ```bash
   python3 scripts/check_contract_parity.py <SymbolName> <contract-root> <source-root>
   ```
   e.g. `check_contract_parity.py SourceAdapter docs/contracts src`. Fix
   any reported discrepancy before moving on — either the source has a
   typo/omission (fix the source) or the contract itself needs a
   documented amendment (go through `adr-writer`, don't just edit the
   contract silently). Note the caveat in the script's own docstring:
   it's a textual heuristic, not a real type-checker — it does not
   understand generics, `extends`, or deeply nested inline object types;
   re-check anything complex by eye.
3. Once every symbol in a contract file matches, update that contract's
   `Status:` line from `DESIGNED` to `IMPLEMENTED IN V0.1 CORE` (or
   equivalent), naming the exact source file(s). Do not add a
   verification claim yet.
4. If a real test runner/typechecker is available and dependencies can be
   installed, actually run it now:
   ```bash
   npm install   # or the project's equivalent
   npm run typecheck
   npm test
   ```
   Only after both genuinely succeed, update the status to include
   verification, quoting the exact command and result. If either command
   isn't available (no test suite exists yet, no network access to
   install dependencies, etc.), say so explicitly and leave status at
   `IMPLEMENTED`, not `VERIFIED`.
5. Update `docs/architecture/documentation-audit.md` and the top of
   `docs/decisions/README.md` (or your project's equivalent audit/ledger
   files) to reflect the new implementation evidence, following the
   pattern of an existing "record implementation state" pass if one
   exists in the project's own history (`git log --grep=implementation`
   is a good way to find a prior example to match the tone/structure of).

### Periodic / on-demand drift check

Run the parity checker across every contract-owned symbol whenever source
changes, not just once at initial implementation — drift can be
introduced by any later edit to either side:
```bash
for symbol in <every contract-owned symbol name>; do
  python3 scripts/check_contract_parity.py "$symbol" docs/contracts src
done
```
Any `FAIL` here means the code and the documentation have silently
diverged — treat this exactly like `doc-symbol-audit` finding a
contradiction: don't silently pick a winner, decide deliberately (usually
via `adr-writer` if the contract itself needs to change) and fix
whichever side is wrong.

## Notes

- This skill assumes `contract-freeze-gate` already produced `READY` —
  don't use it to justify starting implementation before that gate
  passes.
- The parity checker only understands flat interface fields (`readonly
  name?: type;`) and string-literal union `type` aliases — it will
  report 0 or ambiguous occurrences for anything more complex (generics,
  `extends`, mapped types) rather than silently giving a false pass;
  treat that as "needs a manual check," not "tool is broken."
- Real example from the session this skill was extracted from: after a
  `README.md`-guided implementation pass, all 11 contract-owned symbols
  checked (`MediaRef`, `ExternalIdentity`, `CanonicalMedia`,
  `SourceCandidate`, `SourceAdapter`, `ResolveContext`, `HealthResult`,
  `ResolutionResult`, `Failure`, `AdapterExecution`, `AdapterStatus`)
  passed this exact parity check field-for-field — genuine evidence the
  freeze held during implementation, not an assumption.
