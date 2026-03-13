# Focused Refactor Analysis: src/cli/logic/audit_renderer.py

Model: grok-4-fast-reasoning
Date: March 2026

## Current Problems

This file (`src/cli/logic/audit_renderer.py`) is a classic monolith in a governance-heavy system like CORE, clocking in at approximately 350 LOC (including comments and docstrings). It violates the single responsibility principle by blending multiple concerns: data modeling (dataclasses like `AuditStats` and `RuleGroup`), configuration (dictionaries like `SEVERITY_ENFORCEMENT`, `SEVERITY_ICON`, `SEVERITY_COLOR`, and `FIX_HINTS`), data processing (grouping helpers like `_group_by_rule`, `_group_by_severity`, `_collect_fix_hints`), and presentation logic (rendering functions like `render_overview` and `render_detail`). This creates a "god module" that's hard to navigate, especially in audit flows where governance requires traceable, immutable data transformations.

Specific pain points:
- **Maintainability**: The file is a wall of text with interleaved sections (e.g., data structures followed immediately by helpers, then rendering). Changes to one area (e.g., adding a new severity level) ripple across the file, as seen in how `SEVERITY_*` constants are referenced in multiple places like the severity breakdown loop in `render_overview`: `for severity in (AuditSeverity.ERROR, AuditSeverity.WARNING, AuditSeverity.INFO): count = len(by_severity[severity]) ...`. This increases cognitive load for developers working on CORE's constitutional audits.
- **Testing**: Rendering logic is tightly coupled to data processing and Rich console output, making unit tests brittle. For instance, `_format_location` is a private helper buried in `render_detail`, but it depends on `AuditFinding` fields—testing it requires mocking the entire rendering pipeline. No isolation for declarative workflows (e.g., grouping should be pure functions returning immutable data structures).
- **Governance Flows**: In CORE's audit/governance stack, this file sits in the CLI layer but performs business-like grouping (e.g., `_group_by_rule` sorts by severity and count: `sorted(groups.values(), key=lambda g: (-g.max_severity.value, -g.count))`), blurring Mind (logic) and Body (output) layers. It hinders extensibility for V2/V3 autonomy, like adding JSON exports or integrating with Will's phased rendering, as everything is imperative and console-bound.
- **Conditional Complexity**: `render_overview` has nested conditionals for verdict handling (e.g., `if verdict_str is None: verdict_str = "PASS" if passed else "FAIL"` then `if verdict_str == "DEGRADED": ...`), plus dynamic card_lines building with P0 additions (e.g., `if stats.total_declared_rules > 0: card_lines.append(...)`). This makes it error-prone for edge cases like zero findings or partial coverage.
- **Immutability Gaps**: Helpers like `_group_by_rule` mutate dicts in-place (`groups[f.check_id].findings.append(f)`), violating declarative principles in a system where audits should produce immutable snapshots for governance traceability.

Overall, this file is a modularity offender because it orchestrates too much, reducing reusability in multi-view audit systems (e.g., CLI vs. API rendering).

## High-Level Refactor Strategy

Refactor to enforce clean architecture: separate data models/config from pure functions (grouping/transformations) from composable renderers. Target: Slim the original file to ~100-150 LOC as a thin orchestrator that imports and wires extracted components. Extract to a new `src/cli/renderers/` directory for CLI-specific output logic, aligning with CORE's layered structure (Mind: shared models/utils; Will: phased rendering; Body: console output). This promotes single responsibility—e.g., one module per render phase (overview vs. detail)—and immutability via functional-style grouping (return new data structures, no in-place mutations).

- **New Module Structure**:
  - `src/shared/models/audit_rendering.py`: Dataclasses (`AuditStats`, `RuleGroup`) and constants (`SEVERITY_*`, `FIX_HINTS`).
  - `src/shared/utils/audit_grouping.py`: Pure grouping functions (`group_by_rule`, `group_by_severity`, `collect_fix_hints`—renamed without underscores for public API).
  - `src/cli/renderers/audit_overview.py`: `OverviewRenderer` class for health card, severity breakdown, rule table, and fixes.
  - `src/cli/renderers/audit_detail.py`: `DetailRenderer` class for grouped findings with locations.
  - Original `src/cli/logic/audit_renderer.py`: Becomes a facade with `render_audit(overview=True, detail=False)` that injects `Console` and data, calling extracted renderers.

