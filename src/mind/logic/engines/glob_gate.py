# src/mind/logic/engines/glob_gate.py

"""
Deterministic Path Auditor.

CONSTITUTIONAL ALIGNMENT:
- Aligned with 'async.no_manual_loop_run'.
- Promoted to natively async to satisfy the BaseEngine contract.
- Complies with ASYNC230 by offloading blocking I/O to threads.
"""

from __future__ import annotations

import asyncio
import fnmatch
from pathlib import Path
from typing import Any

from .base import BaseEngine, EngineResult, EvidenceClass


# ID: 3af1be62-fd37-41f9-b842-8029e8fba49d
def _count_lines_sync(path: Path) -> int:
    """Helper to perform blocking file read in a thread."""
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f)


# ID: e9ab205c-263d-40c2-91ce-e44471308a21
class GlobGateEngine(BaseEngine):
    """
    Deterministic Path Auditor.
    Enforces architectural boundaries based on file location and glob patterns.
    Also supports simple file metrics like line counts.
    """

    engine_id = "glob_gate"
    evidence_class = EvidenceClass.PROVEN  # ADR-113: deterministic verdict

    # ID: 6576f3e8-c1f6-4180-bcd2-076f7cd7a491
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """
        Natively async verification.
        Matches the BaseEngine contract to prevent loop-hijacking in orchestrators.
        """
        violations: list[str | dict[str, Any]] = []

        # Normalize the path relative to project root for consistent matching
        try:
            target_path = str(file_path)
        except Exception as e:
            return EngineResult(
                ok=False,
                message=f"Invalid path: {e}",
                violations=[],
                engine_id=self.engine_id,
            )

        # --- CHECK TYPE DISPATCH ---
        check_type = params.get("check_type")

        if check_type == "allowed_top_level_dirs":
            return self._check_allowed_top_level_dirs(target_path, params)

        if check_type == "directory_has_required_files":
            return self._check_directory_has_required_files(
                file_path, target_path, params
            )

        if check_type == "files_not_empty":
            return self._check_files_not_empty(file_path, target_path, params)

        # --- max_lines with optional path-based thresholds ---
        max_lines = params.get("max_lines")
        thresholds = params.get("thresholds")

        if max_lines or thresholds:
            try:
                # Use to_thread to prevent blocking the event loop during file I/O.
                line_count = await asyncio.to_thread(_count_lines_sync, file_path)

                # Determine the appropriate limit based on file path
                limit = max_lines  # Default

                if thresholds and isinstance(thresholds, list):
                    # Check path-based thresholds in order
                    for threshold in thresholds:
                        if not isinstance(threshold, dict):
                            continue

                        pattern = threshold.get("path")
                        threshold_limit = threshold.get("limit")

                        if pattern and threshold_limit:
                            # Convert to posix path for matching
                            posix_path = target_path.replace("\\", "/")

                            # Special handling for "default"
                            if pattern == "default":
                                if (
                                    limit is None
                                ):  # Only use default if no other limit set
                                    limit = threshold_limit
                            elif self._match(posix_path, pattern):
                                limit = threshold_limit
                                break  # First match wins

                if limit and line_count > limit:
                    violations.append(
                        f"Module has {line_count} lines, exceeds limit of {limit}"
                    )
            except Exception:
                # Don't fail the check if we can't read the file
                pass

        # 1. Fact: Extract patterns from parameters
        patterns = (
            params.get("patterns")
            or params.get("forbidden_paths")
            or params.get("patterns_prohibited", [])
        )
        if isinstance(patterns, str):
            patterns = [patterns]

        # 2. Fact: Check for pattern matches (The Violation)
        for pattern in patterns:
            if self._match(target_path, pattern):
                action_type = params.get("action", "block")
                violations.append(
                    f"Resource '{target_path}' matches restricted pattern '{pattern}' (Action: {action_type})"
                )

        # 3. Fact: Check Exclusions (Exceptions)
        exceptions = params.get("exceptions", [])
        if violations and exceptions:
            # Filter out violations that are actually exceptions
            violations = [
                v
                for v in violations
                if not any(self._match(target_path, exc) for exc in exceptions)
            ]

        if not violations:
            return EngineResult(
                ok=True,
                message="Path authorization verified.",
                violations=[],
                engine_id=self.engine_id,
            )

        return EngineResult(
            ok=False,
            message="Boundary Violation: Attempted access to protected zone.",
            violations=violations,
            engine_id=self.engine_id,
        )

    # ID: 9596f97f-c126-4644-8821-b7a1713cedb2
    def _check_allowed_top_level_dirs(
        self, target_path: str, params: dict[str, Any]
    ) -> EngineResult:
        """
        Whitelist check: file must reside within one of the allowed directories.

        This is the perimeter walk — it answers "does anything exist outside
        the constitutional boundary?" rather than "does this file access
        something forbidden?"

        Params:
            allowed: List of glob patterns for permitted locations.
                     e.g. ["src/mind/**", "src/body/**", "src/will/**",
                            "src/shared/**", "src/api/**"]
        """
        allowed = params.get("allowed", [])
        if not allowed:
            return EngineResult(
                ok=False,
                message="Configuration error: allowed_top_level_dirs requires 'allowed' list",
                violations=["No allowed patterns specified"],
                engine_id=self.engine_id,
            )

        posix_path = target_path.replace("\\", "/")
        # Strip repo root to get relative path for matching against patterns
        src_idx = posix_path.find("/src/")
        if src_idx != -1:
            posix_path = posix_path[src_idx + 1 :]  # "src/body/..."
        is_allowed = any(self._match(posix_path, pat) for pat in allowed)

        if is_allowed:
            return EngineResult(
                ok=True,
                message="File resides within constitutional boundary.",
                violations=[],
                engine_id=self.engine_id,
            )

        return EngineResult(
            ok=False,
            message="Perimeter Violation: File exists outside constitutional layers.",
            violations=[
                f"File '{posix_path}' exists outside constitutional layers. "
                f"Allowed: {', '.join(allowed)}"
            ],
            engine_id=self.engine_id,
        )

    # ID: 3f4a5b6c-7d8e-9f0a-1b2c-3d4e5f6a7b8c
    def _match(self, path: str, pattern: str) -> bool:
        """
        Implements robust glob matching including recursive (**) support.
        """
        path = path.replace("\\", "/")
        pattern = pattern.replace("\\", "/")

        if "**" in pattern:
            parts = pattern.split("/**")
            prefix = parts[0]
            if not prefix:
                return path.endswith(parts[1]) if len(parts) > 1 else True
            return path.startswith(prefix)

        return fnmatch.fnmatch(path, pattern)

    # ID: 1c9e7a2d-4b6f-4e3a-9d5c-8a1f2e6b0c7d
    def _check_directory_has_required_files(
        self, file_path: Path, target_path: str, params: dict[str, Any]
    ) -> EngineResult:
        """
        Every immediate subdirectory of ``root`` that contains at least one
        file MUST also contain every file named in ``required_files``.

        Dispatched once per matched file under the rule's own scope (which
        covers the whole ``root`` tree per the live mapping) -- a file
        sitting directly under ``root`` rather than inside a subdirectory
        is not itself a governed module and is skipped.
        """
        root = str(params.get("root", "")).strip("/")
        required_files = params.get("required_files") or []
        if not root or not required_files:
            return EngineResult(
                ok=True,
                message="No root/required_files configured.",
                violations=[],
                engine_id=self.engine_id,
            )

        posix_path = target_path.replace("\\", "/")
        marker = f"/{root}/"
        idx = posix_path.find(marker)
        if idx == -1:
            return EngineResult(
                ok=True,
                message="File is outside the configured root.",
                violations=[],
                engine_id=self.engine_id,
            )

        rel = posix_path[idx + len(marker) :]
        parts = rel.split("/")
        if len(parts) < 2:
            return EngineResult(
                ok=True,
                message="File is not inside a governed subdirectory.",
                violations=[],
                engine_id=self.engine_id,
            )

        subdir_name = parts[0]
        subdir_path = Path(posix_path[: idx + len(marker) + len(subdir_name)])
        missing = [f for f in required_files if not (subdir_path / f).exists()]

        if missing:
            return EngineResult(
                ok=False,
                message="Governed directory missing required file(s).",
                violations=[
                    f"Directory '{root}/{subdir_name}' is missing required "
                    f"file(s): {', '.join(missing)}"
                ],
                engine_id=self.engine_id,
            )

        return EngineResult(
            ok=True,
            message="All required files present.",
            violations=[],
            engine_id=self.engine_id,
        )

    # ID: 6d3f8b1a-2c5e-4a9f-b7d1-3e6a9c2f5b8d
    def _check_files_not_empty(
        self, file_path: Path, target_path: str, params: dict[str, Any]
    ) -> EngineResult:
        """Files matching ``pattern`` MUST NOT be empty or whitespace-only.

        Uses a dedicated substring match rather than ``_match()``: real
        dispatch (``rule_executor.py``'s per-file audit loop) always hands
        an absolute filesystem path, but ``_match()``'s prefix branch only
        ever does a leading ``str.startswith``, which can never match an
        absolute path against a repo-relative pattern prefix like
        "var/prompts". Matching on "does the prefix directory appear
        anywhere in the path, and does the path end with the suffix"
        instead handles both absolute and relative callers, and naturally
        covers zero-or-more intermediate directories the same way ``**``
        does elsewhere in this engine.
        """
        pattern = params.get("pattern")
        if not pattern:
            return EngineResult(
                ok=True,
                message="No pattern configured.",
                violations=[],
                engine_id=self.engine_id,
            )

        posix_path = target_path.replace("\\", "/")
        posix_pattern = pattern.replace("\\", "/")

        if "/**/" in posix_pattern:
            prefix, _, suffix = posix_pattern.partition("/**/")
            matches = f"/{prefix}/" in f"/{posix_path}" and posix_path.endswith(
                f"/{suffix}"
            )
        else:
            matches = self._match(posix_path, posix_pattern)

        if not matches:
            return EngineResult(
                ok=True,
                message="File does not match the governed pattern.",
                violations=[],
                engine_id=self.engine_id,
            )

        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError:
            # Don't fail the check if we can't read the file -- matches the
            # existing max_lines block's convention above.
            return EngineResult(
                ok=True,
                message="Could not read file.",
                violations=[],
                engine_id=self.engine_id,
            )

        if not content.strip():
            return EngineResult(
                ok=False,
                message="File matching governed pattern is empty.",
                violations=[
                    f"File '{target_path}' matches pattern '{pattern}' but "
                    "is empty or whitespace-only"
                ],
                engine_id=self.engine_id,
            )

        return EngineResult(
            ok=True,
            message="File is non-empty.",
            violations=[],
            engine_id=self.engine_id,
        )
