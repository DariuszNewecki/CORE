"""
Intent: Provide an intent-aligned capability drift detector that compares the .intent
manifest to capabilities discovered in code, producing a machine-readable report
for governance. This module avoids static imports from forbidden domains.

Strict mode behavior:
- Prefer live KnowledgeGraphBuilder (KGB) if available.
- If KGB yields nothing, also look for an on-disk knowledge graph artifact.
- Only if both are absent will strict mode fail.
"""
from __future__ import annotations
import importlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
try:
    import yaml
except Exception:
    yaml = None
_CAPABILITY_RE = re.compile('^\\s*#\\s*CAPABILITY:\\s*([A-Za-z0-9_.\\-:/]+)(.*)$')
_INLINE_KV_RE = re.compile('\\[\\s*([^\\]]+)\\s*\\]')
_KV_PAIR_RE = re.compile('([A-Za-z0-9_.\\-:/]+)\\s*=\\s*([^\\s,;]+)')

@dataclass(frozen=True)
class CapabilityMeta:
    """Intent: Minimal data container for capability metadata used in drift comparison."""
    capability: str
    domain: Optional[str] = None
    owner: Optional[str] = None

def _parse_inline_meta(trailing: str) -> Dict[str, str]:
    """Intent: Parse inline [key=value] metadata next to CAPABILITY tags."""
    m = _INLINE_KV_RE.search(trailing or '')
    if not m:
        return {}
    body = m.group(1)
    return {k: v for k, v in _KV_PAIR_RE.findall(body)}

def _try_import_kgb():
    """Intent: Attempt to access KnowledgeGraphBuilder without static cross-domain imports."""
    try:
        mod = importlib.import_module('system.tools.codegraph_builder')
        return getattr(mod, 'KnowledgeGraphBuilder', None)
    except Exception:
        return None

def _find_manifest(start: Path) -> Path:
    """Intent: Locate the authoritative .intent manifest file."""
    candidates = [start / '.intent' / 'project_manifest.yaml', start / '.intent' / 'manifest.yaml']
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError('No manifest found in .intent/ (looked for project_manifest.yaml, manifest.yaml)')

def _normalize_cap_list(items: Any) -> Dict[str, CapabilityMeta]:
    """Intent: Normalize many shapes (list[str], list[dict], dict[str,dict]) into {cap: CapabilityMeta}."""
    out: Dict[str, CapabilityMeta] = {}
    if isinstance(items, dict):
        for cap, meta in items.items():
            if not isinstance(cap, str):
                continue
            if isinstance(meta, dict):
                out[cap] = CapabilityMeta(capability=cap, domain=meta.get('domain'), owner=meta.get('owner'))
            else:
                out[cap] = CapabilityMeta(capability=cap)
        return out
    if isinstance(items, list):
        for it in items:
            if isinstance(it, str):
                out[it] = CapabilityMeta(it)
            elif isinstance(it, dict):
                cap = it.get('id') or it.get('key') or it.get('name') or it.get('capability')
                if cap:
                    out[cap] = CapabilityMeta(capability=cap, domain=it.get('domain'), owner=it.get('owner'))
    return out

def _normalize_manifest_caps(raw: dict) -> Dict[str, CapabilityMeta]:
    """
    Intent: Normalize different manifest shapes into a {capability: CapabilityMeta} map.
    Looks for keys commonly used in CORE manifests:
      - capabilities
      - required_capabilities
      - expected_capabilities
      - capability_map / capability_registry
      - components[*].capabilities
    """
    from collections import deque

    def extract_from_node(node: Any) -> Optional[Dict[str, CapabilityMeta]]:
        if not isinstance(node, dict):
            return None
        for key in ('capabilities', 'required_capabilities', 'expected_capabilities', 'capability_map', 'capability_registry'):
            if key in node:
                got = _normalize_cap_list(node[key])
                if got:
                    return got
        comps = node.get('components') or node.get('modules') or node.get('services')
        if isinstance(comps, list):
            merged: Dict[str, CapabilityMeta] = {}
            for c in comps:
                if isinstance(c, dict) and 'capabilities' in c:
                    merged.update(_normalize_cap_list(c['capabilities']))
            if merged:
                return merged
        return None
    q = deque([raw])
    while q:
        node = q.popleft()
        got = extract_from_node(node)
        if got:
            return got
        if isinstance(node, dict):
            q.extend(node.values())
        elif isinstance(node, list):
            q.extend(node)
    return {}

