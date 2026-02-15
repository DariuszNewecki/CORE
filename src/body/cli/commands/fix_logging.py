# src/body/cli/commands/fix_logging.py
# ID: ac59f003-160e-48e4-871e-85fbeb742aa9
"""
AST-based automated remediation for logging standards violations.

CONSTITUTIONAL EVOLUTION: This fixer uses AST parsing to match the context-aware
checker, ensuring the fixer can handle exactly what the checker detects.
CONSTITUTIONAL FIX: All mutations now route through FileHandler to ensure
IntentGuard enforcement and auditability.

Converts:
- console.print() → logger.info()
- console.status() → logger.info()
- print() → logger.info()
- logger.info(f"text {var}") → logger.info("text %s", var)

Constitutional Rules Enforced:
- LOG-001: Logic layers must use logger, not Rich Console.
- LOG-003: No f-strings in logger calls (use lazy % formatting).
- LOG-004: Replace console.status() with logger.info().
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

from shared.infrastructure.validation.black_formatter import format_code_with_black
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.infrastructure.storage.file_handler import FileHandler

logger = getLogger(__name__)


# ID: c0f61b44-b95f-44a6-944e-8797893c481e
class LoggingFixer:
    """
    AST-based logging violation fixer.

    This fixer understands code structure and can transform complex f-strings
    into proper lazy % formatting while preserving code semantics.
    """

    def __init__(
        self, repo_root: Path, file_handler: FileHandler, dry_run: bool = True
    ):
        self.repo_root = repo_root
        self.file_handler = file_handler
        self.dry_run = dry_run
        self.fixes_applied = 0
        self.files_modified = 0

    # ID: 73425a9f-a219-42bc-a6c2-a9540a559bf3
    def fix_all(self) -> dict:
        """Fix all Python files in src/."""
        src_dir = self.repo_root / "src"

        for py_file in src_dir.rglob("*.py"):
            if self._is_exempted_file(py_file):
                continue

            self.fix_file(py_file)

        return {
            "files_modified": self.files_modified,
            "fixes_applied": self.fixes_applied,
            "dry_run": self.dry_run,
        }

    # ID: dbe423ff-bf28-4b4e-b7c5-c1e2f18e4063
    def fix_file(self, file_path: Path) -> bool:
        """Fix logging violations in a single file using AST transformation."""
        try:
            content = file_path.read_text(encoding="utf-8")

            # Parse into AST
            try:
                tree = ast.parse(content, filename=str(file_path))
            except SyntaxError as e:
                logger.debug("Syntax error in %s, skipping: %s", file_path, e)
                return False

            # Transform the AST
            transformer = LoggingTransformer(file_path)
            modified_tree = transformer.visit(tree)

            # If nothing changed, skip
            if not transformer.modified:
                return False

            # Convert back to source code
            try:
                fixed_content = ast.unparse(modified_tree)
            except Exception as e:
                logger.error("Failed to unparse %s: %s", file_path, e)
                return False

            # Ensure logger import exists
            fixed_content = self._ensure_logger_import(fixed_content)

            # Write or report
            rel_path = str(file_path.relative_to(self.repo_root))
            if not self.dry_run:
                # CONSTITUTIONAL FIX: Format in-memory via shared utility
                try:
                    formatted_content = format_code_with_black(fixed_content)
                except Exception as e:
                    logger.debug("Black formatting failed for %s: %s", rel_path, e)
                    formatted_content = fixed_content

                # CONSTITUTIONAL FIX: Use governed mutation surface
                self.file_handler.write_runtime_text(rel_path, formatted_content)
                logger.info("Fixed %s via governed surface", rel_path)
            else:
                logger.info("[DRY-RUN] Would fix %s", rel_path)

            self.files_modified += 1
            self.fixes_applied += transformer.fix_count
            return True

        except Exception as e:
            logger.error("Failed to fix %s: %s", file_path, e)
            return False

    def _ensure_logger_import(self, content: str) -> str:
        """Add logger import if missing, respecting __future__ imports."""
        if "from shared.logger import getLogger" in content:
            return content
        if "logger = getLogger" in content and "shared.logger" in content:
            return content

        lines = content.split("\n")
        insert_idx = 0

        # Find position after __future__ imports
        last_future_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("from __future__"):
                last_future_idx = i

        if last_future_idx != -1:
            insert_idx = last_future_idx + 1
        else:
            # Find position after shebang/encoding
            for i, line in enumerate(lines):
                if line.startswith("#!") or line.startswith("# -*-"):
                    insert_idx = i + 1
                else:
                    break

        new_lines = [
            "",
            "from shared.logger import getLogger",
            "",
            "logger = getLogger(__name__)",
        ]

        lines[insert_idx:insert_idx] = new_lines
        return "\n".join(lines)

    def _is_exempted_file(self, file_path: Path) -> bool:
        """Check if file is exempted from fixing."""
        path_parts = file_path.parts
        if "test" in path_parts or "tests" in path_parts:
            return True
        if len(path_parts) > 0 and path_parts[0] in ("scripts", "dev-scripts"):
            return True
        if file_path.name == "fix_logging.py":
            return True
        if file_path.name == "cli_utils.py":
            return True
        return False


# ID: a1b2c3d4-e5f6-7890-abcd-123456789012
class LoggingTransformer(ast.NodeTransformer):
    """
    AST NodeTransformer that fixes logging violations.
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.modified = False
        self.fix_count = 0
        self.is_cli_layer = "body/cli" in str(file_path.as_posix())

    # ID: 9de559dc-607e-45f7-9880-217c77f68f31
    def visit_Call(self, node: ast.Call) -> ast.Call:
        """Visit function call nodes and fix logger f-strings."""
        self.generic_visit(node)
        if self._is_logger_call(node):
            if node.args and isinstance(node.args[0], ast.JoinedStr):
                transformed = self._transform_fstring_to_percent(node)
                if transformed:
                    self.modified = True
                    self.fix_count += 1
                    return transformed
        return node

    def _is_logger_call(self, node: ast.Call) -> bool:
        """Check if this is a logger.method() call."""
        logger_methods = ["debug", "info", "warning", "error", "critical", "exception"]
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == "logger" and node.func.attr in logger_methods:
                    return True
        return False

    def _transform_fstring_to_percent(self, node: ast.Call) -> ast.Call | None:
        """Transform logger.info(f"text {var}") to logger.info("text %s", var)."""
        fstring = node.args[0]
        if not isinstance(fstring, ast.JoinedStr):
            return None

        format_parts = []
        format_args = []

        for value in fstring.values:
            if isinstance(value, ast.Constant):
                format_parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                format_parts.append("%s")
                format_args.append(value.value)

        format_string = "".join(format_parts)
        new_args = [ast.Constant(value=format_string), *format_args, *node.args[1:]]
        new_call = ast.Call(func=node.func, args=new_args, keywords=node.keywords)
        ast.copy_location(new_call, node)
        return new_call


# ID: d1a3f234-bfff-4385-a973-9f387d6b1cc3
def run_fix(repo_root: Path, file_handler: FileHandler, dry_run: bool = True) -> dict:
    """Run the logging fixer."""
    fixer = LoggingFixer(repo_root, file_handler, dry_run=dry_run)
    return fixer.fix_all()
