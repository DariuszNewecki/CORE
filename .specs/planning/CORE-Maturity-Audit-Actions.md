---
kind: planning
title: CORE — Maturity-Audit Action List
status: draft
---

# CORE — Maturity-Audit Action List

**Status:** Working backlog (derived, non-authoritative)
**Location:** `.specs/planning/CORE-Maturity-Audit-Actions.md`
**Audience:** Internal — engineering sequencing input
**Created:** 2026-06-16
**Verification pass:** 2026-06-17 — every checkable item below was re-derived against the
working tree (`.github/workflows/`, repo root, `pyproject.toml`, `gh issue`). Each item
now carries its **verified state**, not the audit's read. Items that could not be checked
from the repo this pass are marked `❓ UNVERIFIED` rather than asserted.

**Source:** External artifact-based maturity audit (2026-06-16). The audit did **not** clone
the repo, run `install-core.sh`, run tests, or read CI logs / `.intent/` rules — it read
public GitHub artifacts only. It is a list of **leads**, and as the verification pass below
shows, several leads were already stale at the audit's own authoring date.

---

## 0. How to read this

This is a **derived** backlog. It does not govern sequencing. The authoritative operational
surface is [`CORE-Operational-Completeness.md`](CORE-Operational-Completeness.md) (ADR-085);
when an item here overlaps that tracker, **the tracker wins** and this doc just points at it.

Each item is tagged with its verified state as of the 2026-06-17 pass:

- ✅ **VERIFIED-REAL** — checked against the repo; the gap exists. Safe to action.
- ⚠️ **STALE / PARTIAL** — already shipped or partly shipped; the residual (if any) is
  narrower than the audit claimed. The real residual is stated inline.
- ❓ **UNVERIFIED** — not checkable from the repo this pass (e.g. needs the Proof Index, a
  runtime trial, or external infra). Confirm before spending effort.

The audit's composite "3.6 / 5" score is intentionally omitted — an unweighted average across
heterogeneous axes discards the only signal that matters (which axis is weak and why).

---

## 1. P1 — Adoption blocker

