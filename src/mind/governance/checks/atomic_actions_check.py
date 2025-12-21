# src/mind/governance/checks/atomic_actions_check.py
"""
Atomic Actions Governance Check

Enforces the CORE Atomic Actions contract as declared in:
- .intent/policies/architecture/atomic_actions.json

Targets the highest-severity gaps currently reported by governance coverage:
- atomic.action_must_be_headless
- atomic.action_must_return_result
- atomic.governance_never_bypassed
- atomic.result_must_be_structured
- atomic.workflow_must_declare_intent

Design constraints:
- Prefer internal CORE capabilities first (Body checker modules / shared utilities).
- Fall back to conservative static analysis only if checker modules are unavailable.
"""

from __future__ import annotations

import ast
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

RULE_ACTION_MUST_BE_HEADLESS = "atomic.action_must_be_headless"
RULE_ACTION_MUST_RETURN_RESULT = "atomic.action_must_return_result"
RULE_GOVERNANCE_NEVER_BYPASSED = "atomic.governance_never_bypassed"
RULE_RESULT_MUST_BE_STRUCTURED = "atomic.result_must_be_structured"
RULE_WORKFLOW_MUST_DECLARE_INTENT = "atomic.workflow_must_declare_intent"

_ACTIONS_ROOT: Path = settings.REPO_PATH / "src" / "body" / "actions"

_FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "streamlit",
    "tkinter",
    "PyQt",
    "PySide",
    "kivy",
    "prompt_toolkit",
    "inquirer",
    "click",
    "typer",
    "rich",
)

_BYPASS_WRITE_CALLS: tuple[str, ...] = ("open",)
_BYPASS_ATTR_CALLS: tuple[str, ...] = (
    "write_text",
    "write_bytes",
    "unlink",
    "replace",
    "rename",
    "rmdir",
    "mkdir",
    "remove",
    "rmtree",
)

_RESULT_TYPE_MARKERS: tuple[str, ...] = (
    "ActionResult",
    "Result",
)


def _is_forbidden_import(module: str) -> bool:
    m = module.strip()
    return any(m == p or m.startswith(f"{p}.") for p in _FORBIDDEN_IMPORT_PREFIXES)


def _call_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def _render_annotation(node: ast.AST) -> str:
    try:
        return ast.unparse(node)  # py>=3.9
    except Exception:
        return node.__class__.__name__