def load_manifest(root: Path, explicit_path: Optional[Path]=None) -> Dict[str, CapabilityMeta]:
    """Intent: Load and parse the .intent manifest with PyYAML."""
    if yaml is None:
        raise RuntimeError('PyYAML is required. Install with `pip install pyyaml`.')
    path = explicit_path if explicit_path else _find_manifest(root)
    with path.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return _normalize_manifest_caps(data)

def _extract_cap_meta_from_node(node: Dict[str, Any]) -> Optional[CapabilityMeta]:
    """Intent: Extract capability/domain/owner from a variety of KG node shapes."""
    cap = node.get('capability')
    domain = node.get('domain')
    owner = node.get('owner')
    if cap is None:
        attrs = node.get('attrs') or node.get('meta') or {}
        if isinstance(attrs, dict):
            cap = attrs.get('capability') or attrs.get('CAPABILITY') or cap
            domain = attrs.get('domain', domain)
            owner = attrs.get('owner', owner)
    if cap is None:
        tags = node.get('tags') or node.get('labels')
        if isinstance(tags, list):
            for t in tags:
                if isinstance(t, str):
                    m = re.match('^\\s*CAPABILITY:\\s*([A-Za-z0-9_.\\-:/]+)\\s*$', t)
                    if m:
                        cap = m.group(1)
                        break
    if cap:
        return CapabilityMeta(str(cap), str(domain) if domain else None, str(owner) if owner else None)
    return None

def _load_json_file(path: Path) -> Optional[Any]:
    """Loads and parses a JSON file from the given path, returning its contents on success or None on failure."""
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None

def _load_ndjson_file(path: Path) -> List[Any]:
    """Loads and parses each non-empty line of an NDJSON file into a list of objects, skipping invalid lines and returning an empty list on file read errors."""
    items: List[Any] = []
    try:
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return []
    return items

def _collect_from_kgb_artifact(root: Path) -> Dict[str, CapabilityMeta]:
    """
    Intent: Read a previously emitted knowledge graph artifact from disk.
    Accepts common file names and shapes, returning a capability map.
    """
    candidates = [root / 'reports' / 'knowledge_graph.json', root / 'reports' / 'codegraph.json', root / 'reports' / 'knowledge_graph.ndjson', root / 'artifacts' / 'knowledge_graph.json', root / '.intent' / 'knowledge_graph.json']
    caps: Dict[str, CapabilityMeta] = {}
    for p in candidates:
        if not p.exists():
            continue
        data: Any
        if p.suffix == '.ndjson':
            data = _load_ndjson_file(p)
        else:
            data = _load_json_file(p)
        if data is None:
            continue
        nodes_iter: Iterable[Any] = []
        if isinstance(data, dict) and 'nodes' in data:
            nodes = data.get('nodes')
            if isinstance(nodes, dict):
                nodes_iter = nodes.values()
            elif isinstance(nodes, list):
                nodes_iter = nodes
        elif isinstance(data, list):
            nodes_iter = data
        else:
            continue
        for n in nodes_iter:
            if not isinstance(n, dict):
                continue
            meta = _extract_cap_meta_from_node(n)
            if meta:
                caps[meta.capability] = meta
        if caps:
            break
    return caps

def _iter_source_files(root: Path, include_globs: List[str], exclude_globs: List[str]) -> Iterable[Path]:
    """Intent: Yield repository files considered for direct CAPABILITY tag scanning."""
    all_files = list(root.rglob('*'))

    def wanted(p: Path) -> bool:
        """Intent: Filter for include/exclude globs and typical source suffixes."""
        if any((p.match(g) for g in exclude_globs)):
            return False
        if include_globs:
            return any((p.match(g) for g in include_globs))
        return p.suffix in {'.py', '.ts', '.tsx', '.js'}
    for p in all_files:
        if p.is_file() and wanted(p):
            yield p

def _collect_from_grep(root: Path, include_globs: List[str], exclude_globs: List[str]) -> Dict[str, CapabilityMeta]:
    """Intent: Fallback discovery by scanning for '# CAPABILITY:' tags with optional inline metadata."""
    caps: Dict[str, CapabilityMeta] = {}
    for file in _iter_source_files(root, include_globs, exclude_globs):
        try:
            for line in file.read_text(encoding='utf-8', errors='ignore').splitlines():
                m = _CAPABILITY_RE.match(line)
                if not m:
                    continue
                cap = m.group(1).strip()
                kv = {}
                trailing = m.group(2) or ''
                if trailing:
                    kv = _parse_inline_meta(trailing)
                caps[cap] = CapabilityMeta(capability=cap, domain=kv.get('domain'), owner=kv.get('owner'))
        except Exception:
            continue
    return caps

