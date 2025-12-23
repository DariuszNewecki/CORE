# src/mind/governance/checks/atomic_composition_check.py
"""
Atomic Composition Governance Check

Enforces CORE Atomic Action composition rule declared in:
- .intent/policies/architecture/atomic_actions.json  (expected via settings.paths.policy("atomic_actions"))

Targets the governance coverage gap:
- atomic.actions_compose_transitively

Meaning (pragmatic interpretation):
Atomic Actions should prefer *composition* (calling other actions via the standard
action execution gateway) rather than re-implementing logic inline.

This check is evidence-backed and conservative:
- It statically analyzes src/body/actions/**/*.py
- It looks for action-like classes and gateway invocations inside run/execute/invoke methods
- It emits WARN findings if composition is insufficient
- It emits a WARN finding if analysis cannot run (e.g., parse errors / no files)

Notes:
- This rule is inherently heuristic until CORE standardizes a single gateway API.
- You can tighten the gateway token set over time once your Body contracts settle.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

# -----------------------------
# Rule ID (must match .intent)
# -----------------------------
RULE_ATOMIC_ACTIONS_COMPOSE_TRANSITIVELY = "atomic.actions_compose_transitively"

# -----------------------------
# Local config / heuristics
# -----------------------------
_BODY_ROOT = settings.REPO_PATH / "src" / "body"
_ACTIONS_ROOT = _BODY_ROOT / "actions"

# Methods considered "action entrypoints"
_ACTION_ENTRYPOINT_METHODS: tuple[str, ...] = ("run", "execute", "invoke")

# Composition gateway tokens:
# - We accept both Name calls (execute_action(...)) and Attribute calls (.execute_action(...))
# - Tighten this list as you converge on one standard API.
_COMPOSITION_GATEWAYS: tuple[str, ...] = (
    # function-style
    "execute_action",
    "run_action",
    "dispatch_action",
    "invoke_action",
    "call_action",
    # method-style (we normalize attributes to ".<name>")
    ".execute_action",
    ".run_action",
    ".dispatch_action",
    ".invoke_action",
    ".call_action",
    # object construction (optional signal)
    "ActionRunner",
    "ActionExecutor",
    "ActionDispatcher",
)


@dataclass(frozen=True)
class _ActionCompositionEvidence:
    file: str
    line: int | None
    owner: str
    entrypoint: str
    gateway: str


@dataclass(frozen=True)
class _ActionCompositionAnalysis:
    parsed_files: int
    parse_errors: int
    action_classes: int
    entrypoints_scanned: int
    composition_hits: list[_ActionCompositionEvidence]
    no_composition_actions: list[dict[str, Any]]


def _collect_py_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _parse_file(p: Path) -> ast.AST | None:
    try:
        return ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
    except Exception:
        return None


def _call_token(call: ast.Call) -> str:
    """
    Normalize a call target into a token we can compare against _COMPOSITION_GATEWAYS.

    - execute_action(...) -> "execute_action"
    - runner.execute_action(...) -> ".execute_action"
    - ActionRunner(...) -> "ActionRunner"
    """
    fn = call.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return f".{fn.attr}"
    return ""


def _is_action_class(cls: ast.ClassDef) -> bool:
    """
    Conservative action classifier:
    - Class name ends with 'Action', OR
    - Defines at least one entrypoint method (run/execute/invoke).
    """
    if cls.name.endswith("Action"):
        return True
    for node in cls.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name in _ACTION_ENTRYPOINT_METHODS
        ):
            return True
    return False


def _analyze_atomic_action_composition(repo_root: Path) -> _ActionCompositionAnalysis:
    """
    Evidence-oriented AST analysis of transitive composition.

    Scope: src/body/actions/**/*.py
    """
    parsed_files = 0
    parse_errors = 0
    action_classes = 0
    entrypoints_scanned = 0

    composition_hits: list[_ActionCompositionEvidence] = []
    no_composition_actions: list[dict[str, Any]] = []

    for f in _collect_py_files(repo_root / "src" / "body" / "actions"):
        tree = _parse_file(f)
        if tree is None:
            parse_errors += 1
            continue
        parsed_files += 1

        rel = str(f.relative_to(repo_root))

        for cls in [
            n for n in getattr(tree, "body", []) if isinstance(n, ast.ClassDef)
        ]:
            if not _is_action_class(cls):
                continue

            action_classes += 1

            class_has_composition = False
            class_entrypoints = [
                n
                for n in cls.body
                if isinstance(n, ast.FunctionDef)
                and n.name in _ACTION_ENTRYPOINT_METHODS
            ]

            # If the class is action-like but has no recognized entrypoints,
            # we still record it as "no composition" (with a clear reason).
            if not class_entrypoints:
                no_composition_actions.append(
                    {
                        "file": rel,
                        "class": cls.name,
                        "reason": "no_entrypoint_methods_found",
                    }
                )
                continue

            for fn in class_entrypoints:
                entrypoints_scanned += 1

                fn_calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
                for call in fn_calls:
                    token = _call_token(call)
                    if not token:
                        continue
                    if token in _COMPOSITION_GATEWAYS:
                        class_has_composition = True
                        composition_hits.append(
                            _ActionCompositionEvidence(
                                file=rel,
                                line=getattr(call, "lineno", None),
                                owner=cls.name,
                                entrypoint=fn.name,
                                gateway=token,
                            )
                        )
                        # One hit is enough to mark this class as composing.
                        break

                if class_has_composition:
                    break

            if not class_has_composition:
                no_composition_actions.append(
                    {
                        "file": rel,
                        "class": cls.name,
                        "reason": "no_action_gateway_invocation_detected",
                        "entrypoints": [fn.name for fn in class_entrypoints],
                    }
                )

    return _ActionCompositionAnalysis(
        parsed_files=parsed_files,
        parse_errors=parse_errors,
        action_classes=action_classes,
        entrypoints_scanned=entrypoints_scanned,
        composition_hits=composition_hits,
        no_composition_actions=no_composition_actions,
    )


# =============================================================================
# Enforcement method
# =============================================================================
# ID: 7cf1bdc9-2c52-4d8c-8b25-e40b4f0fb5c9
class AtomicActionsComposeTransitivelyEnforcement(EnforcementMethod):
    """
    Enforces atomic.actions_compose_transitively using heuristic composition detection.

    Policy decision:
    - We consider the rule "enforced" when a meaningful portion of action classes
      demonstrate transitive composition via gateways.
    - Because this is a WARN-level rule, we do not gate on strict 100%.

    Thresholds:
    - If there are no parseable action files, emit a warning finding (cannot verify).
    - Otherwise, require at least MIN_RATIO of action classes to have composition evidence.
    """

    MIN_RATIO: ClassVar[float] = (
        0.50  # pragmatic default; tighten as composition matures
    )

    # ID: 3f8d7c4a-41d6-4a0f-8b8e-2b2f0c45c5c7
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        analysis = _analyze_atomic_action_composition(context.repo_path)

        # If nothing could be analyzed, we must not "pretend pass".
        if analysis.parsed_files == 0:
            return [
                self._create_finding(
                    message=(
                        "Cannot verify atomic action transitive composition: "
                        "no parseable src/body/actions Python modules were found "
                        f"(parse_errors={analysis.parse_errors})."
                    ),
                    file_path="src/body/actions",
                )
            ]

        total_actions = analysis.action_classes
        composed_actions = len({(h.file, h.owner) for h in analysis.composition_hits})

        # If we detected zero action classes, also cannot verify the intent of the rule.
        if total_actions == 0:
            return [
                self._create_finding(
                    message=(
                        "Cannot verify atomic action transitive composition: "
                        "no action-like classes detected under src/body/actions "
                        f"(parsed_files={analysis.parsed_files}, parse_errors={analysis.parse_errors})."
                    ),
                    file_path="src/body/actions",
                )
            ]

        ratio = composed_actions / total_actions if total_actions else 0.0

        # Pass => no findings
        if ratio >= self.MIN_RATIO:
            return []

        # Fail (warn) => evidence-backed finding
        return [
            self._create_finding(
                message=(
                    "Atomic actions do not sufficiently compose transitively. "
                    "Prefer calling other actions via the standard action execution gateway. "
                    f"(composition_ratio={round(ratio, 4)} required_min_ratio={self.MIN_RATIO}; "
                    f"actions={total_actions}, actions_with_composition={composed_actions})."
                ),
                file_path="src/body/actions",
            )
        ]


# =============================================================================
# Check binding
# =============================================================================
# ID: 0d9c9b6f-5b5b-4b0c-8a19-2a6c1c5d4e18
class AtomicCompositionCheck(RuleEnforcementCheck):
    """
    Enforces atomic action composition rule with evidence-backed method.

    Ref: .intent/policies/architecture/atomic_actions.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        RULE_ATOMIC_ACTIONS_COMPOSE_TRANSITIVELY,
    ]

    policy_file: ClassVar = settings.paths.policy("atomic_actions")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        AtomicActionsComposeTransitivelyEnforcement(
            rule_id=RULE_ATOMIC_ACTIONS_COMPOSE_TRANSITIVELY,
            severity=AuditSeverity.WARNING,
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
