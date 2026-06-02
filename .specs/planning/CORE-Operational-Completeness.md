# CORE — Open Operational Completeness Tracker

**Status:** Authoritative (operational surface for ADR-085)
**Location:** `.specs/planning/CORE-Operational-Completeness.md`
**Audience:** Internal — engineering sequencing, session-protocol "what to pick next"
**Last updated:** 2026-06-02 (ADR-085 lock-in)

---

## 1. Purpose

ADR-085 codifies the constraint: engineering capacity routes only to the five-feature + three-quality-goal list below until all eight are satisfied, then the constraint relaxes via an explicit governance act. This document is the tracker — it carries per-item status, what "done" looks like, and the current best estimate of sequencing.

**This is the operational surface. The constitutional surface is ADR-085.** When this document disagrees with ADR-085, ADR-085 wins. When this document needs amendment (refined criteria, new sub-items, sequencing change), it can be updated freely; an ADR amendment is required only if the intent or scope of the 5+3 list itself changes.

**Session-protocol use:** while the ADR-085 constraint is active, the canonical "what to pick next" filter is:

```bash
gh issue list --label goal:operational-completeness --state open
```

That returns exactly the seven gate issues (F-10 #384, F-27 #401, F-40 #414, F-41 #415, F-42 #416, F-43 #417, F-48 #527). The three quality goals are tracked here, not in the issue tracker.

---

## 2. The 5+3 list

### 2.1 Five feature commitments

| Item | F-ID | Issue | Current status | "Done" looks like | Notes |
|---|---|---|---|---|---|
| CI/CD gate | F-10 | [#384](https://github.com/DariuszNewecki/CORE/issues/384) | roadmap | `status: shipping`; PR annotations + merge-blocking demonstrated against a real external repo | Top of the adoption funnel (Tiers paper §2). **Decomposed 2026-06-02 into 5 MVP sub-issues + 1 deferred** (see §2.3 below). The audit engine itself already runs (`.github/workflows/nightly-audit.yml`); F-10's gap is packaging + distribution + output formatting + external-repo verification. F-10 ships when F-10.4 closes. |
| Local LLM | F-27 | [#401](https://github.com/DariuszNewecki/CORE/issues/401) | **partial** | promotes from `partial` to `shipping`; reliable local-LLM-only Solo run for ≥7 days | Smallest finishing touch in the list. Building on existing infrastructure. |
| OEM API surface | F-40 | [#414](https://github.com/DariuszNewecki/CORE/issues/414) | roadmap | `status: shipping`; documented public contract; sidecar-shape commercial features F-20/F-34/F-45/F-47 can attach without private hooks (ADR-084 D6) | Largest unblocker — releases four commercial sidecars at once. Per ADR-084, interface symmetry means the API surface must be documented as the contract third-parties consume, not just an internal API. |
| Extension interfaces | F-41 + F-42 + F-43 | [#415](https://github.com/DariuszNewecki/CORE/issues/415) [#416](https://github.com/DariuszNewecki/CORE/issues/416) [#417](https://github.com/DariuszNewecki/CORE/issues/417) | all roadmap | all three `status: shipping`; one first-party non-code instantiation exists as proof of the plugin-interface contract | F-41 ships first (F-42 and F-43 depend on it). F-42 + F-43 can land in parallel. The "one non-code instantiation" criterion exists to prove the plugin-interface contract is real, not aspirational. |
| Open library distribution | F-48 | [#527](https://github.com/DariuszNewecki/CORE/issues/527) | roadmap | `status: shipping`; `pip install core-runtime` works; semver tags; CI publishes on tag | Filed 2026-06-02 to close ADR-084 D4 planning gap. No hard blockers; public-vs-internal API distinction is part of its scope. Constitutionally load-bearing per ADR-084 D7 §4. |

### 2.2 Three quality goals

| Item | Type | "Done" looks like | Verification path | Current state |
|---|---|---|---|---|
| Docs polish | system property | An outside developer installs + runs the full thesis (encounter → audit → remediate → verify) from public docs alone, without source-tree archaeology | Recruit a developer who has never seen the project; observe their setup attempt; record gaps; close them; repeat | Not started; not measured. Baseline observation pending. |
| Demo reliability | system property | The consequence-chain bootstrap demo (Tiers §3.2) runs cleanly on first attempt, three times in a row, from a clean repo clone on a freshly-provisioned machine | Scripted: provision VM → clone → run demo → record outcome. Repeat from clean VM until three consecutive clean runs. | Not started; not measured. |
| Signal quality | derived metric | F-19 convergence metric reports resolution rate ≥ creation rate, sustained ≥ 30 days, on this repo | (1) Verify F-19 query produces honest data; (2) start measurement window; (3) sustain for 30 days; (4) record met-date | F-19 query not yet verified honest. Per ADR-085 §Consequences, this verification is in scope for engineering capacity under D1 because it advances signal-quality. |

---

### 2.3 F-10 sub-task decomposition (added 2026-06-02; revised same day after recon)

F-10 is the only feature in the 5+3 list that was decomposed at gate
authoring time. The decomposition is operational (lives in this doc and
in GH parent/sub-issue relations), not constitutional (no ADR required).
Other gate items can be similarly decomposed in-session when scoping
makes them concrete.

**Recon-driven revision (2026-06-02):** F-10.1's original "1 session"
estimate undercounted. Reconnaissance showed there is no standalone
audit invocation today — `core-admin code audit` requires core-api +
DB, and the in-repo `nightly-audit.yml` workflow calls a phantom
`src.core.capabilities` module (bug tracked as #534). F-10.1 is
therefore split into 1a (runner refactor) and 1b (CLI surface). The
architectural decision behind 1a — stateless mode covers the rule
subset that doesn't need the knowledge graph; graph-dependent rules
skip with structured reason — is recorded in #528's body as
"Architectural Option A."

| Sub | Issue | Sized | Blocks | Purpose |
|---|---|---|---|---|
| F-10.1a | [#528](https://github.com/DariuszNewecki/CORE/issues/528) | 1-2 sessions | F-10.1b | Stateless audit runner — DB-free path; graceful skip for graph-rules |
| F-10.1b | [#535](https://github.com/DariuszNewecki/CORE/issues/535) | ~1 session | F-10.2, F-10.3, F-10.5, F-10.P2 | CLI surface: `--offline`, `--json`, exit codes, `--severity` |
| F-10.2 | [#529](https://github.com/DariuszNewecki/CORE/issues/529) | ~1 session | F-10.3, F-10.4 | `--format=github-annotations` output |
| F-10.3 | [#530](https://github.com/DariuszNewecki/CORE/issues/530) | 1–2 sessions | F-10.4, F-10.P2 | `action.yml` + `Dockerfile` + Marketplace prep |
| F-10.4 | [#531](https://github.com/DariuszNewecki/CORE/issues/531) | ~1 session | F-10 status flip → shipping | External-repo end-to-end verification — **closes F-10** |
| F-10.5 | [#532](https://github.com/DariuszNewecki/CORE/issues/532) | ~½ session | — | `.pre-commit-hooks.yaml` distribution (nearly-free bonus) |
| F-10.P2 | [#533](https://github.com/DariuszNewecki/CORE/issues/533) | deferred | — | GitLab CI step + CodeClimate format. Out of MVP; lands after F-10 ships. |

**Total MVP path:** ~6 sessions of focused work (revised up from ~5
after the F-10.1 split).

**Picking order for sessions:** F-10.1a first (foundation; everything
else depends on it through F-10.1b). Then F-10.1b. Then F-10.2 + F-10.3
in parallel. F-10.5 anytime after F-10.1b. F-10.4 is last among MVP
because it's the verification that fires only when F-10.2 + F-10.3 are
both ready.

All seven sub-issues carry the `goal:operational-completeness` label and
are parented to #384 via GH's native sub-issue relation. The default
`gh issue list --label goal:operational-completeness --state open`
query now returns 14 items (7 gates + 7 F-10 sub-tasks). For a F-10-
only view: `gh issue list --search "is:open is:issue parent:384"`.

**Tracked separately (not in F-10 scope):** #534 — `.github/workflows/
nightly-audit.yml` calls `python -m src.core.capabilities`, a module that
no longer exists. Workflow has been silently shipping a non-functional
gate. Fix or remove as a one-shot, separate from F-10.

---

## 3. Sequencing (operational, updateable)

Per ADR-085 D6, this ADR does not prescribe ordering inside the list, but the dependency graph constrains it. Current best estimate:

**Tier-1 (any can ship next, choose by engineering velocity):**
- **F-10** CI/CD gate — top of adoption funnel; visible-impact win
- **F-40** OEM API surface — largest downstream-unblocker (releases 4 commercial sidecars)
- **F-48** Open library distribution — closes the ADR-084 D4 constitutional gap; smallest engineering surface among Tier-1

**Tier-2 (F-41 first, then F-42 + F-43 in parallel):**
- **F-41** Artifact type registry — prerequisite for F-42 + F-43
- **F-42** Pluggable sensor model — after F-41
- **F-43** Pluggable action model — after F-41; can run alongside F-42

**Tier-3 (finishing touches, advanced alongside Tier-1/Tier-2 work):**
- **F-27** Local LLM promotion (partial → shipping)
- **Docs polish** — work continues with every feature
- **Demo reliability** — verification work after each Tier-1 ship
- **Signal quality** — F-19 query verification then sustained-window measurement

This ordering is the current best estimate and lives in this doc. Updating it is operational, not constitutional — change without an ADR amendment.

---

## 4. Updating this tracker

When a feature ships:

1. Update the Current Status column in §2.1 from `roadmap` (or `partial`) to `shipping`.
2. Mark the corresponding row in §3 as complete.
3. Update `CORE-Features.md` §3 entry's Status to `shipping` (the registry stays authoritative for that field).
4. Add a brief note in §6 (Activity Log) with the ship date and any consequence-chain evidence.

When a quality criterion is met:

1. Update the Current State column in §2.2 with the first-met date.
2. For criteria with a sustained-window requirement (signal quality), update again when the sustained window completes.
3. Add a §6 entry.

When all eight items show satisfied state:

1. The constraint in ADR-085 D1 has not yet relaxed — relaxation requires an explicit governance act per D5.
2. Surface this to the governor with a one-line PR or session note: "All ADR-085 exit criteria met as of YYYY-MM-DD; constraint relaxation requires governor confirmation."
3. The governor authors a follow-on ADR or amends ADR-085 to declare the constraint relaxed.

---

## 5. What this tracker is NOT

- **Not a kanban board.** Project #6 "CORE Roadmap" is the kanban surface. This doc carries the strategic gate, not the per-sprint workflow.
- **Not the feature definition.** `CORE-Features.md` is authoritative for what each feature is and what its status is. This doc references status from the registry; it does not own it.
- **Not the commercial roadmap.** ADR-085 explicitly defers commercial engineering work until exit criteria are met. The commercial roadmap continues to exist in stamped form (ADR-083 + ADR-084) but does not consume engineering capacity. This doc does not track commercial features at all.
- **Not policy on what to build after exit.** Once the constraint relaxes, the post-exit roadmap is governed by the planning state at that time (likely starting with F-44 per ADR-083 + ADR-084 first-SKU arguments, but that is the future governor's decision).

---

## 6. Activity log

| Date | Event |
|---|---|
| 2026-06-02 | ADR-085 accepted; constraint active; tracker created. Seven gate issues labeled `goal:operational-completeness`. F-27 starts at `partial`; all others at `roadmap`. All three quality goals at "not started." |
| 2026-06-02 | F-10 decomposed into 5 MVP sub-issues + 1 deferred (#528–#533). Parented to #384; all labeled `goal:operational-completeness`; 8 internal blocked-by edges wired; added to Project #6. F-10's body updated to point at the decomposition; tracker §2.3 added. MVP picking order: F-10.1 first, then F-10.2 + F-10.3 + F-10.5 in parallel, F-10.4 last. |
| 2026-06-02 | F-10.1 reconnaissance discovered no standalone audit path exists today; `core-admin code audit` requires core-api + DB; `nightly-audit.yml` calls a phantom module. F-10.1 split into 1a (#528 runner refactor, Option A — graph-rule skip) and 1b (#535 CLI surface). 5 new dep edges wired; downstream sub-tasks now depend on 1b instead of original 1. Tracker §2.3 revised; F-10 #384 body updated. Surfaced bug #534 filed separately for the broken nightly workflow. MVP estimate revised: ~5 sessions → ~6 sessions. |

---

## 7. References

- ADR-085 — constitutional anchor for the constraint this doc operationalises
- ADR-084 D7 §1 — completeness as honesty commitment (the constitutional grounding)
- `papers/CORE-Features.md` §3 — authoritative status for the five feature items
- `planning/CORE-Feature-Dependency-Graph.md` — picture-form of the sequencing constraints
- `planning/SESSION-PROTOCOL.md` — should reference this doc as canonical "what to pick next" filter while constraint is active
- Memory `feedback_hardening_over_coverage` — the project preference that maps onto this ADR's discipline
