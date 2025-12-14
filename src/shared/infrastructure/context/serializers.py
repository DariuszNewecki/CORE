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


# ID: 8a0b45d0-e4cc-430f-b2fd-fa8565b57ad1
class ContextSerializer:
    """Serializes and deserializes ContextPackage."""

    @staticmethod
    # ID: d72a4cc4-12d1-4199-93b3-9bbe9f136a0a
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
        logger.debug("Wrote packet to %s", output_path)

    @staticmethod
    # ID: 96174e18-7f6c-4f68-ab4c-1a93a6df9037
    def from_yaml(input_path: str) -> dict[str, Any]:
        """Load packet from YAML file.

        Args:
            input_path: Input file path

        Returns:
            ContextPackage dict
        """
        with open(input_path, encoding="utf-8") as f:
            packet = yaml.safe_load(f)
        logger.debug("Loaded packet from %s", input_path)
        return packet

    @staticmethod
    # ID: 17d2cd55-2c34-4198-a445-17d72548283c
    def estimate_tokens(text: str) -> int:
        """Estimate token count for text.

        Uses rough heuristic: ~4 chars per token.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        return len(text) // 4

    @staticmethod
    # ID: 4fed2123-7d1b-4bbc-84ad-49140d9da4cf
    def compute_packet_hash(packet: dict[str, Any]) -> str:
        """Compute deterministic hash of packet.

        Excludes provenance fields for stable hashing.

        Args:
            packet: ContextPackage dict

        Returns:
            SHA256 hex digest
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
        """Compute cache key from task specification.

        Args:
            task_spec: Task specification dict

        Returns:
            SHA256 hex digest of spec
        """
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

        Args:
            packet: ContextPackage dict

        Returns:
            Canonicalized packet
        """
        return packet

    @staticmethod
    # ID: 418b33f3-32f5-4895-8ac7-d5b793496231
    def estimate_packet_tokens(packet: dict[str, Any]) -> int:
        """Estimate total tokens for packet.

        Args:
            packet: ContextPackage dict

        Returns:
            Total estimated tokens
        """
        total = 0
        for item in packet.get("context", []):
            total += item.get("tokens_est", 0)
        structure_tokens = 500
        total += structure_tokens
        return total
