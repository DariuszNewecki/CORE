# src/body/services/cim/baselines.py
# ID: ed67426d-db81-4aa5-946a-edd4657bd457

"""
CIM Baselines - Named anchors for comparison.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from shared.logger import getLogger

from .models import BaselineRegistry, CensusBaseline


logger = getLogger(__name__)


# ID: 24bc667c-43a4-48eb-ad47-53a4a82231b3
class BaselineManager:
    """
    Manages named baselines for census comparison.

    Baselines are named references to specific snapshots.
    """

    def __init__(self, registry_path: Path):
        """Initialize baseline manager."""
        self.registry_path = registry_path
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        if self.registry_path.exists():
            content = self.registry_path.read_text(encoding="utf-8")
            self.registry = BaselineRegistry.model_validate_json(content)
        else:
            self.registry = BaselineRegistry()

    def _save(self):
        """Persist registry to disk."""
        self.registry_path.write_text(
            self.registry.model_dump_json(indent=2), encoding="utf-8"
        )

    # ID: cdc3462e-f8b5-4ac6-9dcb-53f15de55528
    def set_baseline(
        self, name: str, snapshot_file: str, git_commit: str | None = None
    ) -> CensusBaseline:
        """
        Create or update a named baseline.

        Args:
            name: Baseline name (e.g., "v2.0.0", "pre-refactor")
            snapshot_file: Snapshot filename to reference
            git_commit: Git commit hash (optional)

        Returns:
            Created baseline
        """
        baseline = CensusBaseline(
            name=name,
            snapshot_file=snapshot_file,
            git_commit=git_commit,
            created_at=datetime.utcnow(),
        )

        self.registry.baselines[name] = baseline
        self._save()

        logger.info("Set baseline '%s' → %s", name, snapshot_file)
        return baseline

    # ID: e7891b2c-1818-4ddf-8955-c1805ad1e681
    def get_baseline(self, name: str) -> CensusBaseline | None:
        """Get baseline by name."""
        return self.registry.baselines.get(name)

    # ID: 84268cb9-a2d3-4fbc-a93f-fa327493fafd
    def list_baselines(self) -> list[CensusBaseline]:
        """List all baselines in chronological order."""
        return sorted(
            self.registry.baselines.values(), key=lambda b: b.created_at, reverse=True
        )

    # ID: 7ebee765-dc76-4c00-b776-969fd0b86ade
    def delete_baseline(self, name: str) -> bool:
        """Delete a baseline by name."""
        if name in self.registry.baselines:
            del self.registry.baselines[name]
            self._save()
            logger.info("Deleted baseline '%s'", name)
            return True
        return False
