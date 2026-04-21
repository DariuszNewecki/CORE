# ADR-007: `modularity.class_too_large` — rule split from `modularity.needs_split`

**Status:** Accepted
**Date:** 2026-04-21
**Authors:** Darek (Dariusz Newecki)

## Context

ADR-006 aligned `check_needs_split` with its rule statement by switching the gate from `_identify_concerns` (import-based coupling) to `_detect_responsibilities` (content-pattern responsibilities). Findings fell from 32 to 11. Audit: PASS, 18 total.

Inspection of the surviving 11 findings shows 9 are **dominant-class files** — a single top-level class whose line span (`end_lineno - lineno + 1`) exceeds the `max_lines` threshold the check uses. The remaining 2 are module-level multi-symbol files where mechanical redistribution via `fix.modularity` (Architect → RefactoringArchitect flow) works as intended.

The rule statement for `modularity.needs_split` is:

> A source file that exceeds the line limit AND contains a single coherent responsibility SHOULD be split into smaller files along natural seams. The logic must be preserved exactly — splitting is mechanical redistribution, not refactoring.

The rationale:

> Files that are too long but internally coherent are a modularization problem. They are automatable — the system can propose and execute splits without human judgment because **no discipline boundaries are crossed**.

For the dominant-class subset, the rationale is false. When one class occupies more than the file's line budget, the "single coherent responsibility" *is* that class. Any split either:

1. Tears methods off the class into module-level functions or sibling classes — an OOP-to-procedural restructure, which crosses a discipline boundary (shared state, method resolution order, encapsulation invariants).
2. Decomposes the class into collaborators — a semantic refactor requiring a human decision about what the class is *for*.
3. Leaves the class intact in a subpackage — does not reduce the class's line count, so the finding persists.

None of these is mechanical redistribution. The rule's rationale disclaims exactly this case while the rule fires on it.

## Decision

Introduce `modularity.class_too_large` as a distinct rule. The sensor layer routes findings via a deterministic structural test using two sensor methods, matching the existing 1-rule-to-1-method pattern in this module (`check_needs_split` / `check_needs_refactor`).

### New rule

Added to `.intent/rules/code/modularity.json`:

- **id:** `modularity.class_too_large`
- **statement:** A source file in which a single top-level class exceeds the file-size line limit SHOULD be reviewed by a human before remediation. Autonomous mechanical redistribution is not permitted for this class of finding.
- **rationale:** A class that by itself exceeds the file's line budget cannot be resolved by module-level extraction — the problem lives inside the class. The correct response (domain-warranted bigness, extract collaborators, compose over inherit, split into a subpackage with preserved invariants) requires a human judgment about what the class is *for*. The system cannot make this determination and must not preempt it with mechanical action.
- **enforcement:** `reporting`
- **authority:** `policy`
- **phase:** `audit`

### Sensor change

In `src/mind/logic/engines/ast_gate/checks/modularity_checks.py`:

**New private helper `_find_dominant_class(tree: ast.AST, loc: int) -> tuple[str | None, int, float]`.** Returns `(name, lines, ratio)` for the top-level `ClassDef` with the most methods (`FunctionDef` + `AsyncFunctionDef` in body). Returns `(None, 0, 0.0)` if no top-level class has methods. Lines computed as `end_lineno - lineno + 1`. Ratio computed as `lines / loc`. Method-count ranking matches the existing heuristic in `_extract_class_methods_context` (the closest downstream consumer).

**Modified `check_needs_split` (rule: `modularity.needs_split`).** Existing triggers preserved — `loc > max_lines` AND `len(_detect_responsibilities(content)) <= 2`. New gate added: additionally require `dominant_class_lines <= max_lines`. This defers to `check_class_too_large` whenever the class is the oversize driver, restoring the rule rationale's guarantee that no discipline boundary is crossed for findings it emits. Finding `details` gain three structural fields: `dominant_class_name`, `dominant_class_lines`, `dominant_class_ratio`.

**New `check_class_too_large` (rule: `modularity.class_too_large`).** Trigger: `dominant_class_lines > max_lines`. Self-contained — if a class exceeds `max_lines` the file necessarily does too, so no separate file-level size check is needed. Finding `details` carry the same three structural fields. Does not consult `_detect_responsibilities`; orthogonal to `modularity.needs_refactor` (which checks mixed disciplines independently).

The two methods share `_find_dominant_class` and both re-parse the AST, matching the existing pattern of `check_needs_split` and `check_needs_refactor` coexisting today.

### Mapping change

Add to `.intent/enforcement/mappings/code/modularity.yaml`:

```yaml
modularity.class_too_large:
  engine: ast_gate
  params:
    check_type: modularity
    check_method: check_class_too_large
    max_lines: 400
  scope:
    applies_to: ["src/**/*.py"]
    excludes: ["tests/**", "scripts/**", "**/__init__.py"]
```

The `max_lines: 400` value is duplicated across the `modularity.needs_split` and `modularity.class_too_large` mapping entries. YAML anchors would consolidate it, but the existing file does not use anchors; introducing them for a single case is disproportionate. Accepted coupling — if `max_lines` is ever tuned, both entries must move together.

### Remediation mapping

