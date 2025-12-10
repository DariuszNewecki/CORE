# src/shared/infrastructure/context/serializers.py

"""ContextSerializer - YAML I/O and token estimation.

Handles serialization, deserialization, and token counting.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import yaml


logger = logging.getLogger(__name__)


# ID: 59618c33-f542-45ff-89b1-f5882034307f
class ContextSerializer:
    """Serializes and deserializes ContextPackage."""

    @staticmethod
    # ID: 7602d3f0-b811-49eb-8034-3612d24fe610
    def to_yaml(packet: dict[str, Any], output_path: str) -> None:
        """Write packet to YAML file.

        Args:
            packet: ContextPackage dict
            output_path: Output file path
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, "w", encoding="utf-8") as f:
            yaml.safe_dump(packet, f, default_flow_style=False, sort_keys=False)

        # Downgraded to DEBUG
        logger.debug("Wrote packet to %s", output_path)

    @staticmethod
    # ID: dbc3018c-e19a-4928-adba-f2ab712a77f5
    def from_yaml(input_path: str) -> dict[str, Any]:
        """Load packet from YAML file.

        Args:
            input_path: Input file path

        Returns:
            ContextPackage dict
        """
        with open(input_path, encoding="utf-8") as f:
            packet = yaml.safe_load(f)

        # Downgraded to DEBUG
        logger.debug("Loaded packet from %s", input_path)
        return packet

    @staticmethod
    # ID: 782f935e-e825-4049-9d7d-0f8ae7b62220
    def estimate_tokens(text: str) -> int:
        """Estimate token count for text.

        Uses rough heuristic: ~4 chars per token.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        # TODO: Use tiktoken for accurate estimation
        return len(text) // 4

    @staticmethod
    # ID: f2603924-a77a-4cf2-8823-d662a09e6e5f
    def compute_packet_hash(packet: dict[str, Any]) -> str:
        """Compute deterministic hash of packet.

        Excludes provenance fields for stable hashing.

        Args:
            packet: ContextPackage dict

        Returns:
            SHA256 hex digest
        """
        # Create canonical version without provenance
        canonical = {
            "header": packet.get("header", {}),
            "problem": packet.get("problem", {}),
            "scope": packet.get("scope", {}),
            "constraints": packet.get("constraints", {}),
            "context": packet.get("context", []),
            "invariants": packet.get("invariants", []),
            "policy": packet.get("policy", {}),
        }

        # Sort keys for determinism
        canonical_json = json.dumps(canonical, sort_keys=True)
        hash_digest = hashlib.sha256(canonical_json.encode()).hexdigest()

        logger.debug(f"Computed packet hash: {hash_digest[:8]}...")
        return hash_digest

    @staticmethod
    # ID: 973fc8d0-a34d-46c7-bddc-de32ffc7c4fa
    def compute_cache_key(task_spec: dict[str, Any]) -> str:
        """Compute cache key from task specification.

        Args:
            task_spec: Task specification dict

        Returns:
            SHA256 hex digest of spec
        """
        # Include relevant fields for cache lookup
        cache_fields = {
            "task_type": task_spec.get("task_type"),
            "scope": task_spec.get("scope"),
            "roots": task_spec.get("roots"),
            "include": task_spec.get("include"),
            "exclude": task_spec.get("exclude"),
        }

        cache_json = json.dumps(cache_fields, sort_keys=True)
        cache_key = hashlib.sha256(cache_json.encode()).hexdigest()

        logger.debug(f"Computed cache key: {cache_key[:8]}...")
        return cache_key

    @staticmethod
    # ID: 564a8b8e-cf01-44d7-b150-fbb243192c89
    def canonicalize(packet: dict[str, Any]) -> dict[str, Any]:
        """Create canonical representation of packet.

        Sorts all arrays and dicts for deterministic comparison.

        Args:
            packet: ContextPackage dict

        Returns:
            Canonicalized packet
        """
        # TODO: Implement deep sorting for arrays/dicts
        return packet

    @staticmethod
    # ID: 3e108113-ac18-43b9-8ed0-1d533131d4e6
    def estimate_packet_tokens(packet: dict[str, Any]) -> int:
        """Estimate total tokens for packet.

        Args:
            packet: ContextPackage dict

        Returns:
            Total estimated tokens
        """
        total = 0

        # Sum context item estimates
        for item in packet.get("context", []):
            total += item.get("tokens_est", 0)

        # Add overhead for structure
        structure_tokens = 500  # Rough estimate for headers, metadata
        total += structure_tokens

        return total
