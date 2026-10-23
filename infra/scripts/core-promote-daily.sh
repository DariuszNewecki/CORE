#!/bin/bash
# Opens or updates the daily promotion pull request (promote/<sha> -> live),
# and the pull request for CORE's generated tests on core/test-gen (#1252).
#
# Governor 2026-10-23 (#1255, decision 2A): core-claude opens the promotion
# every day at a fixed time, without asking; the governor's part is the
# approval. core-claude's gh login (core-claude-bot) opens every promotion,
# so this runs from core-claude's crontab:
#   0 6 * * * live=$(basename "$(readlink -f /opt/core/current)") && git -C /opt/dev/CORE fetch -q origin && git -C /opt/dev/CORE show "$live:infra/scripts/core-promote-daily.sh" | bash >> "$HOME/.cache/core-promote-daily.log" 2>&1
# An urgent promotion runs the same script with --urgent.
#
# Only approved code runs here (review findings F2, F3, 2026-10-23): this
# script is read from the live commit, `promote propose` is the live
# release's own core-admin, and its working tree is a detached worktree at
# the live commit. Code that only reached main, which needs no approval,
# never runs on the host with the bot's token, and never writes the summary
# the governor approves.

set -euo pipefail

repo="${CORE_DEV_REPO:-/opt/dev/CORE}"
current="${CORE_CURRENT:-/opt/core/current}"
github_repo="DariuszNewecki/CORE"
live="$(basename "$(readlink -f "$current")")"
wt="$repo/var/tmp/wt-promote-daily"

if [[ ! "$live" =~ ^[0-9a-f]{40}$ ]]; then
    echo "core-promote-daily: $current is not a release ($live)" >&2
    exit 1
fi

# The credential is checked by a real call before anything relies on it.
token="$(gh auth token)"
if [[ "$(GH_TOKEN="$token" gh api "repos/$github_repo" --jq .permissions.push)" != "true" ]]; then
    echo "core-promote-daily: core-claude's gh login cannot write to $github_repo" >&2
    exit 1
fi

git -C "$repo" fetch -q --prune origin

git -C "$repo" worktree remove --force "$wt" 2>/dev/null || rm -rf "$wt"
git -C "$repo" worktree add -q --detach "$wt" "$live"
trap 'git -C "$repo" worktree remove --force "$wt"' EXIT

cd "$wt"
CORE_GITHUB_TOKEN="$token" "$current/venv/bin/core-admin" --readonly promote propose "$@"

# CORE's generated tests (#1252): CORE pushes core/test-gen, but its token
# cannot open pull requests. This login opens the one pull request for it,
# with auto-merge (governor 2026-10-23, option A; no new credential). It runs
# after the promotion, so a failure here never stops the promotion opening;
# the script still exits 1 afterwards. Inside `if !` set -e is off, so every
# step returns on failure by hand.
deliver_tests() {
    git -C "$repo" rev-parse -q --verify refs/remotes/origin/core/test-gen >/dev/null || return 0
    local ahead open url
    ahead="$(git -C "$repo" rev-list --count origin/main..origin/core/test-gen)" || return 1
    open="$(GH_TOKEN="$token" gh pr list --repo "$github_repo" --head core/test-gen \
        --state open --json number --jq length)" || return 1
    [[ "$ahead" -gt 0 && "$open" == "0" ]] || return 0
    url="$(GH_TOKEN="$token" gh pr create --repo "$github_repo" --base main \
        --head core/test-gen --title "test: CORE's generated tests (core/test-gen)" \
        --body "Serves 3 (tests written autonomously by CORE), #1252: $ahead commit(s) CORE generated on core/test-gen. Opened by core-claude's daily job because CORE's token cannot open pull requests. It merges itself when CI is green.")" || return 1
    GH_TOKEN="$token" gh pr merge --repo "$github_repo" --auto --merge "$url" || return 1
    echo "core-promote-daily: opened $url"
}

if ! deliver_tests; then
    echo "core-promote-daily: delivering core/test-gen failed (#1252)" >&2
    exit 1
fi
