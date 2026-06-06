# CORE — Open Operational Completeness Tracker

**Status:** Authoritative (operational surface for ADR-085)
**Location:** `.specs/planning/CORE-Operational-Completeness.md`
**Audience:** Internal — engineering sequencing, session-protocol "what to pick next"
**Last updated:** 2026-06-06 (F-41 ships 2026-06-05 via ADR-091 D5 Phases 3+4 closing ADR-090 gates 4 + 6; F-42 ships 2026-06-06 via ADR-091 D5 Phase 7 promotion. Four of five feature commitments now closed; only F-43 remains on the feature plate. ADR-092 accepted 2026-06-06 — amends F-43 exit criterion from "invent a non-code instantiation" to "ratify the action-layer registry-coupling enforcement via negative-path refusal demonstration." ADR-089 precedent shape applied to F-43 row.)

---

## 1. Purpose

ADR-085 codifies the constraint: engineering capacity routes only to the five-feature + three-quality-goal list below until all eight are satisfied, then the constraint relaxes via an explicit governance act. This document is the tracker — it carries per-item status, what "done" looks like, and the current best estimate of sequencing.

**This is the operational surface. The constitutional surface is ADR-085.** When this document disagrees with ADR-085, ADR-085 wins. When this document needs amendment (refined criteria, new sub-items, sequencing change), it can be updated freely; an ADR amendment is required only if the intent or scope of the 5+3 list itself changes.

**Session-protocol use:** while the ADR-085 constraint is active, the canonical "what to pick next" filter is:

```bash
gh issue list --label goal:operational-completeness --state open
```

That returns the remaining gate issues. F-10 #384 + F-48 #527 closed 2026-06-02; F-27 #401 + F-40 #414 closed 2026-06-03; F-41 #415 closed 2026-06-05; F-42 #416 closed 2026-06-06. The open feature set is now **F-43 #417 only** (one issue, last of the three-feature F-41/F-42/F-43 commitment). The three quality goals (#561, #562, #563) are tracked here and in the issue tracker.

---

## 2. The 5+3 list

### 2.1 Five feature commitments

