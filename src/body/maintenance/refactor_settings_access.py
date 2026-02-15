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
# ID: d9f574fb-f11e-4719-8dc2-6aedf598c784
class SettingsUsage:
    """Track where settings is used in a file."""

    file_path: Path
    import_line: int
    usages: list[tuple[int, str]]  # (line_num, attribute like "REPO_PATH")
    has_constructor: bool
    constructor_line: int | None


@dataclass
# ID: 8973cfe0-c350-46d8-a8c7-8a10c929d316
class RefactorPlan:
    """Plan for refactoring a single file."""

    file_path: Path
    remove_import: int  # Line to remove
    add_context_param: int | None  # Where to add context param
    replacements: list[tuple[int, str, str]]  # (line, old, new)


# ID: 161a5d9a-0b33-43f7-b4dc-d18c4ba8b6c8
class SettingsRefactorer:
    """Refactors settings imports to DI pattern."""

    SETTINGS_PATTERN = re.compile(r"from shared\.config import (?:settings|Settings)")
    USAGE_PATTERN = re.compile(r"settings\.(\w+)")

    def __init__(self, repo_path: Path, file_handler: FileHandler):
        self.repo_path = repo_path
        self.file_handler = file_handler

    # ID: ab5ab5ba-e544-4f5f-b692-6565ef5524ee
    def analyze_file(self, file_path: Path) -> SettingsUsage | None:
        """Analyze a file for settings usage."""
        try:
            content = file_path.read_text()
            lines = content.splitlines()
        except Exception as e:
            logger.error("Failed to read %s: %s", file_path, e)
            return None

        # Find import line
        import_line = None
        for i, line in enumerate(lines, 1):
            if self.SETTINGS_PATTERN.search(line):
                import_line = i
                break

        if not import_line:
            return None

        # Find all usages
        usages = []
        for i, line in enumerate(lines, 1):
            for match in self.USAGE_PATTERN.finditer(line):
                attr = match.group(1)
                usages.append((i, attr))

        # Detect constructor
        has_constructor, constructor_line = self._find_constructor(lines)

        return SettingsUsage(
            file_path=file_path,
            import_line=import_line,
            usages=usages,
            has_constructor=has_constructor,
            constructor_line=constructor_line,
        )

    def _find_constructor(self, lines: list[str]) -> tuple[bool, int | None]:
        """Find __init__ method if exists."""
        for i, line in enumerate(lines, 1):
            if re.match(r"\s*def __init__\(", line):
                return True, i
        return False, None

    # ID: e5d39e35-cebb-431f-8437-3afa3d3b5891
    def create_refactor_plan(self, usage: SettingsUsage) -> RefactorPlan:
        """Create refactoring plan for a file."""
        replacements = []

        # Map common settings attributes to context equivalents
        ATTR_MAP = {
            "REPO_PATH": "context.repo_path",
            "MIND": "context.path_resolver.intent_root",
            "LOCAL_EMBEDDING_MODEL_NAME": "context.embedding_model",
            # Add more as needed
        }

        content = usage.file_path.read_text()
        lines = content.splitlines()

        for line_num, attr in usage.usages:
            old_expr = f"settings.{attr}"
            new_expr = ATTR_MAP.get(attr, f"context.settings.{attr}")
            replacements.append((line_num, old_expr, new_expr))

        # Where to add context parameter
        add_at = None
        if usage.has_constructor:
            add_at = usage.constructor_line
        else:
            # Find first class or function definition
            for i, line in enumerate(lines, 1):
                if re.match(r"\s*(?:class|def)\s+", line):
                    add_at = i
                    break

        return RefactorPlan(
            file_path=usage.file_path,
            remove_import=usage.import_line,
            add_context_param=add_at,
            replacements=replacements,
        )

    # ID: c3a4b818-5de9-41f3-b264-b4cd4dd8685b
    def apply_refactor(self, plan: RefactorPlan, dry_run: bool = True) -> bool:
        """Apply refactoring plan to a file."""
        try:
            content = plan.file_path.read_text()
            lines = content.splitlines()

            # 1. Remove settings import
            lines[plan.remove_import - 1] = (
                "# REFACTORED: Removed direct settings import"
            )

            # 2. Add context import if needed
            if "from shared.context import CoreContext" not in content:
                # Insert after other imports
                last_import = 0
                for i, line in enumerate(lines):
                    if line.startswith("from ") or line.startswith("import "):
                        last_import = i
                lines.insert(last_import + 1, "from shared.context import CoreContext")

            # 3. Add context parameter to constructor/function
            if plan.add_context_param:
                line_idx = plan.add_context_param - 1
                line = lines[line_idx]

                # Detect if it's __init__, regular method, or function
                if "def __init__(self" in line:
                    # Add after self
                    line = line.replace("self)", "self, context: CoreContext)")
                    line = line.replace("self,", "self, context: CoreContext,")
                    lines[line_idx] = line

                    # Add instance variable
                    indent = len(line) - len(line.lstrip())
                    lines.insert(
                        line_idx + 1, " " * (indent + 4) + "self.context = context"
                    )

            # 4. Apply replacements
            for line_num, old, new in plan.replacements:
                line_idx = line_num - 1
                if old in lines[line_idx]:
                    # If we added self.context, use that
                    if "def __init__" in content:
                        new = new.replace("context.", "self.context.")
                    lines[line_idx] = lines[line_idx].replace(old, new)

            new_content = "\n".join(lines) + "\n"

            if dry_run:
                logger.info("DRY RUN: Would refactor %s", plan.file_path)
                return True

            # Use FileHandler for governed write
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


# ID: cc7d3fce-9594-45fe-8c0d-8609f969ef42
# ID: ecb86a95-d78b-4fa3-8031-bfc250372621
async def refactor_settings_access(
    repo_path: Path, layers: list[str] | None = None, dry_run: bool = True
) -> dict[str, Any]:
    """
    Main entry point for settings refactoring.

    Args:
        repo_path: Repository root
        layers: Layers to refactor (default: ['mind', 'will'])
        dry_run: If True, only analyze without making changes
    """
    if layers is None:
        layers = ["mind", "will"]  # Don't refactor body - it can use settings

    file_handler = FileHandler(str(repo_path))
    refactorer = SettingsRefactorer(repo_path, file_handler)

    all_results = {}

    for layer in layers:
        logger.info("=" * 60)
        logger.info("Refactoring layer: %s", layer)
        logger.info("=" * 60)

        results = refactorer.refactor_layer(layer, dry_run=dry_run)
        all_results[layer] = results

        logger.info(
            "Layer %s: analyzed=%d, planned=%d, refactored=%d, failed=%d",
            layer,
            results["analyzed"],
            results["planned"],
            results["refactored"],
            results["failed"],
        )

    return all_results
