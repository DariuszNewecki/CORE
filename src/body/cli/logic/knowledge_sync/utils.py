# src/body/cli/logic/knowledge_sync/utils.py
"""
Shared utilities for knowledge synchronization operations in the CORE Working Mind.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import yaml

from shared.config_loader import load_yaml_file


# ID: 0a055408-c1c4-54f2-b2d3-28bc47ace016
def canonicalize(obj: Any) -> Any:
    """Recursively sorts dictionary keys and handles UUIDs to ensure a stable, consistent order for hashing."""
    if isinstance(obj, dict):
        return {k: canonicalize(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [canonicalize(x) for x in obj]
    if isinstance(obj, uuid.UUID):
        return str(obj)
    return obj


# ID: 96c822f2-6aeb-49e1-866f-53d8d97953c4
def compute_digest(items: list[dict[str, Any]]) -> str:
    """Creates a unique fingerprint (SHA256) for a list of items."""
    canon = canonicalize(items)
    payload = json.dumps(
        canon, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


# ID: b91d073b-f19b-42ce-b6a9-afe7594a10a5
def write_yaml(path: Path, items: list[dict[str, Any]], exported_at: str) -> str:
    """Writes a list of items to a YAML file, including version, timestamp, and digest."""
    stringified_items = [
        {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in item.items()}
        for item in items
    ]

    digest = compute_digest(stringified_items)

    doc = {
        "version": 1,
        "exported_at": exported_at,
        "items": stringified_items,
        "digest": digest,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False, indent=2)
    return digest


# The local `read_yaml` function is now an alias for the canonical loader.
read_yaml = load_yaml_file


# ID: 75d790d9-b2f7-5757-b2f7-6d790d9b2f7d
def _get_diff_links_key(item: dict[str, Any]) -> str:
    """Creates a stable composite key for a link dictionary."""
    return f"{str(item.get('symbol_id', ''))}-{str(item.get('capability_id', ''))}-{item.get('source', '')}"


# ID: eab5bc15-09c8-56ca-9103-a160e16f0bce
def _get_items_from_doc(doc: dict[str, Any], doc_name: str) -> list[dict[str, Any]]:
    """Extract items from a document using the appropriate key."""
    possible_keys = [doc_name, "items", "llm_resources", "cognitive_roles"]
    items_key = next((k for k in possible_keys if k in doc), None)
    return doc.get(items_key, []) if items_key else []
