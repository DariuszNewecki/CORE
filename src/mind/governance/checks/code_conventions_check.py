# src/mind/governance/checks/code_conventions_check.py
# ID: model.mind.governance.checks.code_conventions_check
"""
Constitutional check for Code Convention style rules.

This module uses the RuleEnforcementCheck template to verify:
- style.capability_id_placement (warn)
- style.import_order (warn)
- style.universal_helper_first (warn)

Ref: .intent/charter/standards/code_standards.json
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.checks.rule_enforcement_check import RuleEnforcementCheck
from mind.governance.enforcement_methods import EnforcementMethod
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

SRC_ROOT = Path("src")


def _iter_src_python_files(context) -> Iterable[Path]:
    """
    Prefer context-provided python_files for determinism; fall back to repository scan.
    Excludes test paths.
    """
    python_files = getattr(context, "python_files", None)
    if python_files is not None:
        for p in python_files:
            try:
                rel = p.relative_to(context.repo_path)
            except Exception:
                continue

            rel_s = str(rel).replace("\\", "/")
            if not rel_s.startswith("src/"):
                continue
            if "tests/" in rel_s or rel_s.startswith("tests/") or "/test" in rel_s:
                continue
            yield p
        return

    # Fallback: minimal repo scan (should be avoided when context provides files)
    src_dir = context.repo_path / SRC_ROOT
    for p in src_dir.rglob("*.py"):
        rel_s = str(p.relative_to(context.repo_path)).replace("\\", "/")
        if "tests/" in rel_s or rel_s.startswith("tests/") or "/test" in rel_s:
            continue
        yield p


# ID: capability-id-placement-enforcement
# ID: d41aba48-91ac-4093-95eb-720c07725494
class CapabilityIdPlacementEnforcement(EnforcementMethod):
    """
    Verifies that ID tags are placed correctly:
    - Private helpers (starting with _) MUST NOT have IDs
    """

    # ID: 5bd1405a-2a34-4776-91ca-522e2a3250db
    def verify(
        self, context, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        for py_file in _iter_src_python_files(context):
            rel_path = str(py_file.relative_to(context.repo_path)).replace("\\", "/")

            try:
                content = py_file.read_text(encoding="utf-8")
                lines = content.splitlines()
                tree = ast.parse(content, filename=rel_path)

            except (SyntaxError, UnicodeDecodeError):
                # Handled elsewhere; keep check resilient and deterministic.
                continue
            except Exception as exc:
                logger.debug(
                    "CapabilityIdPlacementEnforcement failed for %s: %s", rel_path, exc
                )
                continue

            for node in ast.walk(tree):
                if not isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    continue

                if not getattr(node, "name", "").startswith("_"):
                    continue

                if self._has_id_comment(node, lines):
                    findings.append(
                        self._create_finding(
                            f"Private helper '{node.name}' must not have capability ID",
                            file_path=rel_path,
                            line_number=getattr(node, "lineno", 1),
                        )
                    )

        return findings

    def _has_id_comment(self, node: ast.AST, lines: list[str]) -> bool:
        """Check if symbol has # ID: comment above it."""
        lineno = getattr(node, "lineno", None)
        if lineno is None or lineno < 2:
            return False

        line_above = lines[lineno - 2] if lineno > 1 else ""
        return "# ID:" in line_above or "#ID:" in line_above


