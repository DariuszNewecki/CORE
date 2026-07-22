#!/usr/bin/env bash
#
# scripts/check_readme_counts.sh — #631
#
# Re-derive the README's four quantitative governance claims from source and
# fail when README disagrees. A standing tripwire: the counts cannot silently
# drift again after a hand-fix (closed-by-enforcement, not closed-by-evidence).
#
# It asserts the numbers the README *states* equal the numbers *derived* from
# source — it does NOT hardcode today's values (209/49/204/5/13), so it stays
# correct as the corpus grows. Re-run locally with: bash scripts/check_readme_counts.sh
#
# Derivations (reproduce any of these by hand without reading CI):
#   rules          = unique rule ids across .intent/rules/**/*.json
#   rule documents = number of .intent/rules/**/*.json files
#   mapped         = defined rule ids that appear as a mapping key under
#                    .intent/enforcement/mappings/**/*.yaml
#   unmapped       = defined - mapped
#   engines        = BaseEngine subclasses under src/mind/logic/engines/,
#                    excluding the LLMGateStub fallback (stands in for llm_gate
#                    when no LLM client is present)
#
# A claim whose README prose was reworded so the regex no longer matches is a
# deliberate FAIL — update both the prose and the regex below together.
set -euo pipefail

cd "$(dirname "$0")/.."
# Optional arg: path to the README to check (default repo README.md). Lets the
# comparison be tested against a modified copy while still deriving counts from
# the real source tree.
README="${1:-README.md}"
fail=0

# --- derive from source -----------------------------------------------------
defined=$(find .intent/rules -name '*.json' -exec jq -r '.rules[]?.id' {} + | sort -u)
mapkeys=$(grep -rhoE '^[[:space:]]+[A-Za-z][A-Za-z0-9_.]*:' .intent/enforcement/mappings/ \
            | sed -E 's/^[[:space:]]+//; s/:$//' | sort -u)
mapped_ids=$(comm -12 <(printf '%s\n' "$defined") <(printf '%s\n' "$mapkeys"))

d_rules=$(printf '%s\n' "$defined" | grep -c .)
d_docs=$(find .intent/rules -name '*.json' | wc -l | tr -d ' ')
d_mapped=$(printf '%s\n' "$mapped_ids" | grep -c .)
d_unmapped=$((d_rules - d_mapped))
d_engines=$(grep -rhE 'class [A-Za-z0-9_]+\(BaseEngine\)' src/mind/logic/engines/ \
              | grep -v Stub | grep -c .)

# --- compare against the README's stated numbers ----------------------------
# Each claim: a human label, the source-derived value, and a regex that pulls
# the number(s) the README states. Every matched number must equal the derived
# value; a claim that matches nothing is a failure (prose drifted out of range).
assert_claim() {
  local label="$1" derived="$2" regex="$3" file="${4:-$README}" claims c ok=1
  claims=$(grep -oiE "$regex" "$file" | grep -oE '[0-9]+' | sort -u || true)
  if [[ -z "$claims" ]]; then
    printf 'FAIL  %-14s no claim matched /%s/ in %s (source=%s)\n' "$label" "$regex" "$file" "$derived"
    fail=1
    return
  fi
  for c in $claims; do
    if [[ "$c" != "$derived" ]]; then
      printf 'FAIL  %-14s %s states %s, source has %s\n' "$label" "$file" "$c" "$derived"
      fail=1
      ok=0
    fi
  done
  [[ "$ok" -eq 1 ]] && printf 'ok    %-14s %s (%s)\n' "$label" "$derived" "$file"
  return 0  # never let a mismatch trip `set -e` — collect all drifts, exit once
}

assert_claim "rules"        "$d_rules"    '[0-9]+ rules'
assert_claim "rule docs"    "$d_docs"     '[0-9]+ rule documents'
assert_claim "mapped"       "$d_mapped"   '[0-9]+ are mapped'
assert_claim "unmapped"     "$d_unmapped" '[0-9]+ are advisory rules'
assert_claim "engines"      "$d_engines"  '[0-9]+ engines'

# docs/how-it-works.md carries the same constraints-node mermaid as the README
# ("N rules • M engines"). It drifted unguarded once (#561: said 120 rules / 7
# engines); guard the two claims it states so the two public surfaces cannot
# diverge again. Only checked when the file is present (skipped for an external
# README arg).
HOWITWORKS="docs/how-it-works.md"
if [[ "$README" == "README.md" && -f "$HOWITWORKS" ]]; then
  assert_claim "rules (hiw)"   "$d_rules"   '[0-9]+ rules'   "$HOWITWORKS"
  assert_claim "engines (hiw)" "$d_engines" '[0-9]+ engines' "$HOWITWORKS"
fi

if [[ "$fail" -ne 0 ]]; then
  echo
  echo "README quantitative claims are out of sync with source. Update README.md"
  echo "(or this script's regex if a claim was intentionally reworded)."
  exit 1
fi
echo "README quantitative claims match source."
