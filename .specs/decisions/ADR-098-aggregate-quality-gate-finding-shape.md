<!-- path: .specs/decisions/ADR-098-aggregate-quality-gate-finding-shape.md -->

# ADR-098 — Aggregate quality-gate finding shape: per-file emission with iceberg-tail rendering

**Date:** 2026-06-09
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-09, after #603 triage surfaced that three quality.* rules collapse 764 mypy errors and 3 dependency vulnerabilities into 1 INFO finding each. Recon found the collapse is a single line — `quality.py:48` discards everything after the first stdout line. The fix is local; the ADR question is the shape — what the audit *should* render so the governor's drain-by-leverage triage doesn't keep mis-ranking icebergs as singletons. The governor instructed inclusion of the adjacent declared-advisory-but-emitted-BLOCK drift surfaced during recon.)
**Grounding paper:** NorthStar — *"everything is written down, nothing is assumed silently."* The audit's row-shape is part of "written down"; when 764 errors render as 1 INFO, the iceberg is silently assumed.
**Related:**
- #603 (the originating issue; this ADR is its requested resolution).
- #602 (mypy debt — 764 errors; the case this ADR makes visible).
- #600 (starlette/pip vulnerabilities — 3 vulns; the second case).
- ADR-059 D2 (the five-tier severity scale INFO/LOW/MEDIUM/HIGH/BLOCK; D4 of this ADR enforces that runtime emission must respect the declared tier).
- ADR-076 D1/D2 (workflow_gate dispatches at context level for all twelve check types; the change here lives inside the existing context-level dispatch shape).
- ADR-081 D8 Step 1 (audit-violation isolation worker; D5 of this ADR names the constraint that bounds when per-finding fanout becomes safe to wire downstream).
- Memory: `[[iceberg-class-findings]]` — the structural read this ADR formalizes.
- Memory: `[[count-from-source-not-narrative]]` — why the audit dashboard must show counts derivable from source, not summaries.

---

## Context

Three rules in `.intent/rules/architecture/quality_gates.json` wrap external multi-issue tools through one shared engine path:

| Rule | check_type | External tool | Issue scale (verified 2026-06-09) |
|---|---|---|---|
| `quality.type_safety` | `mypy_check` | mypy | 764 errors across 289 files |
| `quality.security_audit` | `security_check` | pip-audit | 3 CVEs across 2 packages |
| `quality.test_integrity` | `pytest_check` | pytest --collect-only | variable |

All three dispatch to `workflow_gate` engine with `check_type` param, run the external command, and emit findings via `QualityGateCheck.verify` at `src/mind/logic/engines/workflow_gate/checks/quality.py`.

### Where the collapse happens — exactly

`quality.py:48-49`:

```python
output = stdout.decode().strip() or stderr.decode().strip()
error_msg = output.split("\n")[0]                                # ← here
return [f"Quality Gate {self.check_type} failed: {error_msg}"]
```

The check reads stdout, **discards every line after the first**, returns one violation string. The engine (`workflow_gate/engine.py:131-153`) wraps each violation string in one `AuditFinding`. Net result: 764 mypy errors → 1 string → 1 finding.

The collapse is **not** in `AuditFinding`'s shape (`context: dict[str, Any]` is already free-form), not in the ingest pipeline, not in the renderer. Three lines of code in one check class collapse the entire iceberg.

### Why the shape matters even though the fix is local

If the collapse is fixed by "emit one finding per error" without thinking about the shape, three downstream costs land at once:

1. **Audit-row volume.** `audit_renderer.py:93` computes `Total findings: len(findings)`. Going from 33 INFO to ~800 INFO per audit run buries actually-actionable per-file findings under quality.* noise. The dashboard becomes harder to read, not easier.

2. **Ingest-pipeline blast radius.** `will/workers/audit_ingest_worker.py:177` selectively posts findings matching a `_TARGET_RULE` to the blackboard as subjects. Today it filters for one architecture rule — quality.* is unwired. The moment a sensor wires quality.* in, 764 findings → up to 764 blackboard subjects per audit run → an autonomous-remediator flood that ADR-081 D8 isolation does not bound (it isolates the *worker process*, not the row count).

3. **Remediation actionability.** A per-mypy-error finding cannot be remediated through the proposal pipeline today — there is no `fix.mypy_error` atomic action that takes `(file_path, line, error_code)`. Per-error fanout produces data the system cannot act on. Per-file fanout produces data with at least one tractable action shape (`build.tests` for missing tests, `fix.imports` for import-resolution, etc.).

