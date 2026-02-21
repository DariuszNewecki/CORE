# src/body/services/cim/cim_constants.py
# ID: 81edd88e-1bf7-4ab0-81c7-d1d0bc2d6e52
"""CIM-0 Census Constants.

All classification sets and maps used across CIM scanners and path utilities.
Pure data — no logic, no imports.
"""

from __future__ import annotations


# Directories to skip entirely during filesystem walks
SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "var",
    "work",
    "backups",
    ".tox",
    "dist",
    "build",
    "scripts",
    ".eggs",
}

DEPENDENCY_FILES = {"pyproject.toml", "requirements.txt", "setup.py", "Pipfile"}

# Write zone classification
EPHEMERAL_WRITE_ZONES = {
    "var",
    "work",
    ".cache",
    ".ruff_cache",
    ".mypy_cache",
    ".pytest_cache",
    "tmp",
    "temp",
    "reports",
    "logs",
    "backups",
}

PRODUCTION_WRITE_ZONES = {
    "src",  # Production code
    "tests",  # Test suite
    "sql",  # Schema migrations
    "docs",  # Documentation
    ".intent",  # Constitution (with prohibited subzones)
}

PROHIBITED_WRITE_ZONES = {".intent/constitution", ".intent/META"}

# Lane classification
LANE_MAP = {
    "body": ["body/"],
    "mind": ["mind/"],
    "will": ["will/"],
    "shared": ["shared/"],
    "features": ["features/"],
    "tests": ["tests/"],
}

# Allowlisted mutation surfaces (known-safe)
ALLOWLISTED_PATTERNS = [
    "shared/infrastructure/storage/file_handler.py",
    "shared/logger.py",
    "shared/infrastructure/clients/",
    "shared/infrastructure/database/",
    "body/governance/intent_guard.py",
]

# Temp operation detection
TEMP_FUNCTION_NAMES = {
    "mkdtemp",
    "mkstemp",
    "TemporaryDirectory",
    "TemporaryFile",
    "NamedTemporaryFile",
    "SpooledTemporaryFile",
}

TEMP_FIXTURE_NAMES = {
    "tmp_path",
    "tmpdir",
    "tmp_path_factory",
    "tmpdir_factory",
}

# AST mutation surface classification
MUTATION_IMPORTS = {
    "subprocess": ("subprocess", "execute"),
    "requests": ("network", "connect"),
    "httpx": ("network", "connect"),
    "socket": ("network", "connect"),
    "urllib": ("network", "connect"),
    "sqlalchemy": ("database", "connect"),
    "psycopg2": ("database", "connect"),
    "sqlite3": ("database", "connect"),
}

FILESYSTEM_READ_OPS = {"read_text", "read_bytes", "open"}

FILESYSTEM_WRITE_OPS = {
    "write",
    "write_text",
    "write_bytes",
    "mkdir",
    "rmdir",
    "unlink",
    "remove",
}
