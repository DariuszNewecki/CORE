# src/shared/infrastructure/specs/specs_repository.py

"""
SpecsRepository — Canonical read-only interface to CORE's human intent layer (.specs).

The .specs/ directory holds human-authored specifications as markdown documents.
Unlike .intent/ (the Mind), .specs/ contains no governance artifacts: no YAML
policies, no JSON rule indexes, no precedence hierarchies. It is purely a
narrative layer describing what the system is intended to be from a human
perspective.

Contract:
- Root is derived from settings.SPECS — never hardcoded.
- Provides text loading and directory listing only.
- No write operations are exposed.
- No rule or policy indexing — .specs/ is markdown, not governance.

Layer: shared/infrastructure/specs — infrastructure.
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from shared.config import settings
from shared.infrastructure.intent.errors import GovernanceError
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: e8c9b81f-dfe9-49d7-948d-35191e9fb0ba
class SpecsRepository:
    """
    The canonical read-only repository for .specs — CORE's human intent layer.

    Contract:
    - Root is derived from settings.SPECS only.
    - Read-only: no write operations are exposed.
    - Boundary-enforced: all paths are resolved against the specs root and
      rejected if they escape it.
    - No governance indexing: .specs/ contains markdown, not policies or rules.
    """

    # ID: 95a0b383-9a00-4b4d-8a0e-4938d0c3e435
    def __init__(self) -> None:
        self._root: Path = settings.SPECS.resolve()

    @property
    # ID: df92b220-3949-4523-b78f-91fa76f43728
    def root(self) -> Path:
        return self._root

    # ID: 21da0aa6-70d0-40da-93e9-5ac9ef724d37
    def resolve_rel(self, rel: str | Path) -> Path:
        rel_path = Path(rel)
        if rel_path.is_absolute():
            raise GovernanceError(f"Absolute paths are not allowed: {rel_path}")

        resolved = (self._root / rel_path).resolve()
        if self._root not in resolved.parents and resolved != self._root:
            raise GovernanceError(f"Path traversal detected: {rel_path}")

        return resolved

    # ID: 10d45a45-e898-4cc1-b954-6bec364cf818
    def load_text(self, rel: str | Path) -> str:
        """
        Load a markdown (or any text) artifact from .specs/.
        Enforces boundary — path must be within specs root.
        Read-only. No parsing.
        """
        abs_path = self.resolve_rel(rel)
        if not abs_path.exists():
            raise GovernanceError(f"Specs artifact not found: {abs_path}")
        try:
            return abs_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            raise GovernanceError(
                f"Failed to read specs artifact {abs_path}: {e}"
            ) from e

    # ID: ba645fbb-9eb3-4e00-a0ae-8c2742431c1e
    def list_files(self, subdir: str = "", suffix: str = ".md") -> list[Path]:
        """
        List all files matching `suffix` under `subdir` (or the specs root if empty).
        Returns absolute paths, sorted deterministically.
        """
        base = self.resolve_rel(subdir) if subdir else self._root
        if not base.exists() or not base.is_dir():
            return []

        return sorted(p for p in base.rglob(f"*{suffix}") if p.is_file())

    # ID: 0a86e141-87e9-487f-9854-ac4d9067c070
    def list_subdirs(self) -> list[str]:
        """List immediate subdirectories of the specs root, sorted by name."""
        if not self._root.exists() or not self._root.is_dir():
            return []
        return sorted(p.name for p in self._root.iterdir() if p.is_dir())


_specs_repo_instance: SpecsRepository | None = None
_SPECS_REPO_LOCK = Lock()


# ID: 2c554a1d-8c94-49eb-9c74-1b912fab6cc5
def get_specs_repository() -> SpecsRepository:
    global _specs_repo_instance
    with _SPECS_REPO_LOCK:
        if _specs_repo_instance is None:
            _specs_repo_instance = SpecsRepository()
        return _specs_repo_instance
