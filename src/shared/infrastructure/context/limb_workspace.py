# src/shared/infrastructure/context/limb_workspace.py

"""
LimbWorkspace - The "Sensation" organism for the Octopus.

Provides a virtual, read-only overlay of the filesystem. It allows limbs to
see a unified view of the code by merging "Future Truth" (uncommitted crate
files) with "Historical Truth" (the current repository on disk).
Constitutional Alignment:
Pillar I (Octopus): Distributed sensation at the execution surface.
Pillar II (UNIX): Does one thing well - provides a unified read interface.
Boundary: READ-ONLY. This component does not perform mutations.
"""

from __future__ import annotations

from pathlib import Path

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 1a2b3c4d-limb-workspace-sensation
# ID: 478c6629-e220-48f8-847a-c543396075b0
class LimbWorkspace:
    """
    A virtual filesystem handler that prioritizes in-flight changes.

    Used by analyzers and strategists to "taste" the result of a refactor
    before it is finalized in the database or the permanent codebase.
    """

    def __init__(
        self, repo_root: Path | str, crate_files: dict[str, str] | None = None
    ):
        """
        Initialize the workspace.

        Args:
            repo_root: The absolute path to the repository root.
            crate_files: A dictionary mapping repo-relative paths to their
                proposed content.
        """
        self.repo_root = Path(repo_root).resolve()
        self._crate = crate_files or {}

        logger.debug(
            "LimbWorkspace initialized with %d virtual files.", len(self._crate)
        )

    # ------------------------------------------------------------------
    # CORE SENSATION (The "Taste" of the Code)
    # ------------------------------------------------------------------

    # ID: 55a77b97-limb-read-text
    # ID: 67ff5ddc-be15-4e11-a44d-bb0c50fb4054
    def read_text(self, rel_path: str) -> str:
        """
        Read a file, prioritizing the virtual crate.

        If the limb has moved a file into the crate, this method returns the
        in-flight version.
        """
        normalized_path = str(rel_path).lstrip("./").replace("\\", "/")
        if normalized_path in self._crate:
            logger.debug("Sensation: Reading from crate: %s", normalized_path)
            return self._crate[normalized_path]

        abs_path = (self.repo_root / normalized_path).resolve()
        if abs_path.exists() and abs_path.is_file():
            logger.debug("Sensation: Reading from disk: %s", normalized_path)
            return abs_path.read_text(encoding="utf-8")

        raise FileNotFoundError(
            f"LimbWorkspace could not find sensation for: {rel_path}"
        )

    # ID: bc1c3a49-limb-exists
    # ID: 78b4aec9-f6fa-46ee-ae48-14c902acab43
    def exists(self, rel_path: str) -> bool:
        """Check if a file exists in the unified virtual/physical view."""
        normalized_path = str(rel_path).lstrip("./").replace("\\", "/")
        if normalized_path in self._crate:
            return True

        return (self.repo_root / normalized_path).exists()

    # ID: 3d1f1c34-limb-list-files
    # ID: 0304d488-a475-4412-a33a-2cdf965e49fe
    def list_files(self, directory: str = "src", pattern: str = "*.py") -> list[str]:
        """
        List files in a directory, merging virtual and physical realities.

        Ensures new files created in the crate are visible to the limb.
        """
        norm_dir = str(directory).lstrip("./").replace("\\", "/")
        found_files: set[str] = set()

        abs_dir = self.repo_root / norm_dir
        if abs_dir.exists() and abs_dir.is_dir():
            for path in abs_dir.rglob(pattern):
                found_files.add(
                    str(path.relative_to(self.repo_root)).replace("\\", "/")
                )

        for crate_path in self._crate.keys():
            if crate_path.startswith(norm_dir):
                if pattern == "*.py" and crate_path.endswith(".py"):
                    found_files.add(crate_path)
                elif pattern == "*" or Path(crate_path).match(pattern):
                    found_files.add(crate_path)

        return sorted(found_files)

    # ------------------------------------------------------------------
    # WORK-IN-PROGRESS UPDATES
    # ------------------------------------------------------------------

    # ID: 6b11bd31-limb-update-crate
    # ID: d697eadb-3d76-4ca0-88e0-468a8158675c
    def update_crate(self, new_files: dict[str, str]) -> None:
        """
        Update the virtual "Future Truth".

        Called by the reflex loop when a self-correction occurs.
        """
        for path, content in new_files.items():
            self._crate[str(path).lstrip("./")] = content
        logger.debug(
            "LimbWorkspace updated with %d new proposed files.", len(new_files)
        )

    # ID: 5a8ff2c6-12af-4c4a-8fb5-5da9b0c7a4d0
    def get_crate_content(self) -> dict[str, str]:
        """Return the current proposed state."""
        return self._crate.copy()