def _file_declares_intent(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "intent" in node.value.lower():
                return True
        if isinstance(node, ast.Dict):
            for k in node.keys:
                if (
                    isinstance(k, ast.Constant)
                    and isinstance(k.value, str)
                    and k.value.lower() == "intent"
                ):
                    return True
        if isinstance(node, ast.Attribute) and node.attr.lower() == "intent":
            return True
    return False


def _find_write_bypass_calls(tree: ast.AST, rel_file: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in _BYPASS_WRITE_CALLS:
            out.append({"file": rel_file, "line": node.lineno, "call": node.func.id})
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in _BYPASS_ATTR_CALLS
        ):
            out.append({"file": rel_file, "line": node.lineno, "call": node.func.attr})
    return out


def _analyze_atomic_actions() -> dict[str, list[dict[str, Any]]]:
    """
    Returns a dict keyed by rule_id -> list of violation dicts.
    Uses Body checker if available, else conservative AST scan of src/body/actions/**.py
    """
    violations: dict[str, list[dict[str, Any]]] = {
        RULE_ACTION_MUST_BE_HEADLESS: [],
        RULE_GOVERNANCE_NEVER_BYPASSED: [],
        RULE_ACTION_MUST_RETURN_RESULT: [],
        RULE_RESULT_MUST_BE_STRUCTURED: [],
        RULE_WORKFLOW_MUST_DECLARE_INTENT: [],
    }

    # Prefer internal checker if it exists and yields usable per-rule findings.
    try:
        from body.cli.logic import atomic_actions_checker as mod  # type: ignore
    except Exception:
        mod = None  # type: ignore[assignment]

    if mod is not None:
        entrypoints = (
            "check",
            "run_check",
            "run",
            "analyze",
            "scan",
            "check_atomic_actions",
        )
        fn = next(
            (
                getattr(mod, n, None)
                for n in entrypoints
                if callable(getattr(mod, n, None))
            ),
            None,
        )
        if callable(fn):
            try:
                out = fn()
            except TypeError:
                try:
                    out = fn(settings.REPO_PATH)
                except Exception:
                    out = None
            except Exception:
                out = None

            # Accept list[dict] with rule_id/id and violations/evidence
            if isinstance(out, list) and all(isinstance(x, dict) for x in out):
                for d in out:
                    rid = str(d.get("rule_id") or d.get("id") or "")
                    if rid in violations:
                        # Try common shapes:
                        # - {violations:[...]}
                        # - {evidence:{violations:[...]}}
                        # - any dict; keep minimal
                        v = d.get("violations")
                        if isinstance(v, list):
                            violations[rid].extend(
                                [x for x in v if isinstance(x, dict)]
                            )
                        else:
                            ev = d.get("evidence")
                            if isinstance(ev, dict) and isinstance(
                                ev.get("violations"), list
                            ):
                                violations[rid].extend(
                                    [x for x in ev["violations"] if isinstance(x, dict)]
                                )
                            elif d.get("ok") is False:
                                violations[rid].append(
                                    {
                                        "source": "body.cli.logic.atomic_actions_checker",
                                        "detail": d,
                                    }
                                )
                # If we got anything meaningful (or explicit ok/fail), use it.
                if any(len(v) > 0 for v in violations.values()) or any(
                    (
                        isinstance(d, dict)
                        and (
                            d.get("rule_id") in violations or d.get("id") in violations
                        )
                    )
                    for d in out
                ):
                    return violations

    # Fallback AST scan
    root = _ACTIONS_ROOT
    if not root.exists():
        return violations

    py_files = sorted(p for p in root.rglob("*.py") if p.is_file())
    if not py_files:
        return violations

    for f in py_files:
        try:
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(f))
        except Exception:
            continue

        rel = str(f.relative_to(settings.REPO_PATH))

        # Headless: forbidden imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name or ""
                    if _is_forbidden_import(name):
                        violations[RULE_ACTION_MUST_BE_HEADLESS].append(
                            {"file": rel, "line": node.lineno, "import": name}
                        )
            elif isinstance(node, ast.ImportFrom):
                modname = node.module or ""
                if modname and _is_forbidden_import(modname):
                    violations[RULE_ACTION_MUST_BE_HEADLESS].append(
                        {"file": rel, "line": node.lineno, "import": modname}
                    )

        # Governance bypass: direct writes
        violations[RULE_GOVERNANCE_NEVER_BYPASSED].extend(
            _find_write_bypass_calls(tree, rel)
        )

        # Return/result structure: heuristics on run/execute/invoke
        for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
            for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
                if fn.name not in ("run", "execute", "invoke"):
                    continue

                returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
                if not returns:
                    violations[RULE_ACTION_MUST_RETURN_RESULT].append(
                        {
                            "file": rel,
                            "class": cls.name,
                            "method": fn.name,
                            "reason": "no_return",
                        }
                    )
                    continue

                if fn.returns is not None:
                    ann_txt = _render_annotation(fn.returns)
                    if not any(m in ann_txt for m in _RESULT_TYPE_MARKERS):
                        violations[RULE_ACTION_MUST_RETURN_RESULT].append(
                            {
                                "file": rel,
                                "class": cls.name,
                                "method": fn.name,
                                "reason": "bad_return_annotation",
                                "return_annotation": ann_txt,
                            }
                        )

                for r in returns:
                    if r.value is None:
                        violations[RULE_RESULT_MUST_BE_STRUCTURED].append(
                            {
                                "file": rel,
                                "class": cls.name,
                                "method": fn.name,
                                "line": r.lineno,
                                "return": "None",
                            }
                        )
                        continue

                    if (
                        isinstance(r.value, ast.Call)
                        and _call_name(r.value) in _RESULT_TYPE_MARKERS
                    ):
                        continue
                    if isinstance(r.value, ast.Dict):
                        continue

                    violations[RULE_RESULT_MUST_BE_STRUCTURED].append(
                        {
                            "file": rel,
                            "class": cls.name,
                            "method": fn.name,
                            "line": r.lineno,
                            "return": type(r.value).__name__,
                        }
                    )

        # Workflow intent marker: if mutating ops detected, require intent marker
        if violations[RULE_GOVERNANCE_NEVER_BYPASSED] and not _file_declares_intent(
            tree
        ):
            violations[RULE_WORKFLOW_MUST_DECLARE_INTENT].append(
                {"file": rel, "reason": "mutating_ops_detected_but_no_intent_marker"}
            )

    return violations


def _summarize(violations: list[dict[str, Any]], limit: int = 5) -> str:
    if not violations:
        return ""
    head = violations[:limit]
    tail = len(violations) - len(head)
    s = "; ".join(str(x) for x in head)
    if tail > 0:
        s = f"{s}; (+{tail} more)"
    return s


# ID: atomic-actions-headless-enforcement
# ID: 1b5350f8-7c2b-4c75-9a2c-0fdba1b0d8e6
class AtomicActionMustBeHeadlessEnforcement(EnforcementMethod):
    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: d8615e63-4627-499c-9653-29b60e3b90b2
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        v = _analyze_atomic_actions()[RULE_ACTION_MUST_BE_HEADLESS]
        if not v:
            return []
        return [
            self._create_finding(
                message=f"Atomic actions import UI/interactive dependencies (headless contract violated): {_summarize(v)}",
                file_path=str(_ACTIONS_ROOT.relative_to(context.repo_path)),
            )
        ]


