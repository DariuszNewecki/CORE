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
# Safe to re-run: the throwaway violation and the demo's seed + fix commits are
# rolled back to the pre-demo HEAD on exit, leaving your tree as it was.
#
# Verified end-to-end on a clean Ubuntu 24.04 machine — 4 consecutive clean runs
# including a fresh public `git clone`. See scripts/coldroom-prep.sh.
set -euo pipefail

cd "$(dirname "$0")/.."
SEED="src/body/analyzers/demo_onramp_violation.py"
ADMIN=(poetry run core-admin)
# CORE executes fixes in a git worktree built from HEAD, so the violation must
# be committed for the fixer to see it. Remember where we started so cleanup can
# roll back the demo's seed + fix commits to a pristine tree.
ORIG_HEAD="$(git rev-parse HEAD 2>/dev/null || true)"

if [[ -t 1 ]]; then B=$'\e[1m'; G=$'\e[32m'; Y=$'\e[33m'; C=$'\e[36m'; D=$'\e[2m'; X=$'\e[0m'
else B=''; G=''; Y=''; C=''; D=''; X=''; fi
act()  { printf '\n%s▸ %s%s\n' "${B}${C}" "$*" "$X"; }
note() { printf '  %s%s%s\n' "$D" "$*" "$X"; }

cleanup() {
  # Roll the throwaway demo commits (seed + fix) back to the pre-demo state.
  if [[ -n "${ORIG_HEAD:-}" ]]; then
    git reset --hard "$ORIG_HEAD" >/dev/null 2>&1 || true
  fi
  rm -f "$SEED"
}
trap cleanup EXIT

# ---- 1. ENCOUNTER — seed a real, structural violation ----------------------
act "A developer adds a function and commits it — forgetting CORE's symbol-ID rule"
cat > "$SEED" <<'PY'
"""Throwaway file created by scripts/demo.sh to demonstrate CORE's governance loop."""
from __future__ import annotations


def greet(name: str) -> str:
    # No '# ID:' anchor above this public function — that violates
    # linkage.assign_ids, a blocking constitutional rule.
    return f"hello, {name}"
PY
# Commit it (--no-verify: skip local hooks) so CORE's from-HEAD fix worktree sees it.
git add "$SEED" >/dev/null 2>&1
git commit --no-verify -q -m "demo: add greet() — missing # ID anchor" >/dev/null 2>&1 \
  && note "committed ${SEED} at $(git rev-parse --short HEAD)" \
  || note "could not commit the seed — check git identity / hooks"

# ---- 2. AUDIT — CORE detects it, deterministically -------------------------
# File-scoped (--files) so the demo is fast; capture output then grep so the
# audit's non-zero "findings present" exit doesn't trip `set -o pipefail`.
act "CORE audits the change (offline — no services, no LLM)"
audit_out="$("${ADMIN[@]}" code audit --offline --files "$SEED" 2>/dev/null || true)"
if grep -qiE 'linkage.assign_ids' <<<"$audit_out"; then
  printf '  %s→ BLOCKED: linkage.assign_ids fired on the new file%s\n' "$Y" "$X"
else
  note "expected a linkage.assign_ids finding on ${SEED}; verify the offline rule set covers it"
fi

# ---- 3. REMEDIATE — propose, approve, execute ------------------------------
act "CORE proposes the fix, the governor approves, CORE executes"
PID="$("${ADMIN[@]}" proposals create "Demo: assign the missing symbol ID" \
        -a fix.ids --write 2>/dev/null \
        | grep -oiE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1 || true)"
[[ -n "$PID" ]] || { note "could not read a proposal id from 'proposals create' — is core-api running?"; exit 1; }
note "proposal ${PID} created"
"${ADMIN[@]}" proposals approve "$PID" --by demo --authority principal.governor >/dev/null 2>&1 \
  && note "approved (authority: principal.governor)"
# execute is a dangerous op and prompts 'Continue? [y/n]'; answer it for the
# unattended demo (the proposal was already governor-approved above).
if printf 'y\n' | "${ADMIN[@]}" proposals execute "$PID" --write >/dev/null 2>&1; then
  printf '  %s→ executed: CORE added the missing ID and committed the change%s\n' "$G" "$X"
else
  note "execute failed — inspect 'proposals show ${PID}'"
fi

# ---- 4. VERIFY — re-audit, now clean ---------------------------------------
act "CORE re-audits to confirm the fix"
verify_out="$("${ADMIN[@]}" code audit --offline --files "$SEED" 2>/dev/null || true)"
if grep -qiE 'linkage.assign_ids' <<<"$verify_out"; then
  note "violation still present — inspect proposals show ${PID}"
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
" 2>/dev/null || note "consequence query failed — confirm DB reachable from the demo shell"

printf '\n%s✓ That is the whole thesis: encounter → audit → remediate → verify, recorded end to end.%s\n' "$G" "$X"
note "Reproduce the chain any time — see docs/proof-index.md (Consequence-chain query)."
