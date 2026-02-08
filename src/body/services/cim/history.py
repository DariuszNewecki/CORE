# src/body/services/cim/history.py
# ID: body.services.cim.history

"""
CIM History - Snapshot management for census tracking.
"""

from __future__ import annotations

from pathlib import Path

from shared.logger import getLogger

from .models import RepoCensus


logger = getLogger(__name__)


# ID: fad78015-cf20-4549-ac53-268afb2e4d33
class CensusHistory:
    """
    Manages census snapshots.

    Append-only storage with named baselines.
    """

    def __init__(self, history_dir: Path):
        """Initialize history manager."""
        self.history_dir = history_dir
        self.history_dir.mkdir(parents=True, exist_ok=True)

    # ID: 04b505ee-35c4-4747-88a8-9c83ea9cd8f9
    def save_snapshot(self, census: RepoCensus) -> Path:
        """
        Save census as immutable snapshot.

        Returns path to saved snapshot.
        """
        timestamp = census.metadata.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"census_{timestamp}.json"
        snapshot_path = self.history_dir / filename

        # Append-only: never overwrite
        if snapshot_path.exists():
            logger.warning("Snapshot already exists: %s", snapshot_path)
            return snapshot_path

        snapshot_path.write_text(census.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Saved snapshot: %s", snapshot_path)

        return snapshot_path

    # ID: c2cb9a04-bd8c-48d5-b0fb-94ebe146ed32
    def load_snapshot(self, filename: str) -> RepoCensus:
        """Load census from snapshot file."""
        snapshot_path = self.history_dir / filename
        if not snapshot_path.exists():
            raise FileNotFoundError(f"Snapshot not found: {filename}")

        content = snapshot_path.read_text(encoding="utf-8")
        return RepoCensus.model_validate_json(content)

    # ID: 8d41aa80-c69c-4a56-9efb-f8fef2d5105b
    def list_snapshots(self) -> list[Path]:
        """List all snapshots in chronological order."""
        snapshots = sorted(self.history_dir.glob("census_*.json"))
        return snapshots

    # ID: 7c9947a1-552c-466b-aae9-8aa511bf1355
    def get_latest_snapshot(self) -> RepoCensus | None:
        """Get most recent snapshot, or None if none exist."""
        snapshots = self.list_snapshots()
        if not snapshots:
            return None

        return self.load_snapshot(snapshots[-1].name)

    # ID: 6a61380e-e53e-4093-987e-0858d2285047
    def get_previous_snapshot(self) -> RepoCensus | None:
        """Get second-most-recent snapshot, or None if <2 exist."""
        snapshots = self.list_snapshots()
        if len(snapshots) < 2:
            return None

        return self.load_snapshot(snapshots[-2].name)
