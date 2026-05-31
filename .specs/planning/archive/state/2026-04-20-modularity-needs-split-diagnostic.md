# Reconnaissance: `modularity.needs_split` concentration — 2026-04-20

**Status:** Recon / diagnostic — no decision proposed. ADR authorship is a
separate session.
**Baseline audit:** `core-admin code audit` at 2026-04-20 21:20, verdict
PASS, 39 findings, 0 crashed.
**Checker path (verified):**
`src/mind/logic/engines/ast_gate/checks/modularity_checks.py` —
`ModularityChecker.check_needs_split`. The briefing's example path
(`src/body/services/cim/modularity/checker.py`) does not exist and
appears to be a stale memory.
**Scope:** every finding emitted under `check_id=modularity.needs_split`
in the current audit run.
**Artifacts (reproducible):**
- `.artifacts/modularity_diagnostic.py` — the helper used
- `.artifacts/needs_split_findings.json` — 32 findings (filtered)
- `.artifacts/per_file.json` — per-finding analysis with category
- `.artifacts/counterfactual.json` — every `src/**.py` > 400 LOC with
  its concerns and responsibilities

**2026-04-20 correction:** §5's counterfactual table originally labelled
the "remain vs drop" columns inverted relative to the rule's actual
`len(resps) <= 2 → fire` semantic. The underlying data was correct; the
column headers were wrong. Fixed in this revision. The retrofit fires
on the low-responsibility side, so the 21 CLASSIFIER-BLIND findings
(resp ≥ 3) **drop**, and the 11 DOMINANT-CLASS + INTERNAL-MODULE-NO-SIGNAL
+ UNCATEGORIZED findings (resp ≤ 2) **remain**. §§1, 2, 4, 6, 7 are
unchanged — they describe the pre-retrofit state, which is what a
diagnostic records.

---

## 1. Summary counts

| Category                   | Count | % of flagged |
|---                         |---    |---           |
| CLASSIFIER-BLIND           |    21 | 65.6%        |
| DOMINANT-CLASS             |     6 | 18.8%        |
| INTERNAL-MODULE-NO-SIGNAL  |     4 | 12.5%        |
| UNCATEGORIZED              |     1 |  3.1%        |
| **Total**                  |    32 | 100.0%       |

**Headline claim.** Two thirds of current `modularity.needs_split`
findings (21 of 32) are CLASSIFIER-BLIND: the file contains ≥3
responsibilities under the content-based `_detect_responsibilities`
classifier that the sibling `check_refactor_score` already uses, but
the import-based `_identify_concerns` classifier that
`check_needs_split` actually consults sees ≤2 concern buckets and so
treats the file as "single coherent responsibility." The rule fires on
those files because they are long — not because the current
implementation has evidence they are internally coherent. 0 of 32
findings come from files where both classifiers agree the file is
multi-concern (that set, `GENUINE-CANDIDATE` in the taxonomy, is
empty — the corresponding findings are instead captured by
`modularity.needs_refactor`, which is blocking).

## 2. The check algorithm, as-is

`check_needs_split(file_path, params)` is ~35 lines. It reads the
file, parses to AST, computes line-count, and returns immediately if
`loc <= max_lines` (default 400). When a file is over the limit, it
extracts top-level import module names, runs them through
`_identify_concerns` — a keyword-matcher over six domain buckets
(`database`, `web`, `testing`, `ml`, `cli`, `file_io`) — and emits a
finding iff the returned concern set has `len(concerns) <= 2`. The
finding carries `concern_count` and `concerns` but no responsibility
signal, no cohesion signal, no class-structure signal, and no
cross-reference to `_detect_responsibilities`.

`_identify_concerns` is a deliberately narrow instrument: the
`IMPORT_CONCERNS` dict's comment states that it "[d]eliberately
excludes infrastructure primitives (async, logging, typing, pathlib,
json) that are present in virtually every Python file and carry no
architectural signal." That reasoning is correct for a coarse
coupling metric — the one used in `check_refactor_score` as the
`coupling_score` term — but it is load-bearing here in a way the
comment does not acknowledge. Every file in CORE whose external
dependencies fit inside `{asyncio, typing, pathlib, json, dataclasses,
re, ast, uuid, datetime, collections, enum}` plus internal
`body|mind|will|shared|cli`-prefixed modules lands at ≤1 concern under
this classifier. That is every file in the Mind, Will, and shared
infrastructure layers that isn't explicitly a DB, web, or CLI
front-door.

