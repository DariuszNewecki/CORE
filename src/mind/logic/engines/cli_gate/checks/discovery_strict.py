# src/mind/logic/engines/cli_gate/checks/discovery_strict.py

"""Verifies cli.discovery_strict: CLI module imports MUST be fail-fast.

Source-AST inspection of the loader (``params.loader``, typically
``src/cli/admin_cli.py``). The rule is satisfied when every import of a
``cli.*`` submodule is a top-level static import — neither wrapped in a
``try/except`` that swallows ``ImportError``/``Exception``/bare except,
nor lazy-loaded via ``importlib.import_module`` with the same error
suppression.

ACCEPTANCE: wrapping any CLI import in ``try: ... except ImportError:``
must produce a violation.
"""

from __future__ import annotations

import ast
from typing import Any

from mind.logic.engines.cli_gate.base_check import CliCheck
from shared.models import AuditFinding, AuditSeverity
from shared.path_resolver import PathResolver


_SUPPRESSED_EXCEPTIONS: frozenset[str] = frozenset(
    {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}
)


def _handler_suppresses_import(handler: ast.ExceptHandler) -> bool:
    """A handler 'suppresses' an import error if it catches one of the
    import-related exception types (or bare except), regardless of body
    contents. We do not try to distinguish raise-from-handler patterns —
    if the rule wanted strict re-raise detection it would say so."""
    exc_type = handler.type
    if exc_type is None:
        return True
    if isinstance(exc_type, ast.Name):
        return exc_type.id in _SUPPRESSED_EXCEPTIONS
    if isinstance(exc_type, ast.Tuple):
        for elt in exc_type.elts:
            if isinstance(elt, ast.Name) and elt.id in _SUPPRESSED_EXCEPTIONS:
                return True
    return False


def _node_imports_cli(node: ast.AST) -> bool:
    """True if ``node`` (or any descendant) imports a ``cli.*`` module
    via either an ``import``/``from`` statement or a runtime
    ``importlib.import_module("cli...")`` call.
    """
    for descendant in ast.walk(node):
        if isinstance(descendant, ast.ImportFrom):
            module = descendant.module or ""
            if module == "cli" or module.startswith("cli."):
                return True
        elif isinstance(descendant, ast.Import):
            for alias in descendant.names:
                if alias.name == "cli" or alias.name.startswith("cli."):
                    return True
        elif isinstance(descendant, ast.Call):
            func = descendant.func
            target = ""
            if isinstance(func, ast.Attribute) and func.attr == "import_module":
                if isinstance(func.value, ast.Name) and func.value.id == "importlib":
                    if descendant.args and isinstance(descendant.args[0], ast.Constant):
                        target = descendant.args[0].value or ""
            elif isinstance(func, ast.Name) and func.id == "__import__":
                if descendant.args and isinstance(descendant.args[0], ast.Constant):
                    target = descendant.args[0].value or ""
            if isinstance(target, str) and (
                target == "cli" or target.startswith("cli.")
            ):
                return True
    return False


# ID: 036adebf-7ba4-42fd-b493-a3d2d9babcbb
class DiscoveryStrictCheck(CliCheck):
    check_type = "discovery_strict"

    # ID: 98c6f6f8-8969-465c-93d2-2db724850f5f
    def __init__(self, path_resolver: PathResolver) -> None:
        self._path_resolver = path_resolver

    # ID: 2dfdadbc-7a0f-4523-ba72-6b066a7f48da
    def verify(
        self, commands: list[dict[str, Any]], params: dict[str, Any]
    ) -> list[AuditFinding]:
        loader_rel = params.get("loader")
        if not loader_rel:
            return [
                AuditFinding(
                    check_id="cli_gate.discovery_strict",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        "discovery_strict mapping is missing the 'loader' parameter."
                    ),
                    file_path="none",
                )
            ]

        loader_path = (self._path_resolver.repo_root / loader_rel).resolve()
        if not loader_path.is_file():
            return [
                AuditFinding(
                    check_id="cli_gate.discovery_strict",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"discovery_strict loader '{loader_rel}' not found on disk."
                    ),
                    file_path=str(loader_rel),
                )
            ]

        try:
            source = loader_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(loader_path))
        except Exception as exc:
            return [
                AuditFinding(
                    check_id="cli_gate.discovery_strict",
                    severity=AuditSeverity.BLOCK,
                    message=(
                        f"discovery_strict could not parse loader '{loader_rel}': {exc}"
                    ),
                    file_path=str(loader_rel),
                )
            ]

        findings: list[AuditFinding] = []
        loader_str = str(loader_rel)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            body_imports_cli = any(_node_imports_cli(stmt) for stmt in node.body)
            if not body_imports_cli:
                continue
            for handler in node.handlers:
                if _handler_suppresses_import(handler):
                    handler_label = (
                        handler.type.id
                        if isinstance(handler.type, ast.Name)
                        else "bare/multi"
                    )
                    findings.append(
                        AuditFinding(
                            check_id="cli_gate.discovery_strict",
                            severity=AuditSeverity.BLOCK,
                            message=(
                                f"CLI import inside try/except {handler_label} "
                                f"at {loader_rel}:{node.lineno} — discovery "
                                "must be fail-fast."
                            ),
                            file_path=loader_str,
                            context={
                                "loader": loader_str,
                                "line": node.lineno,
                                "handler": handler_label,
                            },
                        )
                    )
                    break  # one finding per try/except block

        return findings
