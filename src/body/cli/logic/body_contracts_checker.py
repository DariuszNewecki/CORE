# src/body/cli/logic/body_contracts_checker.py
"""
Body Contracts Checker
Static validator for `.intent/patterns/body_contracts.json`.

UPDATED: Removed 'src/features' from scan patterns (Wave 3 Rebirth).
Now scans Mind, Body, and Will layers for UI leaks.
"""

from __future__ import annotations

import ast
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
# ID: 00f8abb3-bdf4-4bf0-ac23-579e539ddd3b
class Violation:
    rule_id: str
    message: str
    file: Path
    line: int | None = None

    # ID: 0b558899-1ebe-4119-b67e-38f2aa06f618
    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "message": self.message,
            "file": str(self.file),
            "line": self.line,
        }


def _is_test_file(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if "tests" in parts:
        return True
    if path.name.startswith("test_") or path.name.endswith("_test.py"):
        return True
    return False


def _is_cli_command(path: Path, repo_root: Path) -> bool:
    """
    Treat `body/cli/commands/*` as CLI/Workflow layer.
    """
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        return False

    parts = rel.parts
    if (
        len(parts) >= 3
        and parts[0] == "src"
        and parts[1] == "body"
        and parts[2] == "cli"
    ):
        return len(parts) >= 4 and parts[3] == "commands"
    return False


def _iter_python_files(repo_root: Path) -> list[Path]:
    """
    Finds all Python files in the new layered architecture.
    """
    candidates: list[Path] = []
    # UPDATED: We now check the new Mind, Body, and Will homes
    for pattern in [
        "src/mind/**/*.py",
        "src/body/**/*.py",
        "src/will/**/*.py",
        "src/shared/**/*.py",
        "src/api/**/*.py",
    ]:
        candidates.extend(repo_root.glob(pattern))

    unique = []
    seen = set()
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        if not p.is_file():
            continue
        if _is_test_file(p):
            continue
        unique.append(p)
    return unique


def _check_rich_imports(path: Path, tree: ast.AST, repo_root: Path) -> list[Violation]:
    """Enforce `no_ui_imports_in_body` except for CLI commands."""
    if _is_cli_command(path, repo_root):
        return []

    violations: list[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top == "rich":
                    violations.append(
                        Violation(
                            rule_id="no_ui_imports_in_body",
                            message="Rich UI import is not allowed in Body modules.",
                            file=path,
                            line=getattr(node, "lineno", None),
                        )
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top == "rich":
                    violations.append(
                        Violation(
                            rule_id="no_ui_imports_in_body",
                            message="Rich UI import is not allowed in Body modules.",
                            file=path,
                            line=getattr(node, "lineno", None),
                        )
                    )
    return violations


def _check_print_and_input(
    path: Path, tree: ast.AST, repo_root: Path
) -> list[Violation]:
    """Enforce `no_print_or_input_in_body` except for CLI commands."""
    if _is_cli_command(path, repo_root):
        return []

    violations: list[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in {"print", "input"}:
                violations.append(
                    Violation(
                        rule_id="no_print_or_input_in_body",
                        message=f"Use of {func.id}() is not allowed in Body modules.",
                        file=path,
                        line=getattr(node, "lineno", None),
                    )
                )
    return violations


def _check_write_defaults(path: Path, tree: ast.AST) -> list[Violation]:
    """
    Enforce `write_defaults_false`.
    """
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            defaults = list(args.defaults)
            pos_args = args.args
            offset = len(pos_args) - len(defaults)

            for idx, default in enumerate(defaults):
                arg = pos_args[offset + idx]
                if arg.arg != "write":
                    continue

                if isinstance(default, ast.Constant) and default.value is True:
                    violations.append(
                        Violation(
                            rule_id="write_defaults_false",
                            message="Parameter 'write' MUST NOT default to True in Body code.",
                            file=path,
                            line=getattr(node, "lineno", None),
                        )
                    )

            for kwarg, default in zip(args.kwonlyargs, args.kw_defaults):
                if kwarg.arg != "write":
                    continue
                if isinstance(default, ast.Constant) and default.value is True:
                    violations.append(
                        Violation(
                            rule_id="write_defaults_false",
                            message="Keyword-only parameter 'write' MUST NOT default to True in Body code.",
                            file=path,
                            line=getattr(node, "lineno", None),
                        )
                    )

    return violations


def _check_os_environ(path: Path, tree: ast.AST) -> list[Violation]:
    """
    Enforce `no_envvar_access_in_body`.
    """
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr == "environ"
            ):
                violations.append(
                    Violation(
                        rule_id="no_envvar_access_in_body",
                        message="Direct os.environ access found; Body code should use shared.config.settings.",
                        file=path,
                        line=getattr(node, "lineno", None),
                    )
                )
        if isinstance(node, ast.Subscript):
            val = node.value
            if isinstance(val, ast.Attribute):
                if (
                    isinstance(val.value, ast.Name)
                    and val.value.id == "os"
                    and val.attr == "environ"
                ):
                    violations.append(
                        Violation(
                            rule_id="no_envvar_access_in_body",
                            message="Direct os.environ[...] access found; Body code should use shared.config.settings.",
                            file=path,
                            line=getattr(node, "lineno", None),
                        )
                    )
    return violations


# ID: 0c64e50f-f972-4027-893f-5702662871b5
@atomic_action(
    action_id="check.body-contracts",
    intent="Validate Body layer headless contract compliance",
    impact=ActionImpact.READ_ONLY,
    policies=["body_contracts"],
    category="checks",
)
# ID: ad55c8fb-3c0d-4d32-9ea0-7b4b773360b3
async def check_body_contracts(
    repo_root: Path,
) -> ActionResult:
    """
    Run Body Contracts checks over the repository.
    """
    start_time = time.time()

    logger.info("Running Body Contracts checks under %s", repo_root)

    files = _iter_python_files(repo_root)
    violations: list[Violation] = []

    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Skipping file %s (read error: %s)", path, e)
            continue

        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            violations.append(
                Violation(
                    rule_id="syntax_error",
                    message=f"File has syntax error: {e}",
                    file=path,
                    line=getattr(e, "lineno", None),
                )
            )
            continue

        violations.extend(_check_rich_imports(path, tree, repo_root))
        violations.extend(_check_print_and_input(path, tree, repo_root))
        violations.extend(_check_write_defaults(path, tree))
        violations.extend(_check_os_environ(path, tree))

    violation_dicts = [v.to_dict() for v in violations]
    rules_triggered = sorted({v.rule_id for v in violations})

    error_rules = {
        "write_defaults_false",
        "no_ui_imports_in_body",
        "no_print_or_input_in_body",
        "syntax_error",
    }
    has_error = any(v.rule_id in error_rules for v in violations)

    return ActionResult(
        action_id="check.body-contracts",
        ok=not has_error,
        data={
            "file_count": len(files),
            "violation_count": len(violations),
            "violations": violation_dicts,
            "rules_triggered": rules_triggered,
        },
        duration_sec=time.time() - start_time,
        impact=ActionImpact.READ_ONLY,
    )