### Adjacent drift surfaced by recon — declared-advisory but emitted-BLOCK

`quality_gates.json` declares all three rules `enforcement: "advisory"`. The engine at `workflow_gate/engine.py:139,148,159` hardcodes `severity=AuditSeverity.BLOCK` on every finding it emits. The declared tier and the emitted severity are *not* the same axis structurally — `enforcement` is the rule-level governance decision (does this block CI), `AuditSeverity` is the finding-level rendering label (how does it display) — but the emission layer is reading neither. Findings are hardcoded BLOCK regardless of what the rule declares.

The reason the audit summary calls quality.type_safety "INFO" today is downstream: something in the auditor verdict / rendering chain re-maps BLOCK findings down to INFO when the parent rule is declared advisory. That re-mapping is not what the audit display *should* be doing — it's masking the drift. **The drift is real and adjacent to #603's framing.** A rule declared advisory should produce findings that render at the advisory tier directly, not at BLOCK with a downstream re-map. Otherwise the same emission path applied to a *blocking* rule would also wrongly emit BLOCK regardless of the rule's intent.

D4 below makes the severity-derivation explicit — runtime emission must respect declared enforcement — so the fix to #603 and the fix to the drift land in the same place.

### Constraints inherited

- **ADR-076 D1/D2.** All twelve workflow_gate check_types are context-level. This ADR's per-file fanout is still *context-level dispatch* — the engine runs once per check_type and emits N findings — not per-file dispatch. The change is internal to `verify_context`'s result loop.
- **ADR-059 D2.** Five-tier severity (INFO/LOW/MEDIUM/HIGH/BLOCK). D4 below ties runtime emission to this scale via the rule's declared `enforcement` field; new mapping table specified in D4.
- **ADR-081 D8 Step 1.** Audit-violation isolation isolates the *executor process*. It does not bound finding count or rate. D5 of this ADR specifies the wiring constraint that bounds when quality.* sensor hookup is safe.
- **NorthStar honesty principle.** The audit dashboard is governance proprioception. When it shows a number, that number must be derivable from source. The current shape — 1 INFO meaning 1 or 764 — violates this directly.

---

## Decisions

### D1 — Aggregate quality gates emit per-affected-file findings, not per-tool findings

The `QualityGateCheck` (and any future check wrapping a multi-issue external tool) emits **one `AuditFinding` per affected file**, where "affected file" is the natural unit of the wrapped tool's output:

| Tool | "Affected file" unit | Mapping |
|---|---|---|
| `mypy` | repo path | one finding per `src/foo.py`; `context.error_count` = errors in that file |
| `pip-audit` | dependency package | one finding per affected package (file_path = `pyproject.toml`); `context.vuln_count` = CVEs against that package |
| `pytest --collect-only` | test file with collection error | one finding per `tests/foo.py`; `context.collection_errors` = list of import/collection errors |

Files / packages with zero issues produce zero findings. The total finding count from a quality.* rule equals the number of affected files (mypy: ~289 today), not the issue count (mypy: 764) and not 1.

