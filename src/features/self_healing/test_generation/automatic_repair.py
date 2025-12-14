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


# ID: e69950b7-11bd-4c88-b1f3-04f24b03fe21
class QuoteFixer:
    """Fixes mismatched triple quotes - ONE PROBLEM ONLY."""

    @staticmethod
    # ID: 377b67e7-5c64-41c5-a3d7-f1794b0cf934
    def fix(code: str) -> tuple[str, bool]:
        """
        Fix lines with mismatched triple quotes.

        Pattern: Triple-quoted strings with 4+ quotes at end become 3 quotes.

        Returns: (fixed_code, was_changed)
        """
        if not code:
            return (code, False)
        lines = code.split("\n")
        fixed_lines = []
        changed = False
        for line in lines:
            original = line
            if re.search('"{4,}\\s*$', line):
                line = re.sub('"{4,}\\s*$', '"""', line)
                changed = True
            if re.search("'{4,}\\s*$", line):
                line = re.sub("'{4,}\\s*$", "'''", line)
                changed = True
            fixed_lines.append(line)
        if changed:
            logger.info("QuoteFixer: Fixed mismatched triple quotes")
        return ("\n".join(fixed_lines), changed)


# ID: 2fb2a6e6-beb3-4b8d-8693-548b89617804
class UnterminatedStringFixer:
    """Closes unterminated multiline strings - ONE PROBLEM ONLY."""

    @staticmethod
    # ID: 11670780-5071-4b27-859d-a7a4ef15dbfa
    def fix(code: str) -> tuple[str, bool]:
        """
        Close unterminated triple-quoted strings.

        Returns: (fixed_code, was_changed)
        """
        if not code:
            return (code, False)
        double_count = code.count('"""')
        single_count = code.count("'''")
        changed = False
        if double_count % 2 == 1:
            code = code + '\n"""'
            changed = True
            logger.info("UnterminatedStringFixer: Closed unterminated ''' string")
        if single_count % 2 == 1:
            code = code + "\n'''"
            changed = True
            logger.info('UnterminatedStringFixer: Closed unterminated """ string')
        return (code, changed)


# ID: 4faa130f-26c4-41da-8199-5b264dbd70f8
class TrailingWhitespaceFixer:
    """Removes trailing whitespace - ONE PROBLEM ONLY."""

    @staticmethod
    # ID: 4fb77c31-1302-4a9d-8ecc-0a0d47a0ce5b
    def fix(code: str) -> tuple[str, bool]:
        """
        Remove trailing whitespace from lines.

        Returns: (fixed_code, was_changed)
        """
        if not code:
            return (code, False)
        lines = code.split("\n")
        fixed_lines = [line.rstrip() for line in lines]
        changed = "\n".join(lines) != "\n".join(fixed_lines)
        if changed:
            logger.info("TrailingWhitespaceFixer: Removed trailing whitespace")
        return ("\n".join(fixed_lines), changed)


# ID: 81309469-3551-422c-8409-79a2e45b7805
class EmptyFunctionFixer:
    """Fixes functions and classes with no body - ONE PROBLEM ONLY."""

    @staticmethod
    # ID: 1b0d042a-b4af-44b6-a1ba-76444a6e6b76
    def fix(code: str) -> tuple[str, bool]:
        """
        Fix functions/classes that have no body (causes "expected an indented block" error).

        Adds a pass statement to empty functions and classes.

        Returns: (fixed_code, was_changed)
        """
        if not code:
            return (code, False)
        lines = code.split("\n")
        fixed_lines = []
        changed = False
        for i, line in enumerate(lines):
            fixed_lines.append(line)
            stripped = line.strip()
            is_def = stripped.startswith("def ") and stripped.endswith(":")
            is_class = stripped.startswith("class ") and stripped.endswith(":")
            if is_def or is_class:
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_stripped = next_line.strip()
                    if not next_stripped or (
                        next_stripped and (not next_line.startswith((" ", "\t")))
                    ):
                        fixed_lines.append("    pass")
                        changed = True
                        kind = "class" if is_class else "function"
                        logger.info(
                            "EmptyFunctionFixer: Added 'pass' to empty %s on line %s",
                            kind,
                            i + 1,
                        )
                elif i + 1 == len(lines):
                    fixed_lines.append("    pass")
                    changed = True
                    kind = "class" if is_class else "function"
                    logger.info(
                        "EmptyFunctionFixer: Added 'pass' to empty %s at EOF", kind
                    )
        return ("\n".join(fixed_lines), changed)


# ID: 6548afb9-f4b5-468e-90b2-c42f1ac9fddf
class MixedQuoteFixer:
    """Fixes mixed quote usage where triple quotes are used incorrectly - ONE PROBLEM ONLY."""

    @staticmethod
    # ID: fdc484f9-afa9-4989-a92c-37ff425257c2
    def fix(code: str) -> tuple[str, bool]:
        """
        Fix cases where triple quotes are used in non-docstring contexts.

        Replaces triple quotes with single quotes when they appear in
        function calls or other non-docstring contexts.

        Returns: (fixed_code, was_changed)
        """
        if not code:
            return (code, False)
        lines = code.split("\n")
        fixed_lines = []
        changed = False
        for line in lines:
            original = line
            stripped = line.strip()
            is_likely_docstring = (
                stripped.startswith('"""')
                and stripped.endswith('"""')
                and (len(stripped) > 6)
                or (
                    stripped.startswith("'''")
                    and stripped.endswith("'''")
                    and (len(stripped) > 6)
                )
                or ("def " in line or "class " in line)
            )
            if not is_likely_docstring:
                if '"""' in line and line.count('"""') == 1:
                    line = line.replace('"""', '"')
                    changed = True
                if "'''" in line and line.count("'''") == 1:
                    line = line.replace("'''", "'")
                    changed = True
            if line != original:
                logger.info(
                    "MixedQuoteFixer: Fixed mixed quotes in non-docstring context"
                )
            fixed_lines.append(line)
        return ("\n".join(fixed_lines), changed)


