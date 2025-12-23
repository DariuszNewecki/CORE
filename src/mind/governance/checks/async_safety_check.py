# src/mind/governance/checks/async_safety_check.py
"""
Enforces Async-Native architecture.

Prevents usage of asyncio.run() (or equivalent aliases) in business logic
to ensure composability and avoid manual event-loop management.

Ref: .intent/policies/code/code_standards.json
"""

from __future__ import annotations

import ast
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: async-loop-enforcement
# ID: e0e509d4-baad-4e34-82cc-5d577531ee87
class AsyncLoopManagementEnforcement(EnforcementMethod):
    """
    Verifies that business logic doesn't call asyncio.run() directly.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: a0d9e7fa-0f83-4eb7-ac43-bcb4494b852d
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        # Files allowed to manage the loop (CLI entry points / explicit sync wrappers)
        whitelist = [
            "src/main.py",
            "src/shared/cli_utils.py",
        ]

        python_files = getattr(context, "python_files", None)
        if python_files is None:
            python_files = context.get_files(include=["src/**/*.py"])

        for file_path in python_files:
            rel_path = str(file_path.relative_to(context.repo_path))

            if any(rel_path.endswith(w) for w in whitelist):
                continue

            # Skip tests
            if "tests/" in rel_path or rel_path.startswith("tests/"):
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                asyncio_module_names, asyncio_run_names = self._extract_asyncio_aliases(
                    tree
                )

                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue

                    if self._is_asyncio_run_call(
                        node,
                        asyncio_module_names=asyncio_module_names,
                        asyncio_run_names=asyncio_run_names,
                    ):
                        findings.append(
                            self._create_finding(
                                message=(
                                    "Found explicit asyncio.run() (or alias). "
                                    "Logic must be 'async def' and awaited, not executed in a new loop."
                                ),
                                file_path=rel_path,
                                line_number=getattr(node, "lineno", 1),
                            )
                        )

            except SyntaxError:
                # Parse error handled by other checks
                continue
            except Exception:
                # Keep audits resilient; other checks / diagnostics will surface details.
                continue

        return findings

    def _extract_asyncio_aliases(self, tree: ast.AST) -> tuple[set[str], set[str]]:
        """
        Detects:
          - import asyncio [as X]  -> module name(s) that reference asyncio
          - from asyncio import run [as Y] -> function name(s) that reference run
        """
        asyncio_module_names: set[str] = set()
        asyncio_run_names: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "asyncio":
                        asyncio_module_names.add(alias.asname or "asyncio")

            elif isinstance(node, ast.ImportFrom):
                if node.module == "asyncio":
                    for alias in node.names:
                        if alias.name == "run":
                            asyncio_run_names.add(alias.asname or "run")

        return asyncio_module_names, asyncio_run_names

    def _is_asyncio_run_call(
        self,
        node: ast.Call,
        *,
        asyncio_module_names: set[str],
        asyncio_run_names: set[str],
    ) -> bool:
        """
        Matches:
          - asyncio.run(...)
          - aio.run(...) where `import asyncio as aio`
          - run(...) where `from asyncio import run`
          - arun(...) where `from asyncio import run as arun`
        """
        func = node.func

        # asyncio.run(...) or alias.run(...)
        if isinstance(func, ast.Attribute) and func.attr == "run":
            if (
                isinstance(func.value, ast.Name)
                and func.value.id in asyncio_module_names
            ):
                return True

        # run(...) where imported from asyncio
        if isinstance(func, ast.Name) and func.id in asyncio_run_names:
            return True

        return False


# ID: d34b8d0d-89fc-40ed-989f-807e0eb5e384
class AsyncSafetyCheck(RuleEnforcementCheck):
    """
    Enforces Async-Native architecture.

    Prevents usage of asyncio.run() (or equivalent aliases) in business logic
    to ensure composability and avoid manual event-loop management.

    Ref: .intent/policies/code/code_standards.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["async.no_manual_loop_management"]

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        AsyncLoopManagementEnforcement(rule_id="async.no_manual_loop_management"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
