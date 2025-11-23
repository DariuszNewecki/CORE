# src/shared/utils/header_tools.py
"""
Provides a deterministic tool for parsing and reconstructing Python file headers
according to CORE's constitutional style guide.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field


@dataclass
# ID: 4a498b02-ef0b-4ce2-bd66-d8289669cd8f
class HeaderComponents:
    """A data class to hold the parsed components of a Python file header."""

    location: str | None = None
    module_description: str | None = None
    has_future_import: bool = False
    other_imports: list[str] = field(default_factory=list)
    body: list[str] = field(default_factory=list)


class _HeaderTools:
    """A stateless utility class for parsing and reconstructing file headers."""

    @staticmethod
    # ID: 8f8fa33d-1ab8-4ee8-8dc7-a71355167611
    def parse(source_code: str) -> HeaderComponents:
        """Parses the source code and extracts header components."""
        components = HeaderComponents()
        lines = source_code.splitlines()
        if not lines:
            return components

        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            components.body = lines
            return components

        # Find the end of the header section (last docstring or import)
        last_header_line = 0
        header_nodes = []
        for node in tree.body:
            is_docstring = isinstance(node, ast.Expr) and isinstance(
                node.value, ast.Constant
            )
            is_import = isinstance(node, (ast.Import, ast.ImportFrom))
            if is_docstring or is_import:
                last_header_line = node.end_lineno or node.lineno
                header_nodes.append(node)
            else:
                # First non-header node marks the end of the header
                break

        # Body starts after the header, skipping blank lines
        body_start_index = last_header_line
        while body_start_index < len(lines) and not lines[body_start_index].strip():
            body_start_index += 1

        components.body = lines[body_start_index:]

        # Process Header Content
        if lines and lines[0].strip().startswith("#"):
            components.location = lines[0]

        # Extract docstring directly from source lines to preserve original quotes
        docstring_node = (
            tree.body[0] if tree.body and isinstance(tree.body[0], ast.Expr) else None
        )
        if (
            docstring_node
            and hasattr(docstring_node, "lineno")
            and hasattr(docstring_node, "end_lineno")
        ):
            # Get the exact lines from the source
            start_line = docstring_node.lineno - 1
            end_line = docstring_node.end_lineno - 1

            # Extract lines including quotes
            docstring_lines = lines[start_line : end_line + 1]

            # Preserve original formatting by joining lines
            if docstring_lines:
                # Detect if it's a multi-line docstring
                first_line = docstring_lines[0].strip()
                last_line = docstring_lines[-1].strip()

                # Check if it starts and ends with quotes
                if first_line.startswith(
                    ('"""', "'''", '"', "'")
                ) and last_line.endswith(('"""', "'''", '"', "'")):
                    # For single-line docstrings
                    if len(docstring_lines) == 1:
                        components.module_description = docstring_lines[0].strip()
                    else:
                        # For multi-line docstrings, preserve all lines
                        # Find the indentation level
                        base_indent = len(docstring_lines[0]) - len(
                            docstring_lines[0].lstrip()
                        )
                        # Strip consistent indentation
                        stripped_lines = []
                        for line in docstring_lines:
                            if line.startswith(" " * base_indent):
                                stripped_lines.append(line[base_indent:])
                            else:
                                stripped_lines.append(line)
                        components.module_description = "\n".join(stripped_lines)

        for node in header_nodes:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_line = ast.unparse(node)
                if "from __future__ import annotations" in import_line:
                    components.has_future_import = True
                else:
                    components.other_imports.append(import_line)

        return components

    @staticmethod
    # ID: e85d9dde-b46f-43f7-b83f-106a63103c48
    def reconstruct(components: HeaderComponents) -> str:
        """Reconstructs the source code from its parsed components."""
        parts = []

        if components.location:
            parts.append(components.location)

        if components.module_description:
            if parts and parts[-1].strip():
                parts.append("")
            parts.append(components.module_description)

        imports_present = components.has_future_import or components.other_imports
        if imports_present:
            if parts and parts[-1].strip():
                parts.append("")

            if components.has_future_import:
                parts.append("from __future__ import annotations")

            if components.other_imports:
                # Add a blank line between future import and other imports
                if components.has_future_import:
                    parts.append("")
                parts.extend(sorted(components.other_imports))

        if components.body:
            # If there was any header content, ensure two blank lines before the body
            if parts:
                while parts and not parts[-1].strip():
                    parts.pop()
                parts.append("")
                parts.append("")

            # Remove leading and trailing blank lines from body
            body_lines = components.body[:]
            while body_lines and not body_lines[0].strip():
                body_lines.pop(0)
            while body_lines and not body_lines[-1].strip():
                body_lines.pop()

            parts.extend(body_lines)

        return "\n".join(parts) + "\n"


# Public alias to satisfy callers and tests expecting `HeaderTools`.
HeaderTools = _HeaderTools
