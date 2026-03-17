# src/shared/infrastructure/context/serializers.py

"""
ContextSerializer - YAML I/O and token estimation.

Policy:
- No direct filesystem mutations outside governed surfaces.
- Writes must go through FileHandler so IntentGuard is enforced.
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


# ID: 99a31e5a-ce83-437b-a03c-e21343ceeb3c
class ContextSerializer:
    """Serializes and deserializes ContextPacket."""

    @staticmethod
    # ID: 2ff86f07-0d18-4a4a-8778-ce742223f322
    def to_yaml(packet: dict[str, Any], output_path: str) -> None:
        yaml_text = yaml.safe_dump(packet, default_flow_style=False, sort_keys=False)

        fh = FileHandler(str(settings.REPO_PATH))
        rel = _to_repo_relative_path(output_path)

        result = fh.write_runtime_text(rel, yaml_text)
        try:
            status = getattr(result, "status", "unknown")
            logger.debug("Wrote context packet to %s (status=%s)", rel, status)
        except Exception:
            logger.debug("Wrote context packet to %s", rel)

    @staticmethod
    # ID: 9db70cab-e665-4635-858a-70fb80310b51
    def from_yaml(input_path: str) -> dict[str, Any]:
        packet = yaml.safe_load(Path(input_path).read_text(encoding="utf-8"))
        logger.debug("Loaded context packet from %s", input_path)
        return packet or {}

    @staticmethod
    # ID: f2d10834-5a64-4252-bd12-ec87c8e3f2c0
    def estimate_tokens(text: str) -> int:
        return len(text) // 4

    @staticmethod
    # ID: 4c1edebf-e182-4a7e-a0f7-a7469e431e9b
    def compute_packet_hash(packet: dict[str, Any]) -> str:
        canonical = {
            "header": packet.get("header", {}),
            "phase": packet.get("phase"),
            "constitution": packet.get("constitution", {}),
            "policy": packet.get("policy", {}),
            "constraints": packet.get("constraints", {}),
            "evidence": packet.get("evidence", []),
            "runtime": packet.get("runtime", {}),
        }
        canonical_json = json.dumps(canonical, sort_keys=True, default=str)
        digest = hashlib.sha256(canonical_json.encode()).hexdigest()
        logger.debug("Computed context packet hash: %s...", digest[:8])
        return digest

    @staticmethod
    # ID: fa12d7ab-310e-4b92-8e7a-95d6084e3536
    def compute_cache_key(request_payload: dict[str, Any]) -> str:
        cache_fields = {
            "goal": request_payload.get("goal"),
            "trigger": request_payload.get("trigger"),
            "phase": request_payload.get("phase"),
            "workflow_id": request_payload.get("workflow_id"),
            "stage_id": request_payload.get("stage_id"),
            "target_files": request_payload.get("target_files"),
            "target_symbols": request_payload.get("target_symbols"),
            "target_paths": request_payload.get("target_paths"),
            "include_constitution": request_payload.get("include_constitution"),
            "include_policy": request_payload.get("include_policy"),
            "include_symbols": request_payload.get("include_symbols"),
            "include_vectors": request_payload.get("include_vectors"),
            "include_runtime": request_payload.get("include_runtime"),
        }

        cache_json = json.dumps(cache_fields, sort_keys=True, default=str)
        cache_key = hashlib.sha256(cache_json.encode()).hexdigest()
        logger.debug("Computed cache key: %s...", cache_key[:8])
        return cache_key

    @staticmethod
    # ID: 11dac58e-a863-4210-96f9-cbbb4bc0745b
    def estimate_packet_tokens(packet: dict[str, Any]) -> int:
        total = 0

        for item in packet.get("evidence", []):
            try:
                total += int(item.get("tokens_est", 0))
            except Exception:
                total += 0

        for section_name in ("constitution", "policy", "constraints", "runtime"):
            section = packet.get(section_name, {})
            if section:
                try:
                    total += ContextSerializer.estimate_tokens(
                        json.dumps(section, sort_keys=True, default=str)
                    )
                except Exception:
                    total += 0

        phase = packet.get("phase")
        if phase:
            total += ContextSerializer.estimate_tokens(str(phase))

        total += 300
        return total


def _to_repo_relative_path(path_str: str) -> str:
    p = Path(path_str)

    if not p.is_absolute():
        return p.as_posix().lstrip("./")

    repo_root = Path(settings.REPO_PATH).resolve()
    resolved = p.resolve()

    if resolved.is_relative_to(repo_root):
        return resolved.relative_to(repo_root).as_posix()

    raise ValueError(f"Path is outside repository boundary: {path_str}")
