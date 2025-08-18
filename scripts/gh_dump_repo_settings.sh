#!/usr/bin/env bash
set -euo pipefail

# Simple, readable GitHub status report.
# Usage:
#   OWNER=YourUser REPO=YourRepo scripts/gh_status_report.sh
# Defaults:
OWNER="${OWNER:-DariuszNewecki}"
REPO="${REPO:-CORE}"

has_jq() { command -v jq >/dev/null 2>&1; }
require_gh() { gh auth status >/dev/null 2>&1 || { echo "❌ gh not authenticated. Run: gh auth login"; exit 1; }; }

require_gh
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

out="GH_STATUS.md"
{
  echo "# GitHub Status Report — ${OWNER}/${REPO}"
  echo
  echo "Generated: $(date -u +"%Y-%m-%d %H:%M:%SZ")"
  echo

  echo "## Repository"
  gh api "repos/${OWNER}/${REPO}" > "${tmpdir}/repo.json"
  if has_jq; then
    jq '{name,visibility,default_branch,open_issues_count,description}' "${tmpdir}/repo.json"
  else
    cat "${tmpdir}/repo.json"
  fi
  echo

  echo "## Milestones"
  gh api "repos/${OWNER}/${REPO}/milestones?per_page=100&state=all" --paginate > "${tmpdir}/miles.json" || echo "[]" > "${tmpdir}/miles.json"
  if has_jq; then
    jq '.[] | {number,title,state,due_on,open_issues,closed_issues,description}' "${tmpdir}/miles.json"
  else
    cat "${tmpdir}/miles.json"
  fi
  echo

  # --- Issues ---
  echo "## Open Issues"
  gh issue list --repo "${OWNER}/${REPO}" --state open --limit 200 \
    --json number,title,labels,milestone,url,createdAt > "${tmpdir}/issues_open.json"
  if has_jq; then
    jq '.[] | {number,title,milestone: (.milestone.title // null),labels: (.labels | map(.name)),url,createdAt}' "${tmpdir}/issues_open.json"
  else
    cat "${tmpdir}/issues_open.json"
  fi
  echo

  echo "## Recently Closed Issues"
  gh issue list --repo "${OWNER}/${REPO}" --state closed --limit 30 \
    --json number,title,labels,milestone,url,closedAt > "${tmpdir}/issues_closed.json"
  if has_jq; then
    jq '.[] | {number,title,milestone: (.milestone.title // null),labels: (.labels | map(.name)),url,closedAt}' "${tmpdir}/issues_closed.json"
  else
    cat "${tmpdir}/issues_closed.json"
  fi
  echo

  # --- PRs (useful in practice) ---
  echo "## Open Pull Requests"
  gh pr list --repo "${OWNER}/${REPO}" --state open --limit 50 \
    --json number,title,labels,milestone,url,createdAt,updatedAt > "${tmpdir}/prs_open.json" || echo "[]" > "${tmpdir}/prs_open.json"
  if has_jq; then
    jq '.[] | {number,title,milestone: (.milestone.title // null),labels: (.labels | map(.name)),url,createdAt,updatedAt}' "${tmpdir}/prs_open.json"
  else
    cat "${tmpdir}/prs_open.json"
  fi
  echo

  echo "## Labels"
  gh label list --repo "${OWNER}/${REPO}" --json name,color,description > "${tmpdir}/labels.json" || echo "[]" > "${tmpdir}/labels.json"
  if has_jq; then
    jq '.[] | {name,color,description}' "${tmpdir}/labels.json"
  else
    cat "${tmpdir}/labels.json"
  fi
  echo

  echo "## Projects (Projects v2)"
  gh project list --owner "${OWNER}" > "${tmpdir}/projects.txt" || true
  cat "${tmpdir}/projects.txt"
  echo
  if grep -Eo '#[0-9]+' "${tmpdir}/projects.txt" >/dev/null 2>&1; then
    while read -r num; do
      pnum="${num//#/}"
      echo "### Project ${pnum}"
      gh project view "${pnum}" --owner "${OWNER}" --format json || true
      echo
    done < <(grep -Eo '#[0-9]+' "${tmpdir}/projects.txt" | sort -u)
  fi

  echo "## Releases"
  gh release list --repo "${OWNER}/${REPO}" || true
  echo
} > "${out}"

echo "✅ Report written to ${out}"
