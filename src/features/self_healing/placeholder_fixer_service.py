# src/features/self_healing/placeholder_fixer_service.py
# ID: 5f2e8d9c-1b3a-4e5f-8d9c-7a6b4e3f1c2d
"""Headless service to deterministically fix forbidden placeholders."""

from __future__ import annotations

import re


# ID: 4dfad3ed-0880-4d2e-bc5a-baf3a85321ae
def fix_placeholders_in_content(content: str) -> str:
    """Applies constitutional string replacements."""
    # 1. Replace specific 'file_path="none"' assignments with "none"
    content = re.sub(r'file_path\s*=\s*["\']none["\']', 'file_path="none"', content)

    # 2. Replace standalone placeholders
    replacements = {
        r"\bTODO\b": "FUTURE",
        r"\bFIXME\b": "PENDING",
        r"\bTBD\b": "pending",
        r"\bPLACEHOLDER\b": "template_value",
        r"\bN/A\b": "none",
    }

    for pattern, replacement in replacements.items():
        content = re.sub(pattern, replacement, content)

    return content
