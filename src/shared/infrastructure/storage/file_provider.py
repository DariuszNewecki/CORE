# src/shared/infrastructure/storage/file_provider.py
"""
FileProvider - Governed read-only filesystem access for CORE-managed artefacts.

Why this exists
---------------
CORE already has FileHandler as the governed mutation surface. FileProvider is the
corresponding governed READ surface so the codebase stops performing ad hoc reads
via `open()` / `Path.read_text()`.

Boundaries
----------
- READ-ONLY: no mkdir/write/delete/copy/move operations.
- MUST NOT read externally managed governance inputs such as `.intent/`.
  Those are handled by ConstitutionProvider (renamed IntentProvider).
- Uses Settings.paths (PathResolver) as the SSOT for all resolution.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import yaml

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass(frozen=True, slots=True)
# ID: 41684ac0-5157-47ea-af29-8919e71b1923
class FileRef:
    """Resolved file reference (useful for auditability later)."""

    scope: str
    path: Path


# ID: 9c7b3f3b-6a66-4a3d-8fd8-4b1d0aa1d6c1
class FileProvider:
    """
    Governed read-only filesystem façade for CORE-managed artefacts.

    Callers use a logical `scope` (e.g., "reports", "logs", "var") rather than
    constructing repository-relative paths. This concentrates evolution and
    governance in one place.
    """

    # Forbidden governance/external inputs in this provider
    _FORBIDDEN_SCOPES: ClassVar[set[str]] = {".intent", "intent", ".secrets", "secrets"}

    # Explicit allowlist. Tight now; easy to extend later.
    _DEFAULT_ALLOWED_SCOPES: ClassVar[set[str]] = {
        # repo roots
        "src",
        "tests",
        "docs",
        "sql",
        "scripts",
        "demos",
        "work",  # top-level work/ scratch
        # runtime (var/*) canonical layout
        "var",
        "logs",  # var/logs
        "reports",  # var/reports
        "exports",  # var/exports
        "workflows",  # var/workflows
        "build",  # var/build
        "context",  # var/context
        "context_cache",  # var/cache/context
        "knowledge",  # var/mind/knowledge
        "mind_export",  # var/core/mind_export
        "prompts",  # var/prompts
    }

    def __init__(self, allowed_scopes: set[str] | None = None) -> None:
        self._paths = settings.paths  # SSOT for resolution
        self._allowed_scopes = allowed_scopes or set(self._DEFAULT_ALLOWED_SCOPES)

    # ---------------------------------------------------------------------
    # Resolution / existence
    # ---------------------------------------------------------------------

    # ID: 51789018-fd0b-4237-bd9e-d6eabf65cd0d
    def resolve(self, scope: str, *parts: str) -> FileRef:
        scope_key = self._normalize_scope(scope)

        if scope_key in self._FORBIDDEN_SCOPES:
            raise ValueError(
                f"Scope {scope!r} is forbidden in FileProvider. "
                "Use ConstitutionProvider for `.intent` inputs."
            )

        if scope_key not in self._allowed_scopes:
            raise ValueError(
                f"Scope {scope!r} is not allowed for FileProvider. "
                f"Allowed: {', '.join(sorted(self._allowed_scopes))}"
            )

        base = self._scope_base(scope_key)
        safe_parts = self._sanitize_parts(parts)
        return FileRef(scope=scope_key, path=base.joinpath(*safe_parts))

    # ID: da2bb785-7830-40ac-b433-d9f34e6a4e43
    def exists(self, scope: str, *parts: str) -> bool:
        return self.resolve(scope, *parts).path.exists()

    # ---------------------------------------------------------------------
    # Reads
    # ---------------------------------------------------------------------

    # ID: 87aafc75-9069-4f84-9bfa-fe175155a813
    def read_text(self, scope: str, *parts: str, encoding: str = "utf-8") -> str:
        ref = self.resolve(scope, *parts)
        return ref.path.read_text(encoding=encoding)

    # ID: 51d45dcd-3442-4709-bd97-053e16950e0c
    def read_bytes(self, scope: str, *parts: str) -> bytes:
        ref = self.resolve(scope, *parts)
        return ref.path.read_bytes()

    # ID: 5bac04e1-e6ca-4748-b31e-4c6126659bb4
    def read_json(self, scope: str, *parts: str, encoding: str = "utf-8") -> Any:
        ref = self.resolve(scope, *parts)
        raw = ref.path.read_text(encoding=encoding)
        return json.loads(raw)

    # ID: fdca65ae-6f82-4538-9861-3f02dba7ce92
    def read_yaml(self, scope: str, *parts: str, encoding: str = "utf-8") -> Any:
        ref = self.resolve(scope, *parts)
        raw = ref.path.read_text(encoding=encoding)
        return yaml.safe_load(raw)

    # ---------------------------------------------------------------------
    # Listing
    # ---------------------------------------------------------------------

    # ID: 6978f1cf-d20a-4496-9103-e86e66b4714b
    def list_dir(
        self,
        scope: str,
        *parts: str,
        pattern: str = "*",
        recursive: bool = False,
        include_dirs: bool = False,
    ) -> list[Path]:
        ref = self.resolve(scope, *parts)
        base = ref.path

        if not base.exists():
            return []
        if not base.is_dir():
            raise NotADirectoryError(str(base))

        it = base.rglob(pattern) if recursive else base.glob(pattern)
        items: list[Path] = []
        for p in it:
            if p.is_dir() and not include_dirs:
                continue
            items.append(p)

        return sorted(items)

    # ---------------------------------------------------------------------
    # Internal mapping
    # ---------------------------------------------------------------------

    def _scope_base(self, scope_key: str) -> Path:
        # Repo roots (not exposed as properties in PathResolver)
        if scope_key == "src":
            return self._paths.repo_root / "src"
        if scope_key == "tests":
            return self._paths.repo_root / "tests"
        if scope_key == "docs":
            return self._paths.repo_root / "docs"
        if scope_key == "sql":
            return self._paths.repo_root / "sql"
        if scope_key == "scripts":
            return self._paths.repo_root / "scripts"
        if scope_key == "demos":
            return self._paths.repo_root / "demos"
        if scope_key == "work":
            return self._paths.work_dir

        # Runtime (var/*) via PathResolver canonical layout
        if scope_key == "var":
            return self._paths.var_dir
        if scope_key == "logs":
            return self._paths.logs_dir
        if scope_key == "reports":
            return self._paths.reports_dir
        if scope_key == "exports":
            return self._paths.exports_dir
        if scope_key == "workflows":
            return self._paths.workflows_dir
        if scope_key == "build":
            return self._paths.build_dir
        if scope_key == "context":
            return self._paths.context_dir
        if scope_key == "context_cache":
            return self._paths.context_cache_dir
        if scope_key == "knowledge":
            return self._paths.knowledge_dir
        if scope_key == "mind_export":
            return self._paths.mind_export_dir
        if scope_key == "prompts":
            return self._paths.prompts_dir

        raise ValueError(f"Unmapped scope: {scope_key}")

    @staticmethod
    def _normalize_scope(scope: str) -> str:
        return scope.strip().lower()

    @staticmethod
    def _sanitize_parts(parts: Iterable[str]) -> list[str]:
        safe: list[str] = []
        for raw in parts:
            txt = (raw or "").strip().replace("\\", "/")
            if not txt:
                continue
            segs = [s for s in txt.split("/") if s]
            for s in segs:
                if s in {".", ".."}:
                    raise ValueError("Path traversal segments are not allowed.")
                safe.append(s)
        return safe
