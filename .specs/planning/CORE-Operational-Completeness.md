# CORE — Open Operational Completeness Tracker

**Status:** Authoritative (operational surface for ADR-085)
**Location:** `.specs/planning/CORE-Operational-Completeness.md`
**Audience:** Internal — engineering sequencing, session-protocol "what to pick next"
**Last updated:** 2026-06-02 (F-10 ships; F-48 ships; both flipped to `status: shipping` after F-10.4 external-repo verification against demo PR #1 via core-runtime 0.1.4)

---

## 1. Purpose

ADR-085 codifies the constraint: engineering capacity routes only to the five-feature + three-quality-goal list below until all eight are satisfied, then the constraint relaxes via an explicit governance act. This document is the tracker — it carries per-item status, what "done" looks like, and the current best estimate of sequencing.

**This is the operational surface. The constitutional surface is ADR-085.** When this document disagrees with ADR-085, ADR-085 wins. When this document needs amendment (refined criteria, new sub-items, sequencing change), it can be updated freely; an ADR amendment is required only if the intent or scope of the 5+3 list itself changes.

**Session-protocol use:** while the ADR-085 constraint is active, the canonical "what to pick next" filter is:

```bash
gh issue list --label goal:operational-completeness --state open
```

That returns the remaining gate issues. F-10 #384 and F-48 #527 closed 2026-06-02; the open set is now F-27 #401, F-40 #414, F-41 #415, F-42 #416, F-43 #417 (five issues, three commitments after the F-41/F-42/F-43 trio grouping). The three quality goals are tracked here, not in the issue tracker.

---

## 2. The 5+3 list

### 2.1 Five feature commitments

| Item | F-ID | Issue | Current status | "Done" looks like | Notes |
|---|---|---|---|---|---|
| CI/CD gate | F-10 | [#384](https://github.com/DariuszNewecki/CORE/issues/384) | **shipping** ✅ | `status: shipping`; PR annotations + merge-blocking demonstrated against a real external repo ✅ | Top of the adoption funnel (Tiers paper §2). **Shipped 2026-06-02.** F-10.1a/1b/2/3 landed earlier same day (`d2bf1639`, `0396abbe`, `2513dac9`, `dfe2cad2`); F-10.4 verified via core-runtime 0.1.4 (`73c75f31` + `8e3c7dcb`) against demo PR #1 (https://github.com/DariuszNewecki/core-audit-demo/pull/1) — GitHub check-runs API returned 18 inline annotations with structured `path` field; workflow exit 1 confirms merge-blocking surface. F-10.5 (pre-commit-hooks distribution) remains open as a bonus delivery channel, not part of the gate criterion. F-10.P2 (GitLab + CodeClimate) deferred. The in-repo `.github/workflows/nightly-audit.yml` removed in `a8a232ef` per #534; reinstatement against the F-10.3 Action per ADR-086 is follow-on work. |
| Local LLM | F-27 | [#401](https://github.com/DariuszNewecki/CORE/issues/401) | **partial** | promotes from `partial` to `shipping`; reliable local-LLM-only Solo run for ≥7 days | Smallest finishing touch in the list. Building on existing infrastructure. |
| OEM API surface | F-40 | [#414](https://github.com/DariuszNewecki/CORE/issues/414) | roadmap | `status: shipping`; documented public contract; sidecar-shape commercial features F-20/F-34/F-45/F-47 can attach without private hooks (ADR-084 D6) | Largest unblocker — releases **three** commercial sidecars (F-20, F-34, F-45 read-side). F-47 dropped from F-40 dependents during 2026-06-02 recon — it's managed Qdrant infrastructure, not a FastAPI consumer; the ADR-084 D8 bucket list correction lands as part of F-40.4. **Decomposed 2026-06-02 into 4 MVP sub-issues + 2 post-exit** (see §2.5). MVP path: F-40.1 (classify) → F-40.2 (versioning ADR) → F-40.3 (OpenAPI spec) → F-40.4 (sidecar attach verification). ~4-5 sessions. Phase B (auth, host binding, rate limiting — #554/#555) post-exit. |
| Extension interfaces | F-41 + F-42 + F-43 | [#415](https://github.com/DariuszNewecki/CORE/issues/415) [#416](https://github.com/DariuszNewecki/CORE/issues/416) [#417](https://github.com/DariuszNewecki/CORE/issues/417) | all roadmap | all three `status: shipping`; one first-party non-code instantiation exists as proof of the plugin-interface contract | F-41 ships first (F-42 and F-43 depend on it). F-42 + F-43 can land in parallel. The "one non-code instantiation" criterion exists to prove the plugin-interface contract is real, not aspirational. |
| Open library distribution | F-48 | [#527](https://github.com/DariuszNewecki/CORE/issues/527) | **shipping** ✅ | `status: shipping`; `pip install core-runtime` works; semver tags; CI publishes on tag ✅ | **Shipped 2026-06-02.** F-48.1 (#537) renamed the distribution to `core-runtime` + PyPI metadata; F-48.2 (#538) shipped the Trusted-Publisher OIDC release workflow. Five semver tags published (v0.1.0–v0.1.4); 0.1.3 and 0.1.4 CI-published cleanly during this session as part of the #545/#546 F-10 unblock chain. F-48.3 (Docker/GHCR), F-48.4 (public-vs-internal API), F-48.5 (semver policy doc) remain open as post-exit / v1.0.0-milestone scope per §2.4. Constitutionally load-bearing per ADR-084 D7 §4. |

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

| Sub | Issue | Sized | Status | Purpose |
|---|---|---|---|---|
| F-10.1a | [#528](https://github.com/DariuszNewecki/CORE/issues/528) | 1-2 sessions | ✅ shipped `d2bf1639` | Stateless audit runner — DB-free path; graceful skip for graph-rules |
| F-10.1b | [#535](https://github.com/DariuszNewecki/CORE/issues/535) | ~1 session | ✅ shipped `0396abbe` | CLI surface: `--offline`, `--json`, exit codes, `--severity` |
| F-10.2 | [#529](https://github.com/DariuszNewecki/CORE/issues/529) | ~1 session | ✅ shipped `2513dac9` | `--format=github-annotations` output |
| F-10.3 | [#530](https://github.com/DariuszNewecki/CORE/issues/530) | 1–2 sessions | ✅ shipped `dfe2cad2` | `action.yml` + `Dockerfile` + Marketplace prep |
| F-10.4 | [#531](https://github.com/DariuszNewecki/CORE/issues/531) | ~1 session | ✅ shipped core-runtime 0.1.4 (`73c75f31` + `8e3c7dcb`) | External-repo end-to-end verification — **closed F-10** |
| F-10.5 | [#532](https://github.com/DariuszNewecki/CORE/issues/532) | ~½ session | open (post-ship bonus) | `.pre-commit-hooks.yaml` distribution (additional delivery channel) |
| F-10.P2 | [#533](https://github.com/DariuszNewecki/CORE/issues/533) | deferred | — | GitLab CI step + CodeClimate format. Out of MVP; lands when prioritised. |

**Historical sequencing record (2026-06-02 post-ADR-086):** F-48.1 →
F-48.2 (PyPI publish) → F-10.3 → #544 (offline-audit hardening) →
#545 (engine-side cwd-walk) → #546 (annotation-formatter key fix) →
F-10.4 verification. Total in-session: 5 commits + 2 PyPI releases
(0.1.3, 0.1.4). The originally projected ~6-session MVP path
compressed into a single session once recon resolved the open
ambiguities (the half-built CheckResult-contract assumption in #546
collapsed when the actual `AuditFinding.as_dict()` payload was
inspected — see #546's comment trail).

All seven F-10 sub-issues are parented to #384 via GH's native sub-issue
relation. The default `gh issue list --label goal:operational-completeness
--state open` query now returns the open gate set plus open F-10 and
F-48 sub-issues. For a F-10-only view: `gh issue list --search "is:open
is:issue parent:384"`. For F-48: replace `384` with `527`.

**Tracked separately (not in F-10 scope):** #534 — `.github/workflows/
nightly-audit.yml` called `python -m src.core.capabilities`, a module
that no longer exists; workflow had been silently shipping a
non-functional gate. **Closed 2026-06-02 via `a8a232ef` (Option 1:
remove).** Replacement target is the F-10.3 GitHub Action running
against this repo per ADR-086.

---

### 2.4 F-48 sub-task decomposition (added 2026-06-02)

F-48 was decomposed during F-10.3 reconnaissance. ADR-086 D1+D7 (accepted
same day as F-10's decomposition) introduced a dependency F-10.3's
original scope did not anticipate: the Audit-tier Dockerfile pulls
`core-runtime:X.Y.Z` from PyPI. That made F-48 (PyPI publish) a
prerequisite for F-10.3, which prompted the decomposition + Tier-1
re-sequencing (see §3).

Decomposition is operational (this doc + GH parent/sub-issue relations),
not constitutional — mirrors the §2.3 F-10 pattern.

| Sub | Issue | Sized | Blocks | Purpose |
|---|---|---|---|---|
| F-48.1 | [#537](https://github.com/DariuszNewecki/CORE/issues/537) | ~1 session | F-48.2, F-48.3, F-48.4, F-48.5 | ✅ shipped — distribution renamed `core` → `core-runtime`; PyPI metadata; first publish `v0.1.0` |
| F-48.2 | [#538](https://github.com/DariuszNewecki/CORE/issues/538) | ~1 session | **F-10.3 #530** | ✅ shipped — PyPI release workflow via Trusted Publisher (OIDC); five tags published (v0.1.0–v0.1.4) |
| F-48.3 | [#539](https://github.com/DariuszNewecki/CORE/issues/539) | ~1 session | Solo install (post-exit) | open — Docker `core-engine` image + GHCR release workflow |
| F-48.4 | [#540](https://github.com/DariuszNewecki/CORE/issues/540) | 1–2 sessions | F-31/32/33/35/36 commercial sidecars; `v1.0.0` | open — Public-vs-internal API distinction (`__all__` declarations) |
| F-48.5 | [#541](https://github.com/DariuszNewecki/CORE/issues/541) | ~½ session | `v1.0.0` | open — Semver policy doc per ADR-086 D7 |

**F-48 exit criterion satisfied 2026-06-02** via F-48.1 + F-48.2. Per
ADR-085's 5+3 row for F-48 (`pip install` works; semver tags; CI
publishes on tag), the MVP criterion is met. F-48.3/4/5 remain
post-exit / v1.0.0-milestone scope — they are not gating and were
never on the MVP path. F-48.3's Docker image is the next pickup if a
Solo-tier install path is needed; F-48.4 + F-48.5 are gated to v1.0.0.

All five sub-issues carry `goal:operational-completeness` and are
parented to #527 via GH's native sub-issue relation. F-10.3 #530's
blocked-by set was extended with F-48.2 #538 the same day.

---

### 2.5 F-40 sub-task decomposition (added 2026-06-02 after recon)

F-40 was decomposed once F-10 + F-48 closed and engineering capacity routed to the next 5+3 item. The recon surfaced that **F-40's substance is mostly declaration + contracting**, not new endpoint development — ~30 of the ~74 endpoints under `src/api/v1/` already cover what sidecars need. The four "mixed" routers (`/coverage`, `/quality`, `/lint`, `/refactor`) need per-route classification; the cross-cutting work (versioning policy, OpenAPI spec, sidecar verification) closes the gap.

Decomposition is operational (this doc + GH parent/sub-issue relations), not constitutional — mirrors the §2.3 / §2.4 patterns.

Two phases: Phase A satisfies ADR-085's literal exit criterion (sidecar attachability over localhost — what's required to ship F-40); Phase B is the fuller third-party OEM consumption story (auth, host binding, rate limiting). Phase A gates F-40 closure; Phase B is explicitly post-exit and does NOT block the status flip.

**Phase A — Sidecar attachability (MVP path, gates F-40 ship)**

| Sub | Issue | Sized | Blocks | Purpose |
|---|---|---|---|---|
| F-40.1 | [#550](https://github.com/DariuszNewecki/CORE/issues/550) | ~1 session | F-40.2, F-40.3, F-40.4 | Public-vs-internal route classification |
| F-40.2 | [#551](https://github.com/DariuszNewecki/CORE/issues/551) | ~1 session | F-40.3, F-40.4 | Versioning + stability policy ADR for `/v1/` |
| F-40.3 | [#552](https://github.com/DariuszNewecki/CORE/issues/552) | ~1–2 sessions | F-40.4 | OpenAPI spec + per-route annotation pass |
| F-40.4 | [#553](https://github.com/DariuszNewecki/CORE/issues/553) | ~1 session | **F-40 #414 ship** | Sidecar attachment verification — closes F-40 |

**Phase B — Third-party OEM consumption (post-exit; does NOT gate)**

| Sub | Issue | Sized | Blocks | Purpose |
|---|---|---|---|---|
| F-40.5 | [#554](https://github.com/DariuszNewecki/CORE/issues/554) | ~2 sessions | F-40.6 | Authentication + authorization scheme |
| F-40.6 | [#555](https://github.com/DariuszNewecki/CORE/issues/555) | ~1–2 sessions | — | Host binding + rate limiting + OpenAPI publication |

**MVP path to F-40 ship**: F-40.1 → F-40.2 → F-40.3 → F-40.4. **~4–5 sessions.**

**Picking order:** F-40.1 first (foundation; everything else depends on it). F-40.2 next (versioning policy can be drafted in parallel once F-40.1's classification list is stable). F-40.3 then F-40.4 sequentially. Phase B can run independently after F-40 ships; F-40.5 first within Phase B (auth model unlocks rate limiting + safe host binding).

**Sidecar correction**: F-47 (managed Qdrant) was originally listed as a sidecar consumer of F-40 in ADR-084 D8's bucket. Recon showed F-47 doesn't consume the FastAPI surface at all — its "API" is the Qdrant wire protocol. The correction lands in F-40.4's verification doc; effective F-40 consumers are F-20, F-34, F-45 (read-side only).

All six sub-issues carry `goal:operational-completeness` (Phase A) or are unlabeled-as-gate (Phase B) and parented to #414. F-40 itself remains `roadmap` until F-40.4 closes.

---

## 3. Sequencing (operational, updateable)

Per ADR-085 D6, this ADR does not prescribe ordering inside the list, but the dependency graph constrains it. Current best estimate:

**Tier-1 (current sequence, post 2026-06-02 F-10/F-48 ship):**
- **F-48** Open library distribution — ✅ shipped 2026-06-02. F-48.1 + F-48.2 closed; F-48.3/4/5 post-exit or v1.0.0-gated (see §2.4).
- **F-10** CI/CD gate — ✅ shipped 2026-06-02. All MVP sub-items closed; F-10.5 (pre-commit-hooks) open as bonus delivery channel.
- **F-40** OEM API surface — **active.** Decomposed 2026-06-02 (see §2.5). MVP path F-40.1 → F-40.2 → F-40.3 → F-40.4 (~4–5 sessions). Releases 3 commercial sidecars (F-20, F-34, F-45 read-side) on closure. **F-40.1 (#550) is the next sub-pickup.**

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
| 2026-06-02 | F-10.1a (#528), F-10.1b (#535), F-10.2 (#529) all closed and merged in commits `d2bf1639`, `0396abbe`, `2513dac9`. F-10's `Current status` advanced from `roadmap` → `partial`. |
| 2026-06-02 | ADR-086 accepted (`a99b0088`) — Installation Architecture. D1+D7 introduce a `core-runtime`-on-PyPI dependency for F-10.3's Dockerfile that wasn't visible when F-10 was originally decomposed; surfaces F-48 as F-10.3's prerequisite. |
| 2026-06-02 | F-48 decomposed into 5 sub-issues (#537–#541), parented to #527, all labeled `goal:operational-completeness`. F-10.3 #530's blocked-by set extended with F-48.2 #538. Tier-1 sequence revised: F-48 ahead of F-10's remaining sub-items. Tracker §2.4 added; §3 Tier-1 reordered. MVP estimate: ~2 F-48 sessions ahead of F-10.3. |
| 2026-06-02 | **F-48 ships.** F-48.1 (#537) + F-48.2 (#538) closed earlier same day; PyPI release workflow ran cleanly for v0.1.0 → v0.1.4 across the session. Exit criterion per ADR-085 5+3 row (`pip install` works; semver tags; CI publishes on tag) met. F-48.3/4/5 remain open as post-exit / v1.0.0-milestone scope. Registry row (`CORE-Features.md`) flipped `roadmap` → `shipping`. |
| 2026-06-02 | **F-10 ships.** F-10.3 (#530) shipped earlier same day (`dfe2cad2`); F-10.4 (#531) verified against external demo PR #1 via core-runtime 0.1.4 (#545 engine-side cwd-walk + #546 annotation-formatter key fix, commits `73c75f31` + `8e3c7dcb`). GitHub check-runs API returned 18 inline annotations with structured `path` field; workflow exit 1 → merge-blocking surface works. Exit criterion per ADR-085 5+3 row met. F-10.5 (pre-commit-hooks) remains open as bonus delivery channel. Two 5+3 gate items closed in one session (F-10 + F-48); remaining: F-27, F-40, F-41/F-42/F-43, plus three quality goals. |
| 2026-06-02 | **Post-ship cleanup**: #547 + #549 closed via core-runtime 0.1.5 + 0.1.6. #547 (`6fc4602a`) made cli_gate's `_walk_registry` drop Typer commands rooted outside `repo_root` — removed 5 site-packages-path annotations from the demo PR. #549 (`a12e928b`) made workflow_gate checks silent-skip on `FileNotFoundError` for absent tools (mypy/pytest/pip-audit/ruff/black not in the Action's slim image) — reduced System-path annotations from 7 to 1. Demo PR signal density: ~61% → 94% (16 of 16 inline annotations actionable, 1 remaining cli_gate.discovery_strict context-level entry as a known governance-semantic question). Open: #548 (low — `line_number` population polish). Total this session: 4 PyPI releases (0.1.3 → 0.1.6), 6 issues closed, 2 ADR-085 5+3 items satisfied. |
| 2026-06-02 | F-40 decomposed into 4 MVP sub-issues (#550–#553) + 2 post-exit sub-issues (#554, #555) parented to #414, all labeled `goal:operational-completeness` on Phase A. Recon surfaced: ~30 endpoints in current `src/api/v1/` are clear public-contract candidates; ~24 are clear internal; ~24 in four mixed routers need per-route classification (F-40.1's work). F-47 dropped from F-40 dependents — not a FastAPI consumer; correction lands in F-40.4's verification doc. Tracker §2.5 added; §2.1 F-40 row + §3 Tier-1 updated; F-40 #414 body updated with the decomposition table. F-40.1 #550 is the active sub-pickup. |

---

## 7. References

- ADR-085 — constitutional anchor for the constraint this doc operationalises
- ADR-084 D7 §1 — completeness as honesty commitment (the constitutional grounding)
- `papers/CORE-Features.md` §3 — authoritative status for the five feature items
- `planning/CORE-Feature-Dependency-Graph.md` — picture-form of the sequencing constraints
- `planning/SESSION-PROTOCOL.md` — should reference this doc as canonical "what to pick next" filter while constraint is active
- Memory `feedback_hardening_over_coverage` — the project preference that maps onto this ADR's discipline
