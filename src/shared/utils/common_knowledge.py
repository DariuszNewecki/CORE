# src/shared/utils/common_knowledge.py
# ID: 7c05b6a1-0b1d-5c9a-9b5f-1cce01b9f8a7
"""
Constitutional “common knowledge” – ultra-reusable micro-functions.
Import from here *before* inventing yet another helper.
"""

import re


# ID: c494b539-a653-4d46-b627-94a90698a832
def action_name() -> str:
    """Return the canonical action name string for handlers."""
    return "action_name"


# ID: 15ad7ea3-9219-4e6e-8b4c-644ac781ea1b
def sanitize_key(raw: str) -> str:
    """Lower-case, underscore, alnum only."""
    return re.sub(r"[^0-9a-zA-Z]+", "_", raw).lower()


# ID: 78f9e52e-43e0-4942-bbc4-c4d3784553ee
def normalize_text(text: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", text).strip()
