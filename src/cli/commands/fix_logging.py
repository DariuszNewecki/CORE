# src/cli/commands/fix_logging.py
"""
AST-based automated remediation for logging standards violations.

CONSTITUTIONAL EVOLUTION: This fixer uses AST parsing to match the context-aware
checker, ensuring the fixer can handle exactly what the checker detects.
IntentGuard enforcement and auditability.

Converts:
- print() → logger.info()
- console.print() → logger.info()
- console.status() → logger.info()
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

    Handles:
    - print() → logger.info()
    - console.print() / console.status() → logger.info()
    - logger.info(f"...") → logger.info("...", args)
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

            try:
                tree = ast.parse(content, filename=str(file_path))
            except SyntaxError as e:
                logger.debug("Syntax error in %s, skipping: %s", file_path, e)
                return False

            transformer = LoggingTransformer(file_path)
            modified_tree = transformer.visit(tree)

            if not transformer.modified:
                return False

            try:
                fixed_content = ast.unparse(modified_tree)
            except Exception as e:
                logger.error("Failed to unparse %s: %s", file_path, e)
                return False

            fixed_content = self._ensure_logger_import(fixed_content)

            rel_path = str(file_path.relative_to(self.repo_root))
            if not self.dry_run:
                try:
                    formatted_content = format_code_with_black(fixed_content)
                except Exception as e:
                    logger.debug("Black formatting failed for %s: %s", rel_path, e)
                    formatted_content = fixed_content

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

        last_future_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("from __future__"):
                last_future_idx = i

        if last_future_idx != -1:
            insert_idx = last_future_idx + 1
        else:
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
    AST NodeTransformer that fixes all logging violations:
    - print() → logger.info()
    - console.print() / console.status() → logger.info()
    - logger.*(f"...") → logger.*("...", args)
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.modified = False
        self.fix_count = 0
        self.is_cli_layer = "body/cli" in str(file_path.as_posix())

    # ID: 9de559dc-607e-45f7-9880-217c77f68f31
    def visit_Call(self, node: ast.Call) -> ast.AST:
        """Visit function call nodes and fix all logging violations."""
        self.generic_visit(node)

        # Case 1: print(...) → logger.info(...)
        if self._is_print_call(node):
            # bare print() with no args is a spacer — skip, logger.info() requires a msg
            if not node.args and not node.keywords:
                return node
            return self._replace_with_logger_info(node)

        # Case 2: console.print(...) or console.status(...) → logger.info(...)
        # CLI layer is the constitutional presentation layer — console.print() is
        # allowed and correct there. Only replace in body/logic/shared layers.
        if self._is_console_call(node) and not self.is_cli_layer:
            # bare console.print() is a Rich spacer — skip
            if not node.args and not node.keywords:
                return node
            return self._replace_with_logger_info(node)

        # Case 3: logger.*(f"...") → logger.*("...", args)
        if self._is_logger_call(node):
            if node.args and isinstance(node.args[0], ast.JoinedStr):
                transformed = self._transform_fstring_to_percent(node)
                if transformed:
                    self.modified = True
                    self.fix_count += 1
                    return transformed

        return node

    def _is_print_call(self, node: ast.Call) -> bool:
        """Check if this is a bare print() call."""
        return isinstance(node.func, ast.Name) and node.func.id == "print"

    def _is_console_call(self, node: ast.Call) -> bool:
        """Check if this is a console.print() or console.status() call."""
        if not isinstance(node.func, ast.Attribute):
            return False
        if not isinstance(node.func.value, ast.Name):
            return False
        return node.func.value.id == "console" and node.func.attr in ("print", "status")

    def _is_logger_call(self, node: ast.Call) -> bool:
        """Check if this is a logger.method() call."""
        logger_methods = ["debug", "info", "warning", "error", "critical", "exception"]
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == "logger" and node.func.attr in logger_methods:
                    return True
        return False

    def _replace_with_logger_info(self, node: ast.Call) -> ast.Call:
        """Replace print()/console.print() with logger.info(), handling f-strings."""
        # Build logger.info attribute node
        new_func = ast.Attribute(
            value=ast.Name(id="logger", ctx=ast.Load()),
            attr="info",
            ctx=ast.Load(),
        )
        ast.copy_location(new_func, node.func)
        ast.fix_missing_locations(new_func)

        # Use original args — if it's an f-string, convert to % format
        new_args = list(node.args)
        if new_args and isinstance(new_args[0], ast.JoinedStr):
            converted = self._fstring_to_percent_args(new_args[0])
            if converted:
                new_args = converted + new_args[1:]

        new_call = ast.Call(func=new_func, args=new_args, keywords=[])
        ast.copy_location(new_call, node)
        ast.fix_missing_locations(new_call)

        self.modified = True
        self.fix_count += 1
        return new_call

    def _transform_fstring_to_percent(self, node: ast.Call) -> ast.Call | None:
        """Transform logger.info(f"text {var}") to logger.info("text %s", var)."""
        converted = self._fstring_to_percent_args(node.args[0])
        if not converted:
            return None

        new_args = converted + list(node.args[1:])
        new_call = ast.Call(func=node.func, args=new_args, keywords=node.keywords)
        ast.copy_location(new_call, node)
        ast.fix_missing_locations(new_call)
        return new_call

    def _fstring_to_percent_args(self, fstring: ast.JoinedStr) -> list[ast.expr] | None:
        """Convert an f-string AST node to [format_string, *args] for % formatting."""
        if not isinstance(fstring, ast.JoinedStr):
            return None

        format_parts: list[str] = []
        format_args: list[ast.expr] = []

        for value in fstring.values:
            if isinstance(value, ast.Constant):
                format_parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                format_parts.append("%s")
                format_args.append(value.value)

        return [ast.Constant(value="".join(format_parts)), *format_args]


# ID: d1a3f234-bfff-4385-a973-9f387d6b1cc3
def run_fix(repo_root: Path, file_handler: FileHandler, dry_run: bool = True) -> dict:
    """Run the logging fixer."""
    fixer = LoggingFixer(repo_root, file_handler, dry_run=dry_run)
    return fixer.fix_all()
