# src/body/cli/logic/body_contracts_checker.py
"""
Body Contracts Checker

Static validator for `.intent/patterns/body_contracts.json`.

It enforces a subset of the Body Layer Execution Contract:

- Headless execution (no UI imports / print / input in Body modules)
- Safe-by-default write semantics (write defaults must NOT be True)
- No direct os.environ access in Body code (configuration must go via settings)

This checker is intentionally conservative and file-path aware:
- It applies UI rules to features/*, services/*, body/cli/logic/*, etc.
- It SKIPS UI rules for `body/cli/commands/*`, which are treated as
  workflow/CLI layer and allowed to own terminal UI.
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

    These files are allowed to own UI (Rich, print) according to the
    workflow UI contract. We still may want to inspect them later for
    write semantics, but UI rules are skipped here.
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
        # src/body/cli/commands/...
        return len(parts) >= 4 and parts[3] == "commands"
    return False


def _iter_python_files(repo_root: Path) -> list[Path]:
    candidates: list[Path] = []
    for pattern in [
        "src/features/**/*.py",
        "src/services/**/*.py",
        "src/body/cli/logic/**/*.py",
        "src/body/*/actions/**/*.py",
        # Many services live directly under src/body or src/services anyway
    ]:
        candidates.extend(repo_root.glob(pattern))
    # De-duplicate and filter tests
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
    Enforce `write_defaults_false`:

    Any parameter named 'write' that has a default value MUST NOT default to True.
    """
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            defaults = list(args.defaults)
            # Map last N defaults to last N positional args
            pos_args = args.args
            offset = len(pos_args) - len(defaults)

            for idx, default in enumerate(defaults):
                arg = pos_args[offset + idx]
                if arg.arg != "write":
                    continue

                # We only care if default is literally True
                if isinstance(default, ast.Constant) and default.value is True:
                    violations.append(
                        Violation(
                            rule_id="write_defaults_false",
                            message="Parameter 'write' MUST NOT default to True in Body code.",
                            file=path,
                            line=getattr(node, "lineno", None),
                        )
                    )

            # Also check keyword-only args
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
    Enforce `no_envvar_access_in_body` (warning-level rule in body_contracts).

    We still surface it as a violation so workflows can report it. Whether
    it fails the build depends on how the ActionResult is interpreted.
    """
    violations: list[Violation] = []

    for node in ast.walk(tree):
        # os.environ
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
        # os.environ["KEY"]
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

    Returns:
        ActionResult with:
          - ok: False if any error-level violations found
          - data:
              - file_count
              - violation_count
              - violations: List[dict]
              - rules_triggered: Set of rule_ids
    """
    start_time = time.time()

    logger.info("Running Body Contracts checks under %s", repo_root)

    files = _iter_python_files(repo_root)
    violations: list[Violation] = []

    for path in files:
        try:
            source = path.read_text(encoding="utf-8")
        except Exception as e:  # pragma: no cover - defensive
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

    # Decide ok/failure:
    # - Treat 'write_defaults_false' and 'no_ui_imports_in_body' and
    #   'no_print_or_input_in_body' and 'syntax_error' as error-level.
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