- [ ] ✅ **VERIFIED-REAL — Fix BYOR onboarding (#640).** `gh issue view 640` → **OPEN**;
  there is **no `starter_kits/` directory anywhere in the tree**. `project onboard` reads a
  missing `starter_kits/default/` path → fails at runtime. Ship a minimal valid `.intent/`
  scaffold so an external repo can be governed without hand-authoring the constitution. *The
  audit's single most load-bearing finding, and it holds. Restore + wire per ADR-075.*
- [ ] ❓ **UNVERIFIED — Fail-fast on a no-`.intent/` repo.** Auditing a repo with no
  constitution is reported to hang instead of erroring with guidance. Same root surface as
  #640. *Not reproduced this pass — confirm the hang before treating as separate work; it may
  resolve with the #640 scaffold.*

---

## 2. P2 — Proof → enforcement (highest leverage, in CORE's own idiom)

- [ ] ❓ **UNVERIFIED — Convert each Proof Index row into a CI-enforced regression check**
  where mechanizable. A proof claim with no standing check is exactly the rot pattern CORE
  exists to prevent (`feedback_closed_by_adr_not_evidence`). *Not audited row-by-row this
  pass — needs a walk of the Proof Index against the workflow set in §3.*
- [ ] ❓ **UNVERIFIED — For rows that cannot be mechanized yet, mark them attestation-only**
  so the gap is visible rather than implied-covered. Relates to `CORE-Instrument-Attestation`.

---

## 3. P3 — CI assurance (smoke → tiered)

> **Correction (2026-06-17):** the source audit, and the first draft of this list, asserted
> internal CI was "still smoke-only (`pytest -q`)." **That premise was already false at
> authoring time.** The repo carries **6 workflows** under `.github/workflows/`. The accurate
> inventory:
>
> | Workflow | What it actually runs | Trigger |
> |---|---|---|
> | `ci.yml` | `pytest -q` (the smoke job the audit saw) | push `main`, all PRs |
> | `core-ci.yml` | README count-drift (#631) · `core-admin intent sync vocabulary --check` · **blocking** `core-admin check lint` · `pytest --cov --cov-fail-under=45` · Codecov · PR intent linter | push `main`/`develop`, PRs |
> | `daily_sync.yml` | `core-admin code audit --offline --severity=block` | **cron `0 8 * * *`** + `workflow_dispatch` |
> | `publish-pypi.yml` | tag/version guard · `poetry build` · PyPI OIDC publish | tag push |
> | `publish-docker-core-engine.yml` | docker build + publish | tag push |
> | `docs.yml` | docs build | — |
>
> The **F-10 external CI/CD gate** (the `action.yml` GitHub Action running
> `core-admin code audit --offline` with merge-blocking annotations against *consumer* repos)
> shipped 2026-06-02 and is a distinct surface — do not conflate it with internal CI below.

- [x] ⚠️ **STALE — "Add a full test tier beyond `pytest -q`."** Already shipped:
  `core-ci.yml` runs coverage-gated `pytest --cov --cov-fail-under=45` alongside the `ci.yml`
  smoke job. **Residual:** decide whether "full" should mean a separate *integration* tier
  (DB-backed) beyond the current coverage run — that is a scoping question, not a missing gate.
- [x] ⚠️ **PARTIAL — "Add an offline constitutional audit job."** Already exists in
  `daily_sync.yml` — but it is **cron-only (08:00 daily), not a PR/merge gate**. **Residual:**
  promote the offline audit to a per-PR gate if regressions between daily runs are
  unacceptable; otherwise mark the daily cadence as the deliberate posture.
- [ ] ✅ **VERIFIED-REAL — Add package build + `pip install` smoke test.** `publish-pypi.yml`
  runs `poetry build` and `ls -la dist/`, then publishes — there is **no install-and-import
  smoke step** on the built wheel. The published-wheel-vs-source drift class
  (`feedback_verify_cli_against_published_wheel`) is still ungated.
- [ ] ✅ **VERIFIED-REAL — Add a GitHub Action self-test.** `action.yml` exists at the repo
  root, but **no workflow invokes it** (`grep 'uses: ./'` over `.github/workflows/` → none).
  The Action is published but never exercised against CORE itself.
- [ ] ✅ **VERIFIED-REAL — Add a containerized demo / `install-core.sh` dry-run test.**
  `install-core.sh` exists (9.2 KB, Jun 14) but **no CI workflow runs it.**
  ⚠️ Demo *reliability* (#562) was closed met 2026-06-14 via the Proxmox cold-room
  (4 clean / 0 fail) — that was a **manual** proof. The open item is the *CI-automated*
  version of that cold-room run, not a re-do of the manual proof.
- [ ] ✅ **VERIFIED-REAL — Wire Bandit + pip-audit into CI.** Both are declared in
  `pyproject.toml` (`pip-audit ^2.10.0`, `bandit ^1.9.2`) but appear in **zero workflows**.
  They already exist as advisory constitutional rules (`quality.security_audit`); this is
  strictly about the *CI* surface.
- [x] ⚠️ **REFRAME (holds) — coverage `--cov-fail-under=45`.** The audit read this as a "low
  quality bar." It is enforced at 45 in `core-ci.yml` (not merely opt-in) and is best read as
  a deliberate ramp (`feedback_ramp_arc_three_phase_pattern`,
  `user_prefers_visibility_over_polish`). Action is **document the ratchet plan**, not "raise
  the number now."
- [x] ⚠️ **STALE — "Non-zero-exit lint tier."** Already present: `core-ci.yml` runs
  **blocking** `core-admin check lint`. Only the *pre-commit* hook is `ruff --fix --exit-zero`
  (ergonomics, by design). No residual at the CI level.

---

## 4. P4 — Security governance

- [ ] ✅ **VERIFIED-REAL — Add `SECURITY.md`.** Confirmed **absent** at repo root. Should
  cover: supported versions, vulnerability-reporting process, disclosure contact,
  secret-handling expectations, production-hardening warning, known security boundaries.
- [ ] ❓ **UNVERIFIED — Mark demo credentials dev-only.** Docker/Postgres demo creds +
  default-port Qdrant reportedly need an explicit "development only" boundary and a production
  profile. *Not traced to specific files this pass — confirm against the compose/demo assets.*
- [x] ⚠️ **REFRAME (holds) — security posture vs document surface.** The audit scored security
  2.5 largely on *doc absence*. For a system whose substance is enforcement / provenance /
  audit-chain, the constitution itself is a security control surface the artifact method can't
  see. Action is a one-page **"where security enforcement actually lives"** legibility doc
  (`feedback_external_review_false_positive_is_legibility_map`), not assuming the posture is
  weak. *Pairs with the `SECURITY.md` above — one is the disclosure process, this is the map.*

---

## 5. P5 — Release / interface stability

- [x] ⚠️ **STALE — public API boundary.** The audit calls this "pending," but **F-48.4
  (public-vs-internal API) shipped 2026-06-02** and **F-40 / ADR-087** authored the OEM API
  stability policy with a published OpenAPI contract — verified at
  `.specs/contracts/oem_api_v1.openapi.json` (the audit/earlier draft mis-cited the path as
  `contracts/…`). The boundary itself is **not** open. **Residual:** promotion criteria from
  Beta → stable. See [`CORE-Semver-Policy.md`](CORE-Semver-Policy.md).
- [ ] ❓ **UNVERIFIED — Keep PyPI status honest (Beta)** until any remaining promotion criteria
  land. *Current PyPI classifier not checked this pass.*

---

## 6. P6 — Operational completeness

- [ ] ❓ **UNVERIFIED — Define a production deployment profile.** Audited artifacts show
  local-runtime only. *Check this isn't already covered under the ADR-085 operational tracker
  before opening new work.*
- [ ] ❓ **UNVERIFIED — Document production secret-management** beyond `.env.example`.

---

## 7. What this list is NOT

- It is **not** a re-scoping of ADR-085's 5+3 list. New items here that warrant engineering
  capacity under the active constraint must route through the operational-completeness tracker
  / governance, not this doc.
- It is **not** uniformly confirmed debt. The 2026-06-17 pass verified the items it could; the
  rest are tagged ❓ **UNVERIFIED** and must be confirmed before action.
- It is a standing reminder that **external artifact audits go stale at their own authoring
  date** — the P3 "smoke-only CI" premise was already false when the audit was written. Re-derive
  before trusting (`feedback_closed_by_adr_not_evidence`, `feedback_count_from_source_not_narrative`).

---

## 9. 2026-06-30 External Review — governance enforcement maturity

Second external review (blind, description-only). Items below are the **strategic / long-horizon** findings; discrete actionable items were filed as GH issues (#722–#727). Items here are either too large for a single issue or require a governance decision before scoping.

- [ ] ✅ **VERIFIED-REAL — Shared layer periodic audit cadence (finding 1b).** `src/shared/`
  has no active audit cadence to detect upward dependencies or workflow assumptions leaking
  in. The `architecture.shared.no_layer_imports` blocking rule catches explicit imports, but
  conceptual coupling (shared encoding Body/Will assumptions without importing them) is not
  detected. **Action:** establish a quarterly "shared independence audit" motion — walk every
  `src/shared/` module for workflow-specific assumptions and split anything that doesn't
  belong. No GH issue yet; needs a governance framing first.

- [ ] ✅ **VERIFIED-REAL — Will fan-in/fan-out metrics (finding 1c).** No tooling tracks
  how many Body services Will imports per worker. If Will begins depending heavily on Body
  internals (rather than using the blackboard/service layer), it becomes a god layer.
  **Action:** add a `will_fan_in` metric to the dashboard or a periodic `import-count` check
  in CI that alerts when any Will worker exceeds N direct Body imports. Filed as planning
  input; not yet a concrete issue.

- [ ] ✅ **VERIFIED-REAL — Intent read access logging (finding 2c).** `IntentRepository`
  does not log reads. The `architecture.namespace.no_direct_protected_access` reporting rule
  catches raw `Path` access at audit time, but shadow access via undiscovered code paths is
  undetected at runtime. **Action:** add `logger.debug` on every `IntentRepository.load_*`
  call — cost is negligible; gain is a runtime tap for shadow-access detection.
  Small — could be a one-liner change, but the value is in the *operational visibility*
  story, so it warrants a brief ADR note when implemented.

- [ ] ✅ **VERIFIED-REAL — ADR invariant tests for key ADR clauses (findings 3a/3b).** Some
  ADRs have dedicated tests (`test_role_enforcement.py` for ADR-132, atomic-action tests for
  ADR-021/ADR-101). Most do not. No framework exists for "given this ADR clause, here is the
  test that asserts the invariant." **Action:** as part of the next governance maturity cycle,
  require a `tests/adrs/test_ADR_NNN_DN.py` alongside each multi-phase ADR D-step that can
  be mechanically tested. Start with the highest-risk ADRs (ADR-104 liveness, ADR-129
  GitService, ADR-132 auth boundary). Relates to #726 (ADR phase tracking).

- [ ] ❓ **UNVERIFIED — Perf / cost / observability SLA governance (finding 9a).** The
  reviewer correctly identified three missing risk categories: (1) no latency governance
  (no constitutional rule on AI call duration or API response time); (2) no AI cost budget
  (LLM spend is unmonitored at the governance layer); (3) no SLA on what must be logged /
  retained. #413 [F-39] covers SLA support at the product level but does not address the
  constitutional framing. **Action:** confirm whether these belong as `.intent/` rules
  (e.g. `governance.cost.llm_budget_required`) or as operational ADRs. Scope decision
  needed before filing an issue.

---

## 8. References

- [`CORE-Operational-Completeness.md`](CORE-Operational-Completeness.md) — authoritative
  ADR-085 tracker (overlapping items defer to it)
- [`CORE-Semver-Policy.md`](CORE-Semver-Policy.md) — release / version policy
- ADR-085 — operational-completeness constraint
- ADR-087 — OEM API stability policy
- #640 — BYOR onboarding defect (P1, verified OPEN 2026-06-17)