This improves separation: Mind layer (shared/models and utils) handles immutable data; Will layer (renderers) composes declarative views; Body (CLI) focuses on I/O. Reduces cognitive load by making rendering declarative (e.g., pass pre-grouped data to renderers). Aligns with governance by isolating audit stats for traceability and enabling pluggable outputs (e.g., future HTML renderer).

## Detailed Extraction Plan (numbered steps)

Step 1: Extract data structures and constants to `src/shared/models/audit_rendering.py`. Move `AuditStats`, `RuleGroup` (including properties), `SEVERITY_ENFORCEMENT`, `SEVERITY_ICON`, `SEVERITY_COLOR`, and `FIX_HINTS`. No dependencies to move—import `AuditFinding` and `AuditSeverity` from `shared.models`. Update imports in original file. This creates an immutable config hub (e.g., freeze dicts if needed for V3).

Step 2: Extract grouping helpers to `src/shared/utils/audit_grouping.py`. Move `_group_by_rule` → public `group_by_rule` (return immutable list of `RuleGroup`); `_group_by_severity` → public `group_by_severity` (use `defaultdict` but return copy for immutability); `_collect_fix_hints` → public `collect_fix_hints`; `_format_location` → public `format_location` (pure function, no console). Inject no deps—pure on `list[AuditFinding]`. Testable as standalone utils. Refactor to avoid mutations: e.g., use `collections.defaultdict(list)` and `copy.deepcopy` if needed, but prefer immutable dataclasses.

Step 3: Extract overview rendering to `src/cli/renderers/audit_overview.py`. Create class `OverviewRenderer` with `__init__(self, console: Console)` and method `render(self, findings: list[AuditFinding], stats: AuditStats, duration_sec: float, passed: bool, verdict_str: str | None = None) -> None`. Move logic from `render_overview`: compute groups internally via imported utils, but inject pre-grouped data for flexibility (e.g., optional `by_severity: dict[AuditSeverity, list[AuditFinding]]`). Dependencies: Import `Console`, `Panel`, `Table`, `Text` from Rich; models/utils from Step 1/2. Make verdict logic declarative: use a dict mapping `verdict_str` to (color, text).

Step 4: Extract detail rendering to `src/cli/renderers/audit_detail.py`. Create class `DetailRenderer` with `__init__(self, console: Console)` and `render(self, findings: list[AuditFinding]) -> None`. Move logic from `render_detail`: use imported `group_by_severity` and `format_location`. Sub-grouping becomes a nested call to a new util `group_by_check_id_within_severity` if needed, but keep simple. Dependencies: Same Rich imports; models/utils. Prioritize immutability by passing frozen sets of findings.

Step 5: Refactor original file as orchestrator. Remove extracted code; add imports from new modules. Introduce `AuditRenderer` class with `render_overview(...)` and `render_detail(...)` that instantiate and call the extracted renderers (e.g., `OverviewRenderer(console).render(...)`). Expose a top-level `render_audit(console, findings, stats, ...)` that sequences overview + detail based on flags. Update docstring to note it's now a facade. No new deps—inject all via params.

Step 6: Add type hints and immutability guards. Ensure all functions return immutable types (e.g., `frozenlist` for findings lists). In utils, use `typing.Final` for constants. Run mypy and add tests for each extracted module (e.g., pytest for grouping: assert `group_by_rule(mock_findings) == expected_groups`).

## Code Examples / Mini-Diffs