The rule statement in `.intent/rules/code/modularity.json` says "A
source file that exceeds the line limit AND contains a *single
coherent responsibility* SHOULD be split into smaller files along
natural seams." The implementation measures neither coherence nor
responsibility — it measures *external domain spread* and treats
"≤2 buckets" as a proxy for "single coherent responsibility." For any
file whose responsibilities are expressed through internal modules or
stdlib rather than through external domain packages, the proxy
collapses and the rule degenerates to "file has more than 400 lines."
The gap between statement and implementation is the root finding of
this diagnostic.

## 3. Per-finding table

Sorted by category, then file. All 32 findings.

| # | file | loc | concerns | responsibilities | imports_ext | imports_int | class_count | dominant_class | CATEGORY |
|---|---|---|---|---|---|---|---|---|---|
|  1 | src/body/atomic/executor.py                                                   | 416 | 2 | 3 |  6 |  7 | 1 | 319 | CLASSIFIER-BLIND |
|  2 | src/body/atomic/fix_actions.py                                                | 417 | 0 | 3 |  3 | 15 | 0 | —   | CLASSIFIER-BLIND |
|  3 | src/body/atomic/modularity_fix.py                                             | 408 | 1 | 3 |  6 |  9 | 0 | —   | CLASSIFIER-BLIND |
|  4 | src/body/atomic/modularity_splitter.py                                        | 479 | 1 | 3 |  4 |  3 | 2 | 440 | CLASSIFIER-BLIND |
|  5 | src/body/atomic/sync_actions.py                                               | 578 | 2 | 3 |  7 | 14 | 0 | —   | CLASSIFIER-BLIND |
|  6 | src/body/services/crawl_service/main_module.py                                | 566 | 2 | 4 |  7 | 12 | 1 | 514 | CLASSIFIER-BLIND |
|  7 | src/body/workers/call_site_rewriter.py                                        | 508 | 2 | 4 |  9 |  9 | 1 | 426 | CLASSIFIER-BLIND |
|  8 | src/cli/resources/runtime/health.py                                           | 779 | 2 | 4 |  9 |  3 | 0 | —   | CLASSIFIER-BLIND |
|  9 | src/mind/governance/authority_package_builder.py                              | 499 | 0 | 4 |  3 |  4 | 4 | 332 | CLASSIFIER-BLIND |
| 10 | src/mind/logic/engines/knowledge_gate.py                                      | 432 | 2 | 4 |  7 |  4 | 1 | 399 | CLASSIFIER-BLIND |
| 11 | src/shared/ai/prompt_model.py                                                 | 590 | 1 | 4 |  6 |  3 | 3 | 436 | CLASSIFIER-BLIND |
| 12 | src/shared/infrastructure/clients/qdrant_client.py                            | 449 | 0 | 3 |  6 |  4 | 3 | 394 | CLASSIFIER-BLIND |
| 13 | src/shared/infrastructure/context/builder.py                                  | 742 | 0 | 3 | 10 |  5 | 2 | 606 | CLASSIFIER-BLIND |
| 14 | src/shared/infrastructure/intent/intent_repository.py                         | 658 | 1 | 3 |  7 |  5 | 3 | 593 | CLASSIFIER-BLIND |
| 15 | src/will/agents/strategic_auditor/context_gatherer.py                         | 583 | 1 | 3 |  9 |  6 | 1 | 525 | CLASSIFIER-BLIND |
| 16 | src/will/autonomy/proposal.py                                                 | 422 | 0 | 3 |  6 |  2 | 5 | 293 | CLASSIFIER-BLIND |
| 17 | src/will/autonomy/proposal_executor.py                                        | 638 | 2 | 3 |  6 |  6 | 1 | 604 | CLASSIFIER-BLIND |
| 18 | src/will/phases/code_generation_phase.py                                      | 480 | 1 | 3 | 10 | 15 | 1 | 431 | CLASSIFIER-BLIND |
| 19 | src/will/self_healing/remediation_interpretation/file_role_detector.py        | 599 | 0 | 3 |  3 |  1 | 1 | 585 | CLASSIFIER-BLIND |
| 20 | src/will/workers/intent_inspector.py                                          | 555 | 1 | 4 |  5 |  3 | 1 | 472 | CLASSIFIER-BLIND |
| 21 | src/will/workers/violation_remediator_body/worker.py                          | 503 | 0 | 3 |  8 |  4 | 1 | 428 | CLASSIFIER-BLIND |
| 22 | src/body/evaluators/atomic_actions_evaluator.py                               | 428 | 1 | 2 |  7 |  2 | 2 | 349 | DOMINANT-CLASS |
| 23 | src/body/services/constitutional_validator.py                                 | 426 | 0 | 2 |  6 |  2 | 4 | 288 | DOMINANT-CLASS |
| 24 | src/shared/path_resolver.py                                                   | 403 | 1 | 2 |  3 |  2 | 1 | 367 | DOMINANT-CLASS |
| 25 | src/will/agents/strategic_auditor/agent.py                                    | 417 | 2 | 2 |  7 | 10 | 1 | 355 | DOMINANT-CLASS |
| 26 | src/will/self_healing/remediation_interpretation/responsibility_extractor.py  | 421 | 0 | 2 |  2 |  1 | 1 | 411 | DOMINANT-CLASS |
| 27 | src/will/strategists/fix_strategist.py                                        | 467 | 0 | 2 |  3 |  4 | 1 | 430 | DOMINANT-CLASS |
| 28 | src/body/services/blackboard_service.py                                       | 658 | 2 | 2 |  5 | 16 | 1 | 620 | INTERNAL-MODULE-NO-SIGNAL |
| 29 | src/will/workers/audit_violation_sensor.py                                    | 434 | 0 | 1 |  2 |  5 | 1 | 361 | INTERNAL-MODULE-NO-SIGNAL |
| 30 | src/will/workers/test_remediator.py                                           | 412 | 0 | 2 |  2 | 10 | 1 | 337 | INTERNAL-MODULE-NO-SIGNAL |
| 31 | src/will/workers/violation_remediator.py                                      | 503 | 0 | 2 |  2 | 13 | 1 | 434 | INTERNAL-MODULE-NO-SIGNAL |
| 32 | src/will/interpreters/request_interpreter.py                                  | 441 | 0 | 2 |  7 |  2 | 5 | —   | UNCATEGORIZED |

