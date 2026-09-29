#!/usr/bin/env bash
# git_sync_check.sh — detect whether the local checkout of the current
# branch actually matches its remote tracking branch's real tip, and
# print the exact recovery commands if not. Does not modify anything by
# itself (read-only) — recovery is a separate, deliberate step.
#
# Why this exists: sandboxed agent environments can silently re-clone a
# repository mid-session, landing the local checkout on a stale ref (e.g.
# the branch's base/first commit) while the *remote* branch is actually
# many commits ahead (including commits from earlier in the very same
# session). Committing on top of the stale local state, then pushing,
# would either fail (non-fast-forward) or — worse — succeed as a
# force-push and silently discard real history. This happened three
# times in the session this skill was extracted from; always run this
# before trusting `git log`/`git status`/`HEAD` for anything, and before
# any commit+push sequence.
#
# Usage:
#   git_sync_check.sh [branch] [remote]
#
# branch defaults to the current branch, remote defaults to "origin".
# Exit code 0 if local HEAD already matches the remote branch's tip.
# Exit code 1 if they differ (prints a diagnosis and next-step commands).
# Exit code 2 on usage/environment error (e.g. not a git repo).

set -euo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "git_sync_check.sh: not inside a git repository" >&2
  exit 2
fi

BRANCH="${1:-$(git branch --show-current)}"
REMOTE="${2:-origin}"

if [ -z "$BRANCH" ]; then
  echo "git_sync_check.sh: could not determine current branch (detached HEAD?)" >&2
  exit 2
fi

echo "Checking '$BRANCH' against '$REMOTE/$BRANCH'..."
git fetch "$REMOTE" "$BRANCH" -q

LOCAL_HEAD=$(git rev-parse HEAD)
REMOTE_HEAD=$(git rev-parse FETCH_HEAD)

echo "  local HEAD:  $LOCAL_HEAD"
echo "  remote tip:  $REMOTE_HEAD"

if [ "$LOCAL_HEAD" = "$REMOTE_HEAD" ]; then
  echo "OK: local HEAD matches '$REMOTE/$BRANCH' exactly. Safe to proceed."
  exit 0
fi

echo
echo "MISMATCH: local checkout does not match the remote branch's real tip."
echo

if git merge-base --is-ancestor "$LOCAL_HEAD" "$REMOTE_HEAD" 2>/dev/null; then
  echo "Diagnosis: local HEAD is an ANCESTOR of the remote tip — this looks"
  echo "like the known 'stale clone' pattern (local landed on an old commit,"
  echo "e.g. the branch's base commit, while the remote branch is actually"
  echo "further ahead, possibly including work from earlier this session)."
  echo
  echo "Check for uncommitted local work FIRST (do not skip this):"
  echo "    git status --short"
  echo
  echo "If 'git status --short' is clean (no local edits depend on the stale"
  echo "base), it is safe to reset straight to the remote tip:"
  echo "    git reset --hard $REMOTE_HEAD"
  echo
  echo "If you already made a NEW commit on top of the stale base this turn"
  echo "(so local HEAD is not an ancestor check target but a descendant of"
  echo "the stale base), back it up, reset, then cherry-pick it forward:"
  echo "    git branch backup-\$(date +%s) $LOCAL_HEAD"
  echo "    git reset --hard $REMOTE_HEAD"
  echo "    git cherry-pick <the-new-commit-sha>"
  echo "    # then verify (see below) before deleting the backup branch"
elif git merge-base --is-ancestor "$REMOTE_HEAD" "$LOCAL_HEAD" 2>/dev/null; then
  echo "Diagnosis: local HEAD is AHEAD of the remote tip (local has commits"
  echo "not yet pushed). This is the normal 'need to push' case, not the"
  echo "stale-clone bug — just push:"
  echo "    git push $REMOTE $BRANCH"
else
  echo "Diagnosis: local and remote have DIVERGED (neither is an ancestor of"
  echo "the other) — this is more serious than the stale-clone pattern and"
  echo "needs manual inspection. Do not force-push. Inspect both tips first:"
  echo "    git log --oneline $LOCAL_HEAD -10"
  echo "    git log --oneline $REMOTE_HEAD -10"
  echo "    git log --oneline $LOCAL_HEAD..$REMOTE_HEAD"
  echo "    git log --oneline $REMOTE_HEAD..$LOCAL_HEAD"
fi

echo
echo "After any recovery action, re-run this script to confirm local HEAD"
echo "matches '$REMOTE/$BRANCH' again before committing or pushing anything."
exit 1
