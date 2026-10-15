#!/usr/bin/env bash
# CORE's commits come first — ADR-132 D10.12 (proposal 0018).
#
# Claude Code PreToolUse hook (matcher: Bash). Under the release runtime CORE
# commits in its own clone (/opt/core/repo), never in this tree. Those commits
# reach this tree as the branch `core/develop`, fetched by the assistant as
# itself (git runs as core-claude against a repository it can only read).
# Before the assistant commits, its HEAD must already contain core/develop, so
# a push never leaves CORE's work behind or forks the line CORE fast-forwards.
#
# When the assistant runs `git commit`:
#   1. no clone yet (before go-live)            -> pass, nothing to check;
#   2. fetch core/develop from the clone (no forced update);
#      a failed fetch                           -> refuse (fail closed);
#   3. core/develop not an ancestor of the HEAD being committed -> refuse,
#      naming the remedy.
#
# The HEAD checked is the one each commit lands on: the tree the command runs
# in (the payload's cwd, then a `cd <dir>` or `git -C <dir>` in the command)
# when that tree is this repository or one of its worktrees; otherwise this
# repository's HEAD, as before. Checking only this repository's HEAD refused
# every worktree commit whenever the development checkout lagged main, which
# only the governor can fast-forward (governor 2026-10-13).
#
# Which commands commit, and in which tree, is decided by core-commit-target.py
# beside this file (shared with core-verdict.sh): `git -C <dir> commit`,
# `git -c k=v commit` and `/usr/bin/git commit` are commits. Commands built by
# hand-quoting (`bash -c "git commit"`, eval, xargs) are out of scope. An
# unreadable payload, or a detector that cannot run, refuses (fail closed).
#
# The installed copy lives in .claude/hooks/ (core-law, not in git); this
# file in infra/claude-hooks/ is its source and what CI tests.
#
# Scope, as with core-verdict.sh: the assistant's normal commit path only.
# The governor's own shell is not hooked.

set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-/opt/dev/CORE}"
CLONE="${CORE_CLONE:-/opt/core/repo}"
SAFE=(-c core.hooksPath=/dev/null -c core.fsmonitor=false)

payload="$(cat)"

if ! trees="$(printf '%s' "$payload" | python3 -I "$(dirname "$0")/core-commit-target.py" "$REPO")"; then
  echo "CORE ancestry: command refused — the hook could not tell whether it commits (see above)." >&2
  exit 2
fi
[ -n "$trees" ] || exit 0

[ -d "$CLONE/.git" ] || exit 0

if ! err="$(git -C "$REPO" "${SAFE[@]}" fetch --quiet --no-tags "$CLONE" develop:refs/heads/core/develop 2>&1)"; then
  {
    echo "CORE ancestry: commit refused — could not fetch core/develop from $CLONE:"
    printf '  %s\n' "$err"
    echo "If CORE's line was rewritten, that needs the governor; if access failed, check safe.directory."
  } >&2
  exit 2
fi

while IFS= read -r TREE; do
  if ! git -C "$TREE" "${SAFE[@]}" merge-base --is-ancestor refs/heads/core/develop HEAD; then
    ahead="$(git -C "$TREE" "${SAFE[@]}" rev-list --count HEAD..refs/heads/core/develop 2>/dev/null || echo '?')"
    {
      echo "CORE ancestry: commit refused — HEAD of $TREE does not contain core/develop ($ahead CORE commit(s) missing)."
      echo "Bring them in first: git merge --ff-only core/develop"
      echo "(if your unpushed commits block the fast-forward, rebase them onto core/develop)."
    } >&2
    exit 2
  fi
done <<<"$trees"
exit 0