### Extraction 1: Grouping Helpers (from Step 2)
**Before** (in original file):
```python
# ID: f9c5a3b4-0d6e-7f8a-c2b3-e4f5a6b7c8d9
def _group_by_rule(findings: list[AuditFinding]) -> list[RuleGroup]:
    """Group findings by check_id, sorted by severity (highest first) then count."""
    groups: dict[str, RuleGroup] = {}
    for f in findings:
        if f.check_id not in groups:
            groups[f.check_id] = RuleGroup(check_id=f.check_id)
        groups[f.check_id].findings.append(f)  # Mutation!

    return sorted(
        groups.values(),
        key=lambda g: (-g.max_severity.value, -g.count),
    )
```

**After** (in `src/shared/utils/audit_grouping.py`—immutable version using `defaultdict` and list comprehension):
```python
from collections import defaultdict
from typing import List
from shared.models.audit_rendering import RuleGroup, AuditFinding, AuditSeverity

def group_by_rule(findings: List[AuditFinding]) -> List[RuleGroup]:
    """Group findings by check_id, sorted by severity (highest first) then count.

    Returns immutable list of RuleGroup.
    """
    groups: dict[str, RuleGroup] = defaultdict(lambda: RuleGroup(check_id=""))  # Temp init
    for f in findings:
        group = groups[f.check_id]
        if not group.check_id:  # Init if needed
            group = RuleGroup(check_id=f.check_id)
            groups[f.check_id] = group
        # Immutable append: create new list
        groups[f.check_id] = RuleGroup(
            check_id=group.check_id,
            findings=group.findings + [f]  # Concat for immutability
        )

    return sorted(
        list(groups.values()),
        key=lambda g: (-g.max_severity.value, -g.count),
    )
```
*(Note: For full immutability, make `RuleGroup.findings` a `tuple` or use `frozenlist` from `pcollections`.)*

In original file, replace call with: `from shared.utils.audit_grouping import group_by_rule; rule_groups = group_by_rule(findings)`

### Extraction 2: Overview Rendering (from Step 3)
**Before** (excerpt from `render_overview`—health card + verdict):
```python
# — Verdict —
if verdict_str is None:
    # Backward compat: derive from bool
    verdict_str = "PASS" if passed else "FAIL"

if verdict_str == "DEGRADED":
    verdict_color = "yellow"
    verdict_text = "DEGRADED (enforcement failures — compliance status UNKNOWN)"
elif verdict_str == "PASS":
    verdict_color = "green"
    verdict_text = "PASSED (no blocking violations)"
else:
    verdict_color = "red"
    verdict_text = "FAILED (blocking violations detected)"

# — Health Card —
card_lines = [
    f"Rules Executed : {stats.executed_rules}/{stats.total_rules} ({stats.coverage_percent}%)",
]
# ... (conditionals for P0 additions)
card_lines.extend([...])
console.print(Panel("\n".join(card_lines), ...))
```

**After** (in `src/cli/renderers/audit_overview.py`—declarative verdict mapping):
```python
from rich.console import Console
from rich.panel import Panel
from shared.models.audit_rendering import AuditStats
from shared.utils.audit_grouping import group_by_severity, collect_fix_hints

class OverviewRenderer:
    def __init__(self, console: Console):
        self.console = console
        self.verdict_map = {
            "DEGRADED": ("yellow", "DEGRADED (enforcement failures — compliance status UNKNOWN)"),
            "PASS": ("green", "PASSED (no blocking violations)"),
            "FAIL": ("red", "FAILED (blocking violations detected)"),
        }

    def render(self, findings: list[AuditFinding], stats: AuditStats, duration_sec: float,
               passed: bool, verdict_str: str | None = None) -> None:
        if verdict_str is None:
            verdict_str = "PASS" if passed else "FAIL"
        verdict_color, verdict_text = self.verdict_map.get(verdict_str, ("red", "UNKNOWN"))

        card_lines = [f"Rules Executed : {stats.executed_rules}/{stats.total_rules} ({stats.coverage_percent}%)"]
        if stats.total_declared_rules > 0:
            card_lines.append(f"True Coverage  : {stats.executed_rules}/{stats.total_declared_rules} ({stats.effective_coverage_percent}%)")
        # ... (other conditionals unchanged, but declarative)
        card_lines.extend([f"Total Findings : {len(findings)}", f"Duration       : {duration_sec:.1f}s",
                           f"Verdict        : [{verdict_color}]{verdict_text}[/{verdict_color}]"])

        self.console.print(Panel("\n".join(card_lines), title="[bold]Constitutional Audit[/bold]",
                                 border_style="cyan", padding=(1, 2)))
        # ... (rest: severity breakdown, table, hints using imported utils)
```

