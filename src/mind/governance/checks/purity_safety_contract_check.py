# src/mind/governance/checks/purity_safety_contract_check.py
"""
Purity Safety Contract Governance Check

Enforces safety-contract requirement declared in standard_code_purity:
- purity.safety_contract_required

What this check enforces (evidence-backed, conservative):
1) Identify *safety-relevant* Body code surfaces:
   - src/body/actions/**/*.py  (atomic actions)
   - src/body/tools/**/*.py    (tool primitives)  [if present]
2) Require each target module to declare a "safety contract" in a discoverable form.
   Accepted minimal declarations (any of):
   - A module docstring containing the marker "SAFETY CONTRACT"
   - A module-level constant SAFETY_CONTRACT = {...} (dict)
   - A module-level constant SAFETY_CONTRACT = "..." (non-empty str)
3) Report concrete violating files, with exact evidence.

Non-goals:
- We do not judge correctness/quality of the safety contract contents yet.
- We do not attempt to infer safety contracts from external policy text.

Design constraints:
- No pretend-pass: if targets exist and are missing contracts, we fail with evidence.
- If no targets exist (e.g., directories absent), we fail (cannot validate).
- Hardened against varying EnforcementMethod._create_finding() signatures.
"""

from __future__ import annotations

import ast
import inspect
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

RULE_PURITY_SAFETY_CONTRACT_REQUIRED = "purity.safety_contract_required"

_SAFETY_DOCSTRING_MARKER = "SAFETY CONTRACT"
_SAFETY_CONST_NAME = "SAFETY_CONTRACT"


def _create_finding_safe(method: EnforcementMethod, **kwargs: Any) -> AuditFinding:
    """
    EnforcementMethod._create_finding() signature varies across CORE versions.

    We only pass parameters supported by the runtime signature to prevent
    unexpected keyword argument errors.
    """
    sig = inspect.signature(method._create_finding)  # type: ignore[attr-defined]
    allowed = set(sig.parameters.keys())
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    return method._create_finding(**filtered)  # type: ignore[attr-defined]


def _rel(repo_path: Path, p: Path) -> str:
    try:
        return str(p.relative_to(repo_path))
    except Exception:
        return str(p)


def _parse_file(p: Path) -> ast.AST | None:
    try:
        src = p.read_text(encoding="utf-8")
        return ast.parse(src, filename=str(p))
    except Exception as exc:
        logger.debug("PuritySafetyContractCheck: failed parsing %s: %s", p, exc)
        return None


def _module_docstring_contains(tree: ast.AST, marker: str) -> bool:
    doc = ast.get_docstring(tree)
    if not doc:
        return False
    return marker.lower() in doc.lower()


def _has_safety_contract_constant(tree: ast.AST) -> tuple[bool, str]:
    """
    Returns (ok, reason). Detects:
    - SAFETY_CONTRACT = {...}
    - SAFETY_CONTRACT = "non-empty"
    """
    for node in getattr(tree, "body", []):
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name) and tgt.id == _SAFETY_CONST_NAME:
                val = node.value
                if isinstance(val, ast.Dict):
                    return True, "constant_dict"
                if (
                    isinstance(val, ast.Constant)
                    and isinstance(val.value, str)
                    and val.value.strip()
                ):
                    return True, "constant_str"
                # Present but empty / wrong type
                return False, "constant_invalid"
    return False, "constant_missing"


def _collect_targets(repo_path: Path) -> dict[str, list[Path]]:
    """
    Collect safety-relevant modules.
    """
    body_root = repo_path / "src" / "body"
    actions_root = body_root / "actions"
    tools_root = body_root / "tools"

    targets: dict[str, list[Path]] = {"actions": [], "tools": []}

    if actions_root.exists():
        targets["actions"] = sorted(
            p for p in actions_root.rglob("*.py") if p.is_file()
        )

    if tools_root.exists():
        targets["tools"] = sorted(p for p in tools_root.rglob("*.py") if p.is_file())

    return targets


