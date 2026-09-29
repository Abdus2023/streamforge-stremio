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
  echo "By definition of this branch, local has made NO new commit on top of"
  echo "the stale base yet (a new commit would break the ancestor relation —"
  echo "see the DIVERGED case below for that situation instead)."
  echo
  echo "Check for uncommitted local work FIRST (do not skip this):"
  echo "    git status --short"
  echo
  if git diff --quiet && git diff --cached --quiet && [ -z "$(git status --porcelain --untracked-files=all)" ]; then
    echo "Working tree is clean right now — safe to reset straight to the"
    echo "remote tip:"
    echo "    git reset --hard $REMOTE_HEAD"
  else
    echo "Working tree is NOT clean (uncommitted edits and/or untracked"
    echo "files exist on top of this stale base) — a bare 'git reset --hard'"
    echo "here would silently discard them for any path also tracked in the"
    echo "remote tip's commit. Snapshot everything into a real commit first,"
    echo "reset, then re-apply only the real delta:"
    echo "    git add -A"
    echo "    git commit -m 'WIP: snapshot before stale-HEAD recovery'"
    echo "    WIP=\$(git rev-parse HEAD)"
    echo "    git branch backup-wip-\$WIP \$WIP"
    echo "    git diff --stat $REMOTE_HEAD \$WIP   # SAFETY CHECK -- read this before continuing"
    echo "    git diff $REMOTE_HEAD \$WIP > /tmp/recovery.patch"
    echo "    git reset --hard $REMOTE_HEAD"
    echo "    git apply --check /tmp/recovery.patch && git apply /tmp/recovery.patch"
    echo "    git status --short   # review: should show only this turn's genuinely new/changed files"
    echo "    # once verified, delete the backup branch: git branch -D backup-wip-\$WIP"
    echo "Why this works: IF the working tree already had the remote tip's"
    echo "real content checked out on disk (only .git's metadata went stale —"
    echo "the actual observed failure mode this skill targets), the WIP"
    echo "commit's tree equals the remote tip's tree plus this turn's actual"
    echo "new edits, so diffing the two isolates exactly that delta."
    echo
    echo "MANDATORY SAFETY CHECK before running 'git apply': read the"
    echo "'git diff --stat' output above. It should show only a handful of"
    echo "small additions/changes (this turn's real new work). If instead it"
    echo "shows large-scale deletions of files that obviously still belong in"
    echo "the project (this happens if the working tree itself was ALSO"
    echo "reset, not just git's metadata — a genuinely different, more"
    echo "dangerous situation), STOP: do not run 'git apply'. That would"
    echo "delete real tracked files. Instead fall back to the conservative"
    echo "path: keep the backup-wip branch, reset --hard to the remote tip,"
    echo "and manually inspect 'git diff $REMOTE_HEAD \$WIP -- <path>' file by"
    echo "file to decide what (if anything) from the WIP snapshot is worth"
    echo "cherry-picking by hand."
  fi
elif git merge-base --is-ancestor "$REMOTE_HEAD" "$LOCAL_HEAD" 2>/dev/null; then
  echo "Diagnosis: local HEAD is AHEAD of the remote tip (local has commits"
  echo "not yet pushed). This is the normal 'need to push' case, not the"
  echo "stale-clone bug — just push:"
  echo "    git push $REMOTE $BRANCH"
else
  echo "Diagnosis: local and remote have DIVERGED (neither is an ancestor of"
  echo "the other) — this is more serious than the stale-clone pattern and"
  echo "needs manual inspection. Do not force-push. This is also where you"
  echo "land if you already made a NEW commit on top of a stale base (that"
  echo "commit's SHA is not the remote tip's ancestor, since the remote tip"
  echo "advanced independently) — recover by backing up the new commit(s),"
  echo "resetting to the remote tip, then cherry-picking them forward:"
  echo "    git branch backup-\$(date +%s) $LOCAL_HEAD"
  echo "    git reset --hard $REMOTE_HEAD"
  echo "    git cherry-pick <the-new-commit-sha> [<the-next-one> ...]"
  echo "    # then verify (see below) before deleting the backup branch"
  echo "Inspect both tips first to tell genuine divergence from this case:"
  echo "    git log --oneline $LOCAL_HEAD -10"
  echo "    git log --oneline $REMOTE_HEAD -10"
  echo "    git log --oneline $LOCAL_HEAD..$REMOTE_HEAD"
  echo "    git log --oneline $REMOTE_HEAD..$LOCAL_HEAD"
fi

echo
echo "After any recovery action, re-run this script to confirm local HEAD"
echo "matches '$REMOTE/$BRANCH' again before committing or pushing anything."
exit 1