- `modularity.needs_split` remains in `.intent/enforcement/remediation/auto_remediation.yaml` with `status: ACTIVE` and `action_id: fix.modularity`.
- `modularity.class_too_large` is NOT added to `auto_remediation.yaml`. By existing semantics (rule absent from map → no auto-dispatch), this routes the finding to human review without new infrastructure.

### Gate derivation: `dominant_class_lines > max_lines`, not a ratio

A ratio is a proxy for dominance. The feasibility question the gate must answer is narrower: *can mechanical extraction of module-level material bring the file under `max_lines`?* If the class alone already exceeds `max_lines`, the answer is no. If the class is under `max_lines`, extraction has a mathematical chance.

Using `max_lines` as the gate:

- Is self-calibrating. Reuses the existing check param; no new constant in `.intent/`.
- Directly encodes the capability boundary of `fix.modularity`.
- Approximately matches the 0.70 ratio cutoff observed in current findings (files in the 500–700 line range with a class over 400 lines fall at ~0.70+ naturally), without requiring a ratio constant to be authored or defended.

## Alternatives Considered

**YAML predicate in `auto_remediation.yaml`.** Add an `exclude_when: { dominant_class_ratio: { greater_than: 0.70 } }` clause, keeping the finding under one `rule_id` and gating auto-dispatch at the remediator. Rejected: leaves `modularity.needs_split`'s rationale wrong about 9/11 of its own findings; requires adding a predicate DSL to `ViolationRemediatorWorker`; hides the structural distinction inside a config instead of naming it.

**Single sensor method emitting two rule_ids, one mapping entry.** Rejected: the `ast_gate` engine's handling of an emitted rule_id that differs from the mapping's `rule_id` is untested — it may overwrite, reject, or pass through. Two sensor methods + two mapping entries match the existing 1:1 pattern in `modularity.yaml` (`check_needs_split` / `check_needs_refactor`) and carry no engine-assumption risk.

**Ratio threshold (0.70, 0.85).** Considered as the gate. Rejected in favor of `dominant_class_lines > max_lines`. A ratio does not answer the feasibility question directly; it requires a defended threshold constant; and `max_lines`-based routing tunes automatically if the file-size limit is later adjusted.

**Rank dominant class by method + assignment count** (matching the heuristic inside `ModularitySplitter`'s second-indexing pass). Rejected: method count is a cleaner dominance signal — class-level assignments inflate member count with data that does not signal structural dominance. The existing `_extract_class_methods_context` in the `fix.modularity` action ranks by method count, and that is the closest downstream consumer of this signal.

**Do nothing and let the daemon propose dominant-class splits.** Rejected: crosses the discipline boundary the `modularity.needs_split` rationale disclaims. Would generate proposals the system cannot validate.

## Consequences

**Positive:**

- Rule rationales are now honest per rule. `modularity.needs_split`'s claim of "no discipline boundaries crossed" holds for every finding that fires it.
- The daemon can safely auto-dispatch `fix.modularity` on `needs_split` findings once reactivated. The dominant-class case surfaces for human review via its own rule.
- The feasibility boundary is deterministically encoded — no threshold constant to defend or drift.
- Sensor/mapping design preserves the 1:1 pattern already in use; no new engine assumptions introduced.
- Follows ADR-006's pattern: fix the rule/sensor alignment rather than route around it.

**Negative:**

- Two rules where one existed. Anyone reading the modularity module must now hold both in mind.
- The sensor now makes a structural classification decision across two methods. This is deterministic (AST probe against a file's current `max_lines` param) but is more logic than the prior version.
- `max_lines: 400` duplicated across two mapping entries. Coupling noted above.
- Necessary-not-sufficient for auto-remediation safety. A file with `class_lines = 380, loc = 450` stays in `needs_split`, but `fix.modularity`'s LLM could still propose an unsafe class-split when module-level extraction was sufficient. Closing this gap requires either constraining the `fix.modularity` analyze-phase prompt to disallow class-splits when extraction is feasible, or a post-plan validator. Separate decision.

**Neutral:**

- All 9 current dominant-class findings migrate from `modularity.needs_split` to `modularity.class_too_large`. Total audit finding count unchanged.
- `auto_remediation.yaml` requires no change. Absence of `modularity.class_too_large` from the map means human-only by existing semantics.

## References

- ADR-006 — `check_needs_split` switched to `_detect_responsibilities` (precedent for aligning sensor with rule statement).
- `.intent/rules/code/modularity.json` — `modularity.needs_split`, `modularity.needs_refactor` (existing rule pair this ADR extends).
- `.intent/enforcement/mappings/code/modularity.yaml` — existing 1:1 mapping pattern (`check_needs_split` / `check_needs_refactor`).
- `src/mind/logic/engines/ast_gate/checks/modularity_checks.py` — `check_needs_split`, `_detect_responsibilities`, `RESPONSIBILITY_PATTERNS`.
- `_extract_class_methods_context` in the `fix.modularity` action — precedent for method-count dominance heuristic.
- `ModularitySplitter` second-indexing pass — alternative dominance heuristic considered and rejected for the sensor.
- Follow-up (separate session): constrain `fix.modularity` analyze-phase to disallow class-splits when module-level extraction is feasible; or add a post-plan validator.