In slimmed-down original:
```python
# src/cli/logic/audit_renderer.py (orchestrator excerpt)
from src.cli.renderers.audit_overview import OverviewRenderer

def render_overview(console: Console, findings: list[AuditFinding], stats: AuditStats, ...):
    renderer = OverviewRenderer(console)
    renderer.render(findings, stats, duration_sec, passed, verdict_str)
    # No more inline logic
```

### Extraction 3: Slimmed-Down Original File Orchestration
**After All Extractions** (high-level structure of `src/cli/logic/audit_renderer.py`):
```python
"""
Audit Renderer Facade - Orchestrates extracted renderers for CLI output.
"""

from rich.console import Console
from src.cli.renderers.audit_overview import OverviewRenderer
from src.cli.renderers.audit_detail import DetailRenderer
from shared.utils.audit_grouping import group_by_severity  # If needed for top-level

class AuditRenderer:
    def __init__(self, console: Console):
        self.console = console
        self.overview = OverviewRenderer(console)
        self.detail = DetailRenderer(console)

    def render_audit(self, findings: list[AuditFinding], stats: AuditStats, duration_sec: float,
                     passed: bool, verdict_str: str | None = None, show_detail: bool = False) -> None:
        self.overview.render(findings, stats, duration_sec, passed, verdict_str)
        if show_detail:
            self.detail.render(findings)

# Top-level for backward compat
def render_overview(console: Console, findings: ..., stats: ..., ...):  # Delegates to class
    AuditRenderer(console).overview.render(...)
def render_detail(console: Console, findings: ...):
    AuditRenderer(console).detail.render(findings)
```
*(~120 LOC total: imports, class, delegation—no rendering code.)*

## Benefits & Metrics Estimate

- **LOC Reduction**: Original ~350 LOC → ~120 LOC (65% cut). Extracted modules: models/utils ~80 LOC; each renderer ~100 LOC (total ~280, but distributed). Enables <300 LOC per file rule.
- **Testability Gains**: Grouping utils now pure (100% unit coverage easy, e.g., `assert len(group_by_rule(findings)) == 3`). Renderers testable with mocked `Console` (e.g., capture `print` calls via `rich.console.NoopConsole`). Facade tests focus on wiring.
- **Easier Extension**: New views (e.g., `JsonAuditRenderer` in parallel module) reuse models/utils. Declarative grouping supports immutability for V3 autonomy (e.g., cache `RuleGroup` snapshots in governance DB).
- **Alignment with V2/V3 Goals**: Phased rendering (overview/detail) fits Will's workflows; immutable data aids audit traceability. Reduces CLI bloat, freeing focus for governance integrations like real-time enforcement.

## Potential Risks / Gotchas

- **Breaking Changes**: Public API (`render_overview`, `render_detail`) must remain signatures-compatible—delegate exactly, no param changes. Verdict derivation (`if verdict_str is None: ...`) stays in renderer for backward compat, but deprecate `passed` bool in V3 docs.
- **Rich Dependencies**: Extracting Rich imports to renderers avoids global pollution, but ensure `Console` injection doesn't break threaded CLI use (test with `console.capture()`). If Rich versions change, renderers isolate impact.
- **Immutability Overhead**: Concat-based grouping (e.g., `findings + [f]`) adds minor perf cost for large audits (>10k findings)—profile and fallback to mutable if needed, but prioritize governance purity.
- **Testing Gaps**: New modules need immediate tests (e.g., 80% coverage); original file's inline comments (e.g., "HARDENED (V2.5.0)") should migrate to module docstrings to avoid losing context. Watch for import cycles (e.g., utils → models, but not vice versa).
