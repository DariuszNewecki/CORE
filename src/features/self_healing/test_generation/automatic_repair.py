# src/features/self_healing/test_generation/automatic_repair.py
"""
Automatic code repair using specialized micro-fixers.

Philosophy: Each fixer does ONE thing perfectly. Chain them together.
"""

from __future__ import annotations

import ast
import re

from shared.logger import getLogger

logger = getLogger(__name__)


# ID: c683631a-39ee-452e-853e-62f3589dd853
class QuoteFixer:
    """Fixes mismatched triple quotes - ONE PROBLEM ONLY."""

    @staticmethod
    # ID: e762c37d-489f-4412-aabe-de91ec051ed8
    def fix(code: str) -> tuple[str, bool]:
        """
        Fix lines with mismatched triple quotes.

        Pattern: Triple-quoted strings with 4+ quotes at end become 3 quotes.

        Returns: (fixed_code, was_changed)
        """
        if not code:
            return code, False

        lines = code.split("\n")
        fixed_lines = []
        changed = False

        for line in lines:
            original = line

            # Simple rule: if line ends with 4+ quotes, reduce to 3
            # Match: 4 or more quotes at end of line
            if re.search(r'"{4,}\s*$', line):
                line = re.sub(r'"{4,}\s*$', '"""', line)
                changed = True

            if re.search(r"'{4,}\s*$", line):
                line = re.sub(r"'{4,}\s*$", "'''", line)
                changed = True

            fixed_lines.append(line)

        if changed:
            logger.info("QuoteFixer: Fixed mismatched triple quotes")

        return "\n".join(fixed_lines), changed


# ID: 53499b1f-a556-44d9-a65d-e95c488e64f3
class UnterminatedStringFixer:
    """Closes unterminated multiline strings - ONE PROBLEM ONLY."""

    @staticmethod
    # ID: 9dc69618-f637-4308-884c-fa27cc85dc29
    def fix(code: str) -> tuple[str, bool]:
        """
        Close unterminated triple-quoted strings.

        Returns: (fixed_code, was_changed)
        """
        if not code:
            return code, False

        # Count triple quotes
        double_count = code.count('"""')
        single_count = code.count("'''")

        changed = False

        # If odd number, add closing quote
        if double_count % 2 == 1:
            code = code + '\n"""'
            changed = True
            logger.info("UnterminatedStringFixer: Closed unterminated ''' string")

        if single_count % 2 == 1:
            code = code + "\n'''"
            changed = True
            logger.info('UnterminatedStringFixer: Closed unterminated """ string')

        return code, changed


# ID: af37daee-6da9-476e-bf0e-fb88cd543f5e
class TrailingWhitespaceFixer:
    """Removes trailing whitespace - ONE PROBLEM ONLY."""

    @staticmethod
    # ID: 49bcabcb-60c6-446a-868b-8c8def0bcbfe
    def fix(code: str) -> tuple[str, bool]:
        """
        Remove trailing whitespace from lines.

        Returns: (fixed_code, was_changed)
        """
        if not code:
            return code, False

        lines = code.split("\n")
        fixed_lines = [line.rstrip() for line in lines]

        changed = "\n".join(lines) != "\n".join(fixed_lines)

        if changed:
            logger.info("TrailingWhitespaceFixer: Removed trailing whitespace")

        return "\n".join(fixed_lines), changed


# ID: 59d9da09-4bfb-4e44-b36a-af67ef33b341
class EmptyFunctionFixer:
    """Fixes functions and classes with no body - ONE PROBLEM ONLY."""

    @staticmethod
    # ID: 5b097f22-7350-42c4-b6a8-b78b0e34707a
    def fix(code: str) -> tuple[str, bool]:
        """
        Fix functions/classes that have no body (causes "expected an indented block" error).

        Adds a pass statement to empty functions and classes.

        Returns: (fixed_code, was_changed)
        """
        if not code:
            return code, False

        lines = code.split("\n")
        fixed_lines = []
        changed = False

        for i, line in enumerate(lines):
            fixed_lines.append(line)

            stripped = line.strip()

            # Check if this line defines a function or class
            is_def = stripped.startswith("def ") and stripped.endswith(":")
            is_class = stripped.startswith("class ") and stripped.endswith(":")

            if is_def or is_class:
                # Check if next line exists and is not indented
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    # If next line is empty, not indented, or is another def/class, add pass
                    next_stripped = next_line.strip()
                    if not next_stripped or (
                        next_stripped and not next_line.startswith((" ", "\t"))
                    ):
                        fixed_lines.append("    pass")
                        changed = True
                        kind = "class" if is_class else "function"
                        logger.info(
                            f"EmptyFunctionFixer: Added 'pass' to empty {kind} on line {i+1}"
                        )
                elif i + 1 == len(lines):
                    # Last line is a def/class with no body
                    fixed_lines.append("    pass")
                    changed = True
                    kind = "class" if is_class else "function"
                    logger.info(
                        f"EmptyFunctionFixer: Added 'pass' to empty {kind} at EOF"
                    )

        return "\n".join(fixed_lines), changed


