# Lessons learned (from validating this very skill set)

## `validate_skill.py` caught a real mistake in its own SKILL.md

While writing this skill's own `SKILL.md`, the body's "smoke-test it"
section recommended (as general advice to apply to *other* skills)
recording mistakes in a file at the backticked path
`references/lessons-learned.md`. `validate_skill.py`'s resource-reference
check treats any backticked `references/...`/`scripts/...`/`assets/...`
path in a skill's body as a claimed resource and checks it exists — and
this skill didn't have that file yet, so the very first validation run
failed with `ERROR skill-creator: referenced resource does not exist:
references/lessons-learned.md`.

This file is the fix — and it's also the cleanest possible demonstration
of the advice it was giving: the mistake was caught immediately by
running the validator (not by a later, harder-to-trace failure), and the
fix was to write down what happened rather than just silently removing
the reference.

**Lesson:** run the validator against a skill as soon as it's written,
not as an afterthought — it catches exactly this kind of "the prose
mentions a resource that was never actually created" gap immediately,
while the context for fixing it (what you meant to say) is still fresh.
