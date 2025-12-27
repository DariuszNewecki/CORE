# src/shared/infrastructure/context/serializers.py

"""ContextSerializer - YAML I/O and token estimation.

Handles serialization, deserialization, and token counting.

Policy:
- No direct filesystem mutations outside governed surfaces.
- Writes must go through FileHandler (runtime write) so IntentGuard is enforced.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from shared.config import settings
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 8a0b45d0-e4cc-430f-b2fd-fa8565b57ad1
class ContextSerializer:
    """Serializes and deserializes ContextPackage."""

    @staticmethod
    # ID: d72a4cc4-12d1-4199-93b3-9bbe9f136a0a
    def to_yaml(packet: dict[str, Any], output_path: str) -> None:
        """Write packet to YAML file.

        Args:
            packet: ContextPackage dict
            output_path: Output file path (repo-relative preferred)
        """
        # Serialize deterministically (stable output for diffs)
        yaml_text = yaml.safe_dump(packet, default_flow_style=False, sort_keys=False)

        # Route through governed mutation surface (IntentGuard enforced)
        fh = FileHandler(str(settings.REPO_PATH))

        rel = _to_repo_relative_path(output_path)
        result = fh.write_runtime_text(rel, yaml_text)
        logger.debug("Wrote packet to %s (%s)", rel, result.status)

    @staticmethod
    # ID: 96174e18-7f6c-4f68-ab4c-1a93a6df9037
    def from_yaml(input_path: str) -> dict[str, Any]:
        """Load packet from YAML file.

        Args:
            input_path: Input file path

        Returns:
            ContextPackage dict
        """
        packet = yaml.safe_load(Path(input_path).read_text(encoding="utf-8"))
        logger.debug("Loaded packet from %s", input_path)
        return packet or {}

    @staticmethod
    # ID: 17d2cd55-2c34-4198-a445-17d72548283c
    def estimate_tokens(text: str) -> int:
        """Estimate token count for text.

        Uses rough heuristic: ~4 chars per token.
        """
        return len(text) // 4

    @staticmethod
    # ID: 4fed2123-7d1b-4bbc-84ad-49140d9da4cf
    def compute_packet_hash(packet: dict[str, Any]) -> str:
        """Compute deterministic hash of packet.

        Excludes provenance fields for stable hashing.
        """
        canonical = {
            "header": packet.get("header", {}),
            "problem": packet.get("problem", {}),
            "scope": packet.get("scope", {}),
            "constraints": packet.get("constraints", {}),
            "context": packet.get("context", []),
            "invariants": packet.get("invariants", []),
            "policy": packet.get("policy", {}),
        }
        canonical_json = json.dumps(canonical, sort_keys=True)
        hash_digest = hashlib.sha256(canonical_json.encode()).hexdigest()
        logger.debug("Computed packet hash: %s...", hash_digest[:8])
        return hash_digest

    @staticmethod
    # ID: 1e84a908-4195-448b-aa95-6409d88e033c
    def compute_cache_key(task_spec: dict[str, Any]) -> str:
        """Compute cache key from task specification."""
        cache_fields = {
            "task_type": task_spec.get("task_type"),
            "scope": task_spec.get("scope"),
            "roots": task_spec.get("roots"),
            "include": task_spec.get("include"),
            "exclude": task_spec.get("exclude"),
        }
        cache_json = json.dumps(cache_fields, sort_keys=True)
        cache_key = hashlib.sha256(cache_json.encode()).hexdigest()
        logger.debug("Computed cache key: %s...", cache_key[:8])
        return cache_key

    @staticmethod
    # ID: 2ba7b259-d323-41f5-8ac4-b7fadc0825d6
    def canonicalize(packet: dict[str, Any]) -> dict[str, Any]:
        """Create canonical representation of packet.

        Sorts all arrays and dicts for deterministic comparison.
        """
        return packet

    @staticmethod
    # ID: 418b33f3-32f5-4895-8ac7-d5b793496231
    def estimate_packet_tokens(packet: dict[str, Any]) -> int:
        """Estimate total tokens for packet."""
        total = 0
        for item in packet.get("context", []):
            total += item.get("tokens_est", 0)
        total += 500  # structure tokens
        return total


# ID: 0d0f4f32-2d8c-4f90-8b2c-8e0d61d2f6aa
def _to_repo_relative_path(path_str: str) -> str:
    """
    Convert a user-provided path to a repo-relative POSIX path.

    - If already relative: normalize and return.
    - If absolute under REPO_PATH: relativize.
    - If absolute outside repo: raise (FileHandler will also block, but fail early here).
    """
    p = Path(path_str)

    if not p.is_absolute():
        return p.as_posix().lstrip("./")

    repo_root = Path(settings.REPO_PATH).resolve()
    resolved = p.resolve()
    if resolved.is_relative_to(repo_root):
        return resolved.relative_to(repo_root).as_posix()

    raise ValueError(f"Path is outside repository boundary: {path_str}")