Cross-category observation: 22 of 32 findings (~69%) have a dominant
top-level class accounting for >70% of class-owned lines. That is a
property of the codebase, not of the taxonomy — see §4 for how it
interacts with CLASSIFIER-BLIND.

## 4. Evidence for the dominant category — CLASSIFIER-BLIND

21 of 32 findings (65.6%) land in CLASSIFIER-BLIND: `concerns ≤ 2 AND
responsibilities ≥ 3`. The content-based classifier sees multiple
responsibilities that the import-based classifier misses. Three
representative examples:

### Example 1 — `src/cli/resources/runtime/health.py` (779 LOC)

- **imports_external:** `__future__`, `datetime`, `typing`, `typer`,
  `rich.columns`, `rich.console`, `rich.panel`, `rich.table`,
  `sqlalchemy`
- **imports_internal:** `cli.utils`,
  `shared.infrastructure.database.session_manager`, `shared.logger`
- **concerns (import-based):** `cli`, `database` → **2**
- **responsibilities (content-based):** `data_access`, `network`,
  `orchestration`, `presentation` → **4**
- **class_count:** 0 (pure-function module)

This is a 779-line CLI resource that renders health dashboards using
Rich, orchestrates database queries across multiple sessions, and
calls out to network endpoints. `_detect_responsibilities` picks all
four up from `session.`, `rich.`, `Table(`, and `await ... .execute(`
patterns in the body. `_identify_concerns` sees `typer`+`rich` → `cli`
and `sqlalchemy`+`session_manager` → `database`, lands at 2, and
declares the file a single-coherent-responsibility split candidate.
The rule statement's "single coherent responsibility" clearly does
not hold: this is the canonical example of a file the current rule
mis-describes.

