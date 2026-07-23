---
kind: adr
id: ADR-155
title: "ADR-155 — Isolated consequence-chain demo: replace scripts/demo.sh with an isolation-substrate on-ramp"
status: accepted
---

<!-- path: .specs/decisions/ADR-155-isolated-consequence-chain-demo.md -->

# ADR-155 — Isolated consequence-chain demo: replace `scripts/demo.sh` with an isolation-substrate on-ramp

**Date:** 2026-07-23
**Governing spec:** `.specs/planning/CORE-Isolated-Consequence-Chain-Demo.md` (this ADR records its decisions D1–D12 as constitutional commitments)
**Status:** Accepted (2026-07-23), subject to the design-point resolutions below and a
same-day sequencing correction — see "Governor review and design-point resolutions" and
"Sequencing and blockers." The soak boundary protects the production baseline, not isolated
development: Phase 1 implementation may begin immediately in the isolated clone; see
Sequencing for exactly what remains prohibited before soak-close.
**Author:** Dariusz Newecki (governor)
**Drafter:** Claude (session 2026-07-23 — drafted under governor direction in the isolated development clone `CORE-demo-consequence-chain`, branched from assessment baseline `f7430b25`; the assessed checkout was untouched)
**Relates to:** ADR-146 (CLI consumer/operator split — the reason `core-admin proposals` no longer registers, defect 4 below), ADR-148 (proposal finalization barrier — the `COMPLETED`-as-evidence standard the demo asserts against), ADR-101 (commit authorship — the demo's seed commit must contain only the seed file), ADR-106 / ADR-071 D2.2 (execution sandbox — the hermetic worktree the demo relies on), ADR-068 D5 (`risk_classification.safe_auto_approval` — the authority the demo must display truthfully), ADR-054 / ADR-058 (API surface — the demo exercises real FastAPI routes in-process), the production-readiness assessment at `f7430b25` (this work is sequenced *after* that assessment and must not be represented as its evidence), and the G6 risk-vocabulary defect recorded in that assessment's errata (a Phase-2 blocker, below)

---

## Context

`scripts/demo.sh` is CORE's on-ramp: it makes the system detect a real violation, propose a
fix, approve it, execute it, re-audit, and show the consequence chain it recorded about its own
action. The *narrative* is CORE's central thesis made tangible. The *implementation* has, at
baseline `f7430b25`, five independent defects (enumerated in the governing spec §2), three of
which were independently confirmed during the production-readiness assessment:

1. It creates commits in the invoking checkout and then `git reset --hard`s — it mutates the
   very repository it is meant to demonstrate *on*, and its cleanup can erase a developer's
   uncommitted work (assessment G1 / commit-authorship concerns, ADR-101).
2. It can absorb pre-existing staged changes into its seed commit.
3. `install-core.sh` runs it automatically rather than offering it as opt-in (assessment G1).
4. It calls `core-admin proposals ...`, but after the ADR-146 consumer/operator CLI split that
   namespace is no longer registered in `core-admin` — so the script's remediation step cannot
   run at all at this baseline (assessment G1/G10: independently confirmed the command is
   absent). **The current demo is broken, not merely inelegant.**
5. Its evidence query selects the *most recent* consequence row and labels the proposal's
   `goal` as `FINDING` — it does not prove the displayed proposal is the one linked to the
   seeded finding (assessment G10: "latest"-selection is not proof of linkage).

Additionally, several checks use `|| true` or warn-and-continue, so the script can finish with
a success-shaped banner after a failed audit, execution, verification, or evidence query.

The fix is not to patch the script. It is to rebuild the on-ramp as a genuinely isolated
demonstration that (a) never touches the invoking checkout or any production service, and
(b) proves an *exact*, linkage-verified chain, failing closed on every claim.

## Decision

Adopt the twelve governing decisions of the Isolated Consequence-Chain Demo specification
(`.specs/planning/CORE-Isolated-Consequence-Chain-Demo.md` §3) as binding architectural
commitments for the replacement. They are recorded here so the isolation and orchestration
guarantees are governed, not merely described in a planning doc. The spec's Phase 0 required
this ADR to record "at minimum D1–D11"; this ADR records **all twelve (D1–D12)** — D12
(evidence rendered from the exact chain response) is a load-bearing honesty guarantee and
belongs under governance alongside the rest.

- **D1 — Explicit, opt-in.** Installation never executes the demo. `install-core.sh` finishes
  by *offering* `core-admin demo consequence-chain`. `scripts/demo.sh` becomes a compatibility
  wrapper with no scenario logic.
- **D2 — The invoking checkout is read-only.** No stage/commit/reset/restore/clean/checkout/
  write in the invoking repo; no `git worktree` registered against it; no hardlinked objects;
  no reading of uncommitted files into the clone; no writes to its `.intent/`, `var/`, DB, or
  runtime. The disposable repo is a local clone of committed `HEAD` with copied objects and its
  remote removed before the scenario runs.
- **D3 — Unique, validated run identity.** Each run gets an opaque `run_id`; all disposable
  filesystem resources live under `<CORE_DEMO_STATE_DIR>/runs/<run_id>/`, resolved by
  `shared.config.Settings` outside the invoking repo, never by shell expansion. Cleanup acts
  only under the marker-checked, escape-checked constraints in spec D3 — no wildcards, no
  unresolved env vars, no broad recursive targets.
- **D4 — Disposable, collision-free infrastructure.** Fresh PostgreSQL + Qdrant via a dedicated
  `infra/demo/compose.yaml`: project name derived from `run_id`, no fixed `container_name`,
  loopback-only, dynamic host ports, no pre-existing named volumes, tmpfs storage, schema from
  the canonical fresh-install SQL, health checks, `restart: "no"`, `core.demo.run_id` labels.
  The production Compose project / DB / Qdrant / API / daemon are never inspected, stopped,
  reconfigured, or reused.
- **D5 — Isolated process loads isolated configuration.** The clone gets its own `.env` pointing
  only at run-specific ports; LLM disabled. The scenario runs in a child Python process rooted
  in the clone (clone `src/` first on `PYTHONPATH`), because `shared.config.settings` is
  import-time initialized and cannot be safely re-rooted in-process. Process execution delegates
  to the existing `shared.utils.subprocess_utils` sanctuary; Git and clone cleanup to
  `GitService`; in-clone writes to `FileHandler` or an existing governed write surface. **No new
  direct `subprocess`/`os.system`/`Path.write_*`/`shutil.rmtree`/shell site outside an already
  governed sanctuary.**
- **D6 — The demo uses the real production chain.** It orchestrates existing components only —
  `AuditViolationSensor`, `ViolationRemediatorWorker`, the normal risk computation and proposal
  state manager, `POST /v1/proposals/{id}/execute` in-process via ASGI, the normal
  `ProposalExecutor`/`SandboxLifecycle`/action registry/`fix.ids`/finalization barrier/
  consequence service, and `GET /v1/proposals/{id}/chain` for evidence. **No demo-only audit,
  proposal, approval, execution, or evidence path. Direct SQL and "latest"-selection are
  prohibited.**
- **D7 — Seed committed only in the disposable clone**, with proof the seed path did not exist
  at baseline, only the seed changed in the seed commit, `.intent/` is byte-identical, the seed
  commit is unreachable from the invoking repo, and the clone has no remote.
- **D8 — Exact finding and proposal identity.** Exactly one active finding (rule
  `linkage.assign_ids`, run-specific seed path, in-run creation time, governed subject); the
  proposal is read from that finding's recorded linkage — never from ordering/timestamps/goal-
  text/"latest". Proposal must carry the exact finding ID, one `fix.ids` action scoped to the
  seed file, computed risk, and governed state. Zero/multiple/missing/mismatched fails.
- **D9 — Approval represented truthfully.** `fix.ids` is a safe action; the deterministic path
  auto-approves under `risk_classification.safe_auto_approval`. The demo displays *that*
  authority exactly and never claims human approval. The pre-execution `[y/N]` prompt is consent
  to continue the demonstration, not a proposal-approval event; `--simulate-confirmation` is a
  CI/cold-room flag that must be labeled as simulated and must not alter recorded approval
  identity or authority. A future human-approval scenario must use a genuinely human-gated
  action — never force `fix.ids` into a false risk class.
- **D10 — Every claim fails closed.** The 15 assertions of spec D10 (infra health; seed-only
  commit; exact finding; exactly-one linked proposal; risk/authority match; `completed`;
  durable consequence; consequence belongs to the exact proposal; non-null distinct pre/post
  SHAs; expected `files_changed`; finding resolved and still linked; clean re-audit; clone
  `.intent/` unchanged; invoking-repo HEAD/index/tracked/pre-existing-untracked bytes unchanged)
  must all hold or the command exits non-zero. Warnings never substitute for an assertion.
- **D11 — Cleanup is scoped and observable.** On success: remove only the `run_id`-labeled
  Compose project, its containers/network/storage, and the clone via the validated surface, then
  verify nothing `run_id`-labeled remains. On failure/interruption: infra cleanup still runs,
  the invoking repo stays untouched, a retained workspace prints its exact path marked retained,
  and `core-admin demo cleanup <run_id>` may remove it only after the D3 validations pass.
  Cleanup failure changes the verdict to failure and is never swallowed.
- **D12 — Evidence rendered from the exact chain response.** The summary shows the run/commit,
  finding, proposal (incl. risk, approval authority, approver identity), execution claimer and
  terminal status, pre/post SHA and changed files, resolved finding, re-audit result, cleanup
  result, and whether operator confirmation was human or simulated. `--output <path>` writes a
  Markdown+JSON report to an explicitly chosen destination only; without it, nothing is written
  into the invoking checkout. The report must state: *"This demonstration proves one isolated
  consequence chain. It is not a production-readiness attestation."*

### What this ADR explicitly does NOT authorize

- **It does not authorize CORE to write to `.intent/`.** The demo reads `.intent/` (and asserts
  it is byte-identical before/after in both the invoking repo and the clone) but never mutates
  it. No governed component gains an `.intent/` write surface from this work.
- It does not change the risk classification of `fix.ids`, or any action.
- It does not create an alternative execution or governance lane — D6 is binding.
- It does not license merge, deployment, production execution, or any readiness claim while the
  production-readiness assessment at `f7430b25` remains open (see Sequencing).

### Governor review and design-point resolutions (2026-07-23)

The governor approved this ADR subject to one sequencing correction (see Sequencing and
blockers, below) and resolved the three open design points the companion Phase 1 file/change
map (`CORE-Isolated-Consequence-Chain-Demo-Phase1-Map.md`) raised for review:

1. **Substrate home:** extend `GitService` and `subprocess_utils` with minimal, generic
   reusable primitives only. Do not introduce a `shared/infrastructure/demo/` module — the
   demo is a caller of shared infrastructure, not shared infrastructure itself.
2. **Compose driver placement:** `subprocess_utils` builds and executes raw `docker compose`
   commands; the lifecycle sequencing (up, health verification, failure handling, down,
   cleanup verification) belongs to `cli/logic/demo/isolation.py`, not to a new shared module.
3. **D4 schema source:** the disposable Postgres is initialized from the canonical root
   `schema.sql`, referenced through the same bootstrap mechanism `install-core.sh` uses — not a
   demo-specific copy, and not read from the invoking checkout at execution time.

These resolutions bind the Phase 1 file/change map; they are recorded here so the decisions
are governed, not left to implementation-time judgment.

## Sequencing and blockers (supersedes the spec's original Phase 0)

**Revision note (2026-07-23, same-day correction):** the first accepted version of this ADR
blocked all implementation — including Phase 1 in the isolated clone — until the
production-readiness soak closed. That was overbroad. The soak protects the running production
baseline; it does not require pausing development that stays fully isolated. This section
corrects the boundary; the superseded wording is preserved in commit `df0954bc`.

**What the soak protects, precisely:** `/opt/dev/CORE`, its running production services, the
production database, production configuration, and the soak's own evidence trail must remain
untouched and unrestarted until the soak closes on **2026-07-26 09:17:45 CEST** and the
governor records the final verdict. The soak does **not** require pausing development that
stays fully isolated — clones, worktrees, and disposable infrastructure with no connection to
production resources. The governing spec's Phase 0 predated the running assessment; its entry
conditions are corrected here — the corrected wording also lands in the copied spec in this
clone:

- **Phase 1 (isolation substrate — clone creation/cleanup, run identity + marker validation,
  disposable Compose project, child-process re-rooting, invoking-repo before/after fingerprint)
  may begin immediately, in `/opt/dev/CORE-demo-consequence-chain`.** All development uses
  isolated configuration and disposable Compose infrastructure with no connection to
  production resources; work is committed only in the isolated clone/branch
  (`feat/isolated-consequence-chain-demo`), never merged into or pushed against the invoking
  checkout.
- **The G6 risk-vocabulary defect may also be remediated and regression-tested in isolation**,
  under the same constraint — isolated clone/worktree, disposable infrastructure, no
  production contact.
- **Phase 2 (the genuine chain scenario) is gated on G6 remediation and regression evidence,
  not on the soak** — provided Phase 2 work remains completely isolated. If any Phase 2
  activity would need to touch production resources, the soak gate below applies to that
  activity specifically.
- **Regardless of isolation status, the following remain strictly prohibited until the soak
  closes and the final verdict is recorded:** merge into `/opt/dev/CORE` or any production
  checkout, deployment, production service restart, any material production configuration
  change, any action that could invalidate the soak's evidence trail, and any readiness claim.
- **This ADR is approved (see header) subject to the corrections in this revision.** Approval
  fixes the architecture now so implementation does not have to re-litigate it later; it does
  not license anything the paragraph above prohibits.

## Consequences

**Positive:** the on-ramp becomes trustworthy — isolated, exact, fail-closed, and honest about
its own limits; a developer can run it on a dirty checkout without risk; the demo stops
doubling as an implied readiness claim.

**Costs / risks:** new isolation machinery (validated clone, disposable Compose, child-process
re-rooting, marker-checked cleanup) is non-trivial and security-sensitive — the D10/D11
assertions and the spec §6 negative-claim tests are the mitigation, and the spec §10 reviewer
checklist gates acceptance. Docker/Compose becomes a demo prerequisite (documented per D12/§4).
The child-process re-root (D5) is the subtlest surface and gets first-class Phase-1 tests.

## Compliance notes

- Constitutional surfaces the implementation must honor (verified against the ruleset at
  `f7430b25`): all filesystem writes via `FileHandler` (`governance.mutation_surface.
  filehandler_required`); `subprocess`/shell only inside the designated sanctuary
  (`governance.dangerous_execution_primitives`, D5); no direct DB session import in API/Will
  layers; `.intent/` read-only (`architecture.constitution_read_only`, `governance.
  constitution.read_only`); every new public `def`/`class` carries a fresh `# ID:` UUID; new
  CLI commands use `@core_command` with `dangerous=True` on the mutating demo command.
- The demo command mutates a *disposable clone*, not the invoking repo — but it is still a
  mutating operator command and is classified `dangerous=True` accordingly, with the D9
  confirmation gate.
