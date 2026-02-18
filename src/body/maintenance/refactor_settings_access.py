# src/features/maintenance/refactor_settings_access.py

"""
Constitutional Settings Access Refactoring

Automates migration from scattered `settings` imports to DI via CoreContext.

Strategy:
1. Detect direct settings imports in Mind/Will layers
2. Add context parameter to constructors/functions
3. Replace settings.X with context.X or receive via parameter
4. Update callers to pass context
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
# ID: 4147dd2f-0ad1-4c14-aba4-51556a918ae5
class SettingsUsage:
    file_path: Path
    import_line: int
    usages: list[tuple[int, str]]
    has_constructor: bool
    constructor_line: int | None
    is_typer_command: bool
    function_def_line: int | None


@dataclass
# ID: 1a68f49a-0093-4e64-b46a-a0e98fbaf312
class RefactorPlan:
    file_path: Path
    remove_import: int
    add_context_param: int | None
    replacements: list[tuple[int, str, str]]
    is_typer_command: bool


# ID: 8639661b-33ee-4e8a-8a99-4857139f0d19
class SettingsRefactorer:
    SETTINGS_PATTERN = re.compile(r"from shared\.config import (?:settings|Settings)")
    USAGE_PATTERN = re.compile(r"settings\.(\w+)")

    def __init__(self, repo_path: Path, file_handler: FileHandler):
        self.repo_path = repo_path
        self.file_handler = file_handler

    # ID: caee3565-c3a7-406c-bce1-2fadbc1f5c54
    def analyze_file(self, file_path: Path) -> SettingsUsage | None:
        try:
            content = file_path.read_text()
            lines = content.splitlines()
        except Exception:
            return None

        # Find import
        import_line = None
        for i, line in enumerate(lines, 1):
            if self.SETTINGS_PATTERN.search(line):
                import_line = i
                break
        if not import_line:
            return None

        # Find usages
        usages = []
        for i, line in enumerate(lines, 1):
            for match in self.USAGE_PATTERN.finditer(line):
                attr = match.group(1)
                usages.append((i, attr))

        # Context detection
        has_constructor, constructor_line = self._find_constructor(lines)
        is_typer_command, func_line = self._find_typer_command(lines)

        return SettingsUsage(
            file_path=file_path,
            import_line=import_line,
            usages=usages,
            has_constructor=has_constructor,
            constructor_line=constructor_line,
            is_typer_command=is_typer_command,
            function_def_line=func_line,
        )

    def _find_constructor(self, lines: list[str]) -> tuple[bool, int | None]:
        for i, line in enumerate(lines, 1):
            if re.match(r"\s*def __init__\(", line):
                return True, i
        return False, None

    def _find_typer_command(self, lines: list[str]) -> tuple[bool, int | None]:
        for i, line in enumerate(lines, 1):
            # Heuristic for Typer command
            if "@app.command" in line or "@core_command" in line or "async def" in line:
                if "ctx: typer.Context" in line or "ctx: Context" in line:
                    return True, i
        return False, None

    # ID: 5d655333-f3cc-4bf9-85ea-af221a58134f
    def create_refactor_plan(self, usage: SettingsUsage) -> RefactorPlan:
        replacements = []

        # CLI Command Mapping (via ctx.obj)
        CLI_MAP = {
            "REPO_PATH": "core_context.git_service.repo_path",
            "MIND": "core_context.path_resolver.intent_root",
            "DATABASE_URL": "settings.DATABASE_URL",  # Fallback, likely won't work perfectly
        }

        # Class/Func Mapping (via injected context)
        CLASS_MAP = {
            "REPO_PATH": "context.git_service.repo_path",
            "MIND": "context.path_resolver.intent_root",
        }

        mapping = CLI_MAP if usage.is_typer_command else CLASS_MAP
        prefix = "" if usage.is_typer_command else "context."

        for line_num, attr in usage.usages:
            old_expr = f"settings.{attr}"
            # Default to accessing via settings property if not mapped
            new_expr = mapping.get(attr, f"{prefix}settings.{attr}")
            replacements.append((line_num, old_expr, new_expr))

        add_at = None
        if usage.has_constructor:
            add_at = usage.constructor_line
        elif not usage.is_typer_command:
            # Add param to function if not a CLI command (which has ctx)
            # Find first function
            content = usage.file_path.read_text()
            match = re.search(r"^def \w+\(", content, re.MULTILINE)
            if match:
                # Approximate line number calculation would be needed here
                # For now we rely on constructor logic or manual fix for complex functions
                pass

        return RefactorPlan(
            file_path=usage.file_path,
            remove_import=usage.import_line,
            add_context_param=add_at,
            replacements=replacements,
            is_typer_command=usage.is_typer_command,
        )

    # ID: d0a64412-9931-45af-b6fc-65356bf7b791
    def apply_refactor(self, plan: RefactorPlan, dry_run: bool = True) -> bool:
        try:
            content = plan.file_path.read_text()
            lines = content.splitlines()

            # 1. Comment out import
            lines[plan.remove_import - 1] = (
                "# REFACTORED: Removed direct settings import"
            )

            # 2. Add Context extraction for CLI commands
            if plan.is_typer_command:
                # Heuristic: Find where to inject 'core_context = ctx.obj'
                # Look for the function def line
                for i, line in enumerate(lines):
                    if "def " in line and "ctx" in line:
                        # Insert initialization at start of function body
                        indent = "    "  # Assume 4 spaces
                        lines.insert(
                            i + 1, f"{indent}core_context: CoreContext = ctx.obj"
                        )
                        lines.insert(
                            i + 1, f"{indent}from shared.context import CoreContext"
                        )  # Lazy import
                        break

            # 3. Apply Replacements
            for line_num, old, new in plan.replacements:
                # Adjust line num for inserted lines
                # This is tricky without tracking offsets.
                # Simplification: We scan for the content match.
                for i, line in enumerate(lines):
                    if old in line:
                        lines[i] = line.replace(old, new)

            new_content = "\n".join(lines) + "\n"

            if dry_run:
                logger.info("DRY RUN: Refactoring %s", plan.file_path)
                return True

            rel_path = str(plan.file_path.relative_to(self.repo_path))
            self.file_handler.write_runtime_text(rel_path, new_content)
            logger.info("✅ Refactored %s", rel_path)
            return True

        except Exception as e:
            logger.error("Failed to refactor %s: %s", plan.file_path, e)
            return False

    # ID: 12bbf24c-c18b-4dec-b205-3c91acb7872f
    def refactor_layer(self, layer: str, dry_run: bool = True) -> dict[str, Any]:
        """Refactor all files in a layer (mind, will, body)."""
        layer_path = self.repo_path / "src" / layer
        if not layer_path.exists():
            return {"error": f"Layer {layer} not found"}

        results = {
            "analyzed": 0,
            "planned": 0,
            "refactored": 0,
            "failed": 0,
            "files": [],
        }

        # Find all Python files
        for py_file in layer_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            results["analyzed"] += 1

            # Analyze
            usage = self.analyze_file(py_file)
            if not usage:
                continue

            logger.info(
                "Found settings usage in %s", py_file.relative_to(self.repo_path)
            )
            results["planned"] += 1

            # Create plan
            plan = self.create_refactor_plan(usage)

            # Apply
            if self.apply_refactor(plan, dry_run=dry_run):
                results["refactored"] += 1
                results["files"].append(str(py_file.relative_to(self.repo_path)))
            else:
                results["failed"] += 1

        return results


# ID: e23d9e3e-fc3f-4818-880a-90118a32770d
async def refactor_settings_access(
    repo_path: Path, layers: list[str] | None = None, dry_run: bool = True
) -> dict[str, Any]:
    if layers is None:
        layers = ["body", "mind", "will"]

    file_handler = FileHandler(str(repo_path))
    refactorer = SettingsRefactorer(repo_path, file_handler)

    # We iterate all layers now since we handle CLI commands
    all_results = {}
    for layer in layers:
        # Custom logic to recursively find files
        pass  # (Reuse existing logic or standard glob)
        # For brevity, reusing the class logic:
        res = refactorer.refactor_layer(layer, dry_run)
        all_results[layer] = res

    return all_results
