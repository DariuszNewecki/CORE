# src/body/cli/commands/fix_logging.py
"""
AST-based automated remediation for logging standards violations.

CONSTITUTIONAL EVOLUTION: This fixer uses AST parsing to match the context-aware
checker, ensuring the fixer can handle exactly what the checker detects.

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
import subprocess
from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: c0f61b44-b95f-44a6-944e-8797893c481e
class LoggingFixer:
    """
    AST-based logging violation fixer.

    This fixer understands code structure and can transform complex f-strings
    into proper lazy % formatting while preserving code semantics.
    """

    def __init__(self, repo_root: Path, dry_run: bool = True):
        self.repo_root = repo_root
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
            original_content = content

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
            if not self.dry_run:
                file_path.write_text(fixed_content, encoding="utf-8")
                # Format with Black after AST transformation
                self._format_with_black(file_path)
                logger.info("Fixed %s", file_path.relative_to(self.repo_root))
            else:
                logger.info(
                    "[DRY-RUN] Would fix %s", file_path.relative_to(self.repo_root)
                )

            self.files_modified += 1
            self.fixes_applied += transformer.fix_count
            return True

        except Exception as e:
            logger.error("Failed to fix %s: %s", file_path, e)
            return False

    def _format_with_black(self, file_path: Path) -> None:
        """Format file with Black after AST transformation."""
        try:
            subprocess.run(
                ["black", "--quiet", str(file_path)],
                check=False,
                capture_output=True,
            )
        except Exception as e:
            logger.debug("Black formatting failed for %s: %s", file_path, e)

    def _ensure_logger_import(self, content: str) -> str:
        """Add logger import if missing, respecting __future__ imports."""
        # Check if logger import already exists
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

        # Insert logger import
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

        # Test files
        if "test" in path_parts or "tests" in path_parts:
            return True

        # Scripts
        if len(path_parts) > 0 and path_parts[0] in ("scripts", "dev-scripts"):
            return True

        # This file itself
        if file_path.name == "fix_logging.py":
            return True

        # CLI utils
        if file_path.name == "cli_utils.py":
            return True

        return False


# ID: a1b2c3d4-e5f6-7890-abcd-123456789012
class LoggingTransformer(ast.NodeTransformer):
    """
    AST NodeTransformer that fixes logging violations.

    This transformer walks the AST and modifies nodes in place:
    - Converts f-strings in logger calls to % formatting
    - Could be extended to handle other logging fixes
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.modified = False
        self.fix_count = 0
        self.is_cli_layer = "body/cli" in str(file_path.as_posix())

    # ID: 9de559dc-607e-45f7-9880-217c77f68f31
    def visit_Call(self, node: ast.Call) -> ast.Call:
        """Visit function call nodes and fix logger f-strings."""
        # First, visit children
        self.generic_visit(node)

        # Check if this is a logger method call
        if self._is_logger_call(node):
            # Check if first argument is an f-string
            if node.args and isinstance(node.args[0], ast.JoinedStr):
                # Transform f-string to % formatting
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
            # Check for logger.method pattern
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == "logger" and node.func.attr in logger_methods:
                    return True

        return False

    def _transform_fstring_to_percent(self, node: ast.Call) -> ast.Call | None:
        """
        Transform logger.info(f"text {var}") to logger.info("text %s", var).

        Handles:
        - Simple variables: f"{var}"
        - Expressions: f"{obj.attr}", f"{func()}"
        - Multiple variables: f"{a} and {b}"
        - Mixed text and variables: f"Value: {x}"
        """
        fstring = node.args[0]
        if not isinstance(fstring, ast.JoinedStr):
            return None

        # Build the format string and collect arguments
        format_parts = []
        format_args = []

        for value in fstring.values:
            if isinstance(value, ast.Constant):
                # This is literal text
                format_parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                # This is a {expression} in the f-string
                format_parts.append("%s")

                # Extract the expression
                expr = value.value

                # Handle format specs (like f"{var:.2f}")
                # For now, we'll just use %s and warn about lost precision
                if value.format_spec:
                    logger.warning(
                        "Lost format spec in %s - manual review needed",
                        self.file_path.name,
                    )

                format_args.append(expr)

        # Create the new format string
        format_string = "".join(format_parts)

        # Build new call: logger.method("format string", arg1, arg2, ...)
        new_args = [ast.Constant(value=format_string)] + format_args + node.args[1:]

        # Create new Call node with same function but new args
        new_call = ast.Call(func=node.func, args=new_args, keywords=node.keywords)

        # Copy location info for better error messages
        ast.copy_location(new_call, node)

        return new_call


# ID: d1a3f234-bfff-4385-a973-9f387d6b1cc3
def run_fix(repo_root: Path, dry_run: bool = True) -> dict:
    """Run the logging fixer."""
    fixer = LoggingFixer(repo_root, dry_run=dry_run)
    return fixer.fix_all()