### Example 2 — `src/shared/infrastructure/context/builder.py` (742 LOC)

- **imports_external:** `__future__`, `ast`, `uuid`, `datetime`,
  `typing`, `models`, `serializers`, `providers.ast`, `providers.db`,
  `providers.vectors`
- **imports_internal:** `shared.config`,
  `shared.infrastructure.intent.intent_repository`,
  `shared.infrastructure.knowledge.knowledge_service`, `shared.logger`,
  `shared.infrastructure.context.limb_workspace`
- **concerns (import-based):** *(empty)* → **0**
- **responsibilities (content-based):** `data_access`, `io_operations`,
  `network` → **3**
- **class_count:** 2; **dominant_class_lines:** 606 (`ContextBuilder`)

A ContextBuilder that sits at the heart of the context-build pipeline
and is the authoritative assembler for LLM prompt context. The file
has zero external-domain imports under `_identify_concerns` —
`providers.db` does not match `database` (the keyword list wants
`sqlalchemy|psycopg2|session|query|orm`, not `db`). Three
responsibilities surface from content — DB provider calls,
file-path/I/O access, and async orchestration. The file legitimately
coordinates several distinct concerns; the import classifier's
empty-set output is a measurement artefact, not evidence of coherence.

### Example 3 — `src/will/autonomy/proposal_executor.py` (638 LOC)

- **imports_external:** `__future__`, `asyncio`, `json`, `time`,
  `typing`, `sqlalchemy`
- **imports_internal:** `body.atomic.executor`,
  `body.services.service_registry`, `shared.logger`,
  `will.autonomy.proposal`, `will.autonomy.proposal_repository`,
  `will.autonomy.proposal_state_manager`
- **concerns (import-based):** `database`, `file_io` → **2**
- **responsibilities (content-based):** `data_access`, `network`,
  `orchestration` → **3**
- **class_count:** 1; **dominant_class_lines:** 604 (`ProposalExecutor`)

The ProposalExecutor orchestrates atomic actions against the DB,
coordinates the proposal lifecycle, and is the Will→Body bridge. It
has `sqlalchemy` as its only external-domain import
(→ `database`) and picks up `file_io` via `json` (the keyword
`json` is in the `file_io` bucket). Its actual work — `await` dispatch,
state transitions, data access — is three responsibilities under
`_detect_responsibilities`. The concern count is exactly 2, the rule
fires, and the "single coherent responsibility" framing is wrong for
this file.

**Common shape across the 21.** Every CLASSIFIER-BLIND finding is a
file whose responsibilities are expressed through *internal* or
*stdlib* modules the concern classifier is blind to. Of the 21, 17
have at least one dominant top-level class accounting for >70% of
class-owned lines; 4 are pure-function or multi-class modules. The
category is robust to dominant-class presence precisely because the
first-match ordering of the taxonomy puts CLASSIFIER-BLIND ahead of
DOMINANT-CLASS.

## 5. Counterfactual — what if `_detect_responsibilities` replaced `_identify_concerns` inside `check_needs_split`?

Direct replacement: keep everything else in the check the same, but
compute `resps = self._detect_responsibilities(content)` and fire when
`len(resps) <= 2`. Evaluated against current code (counterfactual data
in `.artifacts/counterfactual.json`):

| Effect | Count |
|---|---|
| Currently flagged, would **drop** (`resp ≥ 3`, no longer fires)         | **21** |
| Currently flagged, would **remain** flagged (`resp ≤ 2`, still fires)   | **11** |
| Not currently flagged, would **become** flagged (`resp ≤ 2`, > 400 LOC) | **0**  |

