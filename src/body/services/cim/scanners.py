# src/body/services/cim/scanners.py
# ID: 4b3016bd-d443-46e8-8d2b-03cda003a2e6
"""Read-only scanners for CIM-0 census.

All functions are pure, deterministic, and safe.
Constants live in cim_constants.py.
Path classification utilities live in cim_path_utils.py.
"""

from __future__ import annotations

import ast
import subprocess
from collections import defaultdict
from pathlib import Path

from shared.logger import getLogger

from .cim_constants import (
    DEPENDENCY_FILES,
    FILESYSTEM_READ_OPS,
    FILESYSTEM_WRITE_OPS,
    MUTATION_IMPORTS,
)
from .cim_path_utils import (
    classify_lane,
    classify_write_zone,
    is_allowlisted,
    is_temp_write_operation,
    should_skip_path,
)
from .models import (
    ArchitecturalSignals,
    CensusError,
    ExecutionSurface,
    MutationSurface,
    RepoInfo,
    TreeStats,
)


logger = getLogger(__name__)


# ID: 3a31edb2-d190-4333-91e3-c87aa4a0010a
def scan_git_metadata(repo_root: Path) -> RepoInfo:
    """Extract git metadata if present."""
    root_str = str(repo_root.resolve())
    git_dir = repo_root / ".git"

    if not git_dir.exists():
        return RepoInfo(root_path=root_str)

    def _git(*args) -> str | None:
        try:
            return subprocess.check_output(
                ["git", *args], cwd=repo_root, text=True, stderr=subprocess.DEVNULL
            ).strip()
        except subprocess.CalledProcessError:
            return None

    return RepoInfo(
        root_path=root_str,
        git_remote=_git("remote", "get-url", "origin"),
        git_branch=_git("rev-parse", "--abbrev-ref", "HEAD"),
        git_commit=_git("rev-parse", "HEAD"),
    )


# ID: 58011774-5cc8-4da2-9cca-4d57575268da
def scan_tree_stats(repo_root: Path) -> TreeStats:
    """Walk filesystem and gather statistics."""
    file_count = 0
    dir_count = 0
    extensions: dict[str, int] = defaultdict(int)
    top_level_dirs: set[str] = set()

    for item in repo_root.rglob("*"):
        if should_skip_path(item, repo_root):
            continue
        if item.is_dir():
            dir_count += 1
            rel = item.relative_to(repo_root)
            if len(rel.parts) == 1:
                top_level_dirs.add(rel.parts[0])
        elif item.is_file():
            file_count += 1
            ext = item.suffix.lower().lstrip(".")
            if ext:
                extensions[ext] += 1

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
    signals.dependency_files = sorted(
        fname for fname in DEPENDENCY_FILES if (repo_root / fname).exists()
    )
    return signals


# ID: 1122fc47-78d0-41b7-b4fb-964b4b82094a
def extract_cli_entrypoints(repo_root: Path) -> list[str]:
    """Extract console_scripts from pyproject.toml."""
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.exists():
        return []
    try:
        import tomli

        data = tomli.loads(pyproject.read_text(encoding="utf-8"))
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
        if should_skip_path(py_file, repo_root):
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
            if (
                '__name__ == "__main__"' in content
                or "__name__ == '__main__'" in content
            ):
                surfaces.append(
                    ExecutionSurface(
                        path=str(py_file.relative_to(repo_root)),
                        type="main_block",
                        line=None,
                    )
                )
        except Exception as e:
            errors.append(
                CensusError(
                    path=str(py_file.relative_to(repo_root)),
                    error_type="read_error",
                    message=str(e),
                )
            )

    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomli

            data = tomli.loads(pyproject.read_text(encoding="utf-8"))
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
    """AST-scan Python files for mutation patterns with full classification."""
    surfaces = []
    errors = []

    for py_file in repo_root.rglob("*.py"):
        if should_skip_path(py_file, repo_root):
            continue

        rel_path = str(py_file.relative_to(repo_root))
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
            lane = classify_lane(rel_path)
            allowlisted = is_allowlisted(rel_path)

            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        for key, (mutation_type, operation) in MUTATION_IMPORTS.items():
                            if key in alias.name:
                                surfaces.append(
                                    MutationSurface(
                                        path=rel_path,
                                        type=mutation_type,
                                        operation=operation,
                                        line=node.lineno,
                                        detail=f"imports {alias.name}",
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

                    if not func_name:
                        continue

                    if func_name in FILESYSTEM_READ_OPS:
                        operation = "read"
                        mutation_type = "filesystem_read"

                        if func_name == "open" and len(node.args) > 1:
                            mode_arg = node.args[1]
                            if isinstance(mode_arg, ast.Constant) and isinstance(
                                mode_arg.value, str
                            ):
                                if "w" in mode_arg.value or "a" in mode_arg.value:
                                    operation, mutation_type = (
                                        "write",
                                        "filesystem_write",
                                    )
                                elif "r" in mode_arg.value:
                                    operation, mutation_type = "read", "filesystem_read"
                                else:
                                    operation, mutation_type = (
                                        "unknown",
                                        "filesystem_write",
                                    )

                        write_zone = None
                        if mutation_type == "filesystem_write":
                            write_zone = (
                                "ephemeral"
                                if is_temp_write_operation(node, content)
                                else classify_write_zone(rel_path)
                            )

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
                        write_zone = (
                            "ephemeral"
                            if is_temp_write_operation(node, content)
                            else classify_write_zone(rel_path)
                        )
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
                CensusError(path=rel_path, error_type="syntax_error", message=str(e))
            )
        except Exception as e:
            errors.append(
                CensusError(path=rel_path, error_type="ast_scan_error", message=str(e))
            )

    unique_surfaces = {}
    for s in surfaces:
        key = (s.path, s.type, s.operation, s.line)
        if key not in unique_surfaces:
            unique_surfaces[key] = s

    return (
        sorted(unique_surfaces.values(), key=lambda x: (x.path, x.type, x.line)),
        errors,
    )
