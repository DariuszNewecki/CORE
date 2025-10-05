# src/cli/logic/knowledge_sync/utils.py
"""
Shared utilities for knowledge synchronization operations in the CORE Working Mind.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List

import yaml


# ID: 4b80a549-6189-4cbe-83e7-6200c9f2274b
def canonicalize(obj: Any) -> Any:
    """Recursively sorts dictionary keys to ensure a stable, consistent order for hashing.

    Args:
        obj: The object to canonicalize.

    Returns:
        Canonicalized object with sorted keys and stringified UUIDs.
    """
    if isinstance(obj, dict):
        return {k: canonicalize(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        if all(isinstance(i, dict) for i in obj):
            try:
                sort_key = next(
                    (k for k in ("id", "name", "key", "role") if k in obj[0]), None
                )
                if sort_key:
                    return sorted(obj, key=lambda x: str(x.get(sort_key, "")))
            except (TypeError, IndexError):
                pass
        return [canonicalize(x) for x in obj]
    if isinstance(obj, uuid.UUID):
        return str(obj)
    return obj


# ID: 96c822f2-6aeb-49e1-866f-53d8d97953c4
def compute_digest(items: List[Dict[str, Any]]) -> str:
    """Creates a unique fingerprint (SHA256) for a list of items.

    Args:
        items: List of dictionaries to hash.

    Returns:
        SHA256 digest prefixed with 'sha256:'.
    """
    canon = canonicalize(items)
    payload = json.dumps(
        canon, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


# ID: 8cf39820-7b79-4db4-90a5-0b5ddb837180
def write_yaml(path: Path, items: List[Dict[str, Any]], exported_at: str) -> str:
    """Writes a list of items to a YAML file, including version, timestamp, and digest.

    Args:
        path: Path to write the YAML file.
        items: List of items to write.
        exported_at: Timestamp of the export.

    Returns:
        The computed digest of the items.
    """
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


# ID: 6533b473-4017-48ee-94f7-9daa63e25f84
def read_yaml(path: Path) -> Dict[str, Any]:
    """Reads a YAML file and returns its content, handling missing files.

    Args:
        path: Path to the YAML file.

    Returns:
        Dictionary containing the YAML content, or empty dict if file doesn't exist.
    """
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Find the items key and convert UUIDs
    items_key = next(
        (k for k in ["items", "llm_resources", "cognitive_roles"] if k in data),
        None,
    )

    if items_key and isinstance(data.get(items_key), list):
        for item in data[items_key]:
            for key in ["id", "symbol_id", "capability_id"]:
                if key in item and isinstance(item[key], str):
                    try:
                        item[key] = uuid.UUID(item[key])
                    except (ValueError, TypeError):
                        pass

    return data


def _get_diff_links_key(item: Dict[str, Any]) -> str:
    """Creates a stable composite key for a link dictionary.

    Args:
        item: Link dictionary.

    Returns:
        Composite key as a string.
    """
    return f"{str(item.get('symbol_id', ''))}-{str(item.get('capability_id', ''))}-{item.get('source', '')}"


def _get_items_from_doc(doc: Dict[str, Any], doc_name: str) -> List[Dict[str, Any]]:
    """Extract items from a document using the appropriate key.

    Args:
        doc: YAML document.
        doc_name: Name of the document (e.g., 'capabilities').

    Returns:
        List of items from the document.
    """
    possible_keys = [doc_name, "items", "llm_resources", "cognitive_roles"]
    items_key = next((k for k in possible_keys if k in doc), None)
    return doc.get(items_key, []) if items_key else []