**Findings that would drop.** All 21 come from CLASSIFIER-BLIND — these
are files with `responsibilities ≥ 3` where the content-based
classifier sees multi-responsibility shape that the rule statement's
"single coherent responsibility" premise excludes. Three examples:

1. `src/cli/resources/runtime/health.py` (779 LOC, resp=4 —
   `data_access`, `network`, `orchestration`, `presentation`). The
   CLI resource rendering health dashboards while coordinating DB
   and network calls; four responsibilities under content
   classification, rule no longer fires.
2. `src/shared/infrastructure/context/builder.py` (742 LOC, resp=3 —
   `data_access`, `io_operations`, `network`). The ContextBuilder
   at the heart of the context-build pipeline; the
   multi-responsibility shape is real and the rule correctly stops
   claiming "coherent" for it.
3. `src/will/autonomy/proposal_executor.py` (638 LOC, resp=3 —
   `data_access`, `network`, `orchestration`). The Will→Body
   bridge; three responsibilities under content classification,
   rule no longer fires.

**Findings that would remain.** All 11 come from DOMINANT-CLASS (6),
INTERNAL-MODULE-NO-SIGNAL (4), and UNCATEGORIZED (1) — files with
`responsibilities ≤ 2`, which the rule statement's "single coherent
responsibility" premise correctly covers. Three examples:

1. `src/shared/path_resolver.py` (403 LOC, resp=2 — `io_operations`,
   `validation`). Single-class file doing path resolution; content
   is one cohesive concern with validation guards. Rule still fires.
2. `src/will/strategists/fix_strategist.py` (467 LOC, resp=2 —
   `orchestration`, `validation`). Strategist under BaseStrategist;
   dominant class 430/467 lines. Rule still fires.
3. `src/will/workers/audit_violation_sensor.py` (434 LOC, resp=1 —
   `network`). A Worker whose external signal is essentially
   `await`-dispatch; one responsibility picked up. Rule still fires.

**Files that would be newly flagged: none.** The counterfactual scan
over every `src/**/*.py` > 400 LOC (88 files in total, excluding
`__init__.py`) found zero files with `responsibilities ≤ 2` that are
not already flagged by the current rule. This means the replacement
would be *strictly narrowing* — it removes false positives without
introducing false negatives against the current codebase. (It does
not prove the replacement classifier is *itself* calibrated; see §8.)

## 6. Autonomy implications

`modularity.needs_split` is mapped in
`.intent/enforcement/remediation/auto_remediation.yaml` at
**Tier 2 ACTIVE, confidence 0.85, risk=high**, with `action:
fix.modularity`. The description states: "Phase 1 (Architect) finds
the seam. Phase 2 (RefactoringArchitect) executes. Logic Conservation
Gate validates before any write. Defers automatically on low/medium
confidence." Proposals are created automatically; a human approval
gate sits before execution. What the daemon would do against each
category:

- **CLASSIFIER-BLIND (21/32).** The split LLM receives a file the
  rule claims is single-coherent but that actually contains 3–4
  responsibilities. Phase 1 will either (a) find a seam along the
  hidden responsibility boundary — in which case the split is
  architecturally sound but the finding it answered was
  mis-described, or (b) split by size without respecting the
  responsibility boundary — mechanically sound but governance-hollow.
  Neither outcome is a faithful response to the stated rule. Logic
  Conservation Gate validates behavior preservation, not
  responsibility-seam fidelity, so it would not catch case (b).

- **DOMINANT-CLASS (6/32).** The file is one large class accounting
  for >70% of class-owned lines. A file-level split ("mechanical
  redistribution, no discipline boundaries crossed", per the rule's
  rationale) is undefined here — you cannot split one class across
  two files without making a type-identity decision that *is* a
  discipline boundary. The likely daemon outcome is either deferral,
  an artificial split of the class's methods into a helper module,
  or a generic "split by size" output that the Logic Conservation
  Gate passes but whose human readability regresses.

- **INTERNAL-MODULE-NO-SIGNAL (4/32).** The rule fires on file size
  alone; the classifier has no meaningful signal. The daemon has no
  "responsibility" to split along. Outcome is the same shape as
  DOMINANT-CLASS: a mechanically valid but semantically arbitrary
  split. 3 of the 4 are Will-layer Workers — a layer where file size
  is often a function of blackboard-contract boilerplate, not of
  mixed responsibilities.

