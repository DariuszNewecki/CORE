# ADR-155 Final Acceptance Report — "Isolated Consequence-Chain Demo"

**Candidate:** `3cbe0be0b813e9be7c7baeebd53cf67ac14f890f`, branch
`feat/isolated-consequence-chain-demo` (9 commits atop `main`).
**Main at time of writing:** `ee00e2b3` (unchanged since the candidate's last rebase).
**Prepared:** 2026-07-26. **Status:** Evidence synthesis for governor signature. Claude
does not sign attestations or authorize merges; this report recommends, the governor
decides. **No merge, deploy, or branch mutation has occurred or is proposed by this
report** — per the governor's repeated explicit instruction, merge remains a separately
authorized action regardless of this verdict.

---

## 1. What this report is

This synthesizes every piece of verification evidence gathered against the frozen
candidate `3cbe0be0` — hosted CI, the full Phase 4 acceptance-test matrix, the DoD
checklist (spec §8), the reviewer checklist (spec §10), and the E15 cold-room run — into
one recommended verdict: **Accepted / Accepted-with-limitations / Blocked**, per the
governor's own directive for how this phase should conclude.

It relies on evidence already independently gathered and verified during this workstream
rather than re-deriving all of it from scratch in this sitting; where evidence predates
this report, that is stated explicitly rather than presented as freshly re-run.

## 2. Candidate lineage (why `3cbe0be0`, not an earlier SHA)

| SHA | What it is |
|---|---|
| `a2c09cb2` | First fully CI-green, Phase-4-matrix-passed candidate. Governor later ruled its "every ID passed" claim an **overclaim** — 3 acceptance IDs (U08/U09/U10, U15/E12, E14) rested on proxy/partial coverage, not direct adversarial tests, even though they protect ADR-155's central safety claims. |
| `b2e87076` | Closed those 3 gaps with new adversarial tests (11 new tests, no production-code changes — test-only, no defect found). Re-verified hosted CI green, Phase 4 matrix rerun green. |
| `3cbe0be0` | Closed one residual gap the `b2e87076` rerun surfaced itself (the outer `asyncio.wait_for` scenario-level deadline, distinct from the already-tested `compose_down` deadline). Hosted CI green a third time. Phase 4 matrix rerun: **every one of the 29 IDs is now direct-adversarial-test-verified, zero remaining partial/proxy notes** — this is the first time the top-line "all passed" claim was actually earned rather than rolled up. |

Each step was independently re-verified in-session (not just relayed from a subagent):
tip/tree state, full demo-scoped suite re-run for real (103 passed, 0 failed at `3cbe0be0`),
ruff/mypy clean, zero Docker leftovers after a real SIGINT run, ambiguous mypy findings
diffed against an untouched baseline commit to confirm pre-existing vs. newly introduced.

## 3. Hosted CI evidence

Three full cycles, one per candidate SHA above, via the same evidence-only mechanism (a
draft "do not merge" PR against `main`, tree-identity-verified against the merge ref
*before* trusting any run result, closed without merging once evidence was captured):

| Candidate | `CORE CI` run | Result | `CI (Smoke)` run | Result |
|---|---|---|---|---|
| `a2c09cb2` | `30209027612` | success — 3817 passed, 1 skipped | `30209027577` | success |
| `b2e87076` | `30213933002` | success — 3828 passed, 1 skipped | `30213932973` | success |
| `3cbe0be0` | `30215457163` | success — **3829 passed, 1 skipped** | `30215457136` | success |

The pass-count increases exactly track the new tests added at each step (11, then 1) —
no unrelated drift. All three `headSha` values were confirmed to match the candidate
exactly; a structural gap discovered along the way (`CORE CI`/`CI (Smoke)` have no
`workflow_dispatch` trigger, so arbitrary-SHA hosted CI requires this draft-PR technique)
is filed as **#827**, non-blocking dev-infra follow-up, not a defect in the candidate.

## 4. Phase 4 acceptance-test matrix — final state at `3cbe0be0`

Per spec §6.1–6.3: **U01–U15 (15 unit/contract IDs), E01–E14 (14 integration/e2e IDs),
and all 18 §6.3 negative-claim tests — 29 IDs + 18 negative claims, all PASS, all now
direct-adversarial-test-verified** (no ID rests on proxy coverage or an assertion-layer
substitute for the thing it claims to test). This closed out a governor-flagged overclaim
from the `a2c09cb2` pass (§2 above) — the final state is not merely "green," it is green
*for the reason each ID actually names*:

- U08/U09/U10 (exact finding/proposal/consequence linkage under zero/duplicate/multi-match
  conditions) — now tested directly against `_resolve_finding`/`_resolve_proposal` with
  mocked query results, not just at the assertion-evaluator layer.
- U15 + E12 (timeout/interrupt handling) — both the `compose_down` deadline *and* the
  outer scenario-level `asyncio.wait_for` deadline are now adversarially tested; E12 sends
  a real OS-level `SIGINT` to a real running child process (Docker-backed) and confirms
  exit 130, zero surviving run-labelled containers, zero orphaned processes.
- E14 (no-LLM independence) — sentinel LLM env vars proven not to leak into the child
  process's explicit env, and the written `.env`'s `LLM_ENABLED=False` proven deterministic
  regardless of parent-process state (explicitly scoped to not overclaim "no network
  attempt," matching the governor's own framing of what's provable).

Offline constitutional audit at `3cbe0be0`: **0 failed rules**, 1 pre-existing info-level
finding (`os.environ.get("PATH")`, legitimate per D5's explicit-env design, reporting-tier
not blocking). Repo-wide audit's only other hit is the untracked `.specs/planning/`
demo-spec doc itself — a known, pre-existing pattern (an unclassified planning doc), not a
demo-code issue.

## 5. E15 — cold-room run (this session, 2026-07-26)

**Verdict: PASS with governor-accepted operator-independence deviation** — not an
unqualified independent-user validation. Full detail in
`.specs/attestations/e15-coldroom-3cbe0be0-20260726.md`. Summary: on a Proxmox-hosted VM
purpose-built for this test (prerequisites baked in, never CORE itself, genuinely never
touched `/opt/dev` or this repo before), following only
`README.md`/`docs/getting-started.md`/`docs/cli-reference.md` with no source inspection —
`git clone` → `git checkout 3cbe0be0` → `./install-core.sh` → `poetry run core-admin demo
consequence-chain --output report.md --simulate-confirmation` — **two independent runs,
both PASSED**, 16/16 fail-closed assertions (D7 + D10.1–15) green with concrete SHAs/IDs
each time, re-audit clean, cleanup independently verified (zero leftover
containers/networks/workspace after `qm destroy`).

**The deviation this verdict carries:** the operator was Claude Code — the same agent
that implemented and verified ADR-155 throughout — not a literal separate human who has
never seen the implementation. What *was* independently enforced (clean host, no shared
state, no source-reading to find or shape the command) is real and non-trivial, but it is
not the same claim as "a genuine outside developer succeeded." Per governor decision
2026-07-26 (§11): this does not block acceptance or merge; a genuinely independent human
cold-room run is recorded as a **post-merge validation item**, required before upgrading
this from "PASS with deviation" to an unqualified independent pass.

Also disclosed there, non-blocking: Run 1's exit code was inferred from the printed
`PASSED` output rather than captured directly (Run 2's was, `RC=0`); the QEMU guest
agent is not actually installed in the template despite its Proxmox config claiming one
(`agent: 1`).

**Evidence-publication correction (governor-caught, 2026-07-26):** an earlier draft of
the E15 report stated the VM's password credential in plaintext. It was never committed
or pushed — caught before the first commit. Remediation went further than a simple
redaction: re-checking found the documented operator SSH key was present in this
session's environment the whole time (the original claim that it was unavailable was
itself wrong — an unchecked assumption, not a real gap) and matches the template's
`authorized_keys` exactly. Password authentication was rotated, then verified, then
**disabled entirely** on `core-template` (VM 300), leaving genuine SSH-key-only access —
the state the template's own documentation claimed but did not actually enforce. Full
remediation record, including the specific `sshd_config.d` ordering bug this fix
uncovered and fixed along the way, is in E15 report §9.

## 6. Definition of Done — spec §8, mapped

| DoD item | Status | Evidence |
|---|---|---|
| Old implementation logic is gone | ✅ | `scripts/demo.sh` is a thin wrapper delegating to `demo consequence-chain`, "no scenario logic of its own" (`docs/cli-reference.md`); Phase 1–3 commits (`7a4605aa`…`57e8b782`) replaced the five defects the spec's §2 identified |
| Installation never runs the demo automatically | ✅ | `install-core.sh` D1 comment + behavior; E15's own install run ended in the "offering," not running, the demo |
| Demo exercises a genuine finding-linked proposal | ✅ | D8 assertions D10.3/D10.4, PASS in every Phase 4 + E15 run |
| Every displayed chain element belongs to the same exact proposal | ✅ | D10.3–D10.12 assertions, PASS every run; §6.3 negative-claim tests prove the demo *cannot* pass on a mismatch |
| Approval authority represented truthfully | ✅ | U11; reports label "policy authority," never "human approved"; operator confirm labelled "simulated" in every `--simulate-confirmation` run |
| Dirty invoking repository unchanged byte-for-byte | ✅ | E02, PASS at `3cbe0be0`'s Phase 4 rerun (not independently re-run in E15, which used a throwaway clone with nothing to protect) |
| No production service or data reused | ✅ | E03 (sentinel collision defense), E04 (parallel runs), E14 (no-LLM) all PASS, direct-adversarial-verified |
| Cleanup bounded, scoped, verified, failure-visible | ✅ | D11, U06, E12; independently re-verified live in E15 (real VM, real Docker, zero residue after) |
| Documentation sufficient for a non-author | ⚠️ mostly | E15 followed the docs successfully with zero gaps hit — but see the operator-identity caveat in §5; sufficiency was demonstrated under discipline, not by a literal outside reader |
| Complete acceptance-test contract is green | ✅ | §4 above — 29/29 IDs + 18/18 negative claims, all direct-verified at `3cbe0be0` |
| Constitutional audit is green | ✅ | 0 failed rules at `3cbe0be0`; E15's own install run independently reproduced a clean offline audit |
| Resulting evidence is independently reviewed | ⚠️ Mostly | Evidence was repeatedly cross-checked against direct runs, Git state, hosted CI, Docker state, and generated artifacts (see §2) — but no separate human or independently developed evaluator reviewed the final result. The same Claude Code agent implemented, verified, operated E15, and assembled this evidence; rechecking subagent output is useful, but it is not independent review in the conventional sense. |

## 7. Reviewer checklist — spec §10, mapped

Any "yes" to 1–7, any "no" to 8–10, or an unverifiable answer blocks acceptance. None
triggered:

| # | Question | Answer | Evidence |
|---|---|---|---|
| 1 | Can any code path write to the invoking checkout? | No | E02 PASS; D2 enforced; E15's clone lived entirely on a separate host with nothing to write back to |
| 2 | Can any code path resolve a finding/proposal/consequence by "latest"? | No | D6 prohibits direct SQL/"latest" selection; D8 exact-linkage assertions D10.3/D10.4 PASS; U09/U10 now direct-tested |
| 3 | Can the demo claim success after a missing link? | No | D10 fail-closed assertions; all 18 §6.3 negative-claim tests PASS |
| 4 | Can operator confirmation be confused with recorded approval? | No | D9; U11; every report explicitly separates "approval: policy authority" from "operator confirm: simulated/human" |
| 5 | Can a production endpoint leak into the child configuration? | No | E03, E14 direct-adversarial-verified |
| 6 | Can cleanup escape the validated run directory? | No | D3, U06 (wrong-parent/missing-marker/symlink-escape all refused); E15 confirmed zero residue on a real host |
| 7 | Can an interruption leave a process or container running? | No | E12 — real OS-level SIGINT test, zero leftovers, direct-verified |
| 8 | Does any demo-only function bypass the normal sensor/proposal/executor/consequence services? | No | D6 — real `AuditViolationSensor`, `ViolationRemediatorWorker`, `ProposalStateManager`, real `POST /v1/proposals/{id}/execute` route, real `ProposalExecutor`; unchanged across all three candidate SHAs |
| 9 | Is `.intent/` byte-identical in both repositories? | Yes | D10.14/D10.15, PASS in every Phase 4 run and both E15 runs (`report.json` shows identical before/after hashes) |
| 10 | Does the report plainly state the limits of what the demo proves? | Yes | Every generated report carries: "This demonstration proves one isolated consequence chain. It is not a production-readiness attestation." |

## 8. Explicit non-goals (spec §9) — none violated

Confirmed not claimed or done: does not fix G1/G5/G10/G13 by existing; no web UI; no
human-approved-dangerous-action demonstration (D9 deliberately avoids staging this); no
DB migration/rollback validation; never ran against the live CORE deployment (E15 used a
disposable VM, never `/opt/dev`); `.intent/` never modified (D10.14); `fix.ids` risk
classification unchanged; no failure concealment (this report and its predecessors
disclose every gap found, including overclaims the governor had to correct); does not
replace the separate production-readiness assessment (G4 soak, closed independently,
`.specs/attestations/soak-closure-f7430b25-20260726.md` — its own gate, not superseded by
this work).

## 9. Residual open items (non-blocking, tracked separately)

- **#827** — no `workflow_dispatch` on `CORE CI`/`CI (Smoke)`; arbitrary-SHA hosted CI
  needs the draft-PR technique used three times in this workstream. Dev-infra, not a
  candidate defect.
- **#828** — `core-admin code audit --format json` interleaves log lines with the JSON
  payload on stdout. Unrelated to the demo; do not fix under ADR-155.
- **Resolved during this session, not left open:** the cold-room template's SSH-key
  access path was initially assumed unavailable (wrongly — see §5's evidence-publication
  correction), then fixed properly: password auth rotated, verified, and disabled
  outright, key-only access confirmed working. No follow-up required here.
- The `qemu-guest-agent` gap remains open on the template (not installed, despite
  `agent: 1` in its Proxmox config) — worth adding so `qm guest exec` works without SSH
  at all, but not urgent now that key-based SSH is confirmed reliable. Local
  infrastructure, not a repo issue.

## 10. Governor decision (2026-07-26) — supersedes the draft recommendation above

**ADR-155 candidate `3cbe0be0b813e9be7c7baeebd53cf67ac14f890f` is Accepted with
limitations.**

The implementation's mechanically verifiable safety claims are accepted based on: hosted
CI success against the frozen candidate; complete U01–U15 and E01–E14 direct adversarial
coverage; all negative-claim tests passing; clean constitutional audit; real
Docker-backed interruption and cleanup verification; successful isolated cold-room
installation and two consequence-chain executions; verified finding, proposal,
execution, consequence, resolution, re-audit, `.intent/` immutability, and cleanup
evidence.

The accepted limitation is that E15 was operated by the same Claude Code agent involved
in implementation and verification rather than by a genuinely independent human
operator. E15 is recorded as **PASS with governor-accepted operator-independence
deviation**, not as an unqualified independent-user validation (§5). The DoD item
"resulting evidence is independently reviewed" is likewise recorded as **partially
satisfied**: the evidence was directly and repeatedly cross-checked, but no independent
human reviewer assessed the completed implementation (§6).

**This limitation does not block merge.** A genuinely independent cold-room run remains
a **post-merge validation item** — tracked narrowly as: *a genuinely independent operator
installs CORE from public documentation and completes `core-admin demo
consequence-chain` without implementation guidance* — validating external
comprehensibility and adoption, not implementation safety, which is already extensively
demonstrated. It is required before upgrading this verdict to an unqualified
**Accepted**.

**Evidence-publication precondition (satisfied before this section was written):** the
plaintext credential disclosed in an earlier E15 draft has been removed, the credential
rotated on the template, and the template documentation flagged for correction (§5, E15
report §9).

## 11. Merge authorization

Following the two corrections above, the governor separately authorizes a
**fast-forward-only** merge of `feat/isolated-consequence-chain-demo` into `main`. Do
**not** squash — the phased implementation and later test-hardening commits carry useful
causal history.

```bash
git switch main
git pull --ff-only
git merge --ff-only feat/isolated-consequence-chain-demo
git push origin main
```

Pre-merge verification (run before executing the above):

```bash
git rev-parse main
git rev-parse feat/isolated-consequence-chain-demo
git merge-base --is-ancestor main feat/isolated-consequence-chain-demo
git status --short
```

Expected pre-merge state: `main` = `ee00e2b3…`, `feature` = `3cbe0be0…`, ancestor check
true, working tree clean. This report's own sanitized text and the sanitized E15 report
are committed as a **separate documentation/evidence commit after** the fast-forward, so
the technical candidate SHA that was verified throughout this workstream is exactly the
SHA that lands on `main` — the evidence commit does not change it.

## 12. Third-party cold-room run — tracked as post-merge, not a blocker

Per the governor: do not keep the implementation hostage to finding a third party. One
narrow follow-up is tracked (see §11's post-merge validation item above) rather than
gating this merge on it.

## 13. G4 production-readiness soak — unchanged, not signed

Per the governor: **do not sign G4 as `met`.** The soak report
(`.specs/attestations/soak-closure-f7430b25-20260726.md`) is retained as historical
evidence — one agreed no-commit condition was not literally met, one worker repeatedly
errored throughout the run, the evidence demonstrates continuity rather than a clean
reliable autonomous loop, and the baseline has since been superseded and restarted.
`production-readiness.yaml` is left unchanged; G4 remains `not_demonstrated` pending a
future assessment against an actual production candidate. This is independent of, and
not resolved by, the ADR-155 merge.
