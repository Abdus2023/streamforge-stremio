<!--
Use this shorter (7-section) format for a normalization pass scoped to
"finish freezing a specific set of contracts and decide go/no-go on
implementation." Fill every bracketed placeholder; do not omit a section
even if its content is "none."
-->

## 1. Repository State

- **Branch:** `<branch>`
- **HEAD:** `<sha>`
- **Base:** `<base-branch>`
- **Ahead/behind:** `<N> ahead / <M> behind`

## 2. Changes Made

| File | Change | Reason |
|---|---|---|
| | | |

## 3. Contract Decisions

| Contract | Decision | Evidence | Status |
|---|---|---|---|
| | | | `PROVED` / `ARGUMENT` / `CONJECTURE` / `OPEN` |

## 4. Remaining Contradictions

<Only genuinely unresolved items. For each: what it is, why it doesn't
block the current freeze scope, and what would resolve it. If none
remain, say so explicitly rather than omitting the section.>

## 5. Verification

<One line per claim category, each labelled exactly one of `VERIFIED` /
`PARTIALLY_VERIFIED` / `PROVISIONAL` / `BLOCKED` / `NOT EXECUTED`. Never
convert a documentation-inspection finding into a runtime/test claim.>

## 6. Freeze Gate

**`<PROJECT>_FREEZE_READY`** or **`<PROJECT>_FREEZE_BLOCKED`**

<If BLOCKED, list every blocking item by name, each tied to a specific
OPEN ledger entry.>

## 7. Next Authorized Step

`BEGIN V0.1 IMPLEMENTATION` (only if READY) or `RESOLVE CONTRACT
BLOCKERS` (if BLOCKED) — or substitute the project's own two-option
phrasing.
