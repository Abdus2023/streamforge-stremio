---
name: session-git-sync-check
description: Detects whether the local git checkout actually matches its remote branch's real current tip, and gives the exact safe recovery steps if not — catching the sandboxed-agent failure mode where a session's working directory gets silently re-cloned onto a stale/base commit mid-session while the remote branch (and possibly the on-disk files) are actually much further ahead. Use this at the very start of any session or turn before trusting git log, git status, or HEAD for anything, and always immediately before any commit-and-push sequence. Run it proactively — do not wait for a git push to fail or for files to look "missing" before checking.
---

# Session Git Sync Check

A pre-flight check for a specific, real, repeatedly-observed failure mode
in sandboxed agent environments: the working directory's git checkout can
get silently reset to a stale commit (often the branch's very first/base
commit) at the start of a turn, while the actual remote branch — and
sometimes even the on-disk files, which can persist independently of
git's own state — are genuinely much further ahead, including work from
earlier in the very same session. This happened **three times** in the
session this skill was extracted from.

**If this goes unnoticed, the consequences are serious:** a new commit
made on top of the stale base looks fine locally, but either fails to
push (non-fast-forward) or, worse, could be force-pushed and silently
discard real history. It can also make a final report describe a
"HEAD"/"branch state" that is flatly wrong.

## When to run this

- At the very start of any session/turn that will do git work — before
  trusting the output of `git log`, `git status`, or `git rev-parse HEAD`
  for anything, including a final report's "Repository State" section.
- Immediately before any commit-and-push sequence (see
  `docs-normalization-commit-plan`), even if you checked earlier in the
  same turn — a reset can in principle happen at any point a new shell
  session starts.
- Any time `git status` shows an entire, large, previously-committed
  directory tree as suddenly `??` (untracked) or a previously-multi-file
  repo now shows only one ancestor commit in `git log` — that's the
  signature of this bug.

## Steps

1. Run:
   ```bash
   scripts/git_sync_check.sh [branch] [remote]
   ```
   (both arguments optional — defaults to the current branch and
   `origin`.) It fetches the remote branch fresh and compares it to local
   `HEAD`. Exit code `0` means they match exactly — proceed normally.

2. **If it reports a mismatch, read the diagnosis before acting** — it
   distinguishes three cases and gives the exact next commands for each:
   - **Local is an ancestor of remote** (the stale-clone bug — by
     definition no new local commit exists yet in this case, since a new
     commit would break the ancestor relationship): check
     `git status --short` for uncommitted local work first.
     - If clean, `git reset --hard <remote-tip>` is safe.
     - **If dirty** (uncommitted edits/untracked files sitting on top of
       the stale base — this happened for real, not just clean-ancestor,
       in the session this addition was extracted from): snapshot
       everything into a throwaway commit first (`git add -A && git
       commit -m 'WIP...'`), back that commit up to a branch, diff it
       against the remote tip, **read the `git diff --stat` output as a
       mandatory safety check** (it should show only small
       additions/changes — this turn's real new work; if it instead shows
       large-scale deletions of files that obviously belong in the
       project, STOP, don't apply, fall back to manual file-by-file
       inspection instead), then reset to the remote tip and apply just
       that diff. The script prints the exact commands.
   - **Local is ahead of remote** (normal case — just hasn't been pushed
     yet): just push.
   - **Diverged** (neither is an ancestor of the other, including the
     case of a genuinely new local commit made on top of a now-stale
     base): this is more serious and script-based auto-recovery isn't
     safe — inspect both tips manually with the printed `git log`
     commands, then back up the new commit(s) to a branch, reset to the
     remote tip, and `git cherry-pick` them forward. Never force-push out
     of this state without understanding exactly what would be
     discarded.

3. **After any recovery action, re-run the script** to confirm local
   `HEAD` now matches the remote tip exactly before doing anything else.

4. Only after a clean match should you: read `git log`/`git status` for a
   final report, make new commits, or push.

## Notes

- This check is read-only by itself — it never modifies the repository.
  The recovery commands it prints are for you to run deliberately, one at
  a time, reading `git status --short` in between when instructed.
- The on-disk working tree files can be more up to date than git's
  checkout in this failure mode (some sandboxed environments persist
  files independently of git state) — do not assume a stale `HEAD`/
  `git log` means the actual files were lost. Check `git status --short`
  and the file tree itself before concluding anything is missing; often
  a `git reset --hard <remote-tip>` alone reconciles everything cleanly
  because the on-disk content already matches what the remote tip
  expects.
- If, after reconciling, `git status --short` still shows real, wanted
  changes as untracked/modified relative to the correct tip, those are
  genuine new edits made this turn (not a re-clone artifact) — proceed to
  commit them normally.
- **A fourth real occurrence, with a likely root cause identified.** This
  bug recurred again, mid-session, while building this very skill's
  sibling skills — and that time `git status --short` was *dirty*, not
  clean, requiring the WIP-snapshot-and-diff recovery above (verified
  safe in a faithful throwaway-clone simulation using `git update-ref` to
  move only the ref, not `git reset --hard`, which would incorrectly also
  reset the working tree and not reproduce the real bug). Investigating
  that occurrence found the local `.git/config` had reverted to a bare
  fresh-clone shape (only a fetch refspec for `main`, no tracking
  configuration for the actual working branch) even though `origin`'s URL
  was still correct — consistent with a sandboxed session-restore
  mechanism that doesn't reliably persist `.git/config` (this platform's
  own tooling explicitly excludes `.git/config`, `.git/credentials`,
  `.git-credentials`, and `.netrc` from cross-turn snapshots, for
  credential-safety reasons) while the ordinary tracked working-tree files
  persist normally. Practical upshot: `scripts/git_sync_check.sh` already
  fetches by explicit branch name (`git fetch origin <branch>`, populating
  `FETCH_HEAD`) rather than relying on a pre-configured remote-tracking
  ref, specifically so it keeps working even if `.git/config`'s branch
  tracking has gone stale — don't "simplify" it to a bare `git fetch`
  followed by reading `origin/<branch>`, since that silently returns wrong
  (or missing-ref) results exactly when this bug is active.