# ID: 1e3e976c-a02d-476a-ab8a-86ed80d30199
class TruncatedDocstringFixer:
    """Fixes truncated/incomplete docstrings - ONE PROBLEM ONLY."""

    @staticmethod
    # ID: f5c8c78f-4079-45b2-afbb-ef374dcda022
    def fix(code: str) -> tuple[str, bool]:
        """
        Fix docstrings and raw strings that start but don't close properly.

        Handles both single-line and multi-line cases.

        Returns: (fixed_code, was_changed)
        """
        if not code:
            return (code, False)
        lines = code.split("\n")
        fixed_lines = []
        changed = False
        in_multiline = False
        multiline_quote = None
        for i, line in enumerate(lines):
            if not in_multiline:
                if '"""' in line:
                    count = line.count('"""')
                    if count % 2 == 1:
                        in_multiline = True
                        multiline_quote = '"""'
                elif "'''" in line:
                    count = line.count("'''")
                    if count % 2 == 1:
                        in_multiline = True
                        multiline_quote = "'''"
                stripped = line.strip()
                if not in_multiline:
                    if (
                        stripped.startswith('"""')
                        and (not stripped.endswith('"""'))
                        and (stripped.count('"""') == 1)
                    ):
                        line = line + '"""'
                        changed = True
                        logger.info(
                            "TruncatedDocstringFixer: Closed single-line docstring on line %s",
                            i + 1,
                        )
                    elif (
                        stripped.startswith("'''")
                        and (not stripped.endswith("'''"))
                        and (stripped.count("'''") == 1)
                    ):
                        line = line + "'''"
                        changed = True
                        logger.info(
                            "TruncatedDocstringFixer: Closed single-line docstring on line %s",
                            i + 1,
                        )
            else:
                if multiline_quote in line:
                    in_multiline = False
                    multiline_quote = None
                stripped = line.rstrip()
                if (
                    stripped.endswith('"')
                    and (not stripped.endswith('"""'))
                    and (multiline_quote == '"""')
                ):
                    line = line.rstrip('"') + '"""'
                    changed = True
                    in_multiline = False
                    multiline_quote = None
                    logger.info(
                        "TruncatedDocstringFixer: Fixed wrong closing quote on line %s",
                        i + 1,
                    )
                elif (
                    stripped.endswith("'")
                    and (not stripped.endswith("'''"))
                    and (multiline_quote == "'''")
                ):
                    line = line.rstrip("'") + "'''"
                    changed = True
                    in_multiline = False
                    multiline_quote = None
                    logger.info(
                        "TruncatedDocstringFixer: Fixed wrong closing quote on line %s",
                        i + 1,
                    )
            fixed_lines.append(line)
        if in_multiline and multiline_quote:
            fixed_lines.append(multiline_quote)
            changed = True
            logger.info("TruncatedDocstringFixer: Added missing closing quotes at EOF")
        return ("\n".join(fixed_lines), changed)


# ID: ebd6246c-8ffb-4d30-a5c4-732638a809e6
class EOFSyntaxFixer:
    """Fixes EOF syntax errors - ONE PROBLEM ONLY."""

    @staticmethod
    # ID: 56c8eef1-3ace-483b-bf7f-47a5d5621e55
    def fix(code: str) -> tuple[str, bool]:
        """
        Fix EOF errors by attempting to close unclosed structures.

        Returns: (fixed_code, was_changed)
        """
        if not code:
            return (code, False)
        try:
            ast.parse(code)
            return (code, False)
        except SyntaxError as e:
            error_msg = str(e)
            if "EOF while scanning triple-quoted string" in error_msg:
                if code.count('"""') % 2 == 1:
                    logger.info('EOFSyntaxFixer: Closing unclosed """ string')
                    return (code + '\n"""', True)
                if code.count("'''") % 2 == 1:
                    logger.info("EOFSyntaxFixer: Closing unclosed ''' string")
                    return (code + "\n'''", True)
        return (code, False)


# ID: 09e40640-e672-4ccb-bb0c-0391e2b6121b
class AutomaticRepairService:
    """
    Orchestrates micro-fixers in a pipeline.

    Strategy: Run each fixer in sequence, up to N iterations.
    Stop when nothing changes or code becomes valid.
    """

    def __init__(self):
        self.fixers = [
            EmptyFunctionFixer(),
            MixedQuoteFixer(),
            TruncatedDocstringFixer(),
            QuoteFixer(),
            UnterminatedStringFixer(),
            EOFSyntaxFixer(),
            TrailingWhitespaceFixer(),
        ]
        self.max_iterations = 3

    # ID: 638d7b88-7280-4ee6-881a-3909a9caf556
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
            if not any_changed:
                break
            try:
                ast.parse(current_code)
                logger.info("Code became valid after %s iteration(s)", iteration + 1)
                break
            except SyntaxError:
                continue
        return (current_code, repairs_applied)
