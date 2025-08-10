#!/usr/bin/env bash
# Create a visible, pragmatic roadmap as GitHub issues.
# Prereq: gh auth login  (or GH_TOKEN env)

set -euo pipefail

REPO="${1:-}" # optional: org/repo, otherwise uses current
LABELS_COMMON="roadmap,organizational"
MILESTONE="${2:-Organizational Pass}"

create_issue () {
  local title="$1"
  local body="$2"
  local labels="$3"
  if [[ -n "$REPO" ]]; then
    gh issue create --repo "$REPO" --title "$title" --body "$body" --label "$labels"
  else
    gh issue create --title "$title" --body "$body" --label "$labels"
  fi
}

# Ensure labels exist (idempotent)
ensure_label () {
  local name="$1"; local color="$2"; local desc="$3"
  gh label create "$name" --color "$color" --description "$desc" 2>/dev/null || true
}
ensure_label "roadmap" "0366d6" "Roadmap item"
ensure_label "organizational" "a2eeef" "Project organization"
ensure_label "ci" "7057ff" "CI/CD"
ensure_label "audit" "d73a4a" "Constitutional audit & governance"
ensure_label "docs" "0e8a16" "Documentation"

create_issue "Add JSON logging & request IDs" $'**Goal**: Switch logger to support LOG_FORMAT=json and add request id middleware in FastAPI.\n\n**Acceptance**\n- LOG_FORMAT=json writes structured logs\n- x-request-id is set/propagated\n- Docs updated in docs/CONVENTIONS.md' "$LABELS_COMMON,ci"

create_issue "Pre-commit hooks (Black, Ruff)" $'**Goal**: Add .pre-commit-config.yaml and wire to Make.\n\n**Acceptance**\n- pre-commit runs Black/Ruff locally\n- CI stays green' "$LABELS_COMMON,ci"

create_issue "Docs: CONVENTIONS.md & DEPENDENCIES.md" $'**Goal**: Codify folder map, import rules, capability tags, dependency policy.\n\n**Acceptance**\n- New contributors can place files w/o asking\n- Import discipline matrix documented' "$LABELS_COMMON,docs"

create_issue "Governance: proposal.schema.json + proposal_checks" $'**Goal**: Enforce schema & drift checks for .intent/proposals.\n\n**Acceptance**\n- Auditor shows schema pass/fail\n- Drift (token mismatch) → warning\n- Example proposal present' "$LABELS_COMMON,audit"

create_issue "Modular manifests (aggregator + fallback)" $'**Goal**: Support src/*/manifest.yaml aggregated into .intent/knowledge/project_manifest_aggregated.yaml.\n\n**Acceptance**\n- Auditor prefers aggregated manifest\n- Backward-compatible with monolith' "$LABELS_COMMON"

create_issue "Pilot domain package (proposals)" $'**Goal**: Create src/domain/proposals/{models,services,schemas}.py and migrate only proposal-related code.\n\n**Acceptance**\n- No new audit failures\n- Clear import boundaries documented' "$LABELS_COMMON"