# ID: b38c031f-a301-464c-af87-32995e91e07d
class MixedQuoteFixer:
    """Fixes mixed quote usage where triple quotes are used incorrectly - ONE PROBLEM ONLY."""

    @staticmethod
    # ID: 5ed71f63-0b56-4a66-9b1c-53114b9434c3
    def fix(code: str) -> tuple[str, bool]:
        """
        Fix cases where triple quotes are used in non-docstring contexts.

        Replaces triple quotes with single quotes when they appear in
        function calls or other non-docstring contexts.

        Returns: (fixed_code, was_changed)
        """
        if not code:
            return code, False

        lines = code.split("\n")
        fixed_lines = []
        changed = False

        for line in lines:
            original = line

            # Check if this is NOT a docstring line (docstrings are typically standalone or after def/class)
            stripped = line.strip()
            is_likely_docstring = (
                (
                    stripped.startswith('"""')
                    and stripped.endswith('"""')
                    and len(stripped) > 6
                )
                or (
                    stripped.startswith("'''")
                    and stripped.endswith("'''")
                    and len(stripped) > 6
                )
                or ("def " in line or "class " in line)
            )

            if not is_likely_docstring:
                # Fix: Replace triple quotes with single quotes in non-docstring context
                if '"""' in line and line.count('"""') == 1:
                    # Only one triple-double-quote - probably wrong
                    line = line.replace('"""', '"')
                    changed = True

                # Same for triple-single-quotes
                if "'''" in line and line.count("'''") == 1:
                    line = line.replace("'''", "'")
                    changed = True

            if line != original:
                logger.info(
                    "MixedQuoteFixer: Fixed mixed quotes in non-docstring context"
                )

            fixed_lines.append(line)

        return "\n".join(fixed_lines), changed


# ID: 20628d67-01d8-4850-aa69-d72b70456f84
class TruncatedDocstringFixer:
    """Fixes truncated/incomplete docstrings - ONE PROBLEM ONLY."""

    @staticmethod
    # ID: a1790802-9e92-4449-b164-3f8605e8cd4d
    def fix(code: str) -> tuple[str, bool]:
        """
        Fix docstrings and raw strings that start but don't close properly.

        Handles both single-line and multi-line cases.

        Returns: (fixed_code, was_changed)
        """
        if not code:
            return code, False

        lines = code.split("\n")
        fixed_lines = []
        changed = False
        in_multiline = False
        multiline_quote = None

        for i, line in enumerate(lines):
            # Track if we're inside a multiline string
            if not in_multiline:
                # Check if this line starts a multiline string
                if '"""' in line:
                    count = line.count('"""')
                    if count % 2 == 1:  # Odd number = starting multiline
                        in_multiline = True
                        multiline_quote = '"""'
                elif "'''" in line:
                    count = line.count("'''")
                    if count % 2 == 1:
                        in_multiline = True
                        multiline_quote = "'''"

                # Check for single-line truncated docstrings
                stripped = line.strip()
                if not in_multiline:
                    if (
                        stripped.startswith('"""')
                        and not stripped.endswith('"""')
                        and stripped.count('"""') == 1
                    ):
                        line = line + '"""'
                        changed = True
                        logger.info(
                            f"TruncatedDocstringFixer: Closed single-line docstring on line {i+1}"
                        )
                    elif (
                        stripped.startswith("'''")
                        and not stripped.endswith("'''")
                        and stripped.count("'''") == 1
                    ):
                        line = line + "'''"
                        changed = True
                        logger.info(
                            f"TruncatedDocstringFixer: Closed single-line docstring on line {i+1}"
                        )
            else:
                # We're in a multiline string, check if this line closes it
                if multiline_quote in line:
                    in_multiline = False
                    multiline_quote = None

                # Check if line has WRONG closing (single instead of triple)
                # Pattern: line ends with single " or ' when it should be """ or '''
                stripped = line.rstrip()
                if (
                    stripped.endswith('"')
                    and not stripped.endswith('"""')
                    and multiline_quote == '"""'
                ):
                    # Replace single " with """
                    line = line.rstrip('"') + '"""'
                    changed = True
                    in_multiline = False
                    multiline_quote = None
                    logger.info(
                        f"TruncatedDocstringFixer: Fixed wrong closing quote on line {i+1}"
                    )
                elif (
                    stripped.endswith("'")
                    and not stripped.endswith("'''")
                    and multiline_quote == "'''"
                ):
                    line = line.rstrip("'") + "'''"
                    changed = True
                    in_multiline = False
                    multiline_quote = None
                    logger.info(
                        f"TruncatedDocstringFixer: Fixed wrong closing quote on line {i+1}"
                    )

            fixed_lines.append(line)

        # If still in multiline at end, close it
        if in_multiline and multiline_quote:
            fixed_lines.append(multiline_quote)
            changed = True
            logger.info("TruncatedDocstringFixer: Added missing closing quotes at EOF")

        return "\n".join(fixed_lines), changed


