# src/body/cli/commands/fix_logging.py
"""
Automated remediation for logging standards violations.
Converts console.print, console.status, and print() to logger calls.
Converts SIMPLE f-strings in logger calls to lazy % formatting.

Constitutional Rules Enforced:
- LOG-001: Logic layers must use logger, not Rich Console.
- LOG-003: No f-strings in logger calls (use lazy % formatting).
- LOG-004: Replace console.status() with logger.info().
- CLI Layer Exemption: src/body/cli/** MAY use Rich Console.

NOTE: LOG-003 fixer only handles simple single-variable f-strings.
Complex f-strings require manual conversion.
"""

from __future__ import annotations

import re
from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: a1b2c3d4-e5f6-7890-abcd-1234567890ab
class LoggingFixer:
    """Automatically fixes logging violations."""

    def __init__(self, repo_root: Path, dry_run: bool = True):
        self.repo_root = repo_root
        self.dry_run = dry_run
        self.fixes_applied = 0
        self.files_modified = 0
        # Matches rich tags like [bold], [/red], [color(1)]
        self.rich_tag_pattern = re.compile(r"\[/?[a-z0-9\(\)\s]+\]")

    # ID: b2c3d4e5-f6a7-8901-bcde-2345678901bc
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

    # ID: c3d4e5f6-a7b8-9012-cdef-3456789012cd
    def fix_file(self, file_path: Path) -> bool:
        """Fix logging violations in a single file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            original = content
            is_cli_layer = "body/cli" in str(file_path.as_posix())

            # 1. Fix Operations based on layer
            if not is_cli_layer:
                # Logic Layer: Strict Ban on Console
                content = self._fix_console_print(content)
                content = self._fix_console_status(content)

            # Universal Ban on print() (except scripts, checked in _is_exempted)
            content = self._fix_print_calls(content, is_cli_layer)

            # 2. Fix SIMPLE f-strings in logger calls (LOG-003)
            content = self._fix_simple_logger_fstrings(content)

            # 3. If changes made, ensure logger import exists
            if content != original:
                content = self._ensure_logger_import(content)

                if not self.dry_run:
                    file_path.write_text(content, encoding="utf-8")
                    logger.info("Fixed %s", file_path.relative_to(self.repo_root))
                else:
                    logger.info(
                        "[DRY-RUN] Would fix %s", file_path.relative_to(self.repo_root)
                    )

                self.files_modified += 1
                self.fixes_applied += 1
                return True

        except Exception as e:
            logger.error("Failed to fix %s: %s", file_path, e)

        return False

    # ID: d4e5f6a7-b8c9-0123-def4-4567890123de
    def _ensure_logger_import(self, content: str) -> str:
        """Add logger import if missing, respecting __future__ imports."""
        if "from shared.logger import getLogger" in content:
            return content
        if "logger = getLogger" in content and "shared.logger" in content:
            return content

        lines = content.split("\n")
        insert_idx = 0

        # Scan the ENTIRE file to find the last __future__ import.
        last_future_idx = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("from __future__"):
                last_future_idx = i

        if last_future_idx != -1:
            insert_idx = last_future_idx + 1
        else:
            # If no future import, we default to 0, but skip shebangs/encoding
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

    def _clean_rich_tags(self, line: str) -> str:
        """Remove Rich tags from a line when converting to logger."""
        return self.rich_tag_pattern.sub("", line)

    # ID: e5f6a7b8-c9d0-1234-ef56-5678901234ef
    def _fix_console_print(self, content: str) -> str:
        """Convert console.print() to logger.info()."""
        lines = content.split("\n")
        new_lines = []
        for line in lines:
            if "console.print(" in line:
                # Remove styling tags if present
                clean_line = self._clean_rich_tags(line)
                new_lines.append(
                    clean_line.replace("console.print(", "logger.info(", 1)
                )
            else:
                new_lines.append(line)
        return "\n".join(new_lines)

    # ID: f6a7b8c9-d0e1-2345-f678-6789012345f0
    def _fix_console_status(self, content: str) -> str:
        """Convert console.status() to logger.info()."""
        # Regex handles the context manager pattern
        # with console.status("Msg"): -> logger.info("Msg")
        # We also strip Rich tags here

        # ID: 1d277446-cef8-4762-a943-8458cfd0b2de
        def replacement(match):
            msg = match.group(1)
            clean_msg = self._clean_rich_tags(msg)
            return f"logger.info({clean_msg})"

        return re.sub(r"with console\.status\((.*?)\):", replacement, content)

    # ID: a7b8c9d0-e1f2-3456-a789-7890123456a1
    def _fix_print_calls(self, content: str, is_cli: bool) -> str:
        """Convert print() to logger.info() (Logic) or console.print() (CLI)."""
        lines = content.split("\n")
        fixed_lines = []

        for line in lines:
            stripped = line.strip()

            # Skip comments and decorators
            if stripped.startswith(("#", "@")):
                fixed_lines.append(line)
                continue

            # Skip if already using logger/console correctly
            if "logger." in line or "console." in line:
                fixed_lines.append(line)
                continue

            # Check for print(...)
            # We use a regex bound \b to avoid replacing "fingerprint(" or "sprint("
            if re.search(r"\bprint\s*\(", line):
                replacement = "console.print(" if is_cli else "logger.info("
                fixed_line = re.sub(r"\bprint\s*\(", replacement, line, count=1)
                fixed_lines.append(fixed_line)
            else:
                fixed_lines.append(line)

        return "\n".join(fixed_lines)

    # ID: 9a8b7c6d-5e4f-3a2b-1c0d-e9f8a7b6c5d4
    def _fix_simple_logger_fstrings(self, content: str) -> str:
        """
        Convert SIMPLE f-strings in logger calls to lazy % formatting (LOG-003).

        Only handles simple patterns to avoid breaking code:
        - Single variable: logger.info(f"Text {var}") → logger.info("Text %s", var)
        - At end: logger.info(f"Text {var}") → logger.info("Text %s", var)
        - At start: logger.info(f"{var} text") → logger.info("%s text", var)

        DOES NOT handle:
        - Multiple variables
        - Complex expressions
        - Format specifiers
        """
        lines = content.split("\n")
        fixed_lines = []

        for line in lines:
            # Only process lines with logger calls
            if not re.search(
                r"logger\.(debug|info|warning|error|critical|exception)", line
            ):
                fixed_lines.append(line)
                continue

            # Pattern: logger.method(f"...{single_var}...")
            # Match: logger.info(f"Started {task_id}")
            pattern = r'(logger\.\w+)\(f"([^"]*)\{(\w+)\}([^"]*)"\)'

            # ID: 15472448-834e-41da-8c6d-349343a072a8
            def replace_fstring(match):
                logger_call = match.group(1)  # logger.info
                before_text = match.group(2)  # "Started "
                var_name = match.group(3)  # task_id
                after_text = match.group(4)  # ""

                # Build the new call
                new_format = f"{before_text}%s{after_text}"
                return f'{logger_call}("{new_format}", {var_name})'

            new_line = re.sub(pattern, replace_fstring, line)

            # Also try single quotes
            pattern_single = r"(logger\.\w+)\(f'([^']*)\{(\w+)\}([^']*)'\)"
            new_line = re.sub(pattern_single, replace_fstring, new_line)

            fixed_lines.append(new_line)

        return "\n".join(fixed_lines)

    # ID: b8c9d0e1-f2a3-4567-b890-8901234567b2
    def _is_exempted_file(self, file_path: Path) -> bool:
        """Check if file is exempted from fixing."""
        path_parts = file_path.parts

        # Test files
        if "test" in path_parts or "tests" in path_parts:
            return True

        # Scripts folder (allowed to use print)
        if "scripts" in path_parts or "dev-scripts" in path_parts:
            return True

        # The fixer itself
        if file_path.name == "fix_logging.py":
            return True

        # CLI Utilities - Allowed to use console
        if file_path.name == "cli_utils.py":
            return True

        return False


# ID: c9d0e1f2-a3b4-5678-c901-9012345678c3
def run_fix(repo_root: Path, dry_run: bool = True) -> dict:
    """Run the logging fixer."""
    fixer = LoggingFixer(repo_root, dry_run=dry_run)
    return fixer.fix_all()