**Why per-file, not per-issue.** Per-issue (Option 1 from #603) is 800× row growth with no downstream actionability — no atomic action takes a single mypy error. Per-file is bounded by the natural unit the tools themselves report against (every tool above outputs file-keyed records), produces a `file_path` that means what `file_path` means everywhere else in the finding pipeline, and degrades cleanly to the proposal layer when the time comes (`build.tests` for pytest collection errors operates on file_path; `fix.mypy_in_file` if it ever ships would too).

**Why not aggregate-with-occurrences (Option 2 alone).** The aggregate-with-occurrences shape preserves the `len(findings) == 1` lie. The summary table would still say "quality.type_safety: 1" — readable correctly only by someone who knows to expand the `context.occurrences` field. The honesty principle says the *summary row count* must match reality. Per-file emission makes that automatic. Occurrences-as-tail (D2) is the *complementary* piece: per-file gives accurate row counts; per-issue-tail-in-context gives drill-down depth.

### D2 — Each finding carries structured occurrence data in `context`

`AuditFinding.context` is already `dict[str, Any]`. This ADR specifies the canonical key set for aggregate-quality-gate findings so the renderer (D3) and any future remediator can rely on it:

```python
finding.context = {
    "tool": "mypy" | "pip_audit" | "pytest_collection" | str,
    "issue_count": int,              # errors in this file / vulns in this package / collection errors
    "sample_issues": list[str],      # up to first 10 raw issue strings, for the detail panel
    "first_issue_line": int | None,  # for tools that report line numbers; null otherwise
}
```

`issue_count` ≥ 1 for any emitted finding (a file with zero issues produces no finding). `sample_issues` is capped at 10 items to keep finding payloads bounded — the full output remains accessible by re-running the tool. `tool` is a string, not an enum, so future aggregate gates (D6) extend without ADR amendment.

No schema migration. `AuditFinding.as_dict()` already serializes `context` as both `context` and `details` (legacy alias). Existing consumers that ignore `context` continue to work; consumers that read it gain the structured payload.

### D3 — Renderer displays an iceberg-tail indicator for findings with `context.issue_count > 1`

`cli/renderers/audit_overview.py` and `cli/renderers/audit_detail.py` extend their finding-row rendering to inspect `context.get("issue_count")`:

- **Overview table** (severity-grouped summary): when a quality.* finding has `issue_count > 1`, the file_path cell renders `src/foo.py (×25)` — a single suffix making the iceberg visible in the per-file row. Total-issue rollup per check_type appears in the section header: `quality.type_safety — 289 findings, 764 underlying issues`.
- **Detail panel** (per-finding expansion): `context.sample_issues` renders as a bullet list under the message, capped at the stored 10 items, with a footer "(showing 10 of 25; re-run mypy for full output)" when truncated.

The rendering is **opt-in via context inspection**, not a new column. Findings without `context.issue_count` (every non-quality-gate finding today) render unchanged. The renderer change is bounded to two functions; no per-rule special-casing.

### D4 — Emitted finding severity is derived from the rule's declared enforcement

`QualityGateCheck` and `WorkflowGateEngine.verify_context` stop hardcoding `severity=AuditSeverity.BLOCK`. The engine receives the rule's declared `enforcement` field from the dispatch layer (it is already loaded by `IntentRepository` and passed through to engine instances; the workflow_gate path drops it) and maps to `AuditSeverity` via this canonical table:

| Declared `enforcement` | Emitted `AuditSeverity` |
|---|---|
| `blocking` | `BLOCK` |
| `reporting` | `MEDIUM` |
| `advisory` | `INFO` |

The three quality.* rules declared `advisory` will therefore emit `INFO` directly — matching what the audit summary already shows today — without the downstream BLOCK→INFO re-map that masks the drift.

**Scope.** This mapping is **not specific to quality gates**. It is the canonical rule-to-finding severity derivation that all engines should follow. The workflow_gate engine is the first site to fix because it is the most visibly wrong; other engines that hardcode severity get a follow-up ticket to apply the same derivation. This ADR mandates the mapping at the rule→finding boundary; per-engine cleanup is sequenced (see Migration step 5).

**Severity escalation by issue count is explicitly rejected.** Option 3 from #603 (advisory→BLOCK if `issue_count > N`) was considered. It crosses the declared-enforcement boundary in the opposite direction — running-tier promotion of a declared-advisory rule. If the governor decides 764 mypy errors should block CI, the correct response is to promote `quality.type_safety` from `advisory` to `blocking` in `.intent/rules/architecture/quality_gates.json` (a one-line governance change), not to add count-based runtime escalation. The rule's tier is the governance authority; runtime emission respects it.

### D5 — Audit-ingest wiring constraint for multi-finding quality rules

`will/workers/audit_ingest_worker.py:163-204` currently filters by a single `_TARGET_RULE` constant and posts each matching finding as a blackboard subject. When (not if) a sensor wires quality.* rules in, the per-file fanout of D1 means 289 mypy findings could become 289 blackboard subjects per audit run — a remediation-pipeline blast radius that ADR-081 D8 worker isolation does not bound.

**Constraint.** Audit-ingest hookup of any rule emitting >1 finding per run requires:

1. **Subject-bounded posting per run.** The ingest path posts at most `quality_ingest_cap` findings per (rule, run) — config-driven, default 25, in `.intent/enforcement/config/audit_ingest.yaml`. Findings beyond the cap remain in the audit-run output (visible to the governor) but do not become blackboard subjects.
2. **Sample-of-tail policy.** When the cap fires, the ingest path posts the top-`quality_ingest_cap` findings ordered by `issue_count` descending — i.e., the files with the most errors get blackboard subjects first, the long tail is visible only in the audit dashboard.
3. **Dedup respects the per-file shape.** Existing `fetch_open_finding_subjects_by_worker` dedup keys on subject string. The subject construction for quality.* findings includes `file_path` so re-runs against the same affected files do not multiply subjects.

This ADR does not specify the sensor that does the hookup — it specifies the *constraint that hookup must satisfy*. The sensor is filed separately when prioritized.

### D6 — Generalization: the shape applies to any aggregate external gate

The per-affected-file + structured-context shape (D1+D2+D3) is the canonical aggregate-quality-gate finding shape, not specific to the three rules in the table. Future rules wrapping multi-issue external tools — `vulture` for dead code, `bandit` for security AST checks, `license-checker` for dependency licenses, `semgrep` for pattern-based audit, others — extend the `tool` enum-string in `context` and route through the same `QualityGateCheck`-shaped emitter. The renderer code (D3) reads `context.issue_count` without caring which tool produced it. The severity derivation (D4) reads the new rule's declared enforcement without caring what it wraps.

The corollary: when a new aggregate gate ships, the work is (i) author the `.intent/` rule JSON and YAML mapping, (ii) extend `QualityGateCheck.verify` (or sibling class) with the tool-specific output parsing, (iii) no renderer change, no severity-mapping change, no ingest-pipeline change. **The aggregate-gate shape is settled by this ADR.**

---

## Migration

Sequencing (each step verifiable independently):

1. **Land the canonical severity-mapping table** as a small utility — `src/shared/models/severity_mapping.py` or extension of `audit_models.py` — exposing `severity_for_enforcement(enforcement: str) -> AuditSeverity`. Pure function; no consumer yet. Test it.
2. **Plumb declared `enforcement` through the workflow_gate dispatch path.** Today `verify_context` receives `params` (a dict) containing `check_type` but not the rule's declared enforcement. The dispatch layer (`mind/governance/rule_executor.py` or equivalent) has the rule object — it must pass `enforcement` through `params` or a sibling channel. This step is plumbing-only; no behavior change yet (engine still hardcodes BLOCK).
3. **Rewrite `quality.py:verify` per D1+D2.** Each `check_type` parses its tool's output into a list of `(file_path, context_dict)` pairs and returns them as structured violations (not bare strings). The output-parsing logic is per-tool, lives inside `QualityGateCheck`, and is bounded — mypy ~15 lines, pip-audit ~20 lines, pytest collection ~10 lines. **Verification: `core-admin code audit` shows quality.type_safety finding count rise from 1 to ~289 (the affected-file count), quality.security_audit from 1 to ~2 (the affected-package count).**
4. **Update `engine.py:verify_context`** to construct each `AuditFinding` with `severity=severity_for_enforcement(rule.enforcement)`, `file_path=violation.file_path`, `context=violation.context`. Hardcoded `BLOCK` lines (139, 148, 159) removed. **Verification: quality.* findings now emit `INFO` directly (declared advisory); audit summary should look numerically identical to before this step at the severity-rollup level, while per-finding rows now show real file paths and `(×N)` annotations.**
5. **Audit other engines for the same hardcoded-severity drift.** `ast_gate`, `cli_gate`, `runtime_gate`, `taxonomy_gate`, `artifact_gate`, `knowledge_gate` — each gets a quick sweep of its `AuditFinding(... severity=...)` call sites. Any site that hardcodes BLOCK against a non-blocking rule is filed as a follow-up. (Not gated on this ADR; this ADR mandates the principle, sequencing follows.)
6. **Extend `audit_overview.py` and `audit_detail.py`** per D3. The per-file-row `(×N)` annotation, the section-header rollup, the bullet-list of sample_issues. Bounded change in two files. **Verification: visual diff on a fresh `core-admin code audit --rich` against the same commit pre/post; quality.type_safety section should read "289 findings, 764 underlying issues" with per-file `(×N)` annotations.**
7. **Land `.intent/enforcement/config/audit_ingest.yaml`** with `quality_ingest_cap: 25` and an empty `enabled_rules:` list. Loader code in `audit_ingest_worker` reads the cap and exposes a helper. **No sensor wiring yet** — this is the constraint substrate D5 specifies, ready for the future sensor hookup.

Steps 1–4 are landing-order-coupled. Step 5 is a sweep that follows. Steps 6–7 land independently after step 4 bakes one audit cycle.

## Verification

- **Honest count check.** Post-step-4, `core-admin code audit` shows `quality.type_safety: N` where N is the number of files with mypy errors (verifiable: `mypy src/ --ignore-missing-imports | awk -F: '{print $1}' | sort -u | wc -l`). The audit's number and the grep's number must agree. Similarly `quality.security_audit: M` where M is the number of affected packages from `pip-audit`.
- **Severity-shape regression check.** Pre-step-4, `core-admin code audit --json` shows quality.* findings with `severity: "block"` (the current hardcoded emission, masked downstream to "info" in summary). Post-step-4, the same JSON shows `severity: "info"` (declared advisory) directly. **The summary display number must not change** — the change is internal-shape honesty, not surface count.
- **Iceberg-visibility check.** A fresh session reading the audit dashboard with no prior context can answer "how big is the mypy debt" from the rendered output. Today the answer is "1, looks small"; post-step-6 the answer is "289 files affected, 764 underlying errors." The honesty principle is satisfied when the proprioceptive number matches the source-derived number.
- **Wiring-constraint check.** Step 7 lands `audit_ingest.yaml` with cap=25. A unit test posts 100 synthetic quality.* findings to a stub ingest path, asserts that exactly 25 blackboard subjects are created, ordered by `context.issue_count` descending. Without this test, the constraint is documented but unenforced.
- **Generalization-readiness check.** Add a single synthetic test case wrapping `echo`-as-vulture-substitute through `QualityGateCheck` with a stub parser. Assert that the renderer treats its findings identically to the production mypy_check findings without any code change to the renderer. This verifies D6's claim that the shape generalizes by extension, not by amendment.

## Out of scope

- **The `audit_ingest_worker` quality.* sensor wiring itself.** D5 specifies the constraint that wiring must satisfy; the wiring is its own follow-up when prioritized. Today no quality.* finding becomes a blackboard subject. This ADR does not change that.
- **Per-mypy-error remediation.** No `fix.mypy_error` atomic action is proposed. `quality.type_safety` findings remain governor-actionable (read the dashboard, decide what to drain), not autonomously remediable. Per-file granularity makes a future `fix.mypy_in_file` (or `build.tests`-style proposal) tractable; this ADR does not author it.
- **The 764 mypy errors themselves.** #602 tracks the substantive drain. This ADR makes the iceberg visible; the work to drain it is separate.
- **The starlette / pip CVEs.** #600 tracks the substantive fix. Same separation.
- **Other engines' hardcoded-severity sites.** Migration step 5 identifies them; per-engine fixes follow this ADR's principle but land in their own change-sets.
- **Replacing `audit_renderer.py`'s `len(findings)` totalizer.** Total findings count remains `len(findings)` post-D1 — it now reflects the real per-file count instead of the collapsed 1, which is the desired outcome. No totalizer-logic change needed.

## References

- #603 — Audit shape: aggregate quality gates collapse N issues into 1 finding (originating issue).
- #602 — Mypy debt: 764 errors across 289 files (the iceberg under quality.type_safety).
- #600 — Starlette/pip vulnerabilities (the iceberg under quality.security_audit).
- ADR-059 D2 — Five-tier audit severity scale (INFO/LOW/MEDIUM/HIGH/BLOCK); D4 of this ADR derives runtime emission from declared enforcement against this scale.
- ADR-076 D1/D2 — Workflow_gate context-level dispatch; this ADR works inside the existing dispatch shape.
- ADR-081 D8 Step 1 — Audit-violation worker isolation; D5 of this ADR names the row-count blast-radius that worker isolation does not bound.
- `src/mind/logic/engines/workflow_gate/checks/quality.py:48` — the line where collapse happens today.
- `src/mind/logic/engines/workflow_gate/engine.py:139,148,159` — the hardcoded `severity=AuditSeverity.BLOCK` sites D4 removes.
- `src/shared/models/audit_models.py:43-101` — `AuditFinding` and `AuditSeverity`; the structural surfaces this ADR uses without modifying.
- `src/will/workers/audit_ingest_worker.py:163-204` — the ingest path D5 constrains for future quality.* wiring.
- Memory: `[[iceberg-class-findings]]` — the structural read this ADR formalizes.
- Memory: `[[count-from-source-not-narrative]]` — the honesty principle the per-file shape satisfies.
- Memory: `[[ramp-arc-three-phase-pattern]]` — the implementation arc this ADR follows (ship reporting at correct severity, resolve drifts via D4 mapping, future promote-to-blocking is a `.intent/` rule edit not a runtime escalation).