# ID: 96ef2599-3c40-40c6-b159-14552919fdfd
class EOFSyntaxFixer:
    """Fixes EOF syntax errors - ONE PROBLEM ONLY."""

    @staticmethod
    # ID: 1d8b2114-b32a-4e90-a4b1-b082540f9bb2
    def fix(code: str) -> tuple[str, bool]:
        """
        Fix EOF errors by attempting to close unclosed structures.

        Returns: (fixed_code, was_changed)
        """
        if not code:
            return code, False

        try:
            ast.parse(code)
            return code, False  # Already valid
        except SyntaxError as e:
            error_msg = str(e)

            # EOF while scanning triple-quoted string
            if "EOF while scanning triple-quoted string" in error_msg:
                if code.count('"""') % 2 == 1:
                    logger.info('EOFSyntaxFixer: Closing unclosed """ string')
                    return code + '\n"""', True
                if code.count("'''") % 2 == 1:
                    logger.info("EOFSyntaxFixer: Closing unclosed ''' string")
                    return code + "\n'''", True

        return code, False


# ID: 82243e6e-1415-4ded-a121-c29288ddfbbe
class AutomaticRepairService:
    """
    Orchestrates micro-fixers in a pipeline.

    Strategy: Run each fixer in sequence, up to N iterations.
    Stop when nothing changes or code becomes valid.
    """

    def __init__(self):
        # Order matters! Run fixers from most specific to most general
        self.fixers = [
            EmptyFunctionFixer(),  # Fix empty function bodies first
            MixedQuoteFixer(),  # Fix """ used where " should be
            TruncatedDocstringFixer(),  # Run first - catches incomplete lines
            QuoteFixer(),
            UnterminatedStringFixer(),
            EOFSyntaxFixer(),
            TrailingWhitespaceFixer(),
        ]
        self.max_iterations = 3

    # ID: d4210d20-f862-4822-876f-0b515efee7dd
    def apply_all_repairs(self, code: str) -> tuple[str, list[str]]:
        """
        Apply all fixers iteratively until nothing changes.

        Returns:
            (repaired_code, list_of_repairs_applied)
        """
        repairs_applied = []
        current_code = code

        for iteration in range(self.max_iterations):
            any_changed = False

            for fixer in self.fixers:
                fixed_code, changed = fixer.fix(current_code)

                if changed:
                    any_changed = True
                    fixer_name = fixer.__class__.__name__
                    repair_key = f"{fixer_name}_iter{iteration}"
                    repairs_applied.append(repair_key)
                    current_code = fixed_code

            # If nothing changed this iteration, we're done
            if not any_changed:
                break

            # Check if code is now valid
            try:
                ast.parse(current_code)
                logger.info(f"Code became valid after {iteration + 1} iteration(s)")
                break
            except SyntaxError:
                continue  # Try next iteration

        return current_code, repairs_applied
