# src/mind/governance/checks/observability_check.py
"""
Observability Governance Check

Enforces observability rules declared in:
- .intent/policies/operations/observability.json

Evidence-backed enforcement for:
- observability.atomic_actions_emit_logs
- observability.cli_commands_valid
- observability.metrics_actionable
"""

from __future__ import annotations

import ast
import json
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


_RULE_ATOMIC_ACTIONS_EMIT_LOGS = "observability.atomic_actions_emit_logs"
_RULE_CLI_COMMANDS_VALID = "observability.cli_commands_valid"
_RULE_METRICS_ACTIONABLE = "observability.metrics_actionable"


_ACTIONS_ROOT = settings.REPO_PATH / "src" / "body" / "actions"
_CLI_COMMANDS_ROOT = settings.REPO_PATH / "src" / "body" / "cli" / "commands"

_LOG_VAR_NAMES = {"logger", "log"}
_LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}
_CLI_FORBIDDEN_CALLS = {"print", "input"}


@dataclass(frozen=True)
# ID: 5ac3ef63-2d0b-47f8-b7a0-0c2a978de0a6
class _Violation:
    file: str
    line: int | None
    detail: str


# -------------------------------------------------------------------------
# Enforcement methods
# -------------------------------------------------------------------------


# ID: 2c9a2b89-5d0b-4d5b-9e33-8a92f6c7f5b8
class ObservabilityAtomicActionsEmitLogsEnforcement(EnforcementMethod):
    """
    Enforces: observability.atomic_actions_emit_logs

    Heuristic enforcement:
    - For action classes under src/body/actions, methods named run/execute/invoke
      should contain at least one logger.<level>(...) call.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 0d52a4d6-3f52-4a55-9f60-6f6c8b6f21d2
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        if not _ACTIONS_ROOT.exists():
            return [
                self._create_finding(
                    message="src/body/actions not found; cannot validate atomic action log emission.",
                    file_path=str(_ACTIONS_ROOT.relative_to(context.repo_path)),
                )
            ]

        py_files = sorted(p for p in _ACTIONS_ROOT.rglob("*.py") if p.is_file())
        if not py_files:
            # Nothing to validate (treat as pass with evidence)
            return []

        violations: list[_Violation] = []
        for p in py_files:
            tree = _parse_python_file(p)
            if tree is None:
                continue

            rel = str(p.relative_to(context.repo_path))

            for cls in [
                n for n in getattr(tree, "body", []) if isinstance(n, ast.ClassDef)
            ]:
                for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
                    if fn.name not in ("run", "execute", "invoke"):
                        continue
                    if not _function_contains_log_call(fn):
                        violations.append(
                            _Violation(
                                file=rel,
                                line=getattr(fn, "lineno", None),
                                detail=f"{cls.name}.{fn.name} has no logger.<level>(...) call",
                            )
                        )

        if not violations:
            return []

        # Emit one aggregated finding (avoids flooding audits)
        sample = violations[:20]
        msg = (
            "Atomic action entrypoints appear silent (missing logger.<level>(...) in run/execute/invoke). "
            f"Violations: {len(violations)}. Sample: "
            + "; ".join(f"{v.file}:{v.line or '?'} {v.detail}" for v in sample)
        )
        return [
            self._create_finding(
                message=msg,
                file_path=str(_ACTIONS_ROOT.relative_to(context.repo_path)),
            )
        ]


# ID: 6ab1c10b-8c7c-4d60-8d98-92e9f6b0a2bf
class ObservabilityCliCommandsValidEnforcement(EnforcementMethod):
    """
    Enforces: observability.cli_commands_valid

    Conservative enforcement:
    - CLI command modules under src/body/cli/commands should not use print()/input().
      (Commands must use governed output/logging instead of ad-hoc I/O.)
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 1d0f6f39-1d6b-4202-bf5a-95b2c26de9b9
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        if not _CLI_COMMANDS_ROOT.exists():
            return [
                self._create_finding(
                    message="src/body/cli/commands not found; cannot validate CLI command validity.",
                    file_path=str(_CLI_COMMANDS_ROOT.relative_to(context.repo_path)),
                )
            ]

        py_files = sorted(p for p in _CLI_COMMANDS_ROOT.rglob("*.py") if p.is_file())
        if not py_files:
            return []

        violations: list[_Violation] = []

        for p in py_files:
            tree = _parse_python_file(p)
            if tree is None:
                continue

            rel = str(p.relative_to(context.repo_path))

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if (
                    isinstance(node.func, ast.Name)
                    and node.func.id in _CLI_FORBIDDEN_CALLS
                ):
                    violations.append(
                        _Violation(
                            file=rel,
                            line=getattr(node, "lineno", None),
                            detail=f"forbidden call: {node.func.id}()",
                        )
                    )

        if not violations:
            return []

        sample = violations[:30]
        msg = (
            "CLI command modules contain forbidden calls (print()/input()). "
            f"Violations: {len(violations)}. Sample: "
            + "; ".join(f"{v.file}:{v.line or '?'} {v.detail}" for v in sample)
        )
        return [
            self._create_finding(
                message=msg,
                file_path=str(_CLI_COMMANDS_ROOT.relative_to(context.repo_path)),
            )
        ]