# ID: import-order-enforcement
# ID: ad35db1b-1b38-4d59-99e3-5580ce731b5a
class ImportOrderEnforcement(EnforcementMethod):
    """
    Verifies that imports follow canonical grouping:
    1. future imports
    2. stdlib
    3. third-party
    4. internal (shared/mind/body/will/features/etc.)
    """

    # ID: 7fab5f42-07db-4b06-8461-921f1dcdc32a
    def verify(
        self, context, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        for py_file in _iter_src_python_files(context):
            rel_path = str(py_file.relative_to(context.repo_path)).replace("\\", "/")

            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=rel_path)
            except (SyntaxError, UnicodeDecodeError):
                continue
            except Exception as exc:
                logger.debug("ImportOrderEnforcement failed for %s: %s", rel_path, exc)
                continue

            imports = self._extract_imports(tree)
            if not imports:
                continue

            if not self._are_imports_ordered(imports):
                findings.append(
                    self._create_finding(
                        "Imports not properly grouped (future→stdlib→third-party→internal)",
                        file_path=rel_path,
                        line_number=imports[0]["line"],
                    )
                )

        return findings

    def _extract_imports(self, tree: ast.AST) -> list[dict[str, Any]]:
        """Extract import statements with classification and line numbers."""
        imports: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue

            module = getattr(node, "module", None)
            if isinstance(node, ast.Import) and node.names:
                module = node.names[0].name.split(".")[0]

            imports.append(
                {
                    "line": getattr(node, "lineno", 1),
                    "type": self._classify_import(module or ""),
                    "module": module or "",
                }
            )

        return sorted(imports, key=lambda x: x["line"])

    def _classify_import(self, module: str) -> str:
        """Classify import as future/stdlib/third-party/internal."""
        root = module.split(".")[0]

        if root == "__future__":
            return "future"

        # Keep list intentionally small; classification is heuristic.
        stdlib_modules = {
            "ast",
            "asyncio",
            "collections",
            "dataclasses",
            "datetime",
            "functools",
            "hashlib",
            "io",
            "itertools",
            "json",
            "logging",
            "os",
            "pathlib",
            "re",
            "subprocess",
            "sys",
            "time",
            "typing",
            "uuid",
        }
        if root in stdlib_modules:
            return "stdlib"

        if root.startswith(
            ("shared", "mind", "body", "will", "services", "features", "api", "src")
        ):
            return "internal"

        return "third_party"

    def _are_imports_ordered(self, imports: list[dict[str, Any]]) -> bool:
        """Check if imports follow canonical order."""
        order = ["future", "stdlib", "third_party", "internal"]
        current_group_idx = 0

        for imp in imports:
            imp_idx = order.index(imp["type"])
            if imp_idx < current_group_idx:
                return False
            current_group_idx = imp_idx

        return True


# ID: universal-helper-first-enforcement
# ID: b0914393-0e02-46fd-9fba-a291c32d4745
class UniversalHelperFirstEnforcement(EnforcementMethod):
    """
    Soft check: verifies shared.universal exists and contains at least one public helper.
    """

    # ID: aa30205a-22e5-4111-9863-efd4aeabd1e5
    def verify(
        self, context, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        universal_path = context.repo_path / "src/shared/universal.py"
        rel_path = "src/shared/universal.py"

        if not universal_path.exists():
            findings.append(
                self._create_finding(
                    "shared.universal module missing - developers have no place to check for reusable helpers",
                    file_path=rel_path,
                )
            )
            return findings

        try:
            content = universal_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=rel_path)
        except (SyntaxError, UnicodeDecodeError) as exc:
            findings.append(
                self._create_finding(
                    f"Failed to parse shared.universal: {exc}",
                    file_path=rel_path,
                )
            )
            return findings

        func_count = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not getattr(node, "name", "").startswith("_")
        )

        if func_count == 0:
            findings.append(
                self._create_finding(
                    "shared.universal exists but has no public helpers - populate it with commonly-used utilities",
                    file_path=rel_path,
                )
            )

        return findings


# ID: code-conventions-check
# ID: 367bb8bb-65f3-4163-84f0-1d1e56eb6e33
class CodeConventionsCheck(RuleEnforcementCheck):
    """
    Verifies code convention style standards.

    Ref: .intent/charter/standards/code_standards.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "style.capability_id_placement",
        "style.import_order",
        "style.universal_helper_first",
    ]
    id: ClassVar[str] = "code_conventions"

    policy_file: ClassVar = settings.paths.policy("code_standards")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        CapabilityIdPlacementEnforcement(
            rule_id="style.capability_id_placement",
            severity=AuditSeverity.WARNING,
        ),
        ImportOrderEnforcement(
            rule_id="style.import_order",
            severity=AuditSeverity.WARNING,
        ),
        UniversalHelperFirstEnforcement(
            rule_id="style.universal_helper_first",
            severity=AuditSeverity.WARNING,
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
