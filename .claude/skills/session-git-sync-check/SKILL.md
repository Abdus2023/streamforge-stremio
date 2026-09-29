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
   - **Local is an ancestor of remote** (the stale-clone bug): check
     `git status --short` for uncommitted local work first. If clean,
     `git reset --hard <remote-tip>` is safe. If you already made a new
     commit on top of the stale base this turn, back it up with
     `git branch backup-<label> <local-head>` first, reset, then
     `git cherry-pick` the backed-up commit forward.
   - **Local is ahead of remote** (normal case — just hasn't been pushed
     yet): just push.
   - **Diverged** (neither is an ancestor of the other): this is more
     serious and script-based auto-recovery isn't safe — inspect both
     tips manually with the printed `git log` commands before deciding
     how to reconcile. Never force-push out of this state without
     understanding exactly what would be discarded.

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
