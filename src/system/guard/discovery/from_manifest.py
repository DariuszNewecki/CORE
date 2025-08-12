# src/system/guard/discovery/from_manifest.py
"""
Intent: Provides a focused tool for discovering capabilities from manifest files.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional, List
from collections import deque
try:
    import yaml
except ImportError:
    yaml = None

from system.guard.models import CapabilityMeta

def _normalize_cap_list(items: Any) -> Dict[str, CapabilityMeta]:
    """Normalizes various list/dict shapes into a standard {cap: Meta} dictionary."""
    out: Dict[str, CapabilityMeta] = {}
    if isinstance(items, dict):
        for cap, meta in items.items():
            if isinstance(meta, dict):
                out[cap] = CapabilityMeta(capability=cap, domain=meta.get('domain'), owner=meta.get('owner'))
    elif isinstance(items, list):
        for it in items:
            if isinstance(it, str):
                out[it] = CapabilityMeta(it)
            elif isinstance(it, dict):
                cap = it.get('name') or it.get('capability')
                if cap:
                    out[cap] = CapabilityMeta(capability=cap, domain=it.get('domain'), owner=it.get('owner'))
    return out

def _find_manifest(start: Path) -> Path:
    """Locates the authoritative .intent manifest file."""
    for p in [start / '.intent/project_manifest.yaml', start / '.intent/manifest.yaml']:
        if p.exists():
            return p
    raise FileNotFoundError('No manifest found in .intent/')

def _normalize_manifest_caps(raw: dict) -> Dict[str, CapabilityMeta]:
    """Normalizes different manifest shapes into a {capability: Meta} map."""
    q = deque([raw])
    while q:
        node = q.popleft()
        for key in ('capabilities', 'required_capabilities'):
            if isinstance(node, dict) and key in node:
                return _normalize_cap_list(node[key])
        if isinstance(node, dict):
            q.extend(node.values())
        elif isinstance(node, list):
            q.extend(node)
    return {}

def load_manifest_capabilities(root: Path, explicit_path: Optional[Path]=None) -> Dict[str, CapabilityMeta]:
    """Loads, parses, and normalizes capabilities from the project's manifest."""
    if yaml is None:
        raise RuntimeError('PyYAML is required.')
    path = explicit_path or _find_manifest(root)
    with path.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return _normalize_manifest_caps(data)