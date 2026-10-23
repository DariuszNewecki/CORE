#!/bin/bash
# Reaps Claude Code worktrees under var/tmp/wt-* once their work has landed.
#
# For each var/tmp/wt-* directory:
#   - registered worktree, clean, branch merged into origin/main:
#       git worktree remove, then git branch -d
#   - registered worktree, dirty or unmerged: kept, one "KEPT" line printed
#   - not a registered worktree (orphan) holding no files but a stale .git
#     pointer: removed
# Then git worktree prune.
#
# Never uses --force; touches nothing outside var/tmp/wt-*. Run from the
# SessionEnd hook in .claude/settings.local.json, or by hand.
#
# Claude Code kills SessionEnd hooks after ~1.5s, and removing several
# worktrees takes longer, so under the hook (CLAUDE_PROJECT_DIR set) the
# script re-runs itself detached and logs to var/tmp/claude-worktree-reap.log.
#
# A branch whose tip lies on origin/main's first-parent line has no commits of
# its own (it was just cut from main), so it counts as unmerged: that is a
# worktree another session may be about to use. PRs land with merge commits,
# so a merged branch tip sits off the first-parent line.

set -euo pipefail

repo="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$repo"
tmp_root="$repo/var/tmp"

if [[ -n "${CLAUDE_PROJECT_DIR:-}" && -z "${REAP_DETACHED:-}" ]]; then
    REAP_DETACHED=1 setsid nohup bash "${BASH_SOURCE[0]}" \
        >>"$tmp_root/claude-worktree-reap.log" 2>&1 </dev/null &
    exit 0
fi

git fetch -q origin main 2>/dev/null || echo "WARN fetch failed; using local origin/main"
main_ref=$(git rev-parse --verify -q origin/main) || { echo "ERROR no origin/main"; exit 1; }
first_parent=$(git rev-list --first-parent "$main_ref")

# path -> branch ("" when detached), and the set of locked worktrees
declare -A wt_branch=() wt_locked=()
path=""
while IFS= read -r line; do
    case "$line" in
        "worktree "*) path="${line#worktree }"; wt_branch["$path"]="" ;;
        "branch refs/heads/"*) wt_branch["$path"]="${line#branch refs/heads/}" ;;
        locked*) wt_locked["$path"]=1 ;;
    esac
done < <(git worktree list --porcelain)

shopt -s nullglob
for dir in "$tmp_root"/wt-*; do
    [[ -d "$dir" && ! -L "$dir" ]] || continue
    dir=$(cd "$dir" && pwd -P)
    [[ "$(dirname "$dir")" == "$tmp_root" ]] || continue

    if [[ -z "${wt_branch[$dir]+set}" ]]; then
        # Orphan: removable only if nothing but a .git pointer file remains.
        if [[ -z "$(find "$dir" -mindepth 1 -type f ! -path "$dir/.git" -print -quit)" ]]; then
            rm -r -- "$dir"
            echo "REMOVED $dir (orphan, empty)"
        else
            echo "KEPT $dir - orphan-with-files"
        fi
        continue
    fi

    branch="${wt_branch[$dir]}"
    if [[ -z "$branch" ]]; then
        echo "KEPT $dir (detached) unmerged"
        continue
    fi
    if [[ -n "${wt_locked[$dir]+set}" ]]; then
        echo "KEPT $dir $branch locked"
        continue
    fi
    if [[ -n "$(git -C "$dir" status --porcelain)" ]]; then
        echo "KEPT $dir $branch dirty"
        continue
    fi
    tip=$(git rev-parse "refs/heads/$branch")
    if ! git merge-base --is-ancestor "$tip" "$main_ref" \
        || grep -qx "$tip" <<<"$first_parent"; then
        echo "KEPT $dir $branch unmerged"
        continue
    fi

    if ! git worktree remove "$dir"; then
        echo "KEPT $dir $branch remove-refused"
        continue
    fi
    if git branch -q -d "$branch" 2>/dev/null; then
        echo "REMOVED $dir $branch"
    else
        echo "REMOVED $dir (branch $branch kept: git branch -d refused)"
    fi
done

git worktree prune
