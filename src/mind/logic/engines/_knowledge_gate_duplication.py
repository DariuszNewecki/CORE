# src/mind/logic/engines/_knowledge_gate_duplication.py

"""
Duplication-detection helpers for KnowledgeGateEngine.

Extracted from knowledge_gate.py to keep KnowledgeGateEngine under the
modularity.class_too_large threshold. The three functions here form the
"duplication" cluster — AST-fingerprint and semantic-vector matching plus
the shared finding factory — and are called by the engine's verify_context
dispatcher. The remaining checks in the engine (capability_assignment,
table_has_records, orphan_file_check) form a different, graph-and-DB-shaped
cluster and stay on the engine. (duplicate_ids moved to ast_gate as a
stateless corpus check per #820 Group C.)
"""

from __future__ import annotations

import fnmatch
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext


def _resolve_symbol_path(sym: dict[str, Any]) -> str | None:
    """Return the symbol's file_path, falling back to a path synthesized
    from its `module` dotted name when file_path is missing or None.

    Knowledge-graph symbols frequently lack file_path but always carry a
    module name. Filtering by path therefore requires this synthesis —
    without it, exclude patterns silently no-op against None/empty values
    (issue #150). Centralized here so capability-assignment, ast-duplication,
    and the duplication-finding factory share one source of truth.

    Returns None when neither file_path nor module is available.
    """
    fp = sym.get("file_path")
    if fp:
        return fp
    module = sym.get("module") or ""
    if not module:
        return None
    return "src/" + module.replace(".", "/") + ".py"


def _check_ast_duplication(
    context: AuditorContext, params: dict[str, Any]
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    if not context.symbols_map:
        return findings

    # Honor scope.excludes from the rule mapping. rule_executor injects
    # rule.exclusions under "_scope_excludes" so excluded symbols are
    # filtered at intake — they cannot be flagged nor pull a non-excluded
    # peer into a finding pair.
    exclude_patterns: list[str] = params.get("_scope_excludes", []) or []

    def _is_excluded(sym: dict) -> bool:
        if not exclude_patterns:
            return False
        fp = _resolve_symbol_path(sym)
        if not fp:
            return False
        return any(fnmatch.fnmatch(fp, pat) for pat in exclude_patterns)

    fingerprint_groups = defaultdict(list)
    for symbol_data in context.symbols_map.values():
        if "test" in symbol_data.get("module", ""):
            continue
        if _is_excluded(symbol_data):
            continue
        fp = symbol_data.get("fingerprint")
        if fp:
            fingerprint_groups[fp].append(symbol_data)
    for symbols in fingerprint_groups.values():
        if len(symbols) > 1:
            for i, data_a in enumerate(symbols):
                for data_b in symbols[i + 1 :]:
                    findings.append(
                        _create_duplication_finding(data_a, data_b, 1.0, "ast")
                    )
    return findings


# ID: 0eae3c74-53d3-43fc-a5b2-6778a496c9be
def _sym_from_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal symbol-dict from a Qdrant chunk payload for the finding factory."""
    fp = chunk.get("file_path", "")
    section = chunk.get("section") or "?"
    module = fp.removesuffix(".py").replace("/", ".") if fp else ""
    return {
        "qualname": section,
        "name": section,
        "module": module,
        "file_path": fp,
    }


# ID: d278ba16-66a2-44f8-8066-554f40a4eb31
async def _check_semantic_duplication(
    context: AuditorContext, params: dict[str, Any]
) -> list[AuditFinding]:
    """Find semantically similar (but syntactically distinct) function/class chunks
    across different source files using pre-stored Qdrant vectors.

    Makes no AI calls — all embeddings come from the 'core-code' Qdrant collection
    written by RepoEmbedderWorker. Similarity is computed via numpy matrix multiply
    (one BLAS call), not per-pair Qdrant queries.
    """
    findings: list[AuditFinding] = []
    qdrant = getattr(context, "qdrant_service", None)
    if not context.symbols_map or not qdrant:
        return findings

    threshold: float = float(params.get("threshold", 0.85))
    exclude_patterns: list[str] = params.get("_scope_excludes", []) or []
    _MAX_FINDINGS = 50
    _MAX_CHUNKS = 2000  # guard against very large repos

    def _chunk_excluded(fp: str) -> bool:
        if not fp:
            return True
        if "test" in fp:
            return True
        return any(fnmatch.fnmatch(fp, pat) for pat in exclude_patterns)

    # Guard: verify collection is available before scrolling
    try:
        available = await qdrant.list_collections()
    except Exception:
        return findings
    collection = qdrant.collection_name
    if collection not in available:
        return findings

    # Single scroll — one Qdrant round-trip with vectors and payloads
    try:
        all_points = await qdrant.scroll_all_points(
            with_payload=True, with_vectors=True, collection_name=collection
        )
    except Exception:
        return findings

    if not all_points:
        return findings

    # Extract function/class chunks from non-test Python source files
    chunks: list[dict[str, Any]] = []
    for point in all_points:
        payload = point.payload or {}
        if payload.get("artifact_type") != "python":
            continue
        if payload.get("chunk_type") not in ("function", "class"):
            continue
        fp = payload.get("file_path", "")
        if _chunk_excluded(fp):
            continue
        vec = getattr(point, "vector", None)
        if not vec or not isinstance(vec, (list, tuple)):
            continue
        chunks.append(
            {"file_path": fp, "section": payload.get("section", ""), "vector": vec}
        )
        if len(chunks) >= _MAX_CHUNKS:
            break

    if len(chunks) < 2:
        return findings

    # Pairwise cosine similarity via numpy (single BLAS matrix multiply)
    import numpy as np  # lazy import; numpy is a declared project dependency

    mat = np.array([c["vector"] for c in chunks], dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    unit = mat / norms
    sim = (unit @ unit.T).astype(float)  # (n, n) symmetric similarity matrix

    n = len(chunks)
    for i in range(n):
        if len(findings) >= _MAX_FINDINGS:
            break
        for j in range(i + 1, n):
            if sim[i, j] < threshold:
                continue
            if chunks[i]["file_path"] == chunks[j]["file_path"]:
                continue
            findings.append(
                _create_duplication_finding(
                    _sym_from_chunk(chunks[i]),
                    _sym_from_chunk(chunks[j]),
                    float(sim[i, j]),
                    "semantic",
                )
            )
            if len(findings) >= _MAX_FINDINGS:
                break

    return findings


def _create_duplication_finding(a, b, score, dtype) -> AuditFinding:
    name_a = a.get("qualname") or a.get("name") or "?"
    name_b = b.get("qualname") or b.get("name") or "?"
    module_a = a.get("module", "")
    file_path = _resolve_symbol_path(a)
    # Per ADR-098 D4 / #606: parent rules purity.no_ast_duplication and
    # purity.no_semantic_duplication are reporting, which rule_executor
    # maps to INFO at dispatch.
    return AuditFinding(
        check_id=f"purity.no_{dtype}_duplication",
        severity=AuditSeverity.INFO,
        message=f"{dtype.upper()} duplication: '{name_a}' duplicates '{name_b}' (score={score:.2f})",
        file_path=file_path,
        context={
            "symbol_a": name_a,
            "symbol_b": name_b,
            "module_a": module_a,
            "module_b": b.get("module", ""),
            "similarity": score,
            "type": dtype,
        },
    )
