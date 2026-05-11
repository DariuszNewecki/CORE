# src/body/evaluators/atomic_actions_format.py
"""Human-readable formatter for AtomicActionViolation lists.

Pure transformation: consumes a list of violations and returns a string
for CLI/log display. No scan logic, no rule logic, no AST awareness.

LAYER: body/evaluators — rendering helper. No side effects beyond
constructing a string.
"""

from __future__ import annotations

from pathlib import Path

from body.evaluators.atomic_actions_rules import AtomicActionViolation


# ID: 2f8a6d5c-3e3f-4f3a-b881-e454ca73d5a4
def format_atomic_action_violations(
    violations: list[AtomicActionViolation],
    verbose: bool = False,
) -> str:
    """Format atomic action violations for display."""
    if not violations:
        return "✅ All atomic actions follow constitutional pattern!"

    output: list[str] = ["\n❌ Found Atomic Action Violations:\n"]

    by_file: dict[Path, list[AtomicActionViolation]] = {}
    for v in violations:
        by_file.setdefault(v.file_path, []).append(v)

    for file_path, file_violations in sorted(by_file.items(), key=lambda x: str(x[0])):
        output.append(f"\n📄 {file_path}")
        for v in file_violations:
            severity_marker = "🔴" if v.severity == "error" else "🟡"
            output.append(
                f"  {severity_marker} {v.function_name} (line {v.line_number or '?'})"
            )
            output.append(f"     Rule: {v.rule_id}")
            output.append(f"     {v.message}")
            if verbose and v.suggested_fix:
                output.append(f"     💡 Fix: {v.suggested_fix}")

    return "\n".join(output)
