#!/bin/bash
# Archive confirmed-superseded orphan files
# Usage: bash archive_orphans.sh
# Run from CORE repo root

ARCHIVE_DIR=".archive/superseded_$(date +%Y-%m-%d)"
mkdir -p "$ARCHIVE_DIR"

FILES=(
  # old governance engine (superseded by IntentRepository)
  "src/mind/governance/anchor.py"
  "src/mind/governance/check_registry.py"
  "src/mind/governance/enforcement/async_units.py"
  "src/mind/governance/enforcement/base.py"
  "src/mind/governance/enforcement/sync_units.py"
  "src/mind/governance/governance_query.py"
  "src/mind/governance/policy_analyzer.py"
  "src/mind/governance/policy_gate.py"
  "src/mind/governance/policy_loader.py"
  "src/mind/governance/policy_resolver.py"
  "src/mind/governance/registry.py"
  "src/mind/governance/schemas.py"
  "src/mind/logic/auditor.py"

  # pre-constitutional agents (superseded by worker model)
  "src/will/agents/action_introspection.py"
  "src/will/agents/context_auditor.py"
  "src/will/agents/conversational_governed.py"
  "src/will/agents/deduction_agent.py"
  "src/will/agents/intent_translator.py"
  "src/will/agents/pre_flight_validator.py"
  "src/will/agents/reconnaissance_agent.py"
  "src/will/agents/researcher_agent.py"
  "src/will/agents/self_correction_engine.py"
  "src/will/agents/specification_agent.py"

  # dead utilities
  "src/shared/constants.py"
  "src/shared/legacy_models.py"
  "src/shared/processors/json_processor.py"
  "src/shared/schemas/manifest_validator.py"
  "src/shared/utils/alias_resolver.py"
  "src/shared/utils/import_scanner.py"
  "src/shared/utils/text_cleaner.py"

  # dead body files
  "src/body/operations/anchor.py"
  "src/body/quality/anchor.py"
  "src/body/test_violation.py"
  "src/body/operations/incident_logic.py"
)

MOVED=0
MISSING=0

for f in "${FILES[@]}"; do
  if [ -f "$f" ]; then
    dest="$ARCHIVE_DIR/$f"
    mkdir -p "$(dirname "$dest")"
    mv "$f" "$dest"
    echo "archived: $f"
    ((MOVED++))
  else
    echo "missing:  $f"
    ((MISSING++))
  fi
done

echo ""
echo "done. moved=$MOVED missing=$MISSING"
echo "archive: $ARCHIVE_DIR"