# Resolve policy file robustly (PathResolver keys vary between repos)
try:
    _POLICY_FILE = settings.paths.policy("code_purity")
except Exception:
    try:
        _POLICY_FILE = settings.paths.policy("purity")
    except Exception:
        _POLICY_FILE = (
            settings.REPO_PATH / ".intent" / "policies" / "code" / "code_purity.yaml"
        )


# ID: 98aa8d14-9bfa-4fa7-9f9b-bc4697b9f14c
class PuritySafetyContractRequiredEnforcement(EnforcementMethod):
    """
    Ensures safety contracts exist on safety-relevant Body primitives.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 2d0b5a4a-4b33-4d3c-9c86-4f40d5e0b0b6
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path

        targets = _collect_targets(repo_path)
        action_files = targets.get("actions", [])
        tool_files = targets.get("tools", [])

        # If we have no targets, we cannot validate; fail conservatively.
        if not action_files and not tool_files:
            return [
                _create_finding_safe(
                    self,
                    message="No safety-relevant Body modules discovered (expected at least src/body/actions or src/body/tools). Cannot validate purity.safety_contract_required.",
                    file_path="src/body",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "expected_roots": ["src/body/actions", "src/body/tools"],
                        "found": {
                            "actions_count": len(action_files),
                            "tools_count": len(tool_files),
                        },
                    },
                )
            ]

        violations: list[dict[str, Any]] = []
        parse_errors: list[dict[str, Any]] = []

        # ID: 7e0d5fc5-fb84-4266-94d2-75887624df49
        def inspect_module(p: Path, category: str) -> None:
            relp = _rel(repo_path, p)
            tree = _parse_file(p)
            if tree is None:
                parse_errors.append(
                    {"file": relp, "category": category, "error": "parse_failed"}
                )
                return

            # Pass if docstring contains marker
            if _module_docstring_contains(tree, _SAFETY_DOCSTRING_MARKER):
                return

            # Pass if constant exists and is usable
            ok_const, reason = _has_safety_contract_constant(tree)
            if ok_const:
                return

            violations.append(
                {
                    "file": relp,
                    "category": category,
                    "reason": reason,
                    "expected_one_of": [
                        f'module docstring contains "{_SAFETY_DOCSTRING_MARKER}"',
                        f"{_SAFETY_CONST_NAME} = {{...}}",
                        f'{_SAFETY_CONST_NAME} = "non-empty"',
                    ],
                }
            )

        for p in action_files:
            inspect_module(p, "actions")
        for p in tool_files:
            inspect_module(p, "tools")

        if violations or parse_errors:
            return [
                _create_finding_safe(
                    self,
                    message="Safety contracts are required on Body actions/tools, but some modules are missing a discoverable safety contract.",
                    file_path="src/body",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "analysis": {
                            "actions_scanned": len(action_files),
                            "tools_scanned": len(tool_files),
                        },
                        "violations_count": len(violations),
                        "parse_errors_count": len(parse_errors),
                        "violations": violations[:200],
                        "parse_errors": parse_errors[:50],
                        "marker": _SAFETY_DOCSTRING_MARKER,
                        "constant": _SAFETY_CONST_NAME,
                    },
                )
            ]

        return []


# ID: 3b5b81aa-2d59-4f86-9f1c-fb1e21a69a9a
class PuritySafetyContractCheck(RuleEnforcementCheck):
    """
    Enforces purity.safety_contract_required.

    Ref:
    - standard_code_purity
    """

    policy_rule_ids: ClassVar[list[str]] = [RULE_PURITY_SAFETY_CONTRACT_REQUIRED]
    policy_file: ClassVar[Path] = Path(_POLICY_FILE)

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        PuritySafetyContractRequiredEnforcement(
            rule_id=RULE_PURITY_SAFETY_CONTRACT_REQUIRED,
            severity=AuditSeverity.ERROR,
        )
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
