# src/will/governance/inspect_runner.py

"""
Inspect runner facade — Will-layer entry point for the /inspect family
of read-only APIs (ADR-057 D3, D5).

Every endpoint in this module is a read-only projection of existing data
(repositories, blackboard, decision traces, DB connection state, component
registries, semantic capability index). No resource table. No background
tasks.

Surface groups:
* `/status/*`      — DB and drift status
* `/decisions`     — DecisionTraceRepository projection
* `/refusals`      — RefusalRepository projection
* `/analysis/*`    — semantic clusters / duplicates / DRY candidates / command-tree / test targets
* `/components`    — V2 component inventory across Mind/Body/Will (ADR-057 D5)
* `/search/*`      — semantic capability search via Will cognitive service (ADR-057 D5)

For Phase 3 every helper here returns a JSON-safe dict suitable for
direct response serialisation by the route handler.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from body.infrastructure.repositories.decision_trace_repository import (
    DecisionTraceRepository,
)
from body.infrastructure.repositories.refusal_repository import RefusalRepository
from shared.context import CoreContext
from shared.logger import getLogger


__all__ = [
    "get_analysis_bridges",
    "get_analysis_clusters",
    "get_analysis_command_tree",
    "get_analysis_common_knowledge",
    "get_analysis_duplicates",
    "get_analysis_test_targets",
    "get_components_list",
    "get_db_status",
    "get_decisions",
    "get_decisions_patterns",
    "get_drift_status",
    "get_refusals",
    "get_refusals_stats",
    "get_search_capabilities",
    "get_search_commands",
]


COMPONENT_PACKAGES: dict[str, str] = {
    "Interpreters": "will.interpreters",
    "Analyzers": "body.analyzers",
    "Strategists": "will.strategists",
    "Evaluators": "body.evaluators",
    "Deciders": "will.deciders",
}


logger = getLogger(__name__)


# ---------- /status -------------------------------------------------------


# ID: 1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d
async def get_db_status(session: Any) -> dict:
    """Probe DB connectivity and migration head.

    Returns connection status and the current schema version (read from
    a probe SELECT). Failures are swallowed and surfaced via `ok=False`
    plus an `error` field so the route still returns a 200.
    """
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        return {
            "ok": False,
            "connected": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    try:
        result = await session.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'core'"
            )
        )
        table_count = int(result.scalar_one())
    except Exception as exc:
        return {
            "ok": True,
            "connected": True,
            "core_schema_tables": None,
            "warning": f"{type(exc).__name__}: {exc}",
        }

    return {
        "ok": True,
        "connected": True,
        "core_schema_tables": table_count,
    }


# ID: 2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e
async def get_drift_status(context: CoreContext, *, scope: str = "all") -> dict:
    """Return a consolidated drift snapshot.

    `scope` is a free-form filter ('symbols' | 'vectors' | 'guard' | 'all').
    For Phase 3 each branch returns a thin summary; the deeper drift
    diagnostics live in mind.* and are exposed through a follow-up
    issue if richer reporting is needed before CLI cutover.
    """
    summary: dict[str, Any] = {"scope": scope}

    if scope in ("symbols", "all"):
        try:
            from body.introspection.drift_service import run_drift_analysis_async

            summary["symbols"] = await run_drift_analysis_async()
        except Exception as exc:
            summary["symbols"] = {"available": False, "error": str(exc)}

    if scope in ("vectors", "all"):
        try:
            qdrant = getattr(context, "qdrant_service", None)
            if qdrant is None:
                summary["vectors"] = {
                    "available": False,
                    "error": "qdrant_service not configured",
                }
            else:
                collections = await qdrant.list_collections()
                summary["vectors"] = {
                    "available": True,
                    "collections": collections,
                    "count": len(collections),
                }
        except Exception as exc:
            summary["vectors"] = {"available": False, "error": str(exc)}

    if scope in ("guard", "all"):
        summary["guard"] = {
            "available": False,
            "error": "guard analyzer not implemented (see #502)",
        }

    return summary


# ---------- /decisions ----------------------------------------------------


# ID: 3c4d5e6f-7a8b-4c9d-0e1f-2a3b4c5d6e7f
def _trace_to_dict(trace: Any) -> dict:
    """Serialise a DecisionTrace ORM row into a JSON-safe dict."""
    return {
        "session_id": getattr(trace, "session_id", None),
        "agent_id": getattr(trace, "agent_id", None),
        "pattern": getattr(trace, "pattern", None),
        "outcome": getattr(trace, "outcome", None),
        "summary": getattr(trace, "summary", None),
        "created_at": (
            trace.created_at.isoformat()
            if getattr(trace, "created_at", None) is not None
            else None
        ),
    }


# ID: 4d5e6f7a-8b9c-4d0e-1f2a-3b4c5d6e7f80
async def get_decisions(
    *,
    session_id: str | None = None,
    agent: str | None = None,
    pattern: str | None = None,
    limit: int = 50,
    after_cursor: str | None = None,
) -> dict:
    """Return recent decision traces filtered by the supplied criteria.

    Backed by DecisionTraceRepository. When `session_id` is supplied
    only that trace is returned. Otherwise the recent feed is keyset-paged
    by `limit` and `after_cursor`, filtered by `agent` and `pattern`.
    """
    async with DecisionTraceRepository.open() as repo:
        if session_id:
            trace = await repo.get_by_session_id(session_id)
            return {
                "count": 1 if trace else 0,
                "has_more": False,
                "next_cursor": None,
                "traces": [_trace_to_dict(trace)] if trace else [],
            }
        traces, has_more, next_cursor = await repo.get_recent_paginated(
            limit=limit,
            after_cursor=after_cursor,
            agent_name=agent,
        )
        rows = [_trace_to_dict(t) for t in traces]
        if pattern:
            rows = [r for r in rows if r.get("pattern") == pattern]
        return {
            "count": len(rows),
            "has_more": has_more,
            "next_cursor": next_cursor,
            "traces": rows,
        }


# ID: 5e6f7a8b-9c0d-4e1f-2a3b-4c5d6e7f8091
async def get_decisions_patterns(*, days: int = 7) -> dict:
    """Return classification stats grouped by pattern."""
    async with DecisionTraceRepository.open() as repo:
        stats = await repo.get_pattern_stats(days=days)  # type: ignore[call-arg]
    return {"days": days, "patterns": stats}


# ---------- /refusals -----------------------------------------------------


# ID: 6f7a8b9c-0d1e-4f2a-3b4c-5d6e7f8091a2
def _refusal_to_dict(record: Any) -> dict:
    """Serialise a RefusalRecord ORM row into a JSON-safe dict."""
    return {
        "id": str(record.id) if getattr(record, "id", None) is not None else None,
        "component_id": getattr(record, "component_id", None),
        "phase": getattr(record, "phase", None),
        "refusal_type": getattr(record, "refusal_type", None),
        "reason": getattr(record, "reason", None),
        "suggested_action": getattr(record, "suggested_action", None),
        "confidence": getattr(record, "confidence", None),
        "session_id": getattr(record, "session_id", None),
        "created_at": (
            record.created_at.isoformat()
            if getattr(record, "created_at", None) is not None
            else None
        ),
    }


# ID: 7a8b9c0d-1e2f-4a3b-4c5d-6e7f8091a2b3
async def get_refusals(
    *,
    refusal_type: str | None = None,
    session_id: str | None = None,
    limit: int = 50,
) -> dict:
    """Return recent refusal records filtered by type/session."""
    repo = RefusalRepository()
    if session_id:
        records = await repo.get_by_session(session_id)
    elif refusal_type:
        records = await repo.get_by_type(refusal_type, limit=limit)
    else:
        records = await repo.get_recent(limit=limit, refusal_type=None)
    return {
        "count": len(records),
        "refusals": [_refusal_to_dict(r) for r in records],
    }


# ID: 8b9c0d1e-2f3a-4b4c-5d6e-7f8091a2b3c4
async def get_refusals_stats(*, days: int = 7) -> dict:
    """Return refusal statistics by type across the lookback window."""
    repo = RefusalRepository()
    stats = await repo.get_statistics(days=days)
    by_type = await repo.count_by_type(days=days)
    return {"days": days, "stats": stats, "counts_by_type": by_type}


# ---------- /analysis -----------------------------------------------------


# ID: 9c0d1e2f-3a4b-4c5d-6e7f-8091a2b3c4d5
async def get_analysis_clusters(*, limit: int = 25) -> dict:
    """Return semantic capability clusters.

    Backed by `body.self_healing.cluster_inspector` (when present). Pre-
    cutover the CLI rendered clusters from a sibling table; the Phase 3
    surface returns the same row set as a plain projection. Missing
    backend → empty list.
    """
    try:
        from body.self_healing.cluster_inspector import (
            inspect_clusters_async,  # type: ignore[import-not-found]
        )
    except Exception as exc:
        logger.info("inspect_runner: cluster_inspector unavailable: %s", exc)
        return {"available": False, "clusters": []}

    clusters = await inspect_clusters_async(limit=limit)
    return {"available": True, "count": len(clusters), "clusters": clusters}


# ID: 0d1e2f3a-4b5c-4d6e-7f80-91a2b3c4d5e6
async def get_analysis_duplicates(
    context: CoreContext, *, threshold: float = 0.85
) -> dict:
    """Return semantic-code duplication candidates.

    Wraps `body.self_healing.duplicates_service.inspect_duplicates_async`.
    The service prints to console pre-cutover; here we capture the
    underlying finding list when available, otherwise fall back to the
    success/failure shape.
    """
    from body.self_healing.duplicates_service import inspect_duplicates_async

    try:
        await inspect_duplicates_async(context, threshold)
        return {"ok": True, "threshold": threshold, "note": "results emitted to logs"}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# ID: 1e2f3a4b-5c6d-4e7f-8091-a2b3c4d5e6f7
async def get_analysis_common_knowledge(*, limit: int = 25) -> dict:
    """Return DRY-violation candidates surfaced by the duplicate engine."""
    try:
        from body.self_healing.common_knowledge_inspector import (  # type: ignore[import-not-found]
            inspect_common_knowledge_async,
        )
    except Exception as exc:
        logger.info("inspect_runner: common_knowledge_inspector unavailable: %s", exc)
        return {"available": False, "candidates": []}

    candidates = await inspect_common_knowledge_async(limit=limit)
    return {
        "available": True,
        "count": len(candidates),
        "candidates": candidates,
    }


# ID: 2f3a4b5c-6d7e-4f80-91a2-b3c4d5e6f708
def get_analysis_command_tree(context: CoreContext) -> dict:
    """Return the introspected CLI command hierarchy.

    Pre-CLI-extraction (ADR-050) this introspects the local Typer app via
    `body.maintenance.command_sync_service.collect_commands`. Post-
    extraction the endpoint's semantics shift to "API endpoint tree";
    that re-binding is tracked as a follow-up ADR per ADR-057 D3.
    """
    try:
        from body.maintenance.command_sync_service import (  # type: ignore[attr-defined]
            collect_commands,
        )

        rows = collect_commands(context.git_service.repo_path)
        return {
            "available": True,
            "source": "cli",
            "count": len(rows),
            "commands": rows,
        }
    except Exception as exc:
        logger.info("inspect_runner: command-tree backend unavailable: %s", exc)
        return {"available": False, "source": "cli", "error": str(exc)}


# ID: 3a4b5c6d-7e8f-4091-a2b3-c4d5e6f70819
def get_analysis_test_targets(context: CoreContext) -> dict:
    """Return SIMPLE / COMPLEX classification for in-scope source files."""
    try:
        from body.quality.test_target_classifier import (
            classify_test_targets,  # type: ignore[import-not-found]
        )

        targets = classify_test_targets(context.git_service.repo_path)
        return {"available": True, "count": len(targets), "targets": targets}
    except Exception as exc:
        logger.info("inspect_runner: test_target_classifier unavailable: %s", exc)
        return {"available": False, "error": str(exc), "targets": []}


# ID: ed356df8-f508-450a-85bc-cdc8b3bc2af7
def get_analysis_bridges(*, consuming: str | None = None) -> dict:
    """Return declared architecture bridge points from .intent/architecture/bridges/*.yaml.

    When `consuming` is supplied, filters to bridges whose consuming_types
    include that string. Returns all fields so consumers can render the
    full bridge declaration without additional HTTP calls.
    """
    try:
        from shared.infrastructure.intent.architecture_bridges import (
            bridges_consuming,
            load_bridges,
        )

        bridges = bridges_consuming(consuming) if consuming else load_bridges()
    except Exception as exc:
        return {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
            "bridges": [],
        }

    def _to_dict(b: Any) -> dict:
        return {
            "id": b.id,
            "title": b.title,
            "description": b.description,
            "bridge_class": b.bridge_class,
            "bridge_layer": b.bridge_layer,
            "source_layer": b.source_layer,
            "source_context": b.source_context,
            "consuming_types": b.consuming_types,
            "sink_target": b.sink_target,
            "sink_layer": b.sink_layer,
            "sink_via": b.sink_via,
            "attribution_mechanism": b.attribution_mechanism,
            "attribution_field": b.attribution_field,
            "attribution_note": b.attribution_note,
            "authority_adrs": b.authority_adrs,
        }

    result = sorted(bridges, key=lambda b: b.id)
    return {
        "available": True,
        "count": len(result),
        "consuming": consuming,
        "bridges": [_to_dict(b) for b in result],
    }


# ---------- /components ---------------------------------------------------


# ID: 85883df2-a504-40ba-abbf-9c633c2cbe7c
def get_components_list(*, filter_type: str | None = None) -> dict:
    """Return the registered V2 component inventory.

    Walks the canonical component packages and instantiates each
    discovered class to read its declared phase and description. The
    `filter_type` parameter is a case-insensitive substring match
    against the package label (e.g. "analyzers", "strategists"). Rows
    that fail to instantiate are surfaced with `ok=False` and an error
    description so the route still returns a 200.
    """
    from shared.component_primitive import discover_components

    rows: list[dict[str, Any]] = []
    for label, package in COMPONENT_PACKAGES.items():
        if filter_type and filter_type.lower() not in label.lower():
            continue
        try:
            components = discover_components(package)
        except Exception as exc:
            rows.append(
                {
                    "phase": "ERROR",
                    "type": label,
                    "component_id": package,
                    "description": f"Discovery failed: {type(exc).__name__}: {exc}",
                    "ok": False,
                }
            )
            continue
        for cid, cls in sorted(components.items()):
            try:
                instance = cls()
                rows.append(
                    {
                        "phase": instance.phase.value.upper(),
                        "type": label,
                        "component_id": cid,
                        "description": instance.description,
                        "ok": True,
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "phase": "ERROR",
                        "type": label,
                        "component_id": cid,
                        "description": f"Initialization failed: {type(exc).__name__}: {exc}",
                        "ok": False,
                    }
                )
    return {"count": len(rows), "components": rows}


# ---------- /search -------------------------------------------------------


# ID: e882584c-533c-4267-bda0-83c8f1cadede
async def get_search_capabilities(
    context: CoreContext, *, q: str, limit: int = 10
) -> dict:
    """Return semantic capability search hits via the Will cognitive service.

    Delegates to `context.cognitive_service.search_capabilities`. If the
    cognitive service is not attached to the context (e.g. daemon
    started without LLM orchestration), returns `available=False` with
    an empty result list so the route still returns a 200.
    """
    cognitive_service = getattr(context, "cognitive_service", None)
    if cognitive_service is None:
        return {
            "query": q,
            "available": False,
            "error": "cognitive_service not configured",
            "count": 0,
            "results": [],
        }
    try:
        results = await cognitive_service.search_capabilities(q, limit=limit)
    except Exception as exc:
        return {
            "query": q,
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
            "count": 0,
            "results": [],
        }
    results = list(results or [])
    return {
        "query": q,
        "available": True,
        "count": len(results),
        "results": results,
    }


# ID: 421fdd90-15da-47ac-aeb3-4ed9a4413d78
async def get_search_commands(session: Any, *, q: str, limit: int = 25) -> dict:
    """Fuzzy substring search over the CLI command registry.

    Case-insensitive match against `name`, `summary`, and `help_text`
    columns of `core.cli_commands`. Returns a {query, count, results}
    envelope matching the `/search/capabilities` response shape so
    consumers can render both endpoints uniformly. ADR-057 D5 Phase 3b
    (#363 — hub_search_cmd extraction).
    """
    try:
        result = await session.execute(
            text(
                """
                SELECT name, module, summary, help_text
                FROM core.cli_commands
                WHERE position(lower(:term) IN lower(name)) > 0
                   OR position(lower(:term) IN lower(coalesce(summary, ''))) > 0
                   OR position(lower(:term) IN lower(coalesce(help_text, ''))) > 0
                ORDER BY name
                LIMIT :limit
                """
            ),
            {"term": q, "limit": limit},
        )
        rows = result.all()
    except Exception as exc:
        return {
            "query": q,
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
            "count": 0,
            "results": [],
        }

    results = [
        {
            "command": row.name,
            "module": row.module or "",
            "description": (row.summary or row.help_text or ""),
        }
        for row in rows
    ]
    return {
        "query": q,
        "available": True,
        "count": len(results),
        "results": results,
    }
