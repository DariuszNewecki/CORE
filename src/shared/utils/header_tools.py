# src/shared/utils/header_tools.py
"""
Provides a deterministic tool for parsing and reconstructing Python file headers
according to CORE's constitutional style guide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
# ID: 4a498b02-ef0b-4ce2-bd66-d8289669cd8f
class HeaderComponents:
    """A data class to hold the parsed components of a Python file header."""

    location: Optional[str] = None
    module_description: Optional[str] = None
    has_future_import: bool = False
    other_imports: List[str] = field(default_factory=list)
    body: List[str] = field(default_factory=list)


# ID: 3f524d93-83cd-41bd-b5e2-38a7703d39d4
class HeaderTools:
    """A stateless utility class for parsing and reconstructing file headers."""

    @staticmethod
    # ID: 8f8fa33d-1ab8-4ee8-8dc7-a71355167611
    def parse(source_code: str) -> HeaderComponents:
        """Parses the source code and extracts header components."""
        components = HeaderComponents()
        lines = source_code.splitlines()
        state = "start"
        docstring_lines = []

        for line in lines:
            if state == "start":
                if line.strip().startswith("#") and ("/" in line or "\\" in line):
                    components.location = line
                    state = "location_found"
                else:  # No header found, treat everything as body
                    components.body.append(line)
                    state = "body_started"

            elif state == "location_found":
                if not line.strip():
                    continue  # Skip blank lines
                if '"""' in line or "'''" in line:
                    docstring_lines.append(line)
                    if line.count('"""') == 2 or line.count("'''") == 2:
                        state = "docstring_done"
                    else:
                        state = "in_docstring"
                else:
                    components.body.append(line)
                    state = "body_started"

            elif state == "in_docstring":
                docstring_lines.append(line)
                if '"""' in line or "'''" in line:
                    state = "docstring_done"

            elif state == "docstring_done":
                if not line.strip():
                    continue
                if "from __future__ import annotations" in line:
                    components.has_future_import = True
                    state = "future_import_found"
                else:
                    components.body.append(line)
                    state = "body_started"

            elif state == "future_import_found":
                if line.strip().startswith("from") or line.strip().startswith("import"):
                    components.other_imports.append(line)
                else:
                    components.body.append(line)
                    state = "body_started"

            elif state == "body_started":
                components.body.append(line)

        if docstring_lines:
            components.module_description = "\n".join(docstring_lines)

        # --- START OF FIX ---
        # Strip future import from body if it was misplaced and rename variable 'l' to 'line'.
        body_without_future = [
            line
            for line in components.body
            if "from __future__ import annotations" not in line
        ]
        # --- END OF FIX ---
        if len(body_without_future) < len(components.body):
            components.has_future_import = True
            components.body = body_without_future

        return components

    @staticmethod
    # ID: e85d9dde-b46f-43f7-b83f-106a63103c48
    def reconstruct(components: HeaderComponents) -> str:
        """Reconstructs the source code from its parsed components."""
        parts = []
        if components.location:
            parts.append(components.location)

        if components.module_description:
            if parts:
                parts.append("")
            parts.append(components.module_description)

        if components.has_future_import:
            if parts:
                parts.append("")
            parts.append("from __future__ import annotations")

        if components.other_imports:
            parts.extend(components.other_imports)

        if components.body:
            if parts and (parts[-1] != "" or components.body[0] != ""):
                parts.append("")
            parts.extend(components.body)

        return "\n".join(parts) + "\n"
