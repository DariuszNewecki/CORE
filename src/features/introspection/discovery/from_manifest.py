# src/features/introspection/discovery/from_manifest.py
"""
Discovers capability definitions by parsing constitutional manifest files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import yaml
from shared.logger import getLogger
from shared.models import CapabilityMeta

log = getLogger("discovery.from_manifest")


# ID: 67f5324b-5dbd-4250-a216-bbd557d3c8e9
def load_manifest_capabilities(
    root: Path, explicit_path: Path | None = None
) -> Dict[str, CapabilityMeta]:
    """
    Scans for manifest files and aggregates all declared capabilities.
    The primary source of truth is now .intent/mind/project_manifest.yaml.
    """
    capabilities: Dict[str, CapabilityMeta] = {}

    manifest_path = root / ".intent" / "mind" / "project_manifest.yaml"

    if manifest_path.exists():
        try:
            content = yaml.safe_load(manifest_path.read_text("utf-8")) or {}
            caps = content.get("capabilities", [])

            if isinstance(caps, list):
                for key in caps:
                    if isinstance(key, str):
                        # --- THIS IS THE FIX ---
                        # Instead of storing None, we store an actual instance
                        # of the CapabilityMeta dataclass, as the consumer expects.
                        capabilities[key] = CapabilityMeta(key=key)
                        # --- END OF FIX ---

        except (yaml.YAMLError, IOError) as e:
            log.warning(f"Could not parse manifest at {manifest_path}: {e}")

    return capabilities
