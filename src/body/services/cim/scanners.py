# src/body/services/cim/scanners.py
# ID: body.services.cim.scanners

"""
Read-only scanners for CIM-0 census.
All functions are pure, deterministic, and safe.
"""

from __future__ import annotations

import ast
import subprocess
from collections import defaultdict
from pathlib import Path

from shared.logger import getLogger

from .models import (
    ArchitecturalSignals,
    CensusError,
    ExecutionSurface,
    MutationSurface,
    RepoInfo,
    TreeStats,
)


logger = getLogger(__name__)

# Explicit skip list for known junk/temporary directories
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
    "scripts",  # Personal toolbelt, not production
    ".eggs",
}

DEPENDENCY_FILES = {"pyproject.toml", "requirements.txt", "setup.py", "Pipfile"}

# Write zone classification (FIXED: scripts is now ephemeral)
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

# Lane classification (FIXED: added tests and scripts)
LANE_MAP = {
    "body": ["body/"],
    "mind": ["mind/"],
    "will": ["will/"],
    "shared": ["shared/"],
    "features": ["features/"],
    "tests": ["tests/"],
}

# Allowlisted patterns (known-safe mutation surfaces)
ALLOWLISTED_PATTERNS = [
    "shared/infrastructure/storage/file_handler.py",
    "shared/logger.py",
    "shared/infrastructure/clients/",
    "shared/infrastructure/database/",
    "body/governance/intent_guard.py",
]

# Temp operation detection patterns (FIX #3: call-site aware)
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


def _should_skip_path(path: Path, repo_root: Path) -> bool:
    """
    Determine if a path should be skipped during scanning.

    Skip rules:
    - All hidden directories EXCEPT .intent
    - Known junk directories (var/, work/, backups/, etc.)
    - Any path containing skip dirs in its ancestry
    """
    try:
        rel_path = path.relative_to(repo_root)
    except ValueError:
        # Path is outside repo_root
        return True

    # Check against explicit skip list
    for part in rel_path.parts:
        if part in SKIP_DIRS:
            return True

    # Skip ALL hidden directories except .intent
    for part in rel_path.parts:
        if part.startswith(".") and part != ".intent":
            return True

    return False


# ID: 7b788111-e305-4663-b836-48dac7bf42f9
def classify_write_zone(path: str) -> str:
    """
    Classify write operation by target zone.

    Returns: "ephemeral" | "production" | "prohibited" | "unknown"
    """
    parts = Path(path).parts
    if not parts:
        return "unknown"

    first = parts[0]

    if first in EPHEMERAL_WRITE_ZONES:
        return "ephemeral"

    if first in PRODUCTION_WRITE_ZONES:
        return "production"

    # Check for prohibited paths (e.g., .intent/constitution/)
    full_path = "/".join(parts)
    for prohibited in PROHIBITED_WRITE_ZONES:
        if full_path.startswith(prohibited):
            return "prohibited"

    return "unknown"


# ID: 4cf69006-889b-47cf-a956-285bae8f408a
def classify_lane(path: str) -> str:
    """
    Map file path to architectural lane.

    Returns: "body" | "mind" | "will" | "shared" | "features" | "tests" | "scripts" | "other"
    """
    # Direct match on top-level
    for lane, prefixes in LANE_MAP.items():
        for prefix in prefixes:
            if path.startswith(prefix):
                return lane

    # Check if path is under src/
    if path.startswith("src/"):
        parts = Path(path).parts
        if len(parts) > 1:
            layer = parts[1]
            if layer in LANE_MAP:
                return layer

    return "other"


# ID: a773fa8e-3a65-492b-8f69-3aa09bda06b3
def is_allowlisted(path: str) -> bool:
    """Check if mutation surface is in allowlist (known-safe)."""
    for pattern in ALLOWLISTED_PATTERNS:
        if pattern in path:
            return True
    return False


# ID: 1bf7976d-73c5-4562-8ca8-48aed0fd7309
def is_temp_write_operation(node: ast.Call, file_content: str) -> bool:
    """
    Detect if a write operation targets a temporary location.

    Strategies:
    1. Function name indicates temp (mkdtemp, TemporaryFile, etc.)
    2. Argument is a temp path (/tmp/, /var/tmp/)
    3. Source uses pytest fixtures (tmp_path, tmpdir)
    """
    # Check function name
    func_name = None
    if isinstance(node.func, ast.Name):
        func_name = node.func.id
    elif isinstance(node.func, ast.Attribute):
        func_name = node.func.attr

    if func_name in TEMP_FUNCTION_NAMES:
        return True

    # Check if first argument is a temp path literal
    if node.args:
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            path = first_arg.value
            if path.startswith(("/tmp/", "/var/tmp/", "tmp/", "temp/")):
                return True

    # Check for pytest fixture usage in source
    for fixture in TEMP_FIXTURE_NAMES:
        if fixture in file_content:
            return True

    return False