def _collect_from_kgb(root: Path) -> Dict[str, CapabilityMeta]:
    """Intent: Use KnowledgeGraphBuilder (if present) to discover capabilities from the repo."""
    KGB = _try_import_kgb()
    if not KGB:
        return {}
    try:
        builder = KGB(root=str(root))
        graph = builder.build()
        caps: Dict[str, CapabilityMeta] = {}
        if hasattr(graph, 'nodes'):
            try:
                for node in getattr(graph, 'nodes'):
                    attrs = {}
                    try:
                        attrs = graph.nodes[node]
                    except Exception:
                        pass
                    meta = _extract_cap_meta_from_node(attrs if isinstance(attrs, dict) else {})
                    if meta:
                        caps[meta.capability] = meta
                return caps
            except Exception:
                pass
        if isinstance(graph, dict):
            nodes = graph.get('nodes')
            if isinstance(nodes, dict):
                iterable = nodes.values()
            elif isinstance(nodes, list):
                iterable = nodes
            else:
                iterable = []
            for n in iterable:
                if isinstance(n, dict):
                    meta = _extract_cap_meta_from_node(n)
                    if meta:
                        caps[meta.capability] = meta
            return caps
        if isinstance(graph, list):
            for n in graph:
                if isinstance(n, dict):
                    meta = _extract_cap_meta_from_node(n)
                    if meta:
                        caps[meta.capability] = meta
            return caps
        return caps
    except Exception:
        return {}

def collect_code_capabilities(root: Path, include_globs: Optional[List[str]]=None, exclude_globs: Optional[List[str]]=None, require_kgb: bool=False) -> Dict[str, CapabilityMeta]:
    """Intent: Unified discovery entrypoint respecting strict-intent when required."""
    include_globs = include_globs or []
    exclude_globs = exclude_globs or ['**/.git/**', '**/.venv/**', '**/__pycache__/**', '**/.pytest_cache/**', '**/.ruff_cache/**', 'logs/**', 'sandbox/**', 'pending_writes/**']
    caps = _collect_from_kgb(root)
    if caps:
        return caps
    artifact_caps = _collect_from_kgb_artifact(root)
    if artifact_caps:
        return artifact_caps
    if require_kgb:
        raise RuntimeError('Strict intent mode: No capabilities found from KnowledgeGraphBuilder or artifacts. Run `core-admin guard kg-export` first (or rerun without --strict-intent).')
    return _collect_from_grep(root, include_globs, exclude_globs)

@dataclass
class DriftReport:
    """Intent: Structured result for capability drift suitable for JSON emission and CI gating."""
    missing_in_code: List[str]
    undeclared_in_manifest: List[str]
    mismatched_mappings: List[Dict[str, Dict[str, Optional[str]]]]

    def to_dict(self) -> dict:
        """Intent: Convert the drift report into a stable JSON-serializable dict."""
        return {'missing_in_code': sorted(self.missing_in_code), 'undeclared_in_manifest': sorted(self.undeclared_in_manifest), 'mismatched_mappings': self.mismatched_mappings}

def detect_capability_drift(manifest_caps: Dict[str, CapabilityMeta], code_caps: Dict[str, CapabilityMeta]) -> DriftReport:
    """Intent: Compute missing/undeclared/mismatched capability sets between manifest and code."""
    m_keys = set(manifest_caps.keys())
    c_keys = set(code_caps.keys())
    missing = sorted(m_keys - c_keys)
    undeclared = sorted(c_keys - m_keys)
    mismatches: List[Dict[str, Dict[str, Optional[str]]]] = []
    for k in sorted(m_keys & c_keys):
        m = manifest_caps[k]
        c = code_caps[k]
        if (m.domain or c.domain) and m.domain != c.domain or ((m.owner or c.owner) and m.owner != c.owner):
            mismatches.append({'capability': k, 'manifest': {'domain': m.domain, 'owner': m.owner}, 'code': {'domain': c.domain, 'owner': c.owner}})
    return DriftReport(missing, undeclared, mismatches)

def write_report(report_path: Path, report: DriftReport) -> None:
    """Intent: Persist the drift report to disk under reports/ for evidence and CI."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding='utf-8')