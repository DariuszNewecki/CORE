# src/features/introspection/discovery/from_manifest.py

"""
Discovers capability definitions by parsing constitutional manifest files.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from shared.logger import getLogger
from shared.models import CapabilityMeta

logger = getLogger(__name__)


# ID: 314b8fb0-ec96-43ab-94a4-5f50cbe3fcce
def load_manifest_capabilities(
    root: Path, explicit_path: Path | None = None
) -> dict[str, CapabilityMeta]:
    """
    Scans for manifest files and aggregates all declared capabilities.
    The primary source of truth is now .intent/mind/project_manifest.yaml.
    """
    capabilities: dict[str, CapabilityMeta] = {}
    manifest_path = root / ".intent" / "mind" / "project_manifest.yaml"
    if manifest_path.exists():
        try:
            content = yaml.safe_load(manifest_path.read_text("utf-8")) or {}
            caps = content.get("capabilities", [])
            if isinstance(caps, list):
                for key in caps:
                    if isinstance(key, str):
                        capabilities[key] = CapabilityMeta(key=key)
        except (OSError, yaml.YAMLError) as e:
            logger.warning(f"Could not parse manifest at {manifest_path}: {e}")
    return capabilities
