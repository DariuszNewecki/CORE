#!/usr/bin/env bash
set -euo pipefail
OWNER="${OWNER:-DariuszNewecki}"
REPO="${REPO:-CORE}"

has_jq() { command -v jq >/dev/null 2>&1; }

out="GH_STATUS.md"
echo "# GitHub Status Report — $OWNER/$REPO" > "$out"
echo "" >> "$out"
echo "Generated: $(date -u +"%Y-%m-%d %H:%M:%SZ")" >> "$out"
echo "" >> "$out"

echo "## Repository" >> "$out"
gh api repos/$OWNER/$REPO > /tmp/repo.json
if has_jq; then
  jq '{name,visibility,default_branch,open_issues_count,description}' /tmp/repo.json >> "$out"
else
  cat /tmp/repo.json >> "$out"
fi
echo "" >> "$out"

echo "## Milestones" >> "$out"
gh api repos/$OWNER/$REPO/milestones --paginate > /tmp/miles.json || echo "[]">/tmp/miles.json
if has_jq; then
  jq '.[] | {number,title,state,due_on,open_issues,closed_issues,description}' /tmp/miles.json >> "$out"
else
  cat /tmp/miles.json >> "$out"
fi
echo "" >> "$out"

# --- THIS IS THE MODIFIED SECTION ---

echo "## Open Issues" >> "$out"
gh issue list --repo $OWNER/$REPO --state open --limit 200 \
  --json number,title,labels,milestone,url,createdAt > /tmp/issues_open.json
if has_jq; then
  jq '.[] | {number,title,milestone: .milestone.title,labels: [.labels[].name],url,createdAt}' /tmp/issues_open.json >> "$out"
else
  cat /tmp/issues_open.json >> "$out"
fi
echo "" >> "$out"

echo "## Recently Closed Issues" >> "$out"
gh issue list --repo $OWNER/$REPO --state closed --limit 30 \
  --json number,title,labels,milestone,url,closedAt > /tmp/issues_closed.json
if has_jq; then
  jq '.[] | {number,title,milestone: .milestone.title,labels: [.labels[].name],url,closedAt}' /tmp/issues_closed.json >> "$out"
else
  cat /tmp/issues_closed.json >> "$out"
fi
echo "" >> "$out"

# --- END OF MODIFIED SECTION ---

echo "## Labels" >> "$out"
gh label list --repo $OWNER/$REPO --json name,color,description > /tmp/labels.json
if has_jq; then
  jq '.[] | {name,color,description}' /tmp/labels.json >> "$out"
else
  cat /tmp/labels.json >> "$out"
fi
echo "" >> "$out"

echo "## Projects (Projects v2)" >> "$out"
gh project list --owner $OWNER > /tmp/projects.txt || true
cat /tmp/projects.txt >> "$out"
echo "" >> "$out"
if grep -Eo '#[0-9]+' /tmp/projects.txt >/dev/null 2>&1; then
  while read -r num; do
    pnum="${num//#/}"
    echo "### Project $pnum" >> "$out"
    gh project view "$pnum" --owner $OWNER --format json >> "$out" || true
    echo "" >> "$out"
  done < <(grep -Eo '#[0-9]+' /tmp/projects.txt | sort -u)
fi

echo "## Releases" >> "$out"
gh release list --repo $OWNER/$REPO >> "$out" || true
echo "" >> "$out"

echo "Report written to $out"