# ID: 3a31edb2-d190-4333-91e3-c87aa4a0010a
def scan_git_metadata(repo_root: Path) -> RepoInfo:
    """Extract git metadata if present."""
    root_str = str(repo_root.resolve())

    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return RepoInfo(root_path=root_str)

    try:
        remote = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        remote = None

    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        branch = None

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        commit = None

    return RepoInfo(
        root_path=root_str, git_remote=remote, git_branch=branch, git_commit=commit
    )


# ID: 58011774-5cc8-4da2-9cca-4d57575268da
def scan_tree_stats(repo_root: Path) -> TreeStats:
    """Walk filesystem and gather statistics."""
    file_count = 0
    dir_count = 0
    extensions: dict[str, int] = defaultdict(int)
    top_level_dirs: set[str] = set()

    for item in repo_root.rglob("*"):
        if _should_skip_path(item, repo_root):
            continue

        if item.is_dir():
            dir_count += 1
            rel = item.relative_to(repo_root)
            if len(rel.parts) == 1:
                top_level_dirs.add(rel.parts[0])
        elif item.is_file():
            file_count += 1
            ext = item.suffix.lower()
            if ext:
                normalized_ext = ext.lstrip(".")
                extensions[normalized_ext] += 1

    return TreeStats(
        total_files=file_count,
        total_directories=dir_count,
        extensions=dict(sorted(extensions.items())),
        top_level_dirs=sorted(top_level_dirs),
    )


# ID: 71a107ff-f7a8-4b7f-a1a4-e4fa52023339
def scan_architectural_signals(repo_root: Path) -> ArchitecturalSignals:
    """Detect presence of architectural markers."""
    signals = ArchitecturalSignals()

    signals.has_src = (repo_root / "src").exists()
    signals.has_intent = (repo_root / ".intent").exists()
    signals.has_sql = (repo_root / "sql").exists()
    signals.has_tests = (repo_root / "tests").exists()
    signals.has_docs = (repo_root / "docs").exists()

    dep_files = []
    for fname in DEPENDENCY_FILES:
        if (repo_root / fname).exists():
            dep_files.append(fname)
    signals.dependency_files = sorted(dep_files)

    return signals


# ID: 1122fc47-78d0-41b7-b4fb-964b4b82094a
def extract_cli_entrypoints(repo_root: Path) -> list[str]:
    """Extract console_scripts from pyproject.toml."""
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return []

    try:
        import tomli

        content = pyproject.read_text(encoding="utf-8")
        data = tomli.loads(content)

        scripts = data.get("project", {}).get("scripts", {})
        if not scripts:
            scripts = data.get("tool", {}).get("poetry", {}).get("scripts", {})

        return sorted(scripts.keys())
    except Exception as e:
        logger.debug("Failed to extract CLI entrypoints: %s", e)
        return []


# ID: 37641417-45c8-4027-aa63-9a032f55c528
def scan_execution_surfaces(
    repo_root: Path,
) -> tuple[list[ExecutionSurface], list[CensusError]]:
    """Detect CLI entrypoints and __main__ blocks."""
    surfaces = []
    errors = []

    for py_file in repo_root.rglob("*.py"):
        if _should_skip_path(py_file, repo_root):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            if (
                '__name__ == "__main__"' in content
                or "__name__ == '__main__'" in content
            ):
                rel_path = str(py_file.relative_to(repo_root))
                surfaces.append(
                    ExecutionSurface(
                        path=rel_path,
                        type="main_block",
                        line=None,
                    )
                )
        except Exception as e:
            rel_path = str(py_file.relative_to(repo_root))
            errors.append(
                CensusError(
                    path=rel_path,
                    error_type="read_error",
                    message=str(e),
                )
            )

    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomli

            content = pyproject.read_text(encoding="utf-8")
            data = tomli.loads(content)
            scripts = data.get("project", {}).get("scripts", {})
            if not scripts:
                scripts = data.get("tool", {}).get("poetry", {}).get("scripts", {})
            if scripts:
                surfaces.append(
                    ExecutionSurface(
                        path="pyproject.toml",
                        type="cli_entrypoint",
                        line=None,
                    )
                )
        except Exception as e:
            errors.append(
                CensusError(
                    path="pyproject.toml",
                    error_type="parse_error",
                    message=str(e),
                )
            )

    surfaces.sort(key=lambda x: (x.path, x.type))
    return surfaces, errors