- **UNCATEGORIZED (1/32).** `src/will/interpreters/request_interpreter.py`
  has 5 top-level classes and 2 responsibilities — below every
  classification bar. Daemon behaviour here is equivalent to
  INTERNAL-MODULE-NO-SIGNAL.

A blunt framing: under the current rule, `fix.modularity` at tier 0.85
runs an LLM refactor whose *input premise* — "this file has one
coherent responsibility" — is false for 21/32 findings and unprovable
for 11/32. The remediation is only aligned with the rule for the 0
findings where both classifiers agree on coherence.

## 7. Options for the governance decision

Four options, weighted by the evidence above. Not ranked; the governor
decides.

### A. Retire the rule as currently implemented

- **Supports:** The rule fires on 32 files, 0 of which meet the
  "single coherent responsibility" premise by the content-based
  classifier. The blocking counterpart `modularity.needs_refactor`
  already handles the multi-discipline case. `check_refactor_score`
  already produces a multi-dimensional score on every file. Retiring
  removes a rule whose statement and implementation are decoupled.
- **Opposes:** The rule is *reporting*, not blocking; it does not
  halt CI. Retirement loses the one signal CORE has for "this file
  should be split along coherent seams" even if today's signal is
  miscalibrated. The daemon's `fix.modularity` action loses its
  trigger, though `fix.modularity` is already constrained by human
  approval.
- **Test burden:** Low. Remove the rule object from
  `.intent/rules/code/modularity.json`, the mapping from
  `.intent/enforcement/mappings/code/modularity.yaml`, and the
  Tier-2 entry. Audit re-run drops 32 findings. No code change.

### B. Replace `_identify_concerns` with `_detect_responsibilities` inside `check_needs_split`

- **Supports:** Counterfactual shows this is *strictly narrowing*: 21
  drop, 11 remain, 0 new flags. The replacement aligns the check's
  computation with the check's sibling `check_refactor_score`, which
  already uses the content classifier for the responsibility
  dimension. Zero false negatives against current code.
- **Opposes:** 11 remaining findings include files with a dominant
  top-level class — §6's "class cannot be split across files without
  a discipline boundary" critique survives the replacement. It fixes
  the classifier blindness but does not fix the autonomy mismatch
  for those files. Also: `_detect_responsibilities` has its own
  calibration risk — its regex patterns (e.g. `r"\.query\("` matches
  `q.query(` which could be any query-shaped method, not just a DB
  query) have not been validated by this diagnostic.
- **Test burden:** Medium. One-line implementation change, plus
  tests for: rule still fires on low-responsibility oversized
  files; rule no longer fires on multi-responsibility files; no
  regression in `check_refactor_score`. Integration test against
  the 32 current findings as a golden set.

### C. Widen `IMPORT_CONCERNS` to include internal module prefixes

