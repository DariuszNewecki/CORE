# src/system/tools/pattern_matcher.py
"""
A dedicated module for applying declarative patterns to identify non-obvious
entry points in the knowledge graph.
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Set

from shared.logger import getLogger
from system.tools.models import FunctionInfo  # <<< FIX: Import from the new models file

log = getLogger(__name__)


class PatternMatcher:
    """Applies declarative patterns to a list of symbols to identify entry points."""

    def __init__(self, patterns: List[Dict[str, Any]], root_path: Path):
        """
        Initialize the PatternMatcher with a set of rules.

        Args:
            patterns: A list of pattern dictionaries from entry_point_patterns.yaml.
            root_path: The absolute path to the repository root.
        """
        self.patterns: List[Dict[str, Any]] = patterns
        self.root_path: Path = root_path

    def apply_patterns(self, functions: Dict[str, FunctionInfo]) -> None:
        """
        Apply configured patterns to identify entry points in function symbols.

        Args:
            functions: A dictionary of FunctionInfo objects from the KnowledgeGraphBuilder.
        """
        all_base_classes: Set[str] = {
            base for info in functions.values() for base in info.base_classes
        }

        for info in functions.values():
            if info.entry_point_type:  # Skip if already identified
                continue

            for pattern in self.patterns:
                if self._is_match(
                    info, pattern.get("match", {}), all_base_classes, functions
                ):
                    info.entry_point_type = pattern.get("entry_point_type")
                    info.entry_point_justification = pattern.get("name")
                    log.debug(
                        f"Identified entry point: {info.name} as {info.entry_point_type} ({info.entry_point_justification})"
                    )
                    break

    def _is_match(
        self,
        info: FunctionInfo,
        rules: Dict[str, Any],
        all_base_classes: Set[str],
        functions: Dict[str, FunctionInfo],
    ) -> bool:
        """Check if a single symbol matches a set of declarative rules."""
        try:
            if rules.get("has_capability_tag") and info.capability == "unassigned":
                return False

            if rules.get("is_base_class") and (
                not info.is_class or info.name not in all_base_classes
            ):
                return False

            if "name_regex" in rules:
                try:
                    if not re.match(rules["name_regex"], info.name):
                        return False
                except re.error as e:
                    log.error(
                        f"Invalid regex pattern '{rules['name_regex']}' for {info.name}: {e}"
                    )
                    return False

            if "base_class_includes" in rules:
                parent_bases = set(info.base_classes)
                parent_key = info.parent_class_key
                if parent_key and parent_key in functions:
                    parent_bases.update(functions[parent_key].base_classes)
                if rules["base_class_includes"] not in parent_bases:
                    return False

            if "has_decorator" in rules:
                file_path = self.root_path / info.file
                if file_path.exists():
                    try:
                        source_lines = file_path.read_text(
                            encoding="utf-8"
                        ).splitlines()
                        if info.line_number < 2 or info.line_number > len(source_lines):
                            return False
                        decorator_line = source_lines[info.line_number - 2].strip()
                        if f"@{rules['has_decorator']}" not in decorator_line:
                            return False
                    except UnicodeDecodeError as e:
                        log.error(
                            f"Failed to read {file_path} due to encoding error: {e}"
                        )
                        return False
                else:
                    return False

            if "module_path_contains" in rules:
                if rules["module_path_contains"] not in info.file:
                    return False

            if rules.get("is_public_function") and info.name.startswith("_"):
                return False

            return True
        except Exception as e:
            log.error(f"Error evaluating rules for {info.name}: {e}", exc_info=True)
            return False
