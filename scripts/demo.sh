#!/usr/bin/env bash
#
# scripts/demo.sh — watch CORE govern itself, end to end, in one run.
#
# This is the on-ramp demo: it makes CORE detect a real violation, propose a
# fix, approve it, execute it, re-audit to confirm, and then shows you the
# consequence chain CORE recorded about its own action — the believer moment.
#
# It uses the DETERMINISTIC self-healing path (fix.ids), so it needs NO LLM and
# no API key. It does need a running CORE API (install-core.sh starts one).
#
# Safe to re-run: the seeded violation is a single throwaway file that is
# removed at the end. On a fresh clone the only effect on your tree is the
# fix-commit CORE makes (expected — that IS the consequence chain).
#
# Status: v1 — first end-to-end run is on a clean VM (#562). Steps marked
# [VM] are the ones most likely to need tuning once observed on a clean box.
set -euo pipefail

cd "$(dirname "$0")/.."
SEED="src/body/analyzers/demo_onramp_violation.py"
ADMIN=(poetry run core-admin)

if [[ -t 1 ]]; then B=$'\e[1m'; G=$'\e[32m'; Y=$'\e[33m'; C=$'\e[36m'; D=$'\e[2m'; X=$'\e[0m'
else B=''; G=''; Y=''; C=''; D=''; X=''; fi
act()  { printf '\n%s▸ %s%s\n' "${B}${C}" "$*" "$X"; }
note() { printf '  %s%s%s\n' "$D" "$*" "$X"; }

cleanup() {
  if git ls-files --error-unmatch "$SEED" >/dev/null 2>&1; then
    git rm -f --quiet "$SEED" 2>/dev/null || rm -f "$SEED"
  else
    rm -f "$SEED"
  fi
}
trap cleanup EXIT

# ---- 1. ENCOUNTER — seed a real, structural violation ----------------------
act "A developer adds a function — but forgets CORE's symbol-ID rule"
cat > "$SEED" <<'PY'
"""Throwaway file created by scripts/demo.sh to demonstrate CORE's governance loop."""
from __future__ import annotations


def greet(name: str) -> str:
    # No '# ID:' anchor above this public function — that violates
    # linkage.assign_ids, a blocking constitutional rule.
    return f"hello, {name}"
PY
note "wrote ${SEED} (a public function with no '# ID:' anchor)"

# ---- 2. AUDIT — CORE detects it, deterministically -------------------------
act "CORE audits the change (offline — no services, no LLM)"
if "${ADMIN[@]}" code audit --offline 2>/dev/null | grep -iE "linkage.assign_ids|${SEED}"; then
  printf '  %s→ BLOCKED: linkage.assign_ids fired on the new file%s\n' "$Y" "$X"
else
  note "[VM] expected a linkage.assign_ids finding on ${SEED}; verify the offline rule set covers it"
fi

# ---- 3. REMEDIATE — propose, approve, execute ------------------------------
act "CORE proposes the fix, the governor approves, CORE executes"
PID="$("${ADMIN[@]}" proposals create "Demo: assign the missing symbol ID" \
        -a fix.ids --write 2>/dev/null \
        | grep -oiE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1 || true)"
[[ -n "$PID" ]] || { note "[VM] could not parse a proposal id from 'proposals create' output — adjust the parse"; exit 1; }
note "proposal ${PID} created"
"${ADMIN[@]}" proposals approve "$PID" --by demo --authority principal.governor >/dev/null 2>&1 \
  && note "approved (authority: principal.governor)"
"${ADMIN[@]}" proposals execute "$PID" --write >/dev/null 2>&1 \
  && printf '  %s→ executed: CORE added the missing ID and committed the change%s\n' "$G" "$X"

# ---- 4. VERIFY — re-audit, now clean ---------------------------------------
act "CORE re-audits to confirm the fix"
if "${ADMIN[@]}" code audit --offline 2>/dev/null | grep -iqE "linkage.assign_ids.*${SEED##*/}"; then
  note "[VM] violation still present — inspect proposals show ${PID}"
else
  printf '  %s→ CLEAN: linkage.assign_ids no longer fires%s\n' "$G" "$X"
fi

# ---- 5. THE PAYOFF — the consequence chain CORE wrote about itself ---------
act "The consequence chain CORE just recorded"
.venv/bin/python -c "
import asyncio
from shared.infrastructure.database.session_manager import get_session
from sqlalchemy import text

async def main():
    async with get_session() as s:
        r = (await s.execute(text('''
            SELECT ap.goal, ap.status, ap.approved_by, ap.approval_authority,
                   left(pc.pre_execution_sha, 8)  AS pre_sha,
                   left(pc.post_execution_sha, 8) AS post_sha,
                   (SELECT string_agg(f->>'path', ', ')
                      FROM jsonb_array_elements(pc.files_changed) f) AS files_changed
            FROM core.proposal_consequences pc
            JOIN core.autonomous_proposals ap ON ap.proposal_id = pc.proposal_id
            ORDER BY pc.recorded_at DESC LIMIT 1
        '''))).mappings().first()
        if not r:
            print('  (no consequence row found — see proof-index.md Consequence-chain query)'); return
        print(f\"  FINDING   → {r['goal']}\")
        print(f\"  APPROVAL  → {r['approved_by']}  ({r['approval_authority']})\")
        print(f\"  EXECUTION → {r['status']}\")
        print(f\"  FILE      → {r['files_changed']}   {r['pre_sha']} → {r['post_sha']}\")
asyncio.run(main())
" 2>/dev/null || note "[VM] consequence query failed — confirm DB reachable from the demo shell"

printf '\n%s✓ That is the whole thesis: encounter → audit → remediate → verify, recorded end to end.%s\n' "$G" "$X"
note "Reproduce the chain any time — see docs/proof-index.md (Consequence-chain query)."
