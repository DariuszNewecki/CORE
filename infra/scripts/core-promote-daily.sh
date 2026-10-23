#!/bin/bash
# Opens or updates the daily promotion pull request (promote/<sha> -> live).
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

git -C "$repo" fetch -q origin
git -C "$repo" worktree remove --force "$wt" 2>/dev/null || rm -rf "$wt"
git -C "$repo" worktree add -q --detach "$wt" "$live"
trap 'git -C "$repo" worktree remove --force "$wt"' EXIT

cd "$wt"
CORE_GITHUB_TOKEN="$token" "$current/venv/bin/core-admin" --readonly promote propose "$@"