| Item | F-ID | Issue | Current status | "Done" looks like | Notes |
|---|---|---|---|---|---|
| CI/CD gate | F-10 | [#384](https://github.com/DariuszNewecki/CORE/issues/384) | **shipping** ✅ | `status: shipping`; PR annotations + merge-blocking demonstrated against a real external repo ✅ | Top of the adoption funnel (Tiers paper §2). **Shipped 2026-06-02.** F-10.1a/1b/2/3 landed earlier same day (`d2bf1639`, `0396abbe`, `2513dac9`, `dfe2cad2`); F-10.4 verified via core-runtime 0.1.4 (`73c75f31` + `8e3c7dcb`) against demo PR #1 (https://github.com/DariuszNewecki/core-audit-demo/pull/1) — GitHub check-runs API returned 18 inline annotations with structured `path` field; workflow exit 1 confirms merge-blocking surface. F-10.5 (pre-commit-hooks distribution) remains open as a bonus delivery channel, not part of the gate criterion. F-10.P2 (GitLab + CodeClimate) deferred. The in-repo `.github/workflows/nightly-audit.yml` removed in `a8a232ef` per #534; reinstatement against the F-10.3 Action per ADR-086 is follow-on work. |
| Local LLM | F-27 | [#401](https://github.com/DariuszNewecki/CORE/issues/401) | **shipping** ✅ | promotes from `partial` to `shipping`; demonstrated end-to-end Solo task on local-LLM-only routing per ADR-089 D1 (capability proof — one consequence-chain run with ADR-024 D1 local rows enabled + zero remote-generative entries in `llm_exchange_log` during the run) ✅ | **Shipped 2026-06-03.** ADR-089 (same day) amended the exit criterion from a "≥7-day Solo run" usage window to a one-shot capability demonstration. Demonstration window 18:20:23–18:28:27Z: `build.tests` on `src/shared/models/audit_rendering.py` returned `ok=True` (90.4s) via `ollama_qwen_coder_small` (qwen2.5-coder:3b) under RemoteCoder role; `llm_exchange_log` recorded 0 remote-locality generative calls during the window. Routing flipped back symmetrically post-demonstration (DeepSeek + Anthropic restored as the day-to-day routing target). |
| OEM API surface | F-40 | [#414](https://github.com/DariuszNewecki/CORE/issues/414) | **shipping** ✅ | `status: shipping`; documented public contract; sidecar-shape commercial features F-20/F-34/F-45/F-47 can attach without private hooks (ADR-084 D6) ✅ | **Shipped 2026-06-02.** All four MVP sub-issues closed in a single session: F-40.1 (#550) declared the route classification (papers/CORE-OEM-API.md); F-40.2 (#551) authored ADR-087 stability policy; F-40.3 (#552) annotated all 46 public routes + published the OpenAPI spec at contracts/oem_api_v1.openapi.json (48 paths); F-40.4 (#553) walked F-20/F-34/F-45 against the public contract and recorded zero gaps (.specs/verification/F-40-sidecar-walk.md). Three commercial sidecars (F-20, F-34, F-45 read-side) unblocked per ADR-084 D3. Phase B (auth, host binding, rate limiting — #554/#555) post-exit. F-47 stayed as managed-infrastructure (not a FastAPI consumer); correction recorded in OEM-API paper + F-40-sidecar-walk verification doc. |
| Extension interfaces | F-41 + F-42 + F-43 | [#415](https://github.com/DariuszNewecki/CORE/issues/415) [#416](https://github.com/DariuszNewecki/CORE/issues/416) [#417](https://github.com/DariuszNewecki/CORE/issues/417) | F-41 + F-42 **shipping** ✅; F-43 roadmap | all three `status: shipping`; one first-party non-code instantiation exists as proof of the plugin-interface contract **(F-43 portion amended per ADR-092 D1, 2026-06-06: F-43 ships on action-layer registry-coupling enforcement — `ActionExecutor.execute()` refuses dispatch when declared `artifact_type` is unregistered, demonstrated by negative-path refusal test; trio-level non-code instantiation clause satisfied by F-41+F-42 per ADR-092 D3)** | **F-41 shipped 2026-06-05** — all 9 ADR-090 §Verification gates closed; first-party non-code instantiations live (`intent_yaml`, `spec_markdown` artifact_types under the published `META/artifact_type.schema.json` contract); key closing commits `e3186d98` (gate 3, crawl_scopes retired), `0854243e` (gate 4, Python pipeline end-to-end via ADR-091 D5 Phase 3), `f08ca3a1` (gate 6, CCC migration via ADR-091 D5 Phase 4), `9db87bdf` (gate 9, advisory anti-regression rule; engine check at #566). **F-42 shipped 2026-06-06** — ADR-091 D5 fully implemented; closing commits `ab0a5706` (engines + governance sensor closing #575), `416f5fdb` (promotion to blocking), `c9953d46` (Phase 7 sensor-supported-by-declaration promotion + asymmetry fix). Published sensor contract structurally stable: single `post_finding` API + `resolution_mechanism` field + sensor-to-artifact_type coherence rule + dispatch sensor model. F-43 remains the last feature on the plate; it depended on F-41 (now complete). |
| Open library distribution | F-48 | [#527](https://github.com/DariuszNewecki/CORE/issues/527) | **shipping** ✅ | `status: shipping`; `pip install core-runtime` works; semver tags; CI publishes on tag ✅ | **Shipped 2026-06-02.** F-48.1 (#537) renamed the distribution to `core-runtime` + PyPI metadata; F-48.2 (#538) shipped the Trusted-Publisher OIDC release workflow. Five semver tags published (v0.1.0–v0.1.4); 0.1.3 and 0.1.4 CI-published cleanly during this session as part of the #545/#546 F-10 unblock chain. F-48.3 (Docker/GHCR) and F-48.5 (semver policy doc) remain open as post-exit distribution polish per §2.4; F-48.4 (public-vs-internal API) also shipped 2026-06-02 (verified 2026-06-03). Constitutionally load-bearing per ADR-084 D7 §4. |

### 2.2 Three quality goals

**Live status:** `gh issue list --label goal:operational-completeness --state all` returns both feature commitments (§2.1) and quality goals. Each quality goal carries a GH issue filed 2026-06-03; closing the issue records met-date + evidence in the closure comment.

| Item | GH issue | Type | "Done" looks like | Verification path |
|---|---|---|---|---|
| Docs polish | [#561](https://github.com/DariuszNewecki/CORE/issues/561) | system property | An outside developer installs + runs the full thesis (encounter → audit → remediate → verify) from public docs alone, without source-tree archaeology | Recruit a developer who has never seen the project; observe their setup attempt; record gaps; close them; repeat |
| Demo reliability | [#562](https://github.com/DariuszNewecki/CORE/issues/562) | system property | The consequence-chain bootstrap demo (Tiers §3.2) runs cleanly on first attempt, three times in a row, from a clean repo clone on a freshly-provisioned machine | Scripted: provision VM → clone → run demo → record outcome. Repeat from clean VM until three consecutive clean runs. |
| Signal quality | [#563](https://github.com/DariuszNewecki/CORE/issues/563) | derived metric | F-19 convergence metric reports resolution rate ≥ creation rate, sustained ≥ 30 days, on this repo | (1) Verify F-19 query produces honest data; (2) start measurement window; (3) sustain for 30 days; (4) record met-date in #563 closure comment. Per ADR-085 §Consequences, F-19 honesty verification is in scope for engineering capacity under D1. |

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
| F-48.4 | [#540](https://github.com/DariuszNewecki/CORE/issues/540) | 1–2 sessions | F-31/F-32/F-33/F-35/F-36 commercial runtime forks per ADR-084 D4; PyPI `Production/Stable` classifier per ADR-088 D2 | ✅ shipped 2026-06-02 (commit `34f597c1`, #540 closed). `__all__` declared in all 6 top-level packages: `shared` (5 symbols — extension contract for forks), `mind` (1 symbol — F-10.3 stateless audit entry), and `api`/`body`/`cli`/`will` (empty — public surface is via HTTP routes / console scripts / future ADRs). Minimal-surface strategy per F-48.4 recommendation. |
| F-48.5 | [#541](https://github.com/DariuszNewecki/CORE/issues/541) | ~½ session | nothing direct; clarifies `core-runtime` user expectations | open — Semver policy doc per ADR-086 D7 + ADR-088 D5 baseline |

**F-48 exit criterion satisfied 2026-06-02** via F-48.1 + F-48.2. Per
ADR-085's 5+3 row for F-48 (`pip install` works; semver tags; CI
publishes on tag), the MVP criterion is met. F-48.3 and F-48.5 remain
open as post-exit distribution polish. F-48.4 also shipped 2026-06-02
(same day; verified 2026-06-03 against commit `34f597c1` and `__all__`
presence). The original "v1.0.0 milestone" framing for F-48.4 / F-48.5
is obsolete per ADR-088 (CORE is on the 2.x track; no v1.0.0 milestone
exists). F-48.3's Docker image is the next pickup if a Solo-tier install
path is needed; F-48.4's closure satisfies ADR-088 D2's gate for PyPI
`Production/Stable` classifier promotion (governor decision, not
automatic). F-48.5 inherits the ADR-088 D5 baseline when authored.

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
| F-40.1 | [#550](https://github.com/DariuszNewecki/CORE/issues/550) | ~1 session | F-40.2, F-40.3, F-40.4 | ✅ shipped `22144571` — `papers/CORE-OEM-API.md` route classification |
| F-40.2 | [#551](https://github.com/DariuszNewecki/CORE/issues/551) | ~1 session | F-40.3, F-40.4 | ✅ shipped `831a95cc` — ADR-087 versioning + stability policy |
| F-40.3 | [#552](https://github.com/DariuszNewecki/CORE/issues/552) | ~1–2 sessions | F-40.4 | ✅ shipped 2026-06-02 (five commits, see §6 activity log) — OpenAPI spec at `.specs/contracts/oem_api_v1.openapi.json` (48 paths) |
| F-40.4 | [#553](https://github.com/DariuszNewecki/CORE/issues/553) | ~1 session | **F-40 #414 ship** | ✅ shipped 2026-06-02 — verification doc at `.specs/verification/F-40-sidecar-walk.md`; zero gaps; F-40 flipped to shipping |

**Phase B — Third-party OEM consumption (post-exit; does NOT gate)**

| Sub | Issue | Sized | Blocks | Purpose |
|---|---|---|---|---|
| F-40.5 | [#554](https://github.com/DariuszNewecki/CORE/issues/554) | ~2 sessions | F-40.6 | Authentication + authorization scheme |
| F-40.6 | [#555](https://github.com/DariuszNewecki/CORE/issues/555) | ~1–2 sessions | — | Host binding + rate limiting + OpenAPI publication |

**MVP path to F-40 ship**: F-40.1 → F-40.2 → F-40.3 → F-40.4. **~4–5 sessions.**

**Picking order:** F-40.1 first (foundation; everything else depends on it). F-40.2 next (versioning policy can be drafted in parallel once F-40.1's classification list is stable). F-40.3 then F-40.4 sequentially. Phase B can run independently after F-40 ships; F-40.5 first within Phase B (auth model unlocks rate limiting + safe host binding).

**Sidecar correction**: F-47 (managed Qdrant) was originally listed as a sidecar consumer of F-40 in ADR-084 D8's bucket. Recon showed F-47 doesn't consume the FastAPI surface at all — its "API" is the Qdrant wire protocol. The correction lands in F-40.4's verification doc; effective F-40 consumers are F-20, F-34, F-45 (read-side only).

All six sub-issues carry `goal:operational-completeness` (Phase A) or are unlabeled-as-gate (Phase B) and parented to #414. F-40 ✅ shipped 2026-06-02 (F-40.4's verification walk recorded zero gaps).

---

## 3. Sequencing (operational, updateable)

Per ADR-085 D6, this ADR does not prescribe ordering inside the list, but the dependency graph constrains it.

**Live state:** `gh issue list --label goal:operational-completeness --state open` — what remains open. Closed items + closure dates are in §6 activity log.

**Remaining-work order (best-estimate, updateable without ADR):**

**Tier-A — Extension interfaces (F-41 + F-42 shipped; F-43 sole remaining feature):**
- ~~**F-41** Artifact type registry — [#415](https://github.com/DariuszNewecki/CORE/issues/415)~~ — ✅ shipped 2026-06-05 (ADR-090; ADR-091 D5 Phases 3+4 closed partials)
- ~~**F-42** Pluggable sensor model — [#416](https://github.com/DariuszNewecki/CORE/issues/416)~~ — ✅ shipped 2026-06-06 (ADR-091 D5 fully implemented; published sensor contract stable)
- **F-43** Pluggable action model — [#417](https://github.com/DariuszNewecki/CORE/issues/417) — F-41 prerequisite satisfied; ready as next feature pickup. Exit criterion is action-layer registry-coupling enforcement per ADR-092 D1 (negative-path refusal test required); declaration site (decorator field / `operational_capabilities.yaml` augment / new YAML surface) is the open implementation decision per ADR-092 D4. `governance.taxonomy.action_supported_by_declaration` coherence rule is parked per ADR-092 D2 with unparking trigger in D5 (second non-Python action ships).

**Tier-B — Quality goals (parallel with Tier-A; any can start now):**
- **Docs polish** — [#561](https://github.com/DariuszNewecki/CORE/issues/561) — work continues with every feature; ready for fresh-developer recruit any time
- **Demo reliability** — [#562](https://github.com/DariuszNewecki/CORE/issues/562) — scripted VM-provisioning harness is the first action item
- **Signal quality** — [#563](https://github.com/DariuszNewecki/CORE/issues/563) — Step 1 (F-19 query honesty verification, in-scope per ADR-085 §Consequences) can start now; Step 2 (sustained 30-day window) requires Step 1

Historical Tier-1 ships (F-10 + F-27 + F-40 + F-48 closed 2026-06-02 / 2026-06-03; F-41 closed 2026-06-05; F-42 closed 2026-06-06) are recorded in §6 activity log.

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
| 2026-06-02 | **F-40 ships.** All four MVP sub-issues closed in a single session (F-40.1 + F-40.2 + F-40.3 + F-40.4). F-40.1 (#550, `22144571`) declared the route classification (papers/CORE-OEM-API.md, 266 lines). F-40.2 (#551, `831a95cc`) authored ADR-087 (OEM API versioning + stability policy, 206 lines, 9 decisions). F-40.3 (#552, five commits `432d4b63` + `b1e4d0f2` + `3ff3aa39` + `a266d300` + `39c7e544`) annotated all ~46 public routes + 7 internal routers + 5 mixed-router internal endpoints + published the OpenAPI spec snapshot at `contracts/oem_api_v1.openapi.json` (48 paths, 49 operations). F-40.4 (#553) walked F-20 (6 endpoints, 0 gaps), F-34 (~35 endpoints, 0 gaps), F-45 read-side (5 endpoints, 0 gaps) against the public contract; verification doc at `.specs/verification/F-40-sidecar-walk.md`. F-47 dependency formally resolved (not a FastAPI consumer). **Three of five 5+3 gate items now closed (F-10 + F-48 + F-40)**; remaining: F-27 (partial), F-41/F-42/F-43 (extension interfaces trio), plus three quality goals. |
| 2026-06-03 | **ADR-089 accepted — F-27 exit criterion amended.** Original ADR-085 §Context line 43 criterion ("reliable local-LLM-only Solo run for ≥7 days") replaced with a one-shot capability demonstration: one consequence-chain run with ADR-024 D1 local rows enabled in `core.llm_resources` + zero generative entries in `llm_exchange_log` against remote-locality resources during the run. Original row stays verbatim per ADR-074 D13 + ADR-080 §D5 append-only precedent; ADR-089 is the controlling statement. Reasoning: the four other 5+3 features have capability exit criteria (F-10 demo PR, F-48 pip-install, F-40 sidecar walk, F-41/F-42/F-43 instantiation proof) — F-27's usage-window criterion was the outlier, did not measure the capability claim, conflicted with operational economics (local Ollama qualitatively weaker than DeepSeek-chat for the governor's day-to-day work), and conflated F-27 (capability) with F-38 (air-gap operational guarantee, commercial post-exit). Tracker §2.1 F-27 "Done" cell + §3 Tier-1 line + §3 Tier-3 bullet updated as consequences. F-27 promotion now collapses from ~7 days to ~30 min in-session; positioned as Tier-1 next pickup. |
| 2026-06-03 | **F-27 ships.** ADR-089 D1 capability demonstration executed same-session. Routing flipped: 10 generative cognitive roles temporarily routed from DeepSeek/Anthropic to `ollama_qwen_coder_small` (qwen2.5-coder:3b) + `ollama_reasoner` (qwen2.5:7b) per ADR-024 D1; Vectorizer left on `ollama_nomic_embedding` per ADR-089 D4. `build.tests` on `src/shared/models/audit_rendering.py` returned `ok=True` (90.4s, 1186 prompt + 1150 completion tokens) via RemoteCoder role bound to `ollama_qwen_coder_small`. `core.llm_exchange_log` window query (18:20:23–18:28:27Z): **0 remote-locality generative calls**, 1 local generative call (qwen2.5-coder:3b), 3 local embedding calls (nomic, expected per ADR-089 D4). Routing restored symmetrically post-demonstration (UPDATE counts 10/13/2 inverse of flip-direction 13/10/2). Exit criterion per ADR-089 D1 met. Registry row (`CORE-Features.md`) flipped `partial` → `shipping`; total now 31 shipping / 0 partial / 17 roadmap. **Four of five 5+3 gate items closed (F-10 + F-48 + F-40 + F-27)**; remaining: F-41/F-42/F-43 (extension interfaces trio), plus three quality goals. Closure recorded in ADR-085 §Context Verification log citing ADR-089 D1 as criterion source. GH #401 closed with evidence summary. |
| 2026-06-03 | **F-48.4 status verified shipped.** Recon audit (`var/recon-product-state-2026-06-03.md` §C2) surfaced a tracker drift: commit `34f597c1` (2026-06-02 21:33Z) shipped F-48.4 + closed GH #540, but tracker §2.4 row + footer + ADR-085 5+3 row §2.1's notes still read "F-48.4 open." Verification cross-checked: (a) GH #540 state `CLOSED` at 2026-06-02T19:33:36Z; (b) `__all__` present in all 6 top-level package `__init__.py` files (`src/{shared,mind,api,body,cli,will}/__init__.py`); (c) commit `34f597c1` message lists the public surface (5 symbols in `shared`, 1 in `mind`, 4 empty). Conclusion: F-48.4 shipped 2026-06-02; tracker was stale. Drift-fixed: §2.4 F-48.4 row + footer + §2.1 F-48 notes updated. **Constitutional consequence**: F-48.4 closure satisfies ADR-088 D2's gate for promoting the PyPI `Development Status` classifier from `4 - Beta` to `5 - Production/Stable` (gate is F-40 + F-48.4; both now closed). The promotion is a governor decision per ADR-088 D2, not automatic. |
| 2026-06-05 | **F-41 ships.** ADR-090's 9 §Verification gates fully met. Phase 1–4 of ADR-090 D4 shipped 2026-06-04 (commits `76e11985`, `d9ff3622`, `17c18408`, `eb2ce2ca`); `crawl_scopes.yaml` retirement closed gate 3 (`e3186d98`); advisory `architecture.artifact_discovery_through_registry` rule closed gate 9 (`9db87bdf`; engine-check tracked at #566). Gates 4 + 6 (full Python pipeline + CCC sub-discovery migrations) closed by ADR-091 D5 Phases 3 + 4 today: Phase 4 (`f08ca3a1`) routed 8 CCC discovery surfaces through the spec_markdown artifact_type; Phase 3 (`0854243e`) migrated AuditViolationSensor end-to-end onto the ADR-091 D2 canonical subject format (`<artifact_type>::<rule_id>::<file_path>`) + centralized the audit-violation predicate + rewrote 5,496 blackboard rows under the deterministic transform. Behavioural identity verified per surface. F-41 #415 closed. Registry now has 9 artifact_type declarations; `META/artifact_type.schema.json` is the first ADR-084 D1 published contract. F-41's first-party non-code instantiations (`intent_yaml` + `spec_markdown`) prove the extension-interface contract is real, not aspirational — completing the 5+3 row's exit criterion. **Five of five feature commitments now closed except F-43.** F-43 unblocked (F-41 was its sole prerequisite). |
| 2026-06-06 | **F-42 ships.** ADR-091 D5 fully implemented and live-enforced. Three closing commits this session: (a) `ab0a5706` shipped two new audit engines (`AwaitingReauditChecks` under `ast_gate` for `architecture.blackboard.reaudit_requires_reaudit_mechanism`; context-level check on `TaxonomyGateEngine` for `governance.taxonomy.self_resolve_resolver_owned`) plus the missing `audit_sensor_governance` namespace sensor — closing #575 and activating two previously inert taxonomy_gate cognates (`operational_capabilities_decorator_backing` ADR-079, `sensor_supported_by_declaration` ADR-091 D4); side-discovery of six `governance.dangerous_execution_primitives` findings filed as #576. (b) `416f5fdb` promoted the new governance rules to blocking after one clean live audit cycle. (c) `c9953d46` promoted `governance.taxonomy.sensor_supported_by_declaration` from `reporting` to `blocking` (cognate `operational_capabilities_decorator_backing` was already blocking per ADR-079 D10 stage 2). The Phase 7 promotion's own engine surfaced an introspected asymmetry (`audit_sensor_governance` declared `mandate.scope.artifact_type: [python]` but missing from `python.yaml`'s `supported_sensors`); a one-line add resolved it and gated the promotion — the rule catching drift caused by the prior commit before promotion is exactly the F-42 D5 boundary invariant in action. Published sensor contract structurally stable: single `post_finding` API + `resolution_mechanism` field + sensor-to-artifact_type coherence rule + dispatch sensor model. F-42 #416 closed. **Four of five feature commitments fully closed (F-10 + F-27 + F-40 + F-48); the fifth (Extension interfaces F-41 + F-42 + F-43) is two-thirds shipped** — F-43 (#417) is the sole remaining feature pickup, plus the three quality goals (#561, #562, #563). |
| 2026-06-06 | **ADR-092 accepted — F-43 exit criterion amended.** Original ADR-085 §Context table line 35 F-43 portion ("one first-party non-code instantiation exists as proof of the plugin-interface contract") replaced by ADR-092 D1: F-43 ships when `ActionExecutor.execute()` refuses to dispatch actions whose declared `artifact_type` is not registered in the F-41 registry, demonstrated by negative-path refusal test (happy-path-only dispatch test is not accepted as evidence), with at least one atomic action in `src/body/atomic/` declaring its target artifact_type. Direct ADR-089 precedent shape (capability claim replaces invented-or-window proof). Original row in ADR-085 stays verbatim per ADR-074 D13 + ADR-080 §D5 append-only discipline; ADR-092 is the controlling statement. Reasoning: F-43 was the only 5+3 item whose exit criterion required *inventing* its own proof rather than ratifying a pre-existing live capability (no consumer is waiting for a non-Python action; every `fix.*` in `src/body/atomic/fix_actions.py` is Python-only; zero open issues request non-Python remediation). The load-bearing F-43 capability is structural — the action-layer registry-coupling chokepoint — not instantiation-counted. ADR-091 D6's four-item forward contract becomes "three committed, one parked": items 1+3+4 (artifact_type field, registry-coupling, subject format boundary) ship under F-43; item 2 (`governance.taxonomy.action_supported_by_declaration` coherence rule) parks per ADR-092 D2 with D5 unparking trigger when a second non-Python action ships. Trio is structurally two-of-three on the coherence-rule axis until that population earns the third rule — honest visible governance debt. Tracker §2.1 F-41/F-42/F-43 row "Done" cell + §3 Tier-A F-43 bullet + header `Last updated` line updated as consequences. F-43 implementation collapses from ~5–8 sessions (original criterion + new YAML surface) to ~1–2 (refusal chokepoint + one declared action). |

---

## 7. References

- ADR-085 — constitutional anchor for the constraint this doc operationalises
- ADR-084 D7 §1 — completeness as honesty commitment (the constitutional grounding)
- `papers/CORE-Features.md` §3 — authoritative status for the five feature items
- `planning/CORE-Feature-Dependency-Graph.md` — picture-form of the sequencing constraints
- `planning/SESSION-PROTOCOL.md` — should reference this doc as canonical "what to pick next" filter while constraint is active
- Memory `feedback_hardening_over_coverage` — the project preference that maps onto this ADR's discipline