# ID: f06c71ba-3475-4973-9594-cecdccbb5592
def scan_mutation_surfaces(
    repo_root: Path,
) -> tuple[list[MutationSurface], list[CensusError]]:
    """
    AST-scan Python files for mutation patterns with full classification.

    Enriches each surface with:
    - write_zone (ephemeral/production/prohibited) - CALL-SITE AWARE
    - lane (body/mind/will/shared/features/tests/scripts)
    - allowlisted flag
    """
    surfaces = []
    errors = []

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

    for py_file in repo_root.rglob("*.py"):
        if _should_skip_path(py_file, repo_root):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
            rel_path = str(py_file.relative_to(repo_root))

            lane = classify_lane(rel_path)
            allowlisted = is_allowlisted(rel_path)

            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        module = alias.name
                        for key, (mutation_type, operation) in MUTATION_IMPORTS.items():
                            if key in module:
                                surfaces.append(
                                    MutationSurface(
                                        path=rel_path,
                                        type=mutation_type,
                                        operation=operation,
                                        line=node.lineno,
                                        detail=f"imports {module}",
                                        write_zone=None,
                                        lane=lane,
                                        allowlisted=allowlisted,
                                    )
                                )

                if isinstance(node, ast.Call):
                    func_name = None
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr

                    if func_name:
                        if func_name in FILESYSTEM_READ_OPS:
                            operation = "read"
                            mutation_type = "filesystem_read"

                            if func_name == "open" and len(node.args) > 1:
                                mode_arg = node.args[1]
                                if isinstance(mode_arg, ast.Constant) and isinstance(
                                    mode_arg.value, str
                                ):
                                    if "w" in mode_arg.value or "a" in mode_arg.value:
                                        operation = "write"
                                        mutation_type = "filesystem_write"
                                    elif "r" in mode_arg.value:
                                        operation = "read"
                                        mutation_type = "filesystem_read"
                                    else:
                                        operation = "unknown"
                                        mutation_type = "filesystem_write"

                            # CALL-SITE AWARE: Check if temp operation
                            write_zone = None
                            if mutation_type == "filesystem_write":
                                if is_temp_write_operation(node, content):
                                    write_zone = "ephemeral"
                                else:
                                    write_zone = classify_write_zone(rel_path)

                            surfaces.append(
                                MutationSurface(
                                    path=rel_path,
                                    type=mutation_type,
                                    operation=operation,
                                    line=node.lineno,
                                    detail=f"calls {func_name}()",
                                    write_zone=write_zone,
                                    lane=lane,
                                    allowlisted=allowlisted,
                                )
                            )

                        elif func_name in FILESYSTEM_WRITE_OPS:
                            # CALL-SITE AWARE: Check if temp operation
                            if is_temp_write_operation(node, content):
                                write_zone = "ephemeral"
                            else:
                                write_zone = classify_write_zone(rel_path)

                            surfaces.append(
                                MutationSurface(
                                    path=rel_path,
                                    type="filesystem_write",
                                    operation="write",
                                    line=node.lineno,
                                    detail=f"calls {func_name}()",
                                    write_zone=write_zone,
                                    lane=lane,
                                    allowlisted=allowlisted,
                                )
                            )

        except SyntaxError as e:
            errors.append(
                CensusError(
                    path=rel_path,
                    error_type="syntax_error",
                    message=str(e),
                )
            )
        except Exception as e:
            errors.append(
                CensusError(
                    path=rel_path,
                    error_type="ast_scan_error",
                    message=str(e),
                )
            )

    # Sort and deduplicate
    unique_surfaces = {}
    for s in surfaces:
        key = (s.path, s.type, s.operation, s.line)
        if key not in unique_surfaces:
            unique_surfaces[key] = s

    sorted_surfaces = sorted(
        unique_surfaces.values(), key=lambda x: (x.path, x.type, x.line)
    )
    return sorted_surfaces, errors