- **Supports:** Directly addresses the "internal imports carry no
  concern weight" gap. A pattern-matched bucket like `{"body":
  ["body.atomic", "body.services", ...], "will": ["will.autonomy",
  "will.workers", ...]}` would give the import classifier visibility
  into files whose responsibilities are expressed through internal
  modules. Preserves `_identify_concerns` as the check's classifier
  (less code churn than option B).
- **Opposes:** The rule statement says "concern" but the expanded
  bucket would effectively mean "internal layer/sub-module" — a
  different semantic. `body.services.blackboard_service.py` (16
  internal imports, all `body.services.*`) would gain 1 concern
  under naive layer-bucketing, no more. Widening to sub-module
  granularity (e.g. `body.atomic` vs `body.services` vs
  `body.workers`) is more informative but effectively measures
  internal coupling spread, which has no clean mapping to the
  existing IMPORT_CONCERNS vocabulary (`database`, `web`, `cli`,
  `ml`, `file_io`, `testing`). The `IMPORT_CONCERNS` comment
  explicitly argues *against* this widening.
- **Test burden:** High. Requires authoring a principled internal
  concern taxonomy; every test that depends on `_identify_concerns`
  output is affected; `check_refactor_score` and
  `check_needs_refactor` both consume `_identify_concerns` and would
  change behaviour too — the blast radius extends beyond
  `check_needs_split`.

### D. Leave as-is, but update the rule statement to match

- **Supports:** The implementation is cheap, well-tested (stable for
  months), and produces a consistent per-file signal. The mismatch
  is between the rule *statement* and the rule *implementation*, not
  between the implementation and the codebase. Rewriting the
  statement to say "A source file that exceeds the line limit AND
  has narrow external-domain exposure (≤2 concern buckets)
  SHOULD…" resolves the mismatch by accepting the operational
  semantics as the law. `modularity.needs_refactor` remains the
  multi-discipline gate.
- **Opposes:** The current statement is load-bearing elsewhere —
  the `fix.modularity` remediation description ("Files exceeding
  line limit with single coherent responsibility are split…")
  assumes coherence. The Evidence Ledger and Prior Art narrative
  both cite "coherent responsibility" as the pass criterion. An
  honest statement revision would propagate into the remediation
  YAML and the whitepaper §4 claim. And the autonomy implication
  in §6 does not go away — it merely gets relabelled: now the
  daemon runs `fix.modularity` against files with narrow external
  imports, a criterion even more obviously arbitrary than "single
  coherent responsibility."
- **Test burden:** Low in code, high in governance documents. No
  src/ change. Requires ADR + statement rewrite + remediation
  description rewrite + narrative update.

## 8. What this diagnostic does not establish

1. **Whether `_detect_responsibilities` is itself well-calibrated.**
   The counterfactual in §5 proves only that replacement would be
   narrowing *relative to the current set of flagged files*. The
   regex patterns (`r"\.query\("`, `r"\.render\("`, etc.) are
   substring matchers; none were validated against a golden set of
   labelled files in this session. A file that legitimately has one
   concern but happens to contain `await ... .execute(` (matches
   `orchestration`) and `Path(` (matches `io_operations`) and
   `validate_` (matches `validation`) would score 3 under the
   replacement and drop out of the needs_split finding set. No such
   case surfaced in the counterfactual scan, but the absence of new
   false negatives in one snapshot is not calibration proof.

2. **Whether the DOMINANT-CLASS findings benefit from class-internal
   splits the check cannot evaluate.** 22 of 32 findings (69%) have
   a dominant top-level class. A long class can be legitimately
   broken into private method groups, mixin classes, or composed
   sub-objects. None of `check_needs_split`,
   `check_refactor_score`, or `_detect_responsibilities` evaluates
   intra-class structure. A fair answer to "is this class too long?"
   requires tooling that does not exist in the current checker.

3. **Historical DEGRADED or FAIL runs against `needs_split`
   findings.** The current finding set is a single snapshot. Whether
   past audits have seen `modularity.needs_split` crash, be skipped,
   or be force-filtered via the `governance.auto_ignore` surface
   would change the operational story — an auto-ignored finding
   behaves differently from a reported one. This diagnostic did not
   inspect `reports/audit_auto_ignored.*` or the rule executor's
   historical crash rate for this check.

4. **The interaction with `modularity.needs_refactor`.** Both checks
   consume the same `_identify_concerns` output. `needs_refactor`
   fires when `len(concerns) > 3`, `needs_split` fires when
   `len(concerns) <= 2`. The narrow band `len(concerns) == 3` is the
   only value for which neither rule fires. This diagnostic did not
   tabulate how many files fall in that band, nor whether any
   CLASSIFIER-BLIND file would cross into `needs_refactor` under
   option C's widening.

5. **The Logic Conservation Gate's actual coverage.** §6 asserts
   that the LCG validates "behavior preservation, not
   responsibility-seam fidelity." The LCG's invariants were not
   read during this recon; that claim should be verified before
   weighting option B.

---

*End of diagnostic. No `.intent/` or `src/` changes were made in
this session. Artifacts for reproduction are in the sibling
`.artifacts/` directory.*
