# src/body/services/cim/cim_path_utils.py
# ID: c84f6a0e-ee82-4f9b-ba09-271b69057c16
"""CIM-0 Path Classification Utilities.

Pure, deterministic functions for path and AST node classification.
No I/O, no side effects.
"""

from __future__ import annotations

import ast
from pathlib import Path

from .cim_constants import (
    ALLOWLISTED_PATTERNS,
    EPHEMERAL_WRITE_ZONES,
    LANE_MAP,
    PRODUCTION_WRITE_ZONES,
    PROHIBITED_WRITE_ZONES,
    SKIP_DIRS,
    TEMP_FIXTURE_NAMES,
    TEMP_FUNCTION_NAMES,
)


# ID: cfac5ee3-c626-40fa-bd97-a027daba80b2
# ID: 19e21116-67e8-43fc-9f19-cd4691ee37b0
def should_skip_path(path: Path, repo_root: Path) -> bool:
    """Determine if a path should be skipped during scanning.

    Skip rules:
    - All hidden directories EXCEPT .intent
    - Known junk directories (var/, work/, backups/, etc.)
    """
    try:
        rel_path = path.relative_to(repo_root)
    except ValueError:
        return True

    for part in rel_path.parts:
        if part in SKIP_DIRS:
            return True
        if part.startswith(".") and part != ".intent":
            return True

    return False


# ID: 1e39f3fa-7672-4b8f-94da-0b1b4adb1f4a
# ID: 662ece26-5c53-4cef-9ab2-6fcd392061e5
def classify_write_zone(path: str) -> str:
    """Classify write operation by target zone.

    Returns:
        "ephemeral" | "production" | "prohibited" | "unknown"
    """
    parts = Path(path).parts
    if not parts:
        return "unknown"

    first = parts[0]

    if first in EPHEMERAL_WRITE_ZONES:
        return "ephemeral"
    if first in PRODUCTION_WRITE_ZONES:
        return "production"

    full_path = "/".join(parts)
    for prohibited in PROHIBITED_WRITE_ZONES:
        if full_path.startswith(prohibited):
            return "prohibited"

    return "unknown"


# ID: 98cb9966-7b48-456a-a19c-3c9838aed469
# ID: c796fef3-36eb-4e39-a38e-b0758d97e4be
def classify_lane(path: str) -> str:
    """Map file path to architectural lane.

    Returns:
        "body" | "mind" | "will" | "shared" | "features" | "tests" | "other"
    """
    for lane, prefixes in LANE_MAP.items():
        for prefix in prefixes:
            if path.startswith(prefix):
                return lane

    if path.startswith("src/"):
        parts = Path(path).parts
        if len(parts) > 1 and parts[1] in LANE_MAP:
            return parts[1]

    return "other"


# ID: 4624907e-767b-4f0d-bd4d-56d45958ea1a
# ID: 7e904c77-2189-4e75-bb9a-f472a13d77ee
def is_allowlisted(path: str) -> bool:
    """Check if mutation surface is in the known-safe allowlist."""
    return any(pattern in path for pattern in ALLOWLISTED_PATTERNS)


# ID: 322f4829-5fec-43aa-bea2-9c417165a81e
# ID: a582546d-384a-41ff-92f8-3355212695f4
def is_temp_write_operation(node: ast.Call, file_content: str) -> bool:
    """Detect if a write operation targets a temporary location.

    Strategies:
    1. Function name indicates temp (mkdtemp, TemporaryFile, etc.)
    2. First argument is a /tmp/ path literal
    3. Source file uses pytest temp fixtures
    """
    func_name = None
    if isinstance(node.func, ast.Name):
        func_name = node.func.id
    elif isinstance(node.func, ast.Attribute):
        func_name = node.func.attr

    if func_name in TEMP_FUNCTION_NAMES:
        return True

    if node.args:
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            if first_arg.value.startswith(("/tmp/", "/var/tmp/", "tmp/", "temp/")):
                return True

    return any(fixture in file_content for fixture in TEMP_FIXTURE_NAMES)
