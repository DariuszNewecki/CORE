# src/body/cli/logic/hub/introspection.py

"""Refactored logic for src/body/cli/logic/hub/introspection.py."""

from __future__ import annotations

import importlib
import inspect
from pathlib import Path


# ID: 4f8cf55a-f4cd-42bc-a4d5-cf515aeecbe0
def resolve_module_file(module_path: str) -> Path | None:
    """Uses Python introspection to find the physical file path for a module."""
    try:
        mod = importlib.import_module(module_path)
        f = inspect.getsourcefile(mod)
        return Path(f).resolve() if f else None
    except Exception:
        return None