# ID: 9e7b6a1c-83f8-49f0-82d0-1c35f3f40b64
class ObservabilityMetricsActionableEnforcement(EnforcementMethod):
    """
    Enforces: observability.metrics_actionable

    Policy hygiene enforcement:
    - The observability policy must define the rule and include actionable guidance
      (metric/signal + remediation/runbook/owner/etc.).
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 7df0b0f3-0a56-4a48-bc8a-3475b3f08b51
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        policy_path = settings.paths.policy("observability")
        if not policy_path.exists():
            return [
                self._create_finding(
                    message="Observability policy file missing; cannot validate metrics_actionable rule definition.",
                    file_path=str(policy_path.relative_to(context.repo_path)),
                )
            ]

        try:
            data = json.loads(policy_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return [
                self._create_finding(
                    message=f"Failed to parse observability policy JSON: {exc}",
                    file_path=str(policy_path.relative_to(context.repo_path)),
                )
            ]

        rules = data.get("rules", [])
        if not isinstance(rules, list):
            return [
                self._create_finding(
                    message="Observability policy malformed: 'rules' must be a list.",
                    file_path=str(policy_path.relative_to(context.repo_path)),
                )
            ]

        target: dict[str, Any] | None = None
        for r in rules:
            if isinstance(r, dict) and r.get("id") == _RULE_METRICS_ACTIONABLE:
                target = r
                break

        if target is None:
            return [
                self._create_finding(
                    message="Observability policy does not declare rule observability.metrics_actionable.",
                    file_path=str(policy_path.relative_to(context.repo_path)),
                )
            ]

        actionable_keys = (
            "metric",
            "metrics",
            "signal",
            "signals",
            "runbook",
            "action",
            "remediation",
            "owner",
        )
        present = [k for k in actionable_keys if k in target]

        if len(present) < 2:
            return [
                self._create_finding(
                    message=(
                        "observability.metrics_actionable lacks actionable guidance fields "
                        f"(expected at least two of {list(actionable_keys)}; present={present})."
                    ),
                    file_path=str(policy_path.relative_to(context.repo_path)),
                )
            ]

        return []


# -------------------------------------------------------------------------
# Check wiring (this is what makes governance coverage count it)
# -------------------------------------------------------------------------


# ID: 0c4e5fa8-9c9c-4cb4-9c5a-628e87a2a7b3
class ObservabilityCheck(RuleEnforcementCheck):
    """
    Enforces observability policy rules.

    Ref: .intent/policies/operations/observability.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        _RULE_ATOMIC_ACTIONS_EMIT_LOGS,
        _RULE_CLI_COMMANDS_VALID,
        _RULE_METRICS_ACTIONABLE,
    ]

    policy_file: ClassVar = settings.paths.policy("observability")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        ObservabilityAtomicActionsEmitLogsEnforcement(
            rule_id=_RULE_ATOMIC_ACTIONS_EMIT_LOGS,
            severity=AuditSeverity.ERROR,
        ),
        ObservabilityCliCommandsValidEnforcement(
            rule_id=_RULE_CLI_COMMANDS_VALID,
            severity=AuditSeverity.ERROR,
        ),
        ObservabilityMetricsActionableEnforcement(
            rule_id=_RULE_METRICS_ACTIONABLE,
            severity=AuditSeverity.ERROR,
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True


# -------------------------------------------------------------------------
# Local helpers (kept small; reuse shared utilities if you have them later)
# -------------------------------------------------------------------------


def _parse_python_file(p: Path) -> ast.AST | None:
    try:
        return ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
    except Exception as exc:
        logger.debug("ObservabilityCheck: failed parsing %s: %s", p, exc)
        return None


def _function_contains_log_call(fn: ast.FunctionDef) -> bool:
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in _LOG_METHODS:
            continue
        base = node.func.value
        if isinstance(base, ast.Name) and base.id in _LOG_VAR_NAMES:
            return True
    return False