# ID: atomic-actions-return-result-enforcement
# ID: 3d6e8c4d-2d4d-41ea-8f22-9c4b8e4c2f8a
class AtomicActionMustReturnResultEnforcement(EnforcementMethod):
    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: fceb6794-9c1f-4c00-88ce-570036a76a0b
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        v = _analyze_atomic_actions()[RULE_ACTION_MUST_RETURN_RESULT]
        if not v:
            return []
        return [
            self._create_finding(
                message=f"Atomic action entrypoints appear to miss/violate explicit return contract: {_summarize(v)}",
                file_path=str(_ACTIONS_ROOT.relative_to(context.repo_path)),
            )
        ]


# ID: atomic-actions-governance-bypass-enforcement
# ID: 0c7d59a6-1c65-4f6d-9c32-62e91ef3c8d1
class AtomicGovernanceNeverBypassedEnforcement(EnforcementMethod):
    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 52ee6cba-1601-4351-8279-cbdf6af59219
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        v = _analyze_atomic_actions()[RULE_GOVERNANCE_NEVER_BYPASSED]
        if not v:
            return []
        return [
            self._create_finding(
                message=f"Atomic actions appear to bypass governed write semantics (direct filesystem mutation detected): {_summarize(v)}",
                file_path=str(_ACTIONS_ROOT.relative_to(context.repo_path)),
            )
        ]


# ID: atomic-actions-structured-result-enforcement
# ID: 9e2abf0f-3b69-48e4-8d12-4f6d5d2c3a10
class AtomicResultMustBeStructuredEnforcement(EnforcementMethod):
    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 6eca74e5-8302-4d77-9c6e-681d72e03c56
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        v = _analyze_atomic_actions()[RULE_RESULT_MUST_BE_STRUCTURED]
        if not v:
            return []
        return [
            self._create_finding(
                message=f"Atomic action returns appear unstructured (expected ActionResult(...) or dict): {_summarize(v)}",
                file_path=str(_ACTIONS_ROOT.relative_to(context.repo_path)),
            )
        ]


# ID: atomic-actions-workflow-intent-enforcement
# ID: 6b2a0c7d-0c65-4f6d-9c32-62e91ef3c8d2
class AtomicWorkflowMustDeclareIntentEnforcement(EnforcementMethod):
    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 396469dd-5b0d-4b08-8019-0a340c0cc4ac
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        v = _analyze_atomic_actions()[RULE_WORKFLOW_MUST_DECLARE_INTENT]
        if not v:
            return []
        return [
            self._create_finding(
                message=f"Mutating atomic actions appear to lack intent declaration markers: {_summarize(v)}",
                file_path=str(_ACTIONS_ROOT.relative_to(context.repo_path)),
            )
        ]


# ID: atomic-actions-check
# ID: 5f4c3b2a-1d0e-4c5b-9a8b-7c6d5e4f3a2b
class AtomicActionsCheck(RuleEnforcementCheck):
    """
    Enforces atomic action constraints as evidence-backed governance rules.
    """

    policy_rule_ids: ClassVar[list[str]] = [
        RULE_ACTION_MUST_BE_HEADLESS,
        RULE_ACTION_MUST_RETURN_RESULT,
        RULE_GOVERNANCE_NEVER_BYPASSED,
        RULE_RESULT_MUST_BE_STRUCTURED,
        RULE_WORKFLOW_MUST_DECLARE_INTENT,
    ]

    policy_file: ClassVar[Path] = settings.paths.policy("atomic_actions")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        AtomicActionMustBeHeadlessEnforcement(
            rule_id=RULE_ACTION_MUST_BE_HEADLESS,
            severity=AuditSeverity.ERROR,
        ),
        AtomicActionMustReturnResultEnforcement(
            rule_id=RULE_ACTION_MUST_RETURN_RESULT,
            severity=AuditSeverity.ERROR,
        ),
        AtomicGovernanceNeverBypassedEnforcement(
            rule_id=RULE_GOVERNANCE_NEVER_BYPASSED,
            severity=AuditSeverity.ERROR,
        ),
        AtomicResultMustBeStructuredEnforcement(
            rule_id=RULE_RESULT_MUST_BE_STRUCTURED,
            severity=AuditSeverity.ERROR,
        ),
        AtomicWorkflowMustDeclareIntentEnforcement(
            rule_id=RULE_WORKFLOW_MUST_DECLARE_INTENT,
            severity=AuditSeverity.ERROR,
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
